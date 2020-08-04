# -*- coding: utf-8 -*-
"""
Interface definitions for ``nti.webhooks``.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import Interface
from zope.interface import Attribute
from zope.interface import taggedValue
from zope.interface import implementer

from zope.interface.interfaces import IInterface
from zope.interface.interfaces import IObjectEvent
from zope.interface.interfaces import ObjectEvent

from zope.container.interfaces import IContainerNamesContainer
from zope.container.interfaces import IContained
from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.componentvocabulary.vocabulary import UtilityNames
from zope.dublincore.interfaces import IDCTimes
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.principalregistry.metadirectives import TextId

from zope.schema import Field


from nti.schema.field import Object
from nti.schema.field import ValidText as Text
from nti.schema.field import ValidChoice as Choice
from nti.schema.field import ValidURI as URI
from nti.schema.field import Dict
from nti.schema.field import Int
from nti.schema.field import Timedelta
from nti.schema.field import Bool

from nti.webhooks._schema import HTTPSURL

# pylint:disable=inherit-non-class,no-self-argument,no-method-argument,
# pylint:disable=too-many-ancestors

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
else: # pragma: no cover
    from nti.base.interfaces import ILastModified


class _ITimes(ILastModified, IDCTimes):
    """
    Internal unifying interface for time metadata.
    """


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
        :meth:`acceptForDelivery` must be captured at this time. The connection that created the
        subscription and attempts must still be open, and the transaction still running.

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

class IPossibleWebhookPayload(Interface):
    """
    Marker interface applied to objects that may have webhook
    subscriptions defined for them.

    The default configuration in ``subscribers.zcml`` loads event
    dispatchers only for event targets that implement this interface.
    """

    taggedValue('_ext_is_marker_interface', True)


class IWebhookPayload(Interface):
    """
    Adapter interface to convert an object that is a
    target of an event (possibly a `IPossibleWebhookPayload`)
    into the object that should actually be used as the payload.
    """

    taggedValue('_ext_is_marker_interface', True)


class IWebhookDialect(Interface):
    """
    Provides control over what data is sent on the wire.
    """

    def externalizeData(data, event):
        """
        Produce the byte-string that is the externalized version of *data*
        needed to send to webhooks using this dialect.

        This is called while the transaction that triggered the *event* is still
        open and not yet committed.

        The default method will externalize the data using an :mod:`nti.externalization`
        externalizer named "webhook-delivery".
        """

    def prepareRequest(http_session, subscription, attempt):
        """
        Produce the prepared request to send.

        :param requests.Session http_session: The session being used
           to send requests. The implementation should generally
           create a :class:`requests.Request` object, and then
           prepare it with :meth:`requests.Session.prepare_request`
           to combine the two.
        :param IWebhookSubscription subscription: The subscription that
           is being delivered.
        :param IWebhookDeliveryAttempt attempt: The attempt being
           sent. It will already have its ``payload_data``, which should be
           given as the ``data`` argument to the request.

        :rtype: requests.PreparedRequest

        .. caution::

           It may not be possible to access attributes of persistent objects
        """

class IWebhookDeliveryAttemptRequest(_ITimes):
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


class IWebhookDeliveryAttemptResponse(_ITimes):
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


class _StatusField(Choice):
    def __init__(self):
        Choice.__init__(
            self,
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

    def isSuccess(self, status):
        return status == 'successful'

    def isFailure(self, status):
        return status == 'failed'

    def isPending(self, status):
        return status == 'pending'

    def isResolved(self, status):
        return self.isFailure(status) or self.isSuccess(status)


class IWebhookDeliveryAttemptInternalInfo(_ITimes):
    """
    Internal (debugging) information stored with a delivery
    attempt.

    This data is never externalized and is only loosely specified.

    It may change over time.
    """

    exception_history = Attribute(
        "A sequence (oldest to newest) of information "
        "about exceptions encountered processing the attempt."
    )

    originated = Attribute(
        "Information about where and how the request originated. "
        "This can be used to see if it might still be pending or if "
        "the instance has gone away."
    )


class IWebhookDeliveryAttempt(_ITimes, IContained):
    """
    The duration of the request/reply cycle is roughly captured
    by the difference in the ``createdTime`` attributes of the
    request and response. More precisely, the network time is captured
    by the ``elapsed`` attribute of the response.
    """
    containers('.IWebhookSubscription')

    status = _StatusField()

    message = Text(
        title=u"Additional explanatory text.",
        required=False,
    )

    internal_info = Object(IWebhookDeliveryAttemptInternalInfo, required=True)
    request = Object(IWebhookDeliveryAttemptRequest, required=True)
    response = Object(IWebhookDeliveryAttemptResponse, required=True)

    def succeeded():
        """Did the attempt succeed?"""

    def failed():
        """Did the attempt fail?"""

    def pending():
        """Is the attempt still pending?"""

    def resolved():
        """Has the attempt been resolved, one way or the other?"""


###
# delivery attempt related events
###

class IWebhookDeliveryAttemptResolvedEvent(IObjectModifiedEvent):
    """
    A pending webhook delivery attempt has been completed.

    This is an object modified event; the object is the attempt.

    This is the root of a hierarchy; more specific events
    are in :class:`IWebhookDeliveryAttemptFailedEvent`
    and :class:`IWebhookDeliveryAttemptSucceededEvent`.
    """
    succeeded = Bool(
        title=u"Was the delivery attempt successful?"
    )

class IWebhookDeliveryAttemptFailedEvent(IWebhookDeliveryAttemptResolvedEvent):
    """
    A delivery attempt failed.

    The ``succeeded`` attribute will be false.
    """

class IWebhookDeliveryAttemptSucceededEvent(IWebhookDeliveryAttemptResolvedEvent):
    """
    A delivery attempt succeeded.

    The ``succeeded`` attribute will be true.
    """



class IWebhookSubscription(_ITimes, IContainerNamesContainer):
    """
    An individual subscription.
    """
    containers('.IWebhookSubscriptionManager')
    contains('.IWebhookDeliveryAttempt')

    # attempt_limit is an implementation artifact, not part of the interface contract.

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
        # XXX: This might not work. zope.schema.Id requires dotted names or URIs;
        # not all principal IDs are guaranteed to be that.
        title=u"The ID of the ``IPrincipal`` that owns this subscription.",
        description=u"""
        This will be validated at runtime when an event arrives. If
        the current ``zope.security.interfaces.IAuthentication`` utility cannot find
        a principal with the given ID, the delivery will be failed.

        Leave unset to disable security checks.

        This cannot be changed after creation.
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

    dialect_id = Choice(
        title=u"The ID of the `IWebhookDialect` to use",
        description=u"""
        Dialects are named utilities. They control the authentication,
        headers, and HTTP method.
        """,
        required=False,
        vocabulary=UtilityNames(IWebhookDialect),
    )

    dialect = Attribute("The resolved dialect to use for this subscription.")

    def isApplicable(data):
        """
        Determine if this subscription applies to the given *data*
        object.

        This does not take into account whether this subscription is
        active or not, but does take into account the permission and principal
        declared for the subscription as well as the type/interface.

        This is a query method that does not mutate this object.
        """

    def createDeliveryAttempt(payload_data):
        """
        Create a new `IWebhookDeliveryAttempt` for this subscription.

        The delivery attempt is in the pending status, and is stored as
        a child of this subscription; its ``__parent__`` is set to this subscription.

        Subscriptions may be limited in the amount of attempts they will store;
        this method may cause that size to temporarily be exceeded
        """

    active = Bool(
        title=u"Is this webhook active? (Registered to process events.)",
        description=u"""
        Determined by the subscription manager that owns this subscription.
        """,
        default=True,
        readonly=True,
    )

    status_message = Text(
        title=u"Explanatory text about the state of this subscription.",
        required=True,
        default=u'Active',
    )


