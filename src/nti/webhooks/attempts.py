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

from nti.externalization.representation import WithRepr
from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured

from nti.webhooks.interfaces import IWebhookDeliveryAttempt


@WithRepr
@implementer(IWebhookDeliveryAttempt)
class WebhookDeliveryAttempt(SchemaConfigured, Contained):
    createFieldProperties(IWebhookDeliveryAttempt)

    def __init__(self, **kwargs):
        self.createdTime = self.lastModified = time.time()
        SchemaConfigured.__init__(self, **kwargs)


class PersistentWebhookDeliveryAttempt(WebhookDeliveryAttempt, Persistent):
    pass
