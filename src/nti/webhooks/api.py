# -*- coding: utf-8 -*-
"""
API functions.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import providedBy
from zope.component import getSiteManager
from zope.container.interfaces import IContainer

from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookResourceDiscriminator
from nti.webhooks.subscriptions import PersistentWebhookSubscriptionManager



def subscribe_to_resource(resource, to, for_=None,
                          when=IWebhookSubscription['when'].default,
                          dialect_id=IWebhookSubscription['dialect_id'].default,
                          owner_id=None,
                          permission_id=IWebhookSubscription['permission_id'].default):
    """
    Produce and return a persistent ``IWebhookSubscription`` based on the *resource*.

    Only the *resource* and *to* arguments are mandatory. The other arguments are
    optional, and are the same as the attributes in that interface.

    :param resource: The resource to subscribe to. Passing a resource does two things.
       First, the resources is used to find the closest enclosing ``ISite``
       that is persistent. A ``IWebhookSubscriptionManager`` utility will be installed
       in this site if one does not already exist, and the subscription will be created
       there.

       Second, if *for_* is not given, then the interfaces provided by the *resource* will
       be used for *for_*. This doesn't actually subscribe
       *just* to events on that exact object, but to events for objects with the same set of
       interfaces.
    """
    if for_ is None:
        # Allow users to customize this. ``providedBy`` returns something
        # very specific, which may not at all be what we want.
        try:
            for_ = IWebhookResourceDiscriminator(resource)
        except TypeError:
            for_ = providedBy(resource)
        else:
            for_ = for_()

    site_manager = getSiteManager(resource)
    sub_name = 'WebhookSubscriptionManager'
    if IContainer.providedBy(site_manager):
        sub_manager = site_manager.get(sub_name) # pylint:disable=no-member
        if sub_manager is None:
            sub_manager = site_manager[sub_name] = PersistentWebhookSubscriptionManager()
            site_manager.registerUtility(sub_manager, IWebhookSubscriptionManager)
    else:
        # Perhaps we should fail?
        sub_manager = site_manager.getUtility(IWebhookSubscriptionManager)

    subscription = sub_manager.createSubscription(to=to, for_=for_, when=when,
                                                  dialect_id=dialect_id,
                                                  owner_id=owner_id,
                                                  permission_id=permission_id)
    return subscription
