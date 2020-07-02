# -*- coding: utf-8 -*-
"""
Default implementation of the delivery manager.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import requests

from zope import interface

from nti.webhooks.interfaces import IWebhookDeliveryManager
from nti.webhooks.interfaces import IWebhookDeliveryManagerShipmentInfo

@interface.implementer(IWebhookDeliveryManagerShipmentInfo)
class ShipmentInfo(object):
    pass

class _TrivialShipmentInfo(ShipmentInfo):

    def __init__(self, subscriptions_and_attempts):
        # This doesn't handle persistent objects.
        self._sub_and_attempts = list(subscriptions_and_attempts)

    def deliver(self):
        for sub, attempt in self._sub_and_attempts:
            response = requests.post(sub.to, data=attempt.payload_data)
            attempt.status = 'successful' if response.ok else 'failed'
            # XXX: Store the full response status, data (to some limit) and headers.
            # We don't want to pickle the Response object to avoid depending on internal
            # details, we need to extract it.
            attempt.message = '%s %s' % (response.status_code, response.reason)

@interface.implementer(IWebhookDeliveryManager)
class DefaultDeliveryManager(object):
    # TODO: Use concurrent.futures to send these using a threadpool.
    def createShipmentInfo(self, subscriptions_and_attempts):
        # TODO: Group by domain and re-use request sessions.
        return _TrivialShipmentInfo(subscriptions_and_attempts)

    def acceptForDelivery(self, shipment_info):
        assert isinstance(shipment_info, ShipmentInfo)

        shipment_info.deliver()

    def waitForPendingDeliveries(self):
        pass
