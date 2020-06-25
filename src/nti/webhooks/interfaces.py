# -*- coding: utf-8 -*-
"""
Interface definitions for ``nti.webhooks``.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import Interface

# pylint:disable=inherit-non-class

__all__ = [
    'IWebhookDeliveryManager',
]

class IWebhookDeliveryManager(Interface):
    """
    Handles the delivery of messages.

    This is usually a global utility registered by the
    ZCML of this package.
    """
