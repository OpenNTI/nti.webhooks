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
from zope.container.interfaces import IContained
from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.componentvocabulary.vocabulary import UtilityNames

from zope.principalregistry.metadirectives import TextId

from zope.schema import Field


from nti.schema.field import Object
from nti.schema.field import ValidText as Text
from nti.schema.field import ValidChoice as Choice
from nti.schema.field import ValidURI as URI
from nti.schema.field import Dict
from nti.schema.field import Int
from nti.schema.field import Timedelta

from nti.webhooks._schema import HTTPSURL

# pylint:disable=inherit-non-class,no-self-argument

# TODO: Add an __all__ when this is closer to finished.

try:
    from nti.base.interfaces import ICreatedTime
except ImportError:
    from zope.schema import Real as Number # pylint:disable=ungrouped-imports
    class ICreatedTime(Interface):
        """
        Something that (immutably) tracks its created time.
        """

        createdTime = Number(title=u"The timestamp at which this object was created.",
                             description=u"Typically set automatically by the object.",
                             default=0.0)


    class ILastModified(ICreatedTime):
        """
        Something that tracks a modification timestamp.
        """

        lastModified = Number(
            title=u"The timestamp at which this object or its contents was last modified.",
            default=0.0)
else:
    from nti.base.interfaces import ILastModified


class IWebhookDeliveryManager(Interface):
    """
    Handles the delivery of messages.

    This is a global utility registered by the ZCML of this package.

    It operates in fire-and-forget mode, in a completely opaque
    fashion. However, this is a two-step process to better work with
    persistent objects and transactions. In the first step, a
    :class:`IWebhookDeliveryManagerShipmentInfo` is created with
    :meth:`createShipmentInfo`, packaging up all the information
    needed to *later* begin the delivery using
    :meth:`acceptForDelivery`.

    (And yes, the terminology is based on the United States Postal
    Service.)
    """

    def createShipmentInfo(subscriptions_and_attempts):
        """
        Given an (distinct) iterable of ``(subscription, attempt)`` pairs,
        extract the information needed to later send that data
        *as well as record its status in the subscription*, independently of
        any currently running transaction or request.

        Each *attempt* must be pending and must not be contained in any other
        shipment info.

        For persistent subscriptions and attempts, all necessary information to complete
        :meth:`acceptForDelivery` must be captured at this time.

        :return: A new :class:`IWebhookDeliveryManagerShipmentInfo` object.
            If the iterable is empty, this may return None or a suitable
            object that causes :meth:`acceptForDelivery` to behave appropriately.
        """

    def acceptForDelivery(shipment_info):
        """
        Given a :class:`IWebhookDeliveryManagerShipmentInfo` previously created
        by this object but not yet accepted for delivery, schedule the delivery
        and begin making it happen.

        This is generally an asynchronous call and SHOULD NOT raise exceptions; the
        caller is likely unable to deal with them.

        As delivery completes, the status of each attempt contained in the shipment info
        should be updated.

        No return value.
        """

class IWebhookDeliveryManagerShipmentInfo(Interface):
    """
    A largely-opaque interface representing values returned from,
    and passed to, a particular :class:`IWebhookDeliveryManager`.
    """


