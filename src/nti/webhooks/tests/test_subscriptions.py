# -*- coding: utf-8 -*-
"""
Tests for subscriptions.py

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import same_instance
from hamcrest import has_properties

from nti.webhooks import subscriptions

class TestGlobalWebhookSubscriptionManager(unittest.TestCase):

    def test_pickle(self):
        import pickle

        gsm = subscriptions.global_subscription_manager

        gsm_2 = pickle.loads(pickle.dumps(gsm))

        assert_that(gsm_2, is_(same_instance(gsm)))
        assert_that(gsm_2, has_properties(registry=same_instance(gsm.registry)))

        assert_that(gsm_2.registry,
                    has_properties(adapters=same_instance(gsm.registry.adapters),
                                   utilities=same_instance(gsm.registry.utilities)))
