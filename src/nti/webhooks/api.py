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
from zope.traversing import api as ztapi
from zope.location.interfaces import LocationError

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
    return subscribe_in_site_manager(site_manager,
                                     dict(
                                         to=to, for_=for_, when=when,
                                         dialect_id=dialect_id,
                                         owner_id=owner_id,
                                         permission_id=permission_id))

DEFAULT_UTILITY_NAME = 'WebhookSubscriptionManager'

def subscribe_in_site_manager(site_manager, subscription_kwargs,
                              utility_name=DEFAULT_UTILITY_NAME):
    """
    Produce and return a persistent ``IWebhookSubscription`` in the
    given site manager.

    The *subscription_kwargs* are as for
    :meth:`nti.webhooks.interfaces.IWebhookSubscriptionManager.createSubscription`.
    No defaults are applied here.

    The *utility_name* can be used to namespace subscriptions.
    It must never be empty.
    """
    if IContainer.providedBy(site_manager):
        # The preferred location for utilities is in the 'default'
        # child: A SiteManagementFolder. But not every site manager
        # is guaranteed to have one of those, sadly.
        # The best way to get there, dealing with unicode, etc, is through
        # traversal.
        try:
            parent = ztapi.traverse(site_manager, 'default')
        except LocationError:
            parent = site_manager
        sub_manager = parent.get(utility_name) # pylint:disable=no-member
        if sub_manager is None:
            sub_manager = parent[utility_name] = PersistentWebhookSubscriptionManager()
            site_manager.registerUtility(
                sub_manager,
                IWebhookSubscriptionManager,
                name=utility_name if utility_name != DEFAULT_UTILITY_NAME else ''
            )
    else:
        # Perhaps we should fail?
        sub_manager = site_manager.getUtility(IWebhookSubscriptionManager)

    subscription = sub_manager.createSubscription(**subscription_kwargs)
    return subscription
