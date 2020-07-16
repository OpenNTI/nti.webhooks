# -*- coding: utf-8 -*-
"""
Webhook delivery attempts.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

from persistent import Persistent
from zope.interface import implementer
from zope.schema.fieldproperty import createFieldProperties
from zope.container.contained import Contained
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent import Attributes

from nti.schema.schema import SchemaConfigured

from nti.webhooks.interfaces import IWebhookDeliveryAttempt
from nti.webhooks.interfaces import IWebhookDeliveryAttemptRequest
from nti.webhooks.interfaces import IWebhookDeliveryAttemptResponse
from nti.webhooks.interfaces import IWebhookDeliveryAttemptSucceededEvent
from nti.webhooks.interfaces import IWebhookDeliveryAttemptFailedEvent


class WebhookDeliveryAttemptResolvedEvent(ObjectModifiedEvent):
    _ATTR = Attributes(IWebhookDeliveryAttempt, 'status')
    success = None

    def __init__(self, attempt):
        ObjectModifiedEvent.__init__(self, attempt, self._ATTR)

@implementer(IWebhookDeliveryAttemptSucceededEvent)
class WebhookDeliveryAttemptSucceededEvent(WebhookDeliveryAttemptResolvedEvent):
    success = True

@implementer(IWebhookDeliveryAttemptFailedEvent)
class WebhookDeliveryAttemptFailedEvent(WebhookDeliveryAttemptResolvedEvent):
    success = False



# Requests and responses are immutable. Thus they are never
# persistent.

class _Base(SchemaConfigured):

    def __init__(self, **kwargs):
        self.createdTime = self.lastModified = time.time()
        super(_Base, self).__init__(**kwargs)

@implementer(IWebhookDeliveryAttemptRequest)
class WebhookDeliveryAttemptRequest(_Base):
    __name__ = 'request'
    createFieldProperties(IWebhookDeliveryAttemptRequest)

@implementer(IWebhookDeliveryAttemptResponse)
class WebhookDeliveryAttemptResponse(_Base):
    __name__ = 'response'
    createFieldProperties(IWebhookDeliveryAttemptResponse)

class _StatusDescriptor(object):
    """
    A data descriptor for the ``status`` field.

    This functions similarly to a FieldPropertyStoredThroughField, in
    that it dispatches events when the property is set. It also
    ensures that the transition from "pending" to anything else only
    happens once.
    """

    def __init__(self, field_property):
        self._fp = field_property

    def __get__(self, inst, klass):
        return self._fp.__get__(inst, klass)

    def __set__(self, inst, value):
        status_field = IWebhookDeliveryAttempt['status']
        if inst.resolved():
            raise AttributeError("Cannot change status once set.")
        self._fp.__set__(inst, value) # This fires IFieldUpdatedEvent
        # Now fire our more specific event, if we've settled
        if not status_field.isResolved(value):
            return

        if status_field.isSuccess(value):
            notify(WebhookDeliveryAttemptSucceededEvent(inst))
        else:
            assert status_field.isFailure(value)
            notify(WebhookDeliveryAttemptFailedEvent(inst))


@implementer(IWebhookDeliveryAttempt)
class WebhookDeliveryAttempt(_Base, Contained):
    status = None
    createFieldProperties(IWebhookDeliveryAttempt)
    # Allow delayed validation for these things.
    request = None
    response = None
    __parent__ = None

    def __init__(self, **kwargs):
        super(WebhookDeliveryAttempt, self).__init__(**kwargs)
        if self.request is None:
            self.request = WebhookDeliveryAttemptRequest()
        if self.response is None:
            self.response = WebhookDeliveryAttemptResponse()

    def __repr__(self):
        return "<%s.%s at 0x%x status=%r>" % (
            self.__class__.__module__,
            self.__class__.__name__,
            id(self),
            self.status,
        )

    status = _StatusDescriptor(status)

    def succeeded(self):
        return IWebhookDeliveryAttempt['status'].isSuccess(self.status)

    def failed(self):
        return IWebhookDeliveryAttempt['status'].isFailure(self.status)

    def pending(self):
        return IWebhookDeliveryAttempt['status'].isPending(self.status)

    def resolved(self):
        return IWebhookDeliveryAttempt['status'].isResolved(self.status)


class PersistentWebhookDeliveryAttempt(WebhookDeliveryAttempt, Persistent):
    # XXX: _p_repr
    pass
