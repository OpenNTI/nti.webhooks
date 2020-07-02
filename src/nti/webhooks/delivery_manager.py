# -*- coding: utf-8 -*-
"""
Default implementation of the delivery manager.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from zope import interface


from nti.webhooks.interfaces import IWebhookDeliveryManager
from nti.webhooks.interfaces import IWebhookDeliveryManagerShipmentInfo

@interface.implementer(IWebhookDeliveryManagerShipmentInfo)
class ShipmentInfo(object):
    pass

@interface.implementer(IWebhookDeliveryManager)
class DefaultDeliveryManager(object):


    def createShipmentInfo(self, subscriptions_and_attempts):
        return ShipmentInfo()

    def acceptForDelivery(self, shipment_info):
        assert isinstance(shipment_info, ShipmentInfo)
