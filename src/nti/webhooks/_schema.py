# -*- coding: utf-8 -*-
"""
Schema fields used internally.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from zope.configuration.fields import GlobalInterface
from zope.schema import InterfaceField
from zope.schema.interfaces import NotAnInterface
from zope.schema.interfaces import InvalidURI

from zope.interface.interfaces import IObjectEvent

from nti.schema.field import ValidURI

# pylint:disable=inherit-non-class

class NotAnObjectEvent(NotAnInterface):
    """
    Raised when the interface is not for an IObjectEvent.
    """


class ObjectEventField(InterfaceField):
    """
    A field that requires an interface that is a kind of ``IObjectEvent``.
    """
    def _validate(self, value):
        super(ObjectEventField, self)._validate(value)
        if not value.isOrExtends(IObjectEvent):
            raise NotAnObjectEvent(
                value,
                self.__name__
            ).with_field_and_value(self, value)


class ObjectEventInterface(GlobalInterface):
    """
    A configuration field that looks up a named ``IObjectEvent``
    interface.
    """
    def __init__(self, **kwargs):
        super(ObjectEventInterface, self).__init__(**kwargs)
        self.value_type = ObjectEventField()


class HTTPSURL(ValidURI):
    """
    A URI that's HTTPS only.

    As opposed to nti.schema.field.HTTPURL, this:

    - allows for a port
    - allows for inline authentication (``https://user:pass@host/path/``)
    - Requires the URL scheme to be specified, and requires it to be HTTPS.

    TODO: Move all those capabilities to nti.schema.
    """

    def _validate(self, value):
        super(HTTPSURL, self)._validate(value)
        if not value.lower().startswith('https://'):
            raise InvalidURI(value).with_field_and_value(self, value)
