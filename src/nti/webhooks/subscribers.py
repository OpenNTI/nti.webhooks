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
    Part of `dispatch_webhook_event`, broken out for testing.

    Internal use only.
    """
    # TODO: What's the practical difference using ``getUtilitiesFor`` and manually walking
    # through the tree using ``getNextUtility``? The first makes a single call to the adapter
    # registry and uses its own ``.ro`` to walk up and find utilities. The second uses
    # the ``__bases__`` of the site manager itself to walk up and find only the next utility.
    subscriptions = []
    provided = [providedBy(data), providedBy(event)]
    last_sub_manager = None
    for context in None, data:
        # A context of None means to use the current site manager.
        sub_managers = component.getUtilitiesFor(IWebhookSubscriptionManager, context)
        for _name, sub_manager in sub_managers:
            if sub_manager is last_sub_manager:
                # De-dup.
                continue
            last_sub_manager = sub_manager
            local_subscriptions = sub_manager.registry.adapters.subscriptions(provided, None)
            subscriptions.extend(local_subscriptions)
    return subscriptions

def dispatch_webhook_event(data, event):
    """
    A subcriber installed globally to dispatch events to webhook
    subscriptions.

    This is registered globally for ``(*, IObjectEvent)`` (TODO: It
    would be nice to make that more specific. Maybe we want to require
    objects to implement the ``IWebhookPayload`` interface?.)

    This function:

    - Queries for all active subscriptions in the ``IWebhookSubscriptionManager``
      instances in the current site hierarchy;
    - And queries for all active subscriptions in the ``IWebhookSubscriptionManager``
      instances in the context of the *data*, which may be separate.
    - Determines if any of those actually apply to the *data*, and if so,
      joins the transaction to prepare for sending them.
    """
    subscriptions = find_active_subscriptions_for(data, event)
    subscriptions = [sub for sub in subscriptions if sub.isApplicable(data)]
    if subscriptions:
        # TODO: Choosing which datamanager resource to use might
        # be a good extension point.
        tx_man = transaction.manager
        tx = tx_man.get() # If not begun, this is an error.

        try:
            data_man = tx.data(dispatch_webhook_event)
        except KeyError:
            data_man = WebhookDataManager(tx_man, data, event, subscriptions)
            tx.set_data(dispatch_webhook_event, data_man)
            tx.join(data_man)
        else:
            data_man.add_subscriptions(data, event, subscriptions)
