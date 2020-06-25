# -*- coding: utf-8 -*-
"""
Event subscribers.

This is an internal implementation module
and contains no public code.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

__all__ = ()

from zope import component

from .interfaces import IWebhookDeliveryManager

def on_webhook_event(data, event):
    manager = component.getUtility(IWebhookDeliveryManager)
    manager.temp(data, event)