class ILimitedAttemptWebhookSubscription(IWebhookSubscription):
    """
    A webhook subscription that should limit the number of
    delivery attempts it stores.
    """

    attempt_limit = Attribute(
        # Note that this is not a schema field, it's intended to be configured
        # on a class, or rarely, through direct intervention on a particular
        # subscription.
        u'An integer giving approximately the number of delivery attempts this object will store. '
        u'This is also used to deactivate the subscription when this many attempts in a row have '
        u'failed.'
    )

class ILimitedApplicabilityPreconditionFailureWebhookSubscription(IWebhookSubscription):
    """
    A webhook subscription that supports a limit on the number
    of times checking applicability can be allowed to fail.

    When this number is exceeded, an event implementing
    `IWebhookSubscriptionApplicabilityPreconditionFailureLimitReached`
    is notified.
    """

    applicable_precondition_failure_limit = Attribute(
        # As for attempt_limit.
        u'An integer giving the number of times applicability checks can fail '
        u'before the event is generated.'
    )

class IWebhookSubscriptionApplicabilityPreconditionFailureLimitReached(IObjectEvent):

    failures = Attribute(
        u"An instance of :class:`nti.zodb.interfaces.INumericValue`. "
        u'You may set its ``value`` property to zero if you want to start the count '
        u'over. Other actions would be to make this subscription inactive.'
    )


