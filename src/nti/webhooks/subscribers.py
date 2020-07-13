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
from zope.interface import providedBy


from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.datamanager import WebhookDataManager

def find_active_subscriptions_for(data, event):
    """
    Part of :func:`dispatch_webhook_event`, broken out for testing.

    Internal use only.
    """
    # TODO: What's the practical difference using ``getUtilitiesFor`` and manually walking
    # through the tree using ``getNextUtility``? The first makes a single call to the adapter
    # registry and uses its own ``.ro`` to walk up and find utilities. The second uses
    # the ``__bases__`` of the site manager itself to walk up and find only the next utility.
    subscriptions = []
    provided = [providedBy(data), providedBy(event)]
    seen_managers = set()
    for context in None, data:
        # A context of None means to use the current site manager.
        sub_managers = component.getUtilitiesFor(IWebhookSubscriptionManager, context)
        for _name, sub_manager in sub_managers:
            if sub_manager in seen_managers:
                # De-dup.
                continue
            seen_managers.add(sub_manager)
            local_subscriptions = sub_manager.registry.adapters.subscriptions(provided, None)
            subscriptions.extend(local_subscriptions)
    return subscriptions

def dispatch_webhook_event(data, event):
    """
    A subcriber installed to dispatch events to webhook subscriptions.

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

    .. caution::

        This function assumes the global, thread-local transaction manager. If any
        objects belong to ZODB connections that are using a different transaction
        manager, this won't work.
    """
    # TODO: I think we could actually find a differen transaction manager if we needed to.
    subscriptions = find_active_subscriptions_for(data, event)
    subscriptions = [sub for sub in subscriptions if sub.isApplicable(data)]
    if subscriptions:
        # TODO: Choosing which datamanager resource to use might
        # be a good extension point.
        WebhookDataManager.join_transaction(transaction.manager, data, event, subscriptions)
