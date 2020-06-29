# -*- coding: utf-8 -*-
"""
Implementations of dialects.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from zope.interface import implementer

from nti import externalization
from nti.webhooks.interfaces import IWebhookDialect

@implementer(IWebhookDialect)
class DefaultWebhookDialect(object):

    externalizer_name = u'webhook-delivery'

    def __init__(self):
        pass

    def externalizeData(self, data):
        ext_data = externalization.to_external_representation(data,
                                                              name=self.externalizer_name)
        return ext_data