@implementer(IWebhookSubscriptionApplicabilityPreconditionFailureLimitReached)
class WebhookSubscriptionApplicabilityPreconditionFailureLimitReached(ObjectEvent):

    def __init__(self, subscription, failures):
        ObjectEvent.__init__(self, subscription)
        self.failures = failures

class IWebhookSubscriptionRegistry(Interface):

    def activeSubscriptions(data, event):
        """
        Find active subscriptions for the *data* and the *event*.

        This is a simple query method and does not result in any status changes
        or signal an intent to deliver.

        :return: A sequence of subscriptions.
        """

    def subscriptionsToDeliver(data, event):
        """
        Find subscriptions that are both active and applicable for the
        *data* and the *event*.

        Subscriptions that are active, but not applicable, due to
        circumstances unrelated to the data and event (for example,
        the permission is not available, or the principal or dialect
        cannot be found) may be removed from the active set of subscriptions
        for future calls to this method and :meth:`activeSubscriptions`.

        :return: A sequence of subscriptions.
        """

class IWebhookSubscriptionManager(_ITimes,
                                  IWebhookSubscriptionRegistry,
                                  IContainerNamesContainer):

    """
    A utility that manages subscriptions.

    Also a registry for which subscriptions fire on what events.
    """
    contains(IWebhookSubscription)

    def createSubscription(to=None, for_=None, when=None,
                           owner_id=None, permission_id=None,
                           dialect=None):
        """
        Create and store a new ``IWebhookSubscription`` in this manager.

        The new subscription is returned. It is a child of this object.

        All arguments are by keyword, and have the same meaning as
        the attributes documented for :class:`IWebhookSubscription`.

        Newly created subscriptions are always active.
        """

    def deactivateSubscription(subscription):
        """
        Given a subscription managed by this object, deactivate it.
        """

    def activateSubscription(subscription):
        """
        Given a subscription managed by this object, activate it.
        """


class IWebhookResourceDiscriminator(Interface):
    """
    An adapter that can figure out a better ``for`` for a resource
    than simply what it provides.
    """

    def __call__(): # pylint:disable=signature-differs
        """
        Return the value to use for ``for``.
        """

class IWebhookSubscriptionSecuritySetter(Interface):
    """
    An adapter for the subscription that sets initial security
    declarations for a subscription.

    The subscription is also passed to the call method to allow for
    simple functions to be used as the adapter.

    In the future, the call method might also accept an ``event`` argument,
    and the request might be passed as a second argument to the constructor.
    """

    def __call__(subscription): # pylint:disable=signature-differs
        """
        Set the security declarations for the subscription.
        """
