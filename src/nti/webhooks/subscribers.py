# -*- coding: utf-8 -*-
"""
Event subscribers.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

__all__ = (
    'dispatch_webhook_event',
    'remove_subscriptions_for_principal',
    'ExhaustiveWebhookSubscriptionManagers',
)

from itertools import chain

import transaction
from zope import component
from zope import interface

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.location.interfaces import ISublocations
from zope.securitypolicy.interfaces import IPrincipalPermissionManager
from zope.security.interfaces import IPrincipal
from zope.traversing import api as ztapi

from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookSubscriptionManagers
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionSecuritySetter
from nti.webhooks.interfaces import IWebhookPrincipal

from nti.webhooks.datamanager import WebhookDataManager

def _utilities_up_tree(data):
    context = data
    while context is not None:
        manager = component.queryNextUtility(context, IWebhookSubscriptionManager)
        context = manager
        if manager is not None:
            yield '<NA>', manager


def _find_subscription_managers(data, seen_managers=None):
    """
    Iterable across subscription managers.
    """
    # What's the practical difference using ``getUtilitiesFor`` and manually walking
    # through the tree using ``getNextUtility``? The first makes a single call to the adapter
    # registry and uses its own ``.ro`` to walk up and find utilities. The second uses
    # the ``__bases__`` of the site manager itself to walk up and find only the next utility.
    # We want to find both. See ``removing_subscriptions.rst`` for an example that
    # fails if we just use ``getUtilitiesFor``.
    seen_managers = set() if seen_managers is None else seen_managers

    utilities_in_current_site = component.getUtilitiesFor(IWebhookSubscriptionManager)
    utilities_in_data_site = component.getUtilitiesFor(IWebhookSubscriptionManager, data)
    utilities_up_tree = _utilities_up_tree(data)
    it = chain(utilities_in_current_site,
               utilities_in_data_site,
               utilities_up_tree)

    for _name, sub_manager in it:
        if sub_manager in seen_managers:
            # De-dup.
            continue
        seen_managers.add(sub_manager)
        yield sub_manager

def find_applicable_subscriptions_for(data, event):
    """
    Part of :func:`dispatch_webhook_event`, broken out for testing.

    Internal use only.
    """
    subscriptions = []
    for sub_manager in _find_subscription_managers(data):
        subscriptions.extend(sub_manager.subscriptionsToDeliver(data, event))
    return subscriptions


def find_active_subscriptions_for(data, event):
    """
    Part of :func:`dispatch_webhook_event`, broken out for testing.

    Internal use only.
    """
    subscriptions = []
    for sub_manager in _find_subscription_managers(data):
        subscriptions.extend(sub_manager.activeSubscriptions(data, event))
    return subscriptions


def dispatch_webhook_event(data, event):
    """
    A subscriber installed to dispatch events to webhook subscriptions.

    This is usually registered in the global registry by loading
    ``subscribers.zcml`` or ``subscribers_promiscuous.zcml``, but the
    event and data for which it is registered may be easily
    customized. See :doc:`/configuration` for more information.

    This function:

        - Queries for all active subscriptions in the
          ``IWebhookSubscriptionManager`` instances in the current
          site hierarchy;

        - And queries for all active subscriptions in the
          ``IWebhookSubscriptionManager`` instances in the context of
          the *data*, which may be separate.

        - Determines if any of those actually apply to the *data*, and
          if so, joins the transaction to prepare for sending them.

    .. important::

       Checking whether a subscription is :term:`applicable`
       depends on the security policy in use. Most security policies
       inspect the object's lineage or location (walking up the ``__parent__`` tree)
       so it's important to use this subscriber only for events where that part
       of the object is intact. For example, it does not usually apply for
       :class:`~.ObjectCreatedEvent`, but does for :class:`~.ObjectAddedEvent`.
       See :doc:`configuration` for more.

    .. caution::

        This function assumes the global, thread-local transaction manager. If any
        objects belong to ZODB connections that are using a different transaction
        manager, this won't work.
    """
    # TODO: I think we could actually find a different transaction manager if we needed to.
    subscriptions = find_applicable_subscriptions_for(data, event)
    if subscriptions:
        # TODO: Choosing which datamanager resource to use might
        # be a good extension point.
        WebhookDataManager.join_transaction(transaction.manager, data, event, subscriptions)

_DEFAULT_PERMISSIONS = (
    'zope.View',
    'nti.actions.delete',
)

@interface.provider(IWebhookSubscriptionSecuritySetter)
def _default_security_setter(subscription):
    prin_per = IPrincipalPermissionManager(subscription)
    for perm_id in _DEFAULT_PERMISSIONS:
        # pylint:disable=too-many-function-args
        prin_per.grantPermissionToPrincipal(perm_id, subscription.owner_id)

@component.adapter(IWebhookSubscription, IObjectAddedEvent)
def apply_security_to_subscription(subscription, event):
    """
    Set the permissions for the *subscription* when it is added to a
    container.

    By default, only the *owner_id* of the *subscription* gets any
    permissions (and those permissions are ``zope.View`` and
    ``nti.actions.delete``). If there is no owner, no permissions are
    added.

    If you want to add additional permissions, simply add an
    additional subscriber. If you want to change or replace the
    default permissions, add an adapter for the subscription (in the
    current site) implementing ``IWebhookSubscriptionSecuritySetter``;
    in that case you will be completely responsible for all security
    declarations.
    """
    if not subscription.owner_id:
        return

    setter = component.queryAdapter(subscription,
                                    IWebhookSubscriptionSecuritySetter,
                                    default=_default_security_setter)
    setter(subscription)


@component.adapter(IPrincipal, IObjectRemovedEvent)
def remove_subscriptions_for_principal(principal, event):
    """
    Subscriber to find and remove all subscriptions for the
    *principal* when it is removed.

    This is an adapter for ``(IPrincipal, IObjectRemovedEvent)`` by
    default, but that may not be the correct event in every system.
    Register it for the appropriate events in your system.

    :param principal: The principal being removed. It should still be
        located (having a proper ``__parent__``) when this subscriber
        is invoked; this is the default for ``zope.container`` objects
        that use :func:`zope.container.contained.uncontained` in their
        ``__delitem__`` method.

        This can be any type of object. It is first adapted to
        :class:`nti.webhooks.interfaces.IWebhookPrincipal`; if that
        fails, it is adapted to ``IPrincipal``, and if that fails, it
        is used as-is. The final object must have the ``id``
        attribute.

    :param event: This is not used by this subscriber.

    This subscriber removes all subscriptions owned by the *principal*
    found in subscription managers:

    - in the current site; and
    - in sites up the lineage of the original principal and adapted object
      (if different).

    If the principal may have subscriptions in more places, provide an implementation
    of :class:`nti.webhooks.interfaces.IWebhookSubscriptionManagers` for the
    original *principal* object. One (exhaustive) implementation is provided
    (but not registered) in :class:`ExhaustiveWebhookSubscriptionManagers`.
    """
    orig_principal = principal
    principal = IWebhookPrincipal(principal, None) or IPrincipal(principal, principal)
    prin_id = principal.id

    manager_iters = [
        _find_subscription_managers(principal)
    ]
    if principal is not orig_principal:
        manager_iters.append(_find_subscription_managers(orig_principal))
    manager_iters.append(IWebhookSubscriptionManagers(orig_principal, ()))

    for manager in chain(*manager_iters):
        manager.deleteSubscriptionsForPrincipal(prin_id)


@interface.implementer(IWebhookSubscriptionManagers)
class ExhaustiveWebhookSubscriptionManagers(object):
    """
    Finds all subscription managers that are located in the same root
    as the *context*.

    This is done using an exhaustive, expensive process of adapting
    the root to :class:`zope.container.interfaces.ISublocations` and
    inspecting each of them for subscription managers.

    This is not registered by default.
    """

    def __init__(self, context):
        self.context = context
        # If the object isn't located or can't find its root,
        # this raises TypeError. That would cause the adaptation of this
        # interface to fail, but still use any provided default.
        self.root = ztapi.getRoot(self.context)

    def __iter__(self):
        seen = set()
        for m in _find_subscription_managers(self.context, seen):
            yield m

        for m in self._find_recur(self.root, seen):
            yield m

    def _find_recur(self, root, seen):
        # This could be better if we memorized the utilities earlier,
        # and applied that to _utilities_up_tree. As it is, this is something like
        # O(n^2)
        if IWebhookSubscriptionManager.providedBy(root):
            yield root

        subs = ISublocations(root, None)
        if subs is None:
            return

        for sub in subs.sublocations(): # pylint:disable=too-many-function-args
            for m in self._find_recur(sub, seen):
                yield m
