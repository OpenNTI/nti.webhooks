# -*- coding: utf-8 -*-
"""
Interface definitions for ``nti.webhooks``.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import Interface
from zope.interface import Attribute
from zope.interface.interfaces import IInterface
from zope.interface.interfaces import IObjectEvent

from zope.container.interfaces import IContainerNamesContainer
from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.componentvocabulary.vocabulary import UtilityNames

from zope.principalregistry.metadirectives import TextId

from zope.schema import Field

from nti.schema.field import Object
from nti.schema.field import ValidChoice as Choice

from nti.webhooks._schema import HTTPSURL

# pylint:disable=inherit-non-class,no-self-argument

__all__ = [
    'IWebhookDeliveryManager',
    'IWebhookPayload',
    'IWebhookDialect',
    'IWebhookSubscription',
    'IWebhookSubscriptionManager',
]

class IWebhookDeliveryManager(Interface):
    """
    Handles the delivery of messages.

    This is usually a global utility registered by the
    ZCML of this package.
    """


class IWebhookPayload(Interface):
    """
    Marker interface for objects that can automatically
    become the payload of a webhook.

    This interface is used as the default in a number of
    places.

    TODO: More docs as this evolves.
    """

class IWebhookDialect(Interface):
    """
    Quirks for sending webhooks to specific services.
    """

    def externalizeData(data):
        """
        Produce the byte-string that is the externalized version of *data*
        needed to send to webhooks using this dialect.

        The default method will externalize the data using an :mod:`nti.externalization`
        externalizer named "webhook-delivery".
        """

class IWebhookDeliveryAttempt(Interface):
    containers('.IWebhookSubscription')

class IWebhookSubscription(IContainerNamesContainer):
    """
    An individual subscription.

    XXX: This is probably a container for the delivery items.
    """
    containers('.IWebhookSubscriptionManager')
    contains('.IWebhookDeliveryAttempt')

    for_ = Field(
        title=u"The type of object to attempt delivery for.",
        description=u"""
        When object events of type *when* are fired for instances
        providing this interface, webhook delivery to *target* might be attempted.

        The default is objects that implement :class:`~.IWebhookPayload`.

        This is interpreted as for :func:`zope.component.registerAdapter` and
        may name an interface or a type.
        """,

        default=IWebhookPayload,
        required=True
    )

    when = Object(
        schema=IInterface,
        title=u'The type of event that should result in attempted deliveries.',
        description=u"""
        A type of ``IObjectEvent``, usually one defined in :mod:`zope.lifecycleevent.interfaces` such
        as ``IObjectCreatedEvent``. The *object* field of this event must provide the
        ``for_`` interface; it's the data from the *object* field of this event that
        will be sent to the webhook.

        If not specified, *all* object events involving the ``for_`` interface
        will be sent.

        This must be an interface.
        """,
        default=IObjectEvent,
        required=True,
        constraint=lambda value: value.isOrExtends(IObjectEvent)
    )

    to = HTTPSURL(
        title=u"The complete destination URL to which the data should be sent",
        description=u"""
        This is an arbitrary HTTPS URL. Only HTTPS is supported for
        delivery of webhooks.
        """,
        required=True,
    )

    owner_id = TextId(
        title=u"The ID of the ``IPrincipal`` that owns this subscription.",
        description=u"""
        This will be validated at runtime when an event arrives. If
        the current ``zope.security.interfaces.IAuthentication`` utility cannot find
        a principal with the given ID, the delivery will be failed.

        Leave unset to disable security checks.
        """,
        required=False,
    )

    permission_id = Choice(
        title=u"The ID of the permission to check",
        description=u"""
        If given, and an *owner* is also specified, then only data that
        has this permission for the *owner* will result in an attempted delivery.
        If not given, but an *owner* is given, this will default to the standard
        view permission ID, ``zope.View``.

        If the permission ID cannot be found at runtime, the delivery will fail.
        """,
        required=False,
        vocabulary="Permission Ids",
    )

    # TODO: Where does specification of the request method go?
    # Dialect or subscription?
    dialect_id = Choice(
        title=u"The ID of the `IWebhookDialect` to use",
        description=u"""
        XXX Fill me in.
        """,
        required=False,
        vocabulary=UtilityNames(IWebhookDialect),
    )

    netloc = Attribute("The network host name portion of the URL.")

    def isApplicable(data):
        """
        Determine if this subscription applies to the given *data*
        object.

        This does not take into account whether this subscription is
        active or not, but does take into account the permission and principal
        declared for the subscription as well as the type/interface.
        """


class IWebhookSubscriptionManager(IContainerNamesContainer):
    """
    A utility that manages subscriptions.

    Also a registry for which subscriptions fire on what events.
    """
    contains(IWebhookSubscription)

    def addSubscription(subscription):
        """
        XXX: Document me.
        :param subscription: A `IWebhookSubscription`.
        """