class IWebhookDestinationValidator(Interface):
    """
    Validates destinations.

    This is the place where we make sure that the destination
    is valid, before attempting to deliver to it, according
    to policy. This may include such things as:

    - Check that the protocol is HTTPs.
    - Verify that the domain is reachable, or at least
      resolvable.
    - Ensure query parameters are innocuous

    Targets are validated before attempting to send data to them.

    This is registered as a single global utility. The utility is
    encouraged to cache valid/invalid results for a period of time,
    especially with domain resolvability.
    """

    def validateTarget(target_url):
        """
        Check that the URL is valid. If it is, return silently.

        If it is not, raise some sort of exception such as a
        :exc:`socket.error` for unresolvable domains.
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

    def externalizeData(data, event):
        """
        Produce the byte-string that is the externalized version of *data*
        needed to send to webhooks using this dialect.

        The default method will externalize the data using an :mod:`nti.externalization`
        externalizer named "webhook-delivery".
        """

class IWebhookDeliveryAttemptRequest(ICreatedTime):
    """
    The details about an HTTP request sent to a webhook.
    """

    # This is largely based on a requests.PreparedRequest,
    # found in the attribute requests.Response.request.
    # XXX: Resolved host addresses would be good too, although in a round-robin DNS
    # we don't necessarily know what one we used. Can requests tell us that?

    url = URI(
        title=u"The URL requested",
        description=u"""
        This is denormalized from the containing delivery attempt and
        its containing subscription because the target URL may change
        over time.
        """,
        required=True,
    )

    method = Text(
        title=u'The HTTP method the request was sent with.',
        default=u'POST',
        required=True
    )

    body = Text(
        # XXX: Think this through. Should it always be bytes?
        # Displaying in the web interface gets more complicated that
        # way, and we'd need to store an encoding. OTOH, we know we
        # externalize to a Text string and later encode it. Or maybe
        # just keep this as a dict in all cases? We'll be sending JSON
        # data...
        title=u"The external data sent to the destination.",
        required=True,
    )

    headers = Dict(
        title=u'The headers sent with the request.',
        description=u"""
        Order is not kept. Security sensitive headers, such as
        those relating to authentication, are removed.
        """,
        key_type=Text(),
        value_type=Text(),
        required=True,
    )


class IWebhookDeliveryAttemptResponse(ICreatedTime):
    """
    The details about the HTTP response.

    - HTTP redirect history is lost; only the final response
      is saved.
    """
    # Much of this is based on what's available in a requests.Response
    # object. requests exposes the redirect history and we could keep it,
    # if desired.

    status_code = Int(
        title=u"The HTTP status code",
        description=u"For example, 200.",
        required=True
    )

    reason = Text(
        title=u"The HTTP reason.",
        description=u"For example, 'OK'",
        required=True,
    )

    headers = Dict(
        title=u"The headers received from the server.",
        key_type=Text(),
        value_type=Text(),
        required=True,
    )

    content = Text(
        title=u"The decoded contents of the response, if any.",
        description=u"""
        If the response contained a body, but it wasn't decodable
        as text, XXX: What?

        TODO: Place some limits on this?
        """,
        required=False,
    )

    elapsed = Timedelta(
        title=u"The amount of time it took to send and receive.",
        description=u"""
        This should be the closest measurement possible of the time
        taken between sending the first byte of the request, and
        receiving a usable response.
        """
    )


class IWebhookDeliveryAttempt(IContained, ILastModified):
    """
    The duration of the request/reply cycle is roughly captured
    by the difference in the ``createdTime`` attributes of the
    request and response. More precisely, the network time is captured
    by the ``elapsed`` attribute of the response.
    """
    containers('.IWebhookSubscription')


    status = Choice(
        title=u"The status of the delivery attempt.",
        description=u"""
        The current status of the delivery attempt.

        Attempts begin in the 'pending' state, and then transition
        to either the 'successful', or 'failed' state.
        """,
        values=(
            'pending', 'successful', 'failed',
        ),
        required=True,
        default='pending',
    )

    message = Text(
        title=u"Additional explanatory text.",
        required=False,
    )

    request = Object(IWebhookDeliveryAttemptRequest, required=True)
    response = Object(IWebhookDeliveryAttemptResponse, required=True)


class IWebhookSubscription(IContainerNamesContainer):
    """
    An individual subscription.
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
    dialect = Attribute("The resolved dialect to use for this subscription.")

    def isApplicable(data):
        """
        Determine if this subscription applies to the given *data*
        object.

        This does not take into account whether this subscription is
        active or not, but does take into account the permission and principal
        declared for the subscription as well as the type/interface.
        """

    def createDeliveryAttempt(payload_data):
        """
        Create a new `IWebhookDeliveryAttempt` for this subscription.

        The delivery attempt is in the pending status, and is stored as
        a child of this subscription; its ``__parent__`` is set to this subscription.

        Subscriptions may be limited in the amount of attempts they will store;
        this method may cause that size to temporarily be exceeded
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
