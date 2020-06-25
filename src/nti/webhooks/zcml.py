# -*- coding: utf-8 -*-
"""
Support for configuring webhook delivery using ZCML.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.configuration.fields import GlobalInterface
from zope.schema import InterfaceField
from zope.schema.interfaces import NotAnInterface
from zope.schema.interfaces import InvalidURI

from zope.interface import Interface
from zope.interface.interfaces import IObjectEvent

from zope.security.zcml import Permission
from zope.principalregistry.metadirectives import TextId

from nti.schema.field import ValidURI

# pylint:disable=inherit-non-class

class _NotAnObjectEvent(NotAnInterface):
    """
    Raised when the interface is not for an IObjectEvent.
    """

class _ObjectEventField(InterfaceField):
    """
    A field that requires an interface that is a kind of ``IObjectEvent``.
    """
    def _validate(self, value):
        super(_ObjectEventField, self)._validate(value)
        if not value.isOrExtends(IObjectEvent):
            raise _NotAnObjectEvent(
                value,
                self.__name__
            ).with_field_and_value(self, value)

class _ObjectEventInterface(GlobalInterface):
    """
    A configuration field that looks up a named ``IObjectEvent``
    interface.
    """
    def __init__(self, **kwargs):
        super(_ObjectEventInterface, self).__init__(**kwargs)
        self.value_type = _ObjectEventField()


class _HTTPSURL(ValidURI):
    """
    A URI that's HTTPS only.

    As opposed to nti.schema.field.HTTPURL, this:

    - allows for a port
    - allows for inline authentication (``https://user:pass@host/path/``)
    - Requires the URL scheme to be specified, and requires it to be HTTPS.

    TODO: Move all those capabilities to nti.schema.
    """

    def _validate(self, value):
        super(_HTTPSURL, self)._validate(value)
        if not value.lower.startswith('https://'):
            raise InvalidURI(value).with_field_and_value(self, value)

class IStaticSubscriptionDirective(Interface):
    """
    Define a static subscription.

    Static subscriptions are not persistent and live only in the
    memory of individual processes. Thus, failed deliveries cannot be
    re-attempted after process shutdown. And of course the delivery history
    is also transient and local to a process.

    """

    for_ = GlobalInterface(
        title=u"The type of object to attempt delivery for.",
        description=u"""
        When object events of type *when* are fired for instances
        having this interface, webhook delivery to *target* might be attempted.
        """
    )

    when = _ObjectEventInterface(
        title=u'The type of event that should result in attempted deliveries.',
        description=u"""
        A type of ``IObjectEvent``, usually one defined in :mod:`zope.lifecycleevent.interfaces` such
        as ``IObjectCreatedEvent``. The *object* field of this event must provide the
        ``for_`` interface; it's the data from the *object* field of this event that
        will be sent to the webhook.

        If not specified, *all* object events involving the ``for_`` interface
        will be sent.
        """,
        default=IObjectEvent,
        required=False,
    )

    to = _HTTPSURL(
        title=u"The complete destination URL to which the data should be sent",
        description=u"""
        This is an arbitrary HTTPS URL. Only HTTPS is supported for
        delivery of webhooks.
        """
    )

    # TODO: Where does specification of the request method go?
    # Dialect or subscription?
    # TODO: Fill in dialect. Should refer to named utilities.
    #dialect = XXX

    owner = TextId(
        title=u"The ID of the ``IPrincipal`` that owns this subscription.",
        description=u"""
        This will be validated at runtime when an event arrives. If
        the current ``zope.security.interfaces.IAuthentication`` utility cannot find
        a principal with the given ID, the delivery will be failed.

        Leave unset to disable security checks.
        """
    )

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
