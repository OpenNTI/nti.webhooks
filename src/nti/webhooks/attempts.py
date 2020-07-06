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

from nti.schema.schema import SchemaConfigured

from nti.webhooks.interfaces import IWebhookDeliveryAttempt
from nti.webhooks.interfaces import IWebhookDeliveryAttemptRequest
from nti.webhooks.interfaces import IWebhookDeliveryAttemptResponse

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


@implementer(IWebhookDeliveryAttempt)
class WebhookDeliveryAttempt(_Base, Contained):
    status = None
    createFieldProperties(IWebhookDeliveryAttempt)
    # Allow delayed validation for these things.
    request = None
    response = None

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

class PersistentWebhookDeliveryAttempt(WebhookDeliveryAttempt, Persistent):
    # XXX: _p_repr
    pass
