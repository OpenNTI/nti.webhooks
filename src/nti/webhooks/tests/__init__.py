# -*- coding: utf-8 -*-
"""
The test package.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from calendar import timegm as dt_tuple_to_unix_ts
import datetime

import pytz

from persistent import Persistent
from zope.dublincore.interfaces import IDCTimes
from zope.dublincore.interfaces import IZopeDublinCore
from zope.dublincore.interfaces import IWriteZopeDublinCore

from hamcrest import assert_that
from hamcrest import is_

from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.matchers import validly_provides
from nti.testing.matchers import has_attr

from nti.webhooks.interfaces import ICreatedTime
from nti.webhooks.interfaces import ILastModified
from nti.webhooks._util import PersistentDCTimesMixin

class WebhookLayer(ConfiguringLayerMixin,
                   ZopeComponentLayer):
    set_up_packages = (
        'nti.webhooks',
        # Even though our configuration does not include
        # zope.dublincore, we want to register it
        # so we can be sure we work as expected when it is
        # registered.
        'zope.dublincore',
    )

    @classmethod
    def setUp(cls):
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()

    @classmethod
    def testSetUp(cls):
        pass

    @classmethod
    def testTearDown(cls):
        pass

class MockConnection(object):

    def register(self, obj):
        "Does nothing."

    # def setstate(self, *args):
    #     raise KeyError


class ReprMixin(object):

    def _makeOne(self):
        raise NotImplementedError

    def test_repr(self):
        inst = self._makeOne()
        self.assertIsNotNone(repr(inst))

        if isinstance(inst, Persistent):
            # pylint:disable=protected-access
            inst._p_jar = MockConnection()
            # The pure-Python implementation only calls back into the connection
            # if it has an oid
            inst._p_oid = b'\x00\x00\x00\x00'
            inst._p_deactivate()

            r = repr(inst)
            # Make sure they don't totally override __repr__
            self.assertIn('MockConnection', r)


class DCTimesMixin(ReprMixin):
    """
    Test mixin or base for items in this package that
    provide `zope.dublincore.interfaces.IDCTimes` directly
    and also the rest of the dublincore data.
    """

    layer = WebhookLayer

    datetime_in_past = datetime.datetime.utcfromtimestamp(123456789)
    ts_in_past = 123456789
    str_in_past = '1973-11-29T21:33:09Z'

    def _makeOne(self):
        raise NotImplementedError

    def test_DC_provides(self):
        inst = self._makeOne()
        assert_that(inst, validly_provides(IDCTimes))
        assert_that(inst, validly_provides(ICreatedTime))
        assert_that(inst, validly_provides(ILastModified))

    def _check_property_sync(self, inst, dc_prop, ts_prop,
                             adapted=False, allow_modified=False):
        # pylint:disable=protected-access
        if isinstance(inst, Persistent):
            inst._p_jar = MockConnection()
            self.assertFalse(inst._p_changed)

        setattr(inst, ts_prop, self.ts_in_past)
        assert_that(inst, has_attr(dc_prop, self.datetime_in_past))

        now = datetime.datetime.now(pytz.utc)
        now_ts = dt_tuple_to_unix_ts(now.utctimetuple())

        setattr(inst, dc_prop, now)
        assert_that(inst, has_attr(ts_prop, now_ts))

        if adapted:
            from .._util import PartialZopeDublinCoreAdapter
            self.assertIsInstance(inst, PartialZopeDublinCoreAdapter)
        if isinstance(inst, Persistent):
            assert_that(inst, is_(PersistentDCTimesMixin))
            assert_that(type(inst).lastModified, is_(PersistentDCTimesMixin.lastModified))
            # In the C implementation, allow_modified for setting the created time always makes
            # _p_changed True. But in the Python implementation, it doesn't...
            if inst._p_changed:
                self.assertTrue(allow_modified, "instance was modified, this must be expected")

    def test_IDCTimes_sync_created(self):
        self._check_property_sync(self._makeOne(),
                                  'created', 'createdTime',
                                  allow_modified=True)

    def test_IDCTimes_sync_modified(self):
        self._check_property_sync(self._makeOne(), 'modified', 'lastModified')

    def test_IZopeDublinCore_sync_created(self):
        self._check_property_sync(
            IZopeDublinCore(self._makeOne()),
            'created',
            'createdTime',
            adapted=True, allow_modified=True)

    def test_IZopeDublinCore_sync_modified(self):
        self._check_property_sync(
            IZopeDublinCore(self._makeOne()),
            'modified',
            'lastModified',
            adapted=True)

    def test_IWriteZopeDublinCore_sync_created(self):
        self._check_property_sync(
            IWriteZopeDublinCore(self._makeOne()),
            'created',
            'createdTime',
            adapted=True, allow_modified=True)

    def test_IWriteZopeDublinCore_sync_modified(self):
        self._check_property_sync(
            IWriteZopeDublinCore(self._makeOne()),
            'modified',
            'lastModified',
            adapted=True)

    def test_IZopeDublinCore_methods(self):
        # pylint:disable=too-many-function-args
        inst = self._makeOne()
        adapt = IZopeDublinCore(inst)
        inst.createdTime = self.ts_in_past
        self.assertEqual(adapt.CreationDate(), self.str_in_past)


        inst.craetedTime = 0
        inst.lastModified = self.ts_in_past
        self.assertEqual(adapt.ModificationDate(), self.str_in_past)
