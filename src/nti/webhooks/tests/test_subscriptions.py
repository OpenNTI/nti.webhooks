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
from hamcrest import is_not
from hamcrest import same_instance
from hamcrest import has_properties

from persistent import Persistent
from zope import component

from nti.webhooks import subscriptions

from nti.webhooks.tests import DCTimesMixin

class TestPersistentSubscriptionManager(DCTimesMixin,
                                        unittest.TestCase):

    def _makeOne(self):
        return subscriptions.PersistentWebhookSubscriptionManager()

class TestGlobalWebhookSubscriptionManager(TestPersistentSubscriptionManager):

    def _makeOne(self):
        return subscriptions.global_subscription_manager

    def test_pickle(self):
        import pickle

        gsm = subscriptions.global_subscription_manager

        gsm_2 = pickle.loads(pickle.dumps(gsm))

        assert_that(gsm_2, is_(same_instance(gsm)))
        assert_that(gsm_2, has_properties(registry=same_instance(gsm.registry)))

        assert_that(gsm_2.registry,
                    has_properties(adapters=same_instance(gsm.registry.adapters),
                                   utilities=same_instance(gsm.registry.utilities)))

        site_man = component.getGlobalSiteManager()
        assert_that(gsm_2.registry,
                    has_properties(
                        adapters=is_not(same_instance(site_man.adapters)),
                        utilities=is_not(same_instance(site_man.utilities))
                    ))


class TestSubscription(DCTimesMixin, unittest.TestCase):

    def _makeOne(self):
        return subscriptions.Subscription()


class TestPersistentSubscription(TestSubscription):

    def _makeOne(self):
        return subscriptions.PersistentSubscription()

    def test_persistent(self):
        assert_that(self._makeOne(), is_(Persistent))
