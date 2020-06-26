# -*- coding: utf-8 -*-
"""
Support for configuring webhook delivery using ZCML.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.configuration.fields import GlobalObject

from zope.interface import Interface

from zope.component.zcml import subscriber

from zope.security.zcml import Permission

from nti.webhooks.subscribers import on_webhook_event
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks._schema import ObjectEventInterface

# pylint:disable=inherit-non-class

class IStaticSubscriptionDirective(Interface):
    """
    Define a static subscription.

    Static subscriptions are not persistent and live only in the
    memory of individual processes. Thus, failed deliveries cannot be
    re-attempted after process shutdown. And of course the delivery history
    is also transient and local to a process.

    """

    for_ = GlobalObject(
        title=IWebhookSubscription['for_'].title,
        description=IWebhookSubscription['for_'].description,
        default=IWebhookSubscription['for_'].default,
        required=False,
    )

    when = ObjectEventInterface(
        title=IWebhookSubscription['when'].title,
        description=IWebhookSubscription['when'].description,
        default=IWebhookSubscription['when'].default,
        required=False,
    )

    to = IWebhookSubscription['to'].bind(None)

    dialect = IWebhookSubscription['dialect_id'].bind(None)

    owner = IWebhookSubscription['owner_id'].bind(None)

    permission = Permission(
        title=u"The permission to check",
        description=u"""
        If given, and an *owner* is also specified, then only data that
        has this permission for the *owner* will result in an attempted delivery.
        If not given, but an *owner* is given, this will default to the standard
        view permission ID, ``zope.View``.
        """,
        required=False
    )


def static_subscription(context, **kwargs):
    to = kwargs.pop('to')
    for_ = kwargs.pop('for_', None) or IStaticSubscriptionDirective['for_'].default
    when = kwargs.pop('when', None) or IStaticSubscriptionDirective['when'].default
    owner = kwargs.pop("owner", None)
    permission = kwargs.pop('permission', None)

    if kwargs: # pragma: no cover
        raise TypeError

    subscriber(context, for_=(for_, when), handler=on_webhook_event,
               trusted=True, locate=True)
