# -*- coding: utf-8 -*-
"""
Event subscribers.

This is an internal implementation module
and contains no public code.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

__all__ = ()

import transaction
from zope import component
from zope import interface
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.securitypolicy.interfaces import IPrincipalPermissionManager

from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionSecuritySetter
from nti.webhooks.datamanager import WebhookDataManager


def _find_subscription_managers(data):
    """
    Iterable across subscription managers.
    """
    # TODO: What's the practical difference using ``getUtilitiesFor`` and manually walking
    # through the tree using ``getNextUtility``? The first makes a single call to the adapter
    # registry and uses its own ``.ro`` to walk up and find utilities. The second uses
    # the ``__bases__`` of the site manager itself to walk up and find only the next utility.
    seen_managers = set()
    for context in None, data:
        # A context of None means to use the current site manager.
        sub_managers = component.getUtilitiesFor(IWebhookSubscriptionManager, context)
        for _name, sub_manager in sub_managers:
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
