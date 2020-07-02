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


@implementer(IWebhookDeliveryAttempt)
class WebhookDeliveryAttempt(SchemaConfigured, Contained):
    status = None
    createFieldProperties(IWebhookDeliveryAttempt)

    def __init__(self, **kwargs):
        self.createdTime = self.lastModified = time.time()
        SchemaConfigured.__init__(self, **kwargs)

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
