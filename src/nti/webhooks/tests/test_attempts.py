# -*- coding: utf-8 -*-
"""
Tests for attempts.py

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest


from nti.webhooks.tests import DCTimesMixin

from nti.webhooks import attempts

class TestWebhookDeliveryAttemptRequest(DCTimesMixin,
                                        unittest.TestCase):

    def _makeOne(self):
        return attempts.WebhookDeliveryAttemptRequest()

class TestWebhookDeliveryAttemptResponse(DCTimesMixin,
                                        unittest.TestCase):

    def _makeOne(self):
        return attempts.WebhookDeliveryAttemptResponse()

class TestWebhookDeliveryAttempt(DCTimesMixin,
                                 unittest.TestCase):

    def _makeOne(self):
        return attempts.WebhookDeliveryAttempt()

class TestPersistentWebhookDeliveryAttempt(TestWebhookDeliveryAttempt):

    def _makeOne(self):
        return attempts.PersistentWebhookDeliveryAttempt()

    def test_persistent(self):
        from persistent import Persistent
        self.assertIsInstance(self._makeOne(), Persistent)
