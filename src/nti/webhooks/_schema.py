# -*- coding: utf-8 -*-
"""
Schema fields used internally.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import re

from zope.configuration.fields import GlobalInterface
from zope.schema import InterfaceField
from zope.schema import Id
from zope.schema.interfaces import NotAnInterface
from zope.schema.interfaces import InvalidURI
from zope.schema.interfaces import InvalidId

from zope.interface.interfaces import IObjectEvent
from zope.principalregistry.metadirectives import TextId

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

class PermissivePrincipalId(TextId):
    """
    A principal ID that allows more than just URIs and dotted names.

    Ids must be text:

        >>> PermissivePrincipalId().validate(b'abc')
        Traceback (most recent call last):
        ...
        WrongType:...

    They cannot contain whitespace::

        >>> PermissivePrincipalId().validate(u'internal space')
        Traceback (most recent call last):
        ...
        InvalidId: Whitespace is not allowed in an ID
        >>> PermissivePrincipalId().validate(u'internal\ttab')
        Traceback (most recent call last):
        ...
        InvalidId: Whitespace is not allowed in an ID

    Email-addresses are allowed::

        >>> PermissivePrincipalId().validate(u'sjohnson@riskmetrics.com')

    As are plain names::

        >>> PermissivePrincipalId().validate(u'sjohnson')

    """

    def _validate(self, value):
        # We bypass most of the validation of the super class.
        super(Id, self)._validate(value) # pylint:disable=bad-super-call
        if re.search(r'\s', value, re.UNICODE):
            # TODO: I18N
            raise InvalidId('Whitespace is not allowed in an ID').with_field_and_value(self, value)
