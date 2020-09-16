# -*- coding: utf-8 -*-
"""
Tests for generations.py

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import unittest

from persistent.mapping import PersistentMapping

from zope import event

from zope.traversing.interfaces import ITraversable
from zope.traversing.adapters import DefaultTraversable

from .. import generations

class TraversablePersistentMapping(PersistentMapping):

    def __conform__(self, iface):
        # We don't want to rely on the component registry
        if iface is ITraversable:
            return DefaultTraversable(self)
        return None

class CleanUp(object):

    def setUp(self):
        self.subscribers = event.subscribers[:]

    def tearDown(self):
        event.subscribers = self.subscribers[:]

class TestConnectionRootTraverser(CleanUp,
                                  unittest.TestCase):

    def _makeOne(self, context=None):
        if context is None:

            context = TraversablePersistentMapping()
        return generations.ConnectionRootTraverser(context)

    def test_traverse_no_path(self):
        context = PersistentMapping()
        self.assertIs(self._makeOne(context).traverse(None), context)

    def test_traverse_dot(self):
        context = TraversablePersistentMapping()
        self.assertIs(self._makeOne(context).traverse('/.'), context)

    def test_traverse_slash(self):
        context = TraversablePersistentMapping()
        self.assertIs(self._makeOne(context).traverse('/'), context)

    def test_traverse_trailing_slash(self):
        context = TraversablePersistentMapping(foo=42)
        t = self._makeOne(context)
        self.assertEqual(t.traverse('/foo'), 42)
        self.assertEqual(t.traverse('/foo/'), 42)

    def test_traverse_double_slash(self):
        inner = TraversablePersistentMapping(biz=42)
        context = TraversablePersistentMapping(foo=inner)
        t = self._makeOne(context)
        self.assertEqual(t.traverse('/foo/biz'), 42)
        self.assertEqual(t.traverse('/foo/biz/'), 42)
        self.assertEqual(t.traverse('/foo//biz'), 42)
        self.assertEqual(t.traverse('/foo//biz/'), 42)
        self.assertEqual(t.traverse('/foo//biz//'), 42)

    def test_restores_site_and_fires_events(self):
        from zope.component.hooks import site as current_site
        from zope.component.hooks import setSite
        from zope.component.hooks import getSite
        from zope.location.interfaces import LocationError
        from nti.site.transient import TrivialSite
        from zope.site.site import LocalSiteManager
        from zope.traversing.interfaces import BeforeTraverseEvent

        site1 = TrivialSite(LocalSiteManager(None))

        site2 = TrivialSite(LocalSiteManager(None))
        site2.installed = 0

        def before_traverse(evnt):
            self.assertIsInstance(evnt, BeforeTraverseEvent)
            setSite(site2)
            # Increment to see if this event is fired multiple times.
            site2.installed += 1

        event.subscribers.append(before_traverse)

        context = TraversablePersistentMapping()
        context['foo'] = 42
        with current_site(site1):
            t = self._makeOne(context)
            # Note the trailing slashes; even so we only fire
            # the event once.
            result = t.traverse(u'/foo//')
            self.assertEqual(result, 42)
            # The site was restored
            self.assertIs(getSite(), site1)

        self.assertEqual(site2.installed, 1)

        site2.installed = 0

        # Even when we raise an error it gets restored.
        with current_site(site1):
            t = self._makeOne(context)
            with self.assertRaises(LocationError):
                t.traverse(u'/bar')
            self.assertIs(getSite(), site1)

        self.assertTrue(site2.installed)

    def test_traverse_default(self):
        t = self._makeOne()
        result = t.traverse(u'/biz/baz', 42)
        self.assertEqual(result, 42)


class TestSubscriptionDescriptor(CleanUp,
                                 unittest.TestCase):

    def test_traverser_find_site(self):
        from zope.traversing.interfaces import BeforeTraverseEvent
        path = u'/abc'

        events = []
        def before_traverse(evnt):
            self.assertIsInstance(evnt, BeforeTraverseEvent)
            events.append(evnt)
        event.subscribers.append(before_traverse)

        desc = generations.SubscriptionDescriptor(path, {})

        result = desc.find_site(TraversablePersistentMapping(abc=42))
        self.assertEqual(result, 42)
        self.assertTrue(events)
