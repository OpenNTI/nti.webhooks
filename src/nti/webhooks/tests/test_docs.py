# -*- coding: utf-8 -*-
"""
Tests for the documentation.

Runs in zope.testrunner.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gc
import os
import sys
import unittest
import doctest
from zope.testing import cleanup

docs_dir = '../../../../docs/'
here_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.abspath(here_dir + '/' + docs_dir)

# For older versions of PyPy, particularly PyPy3,
# it can collect weakrefs at weird times, and if they've
# gone missing, generate output to sys.stderr:
#
# File "/home/travis/...docs/customizing_payloads.rst", line 372, in customizing_payloads.rst
# Failed example:
#     trigger_delivery()
# Expected nothing
# Got:
#     Traceback (most recent call last):
#       File "/home/travis/virtualenv/pypy3.6-7.1.1/lib-python/3/weakref.py", line 388, in remove
#         del self.data[k]
#     KeyError: <weakref at 0x0000000008f3b260; dead>
#
# So try to collect at specified times.

def setUp(_test=None):
    gc.collect()
    cleanup.setUp()
    if docs_dir not in sys.path:
        sys.path.insert(0, docs_dir)

def tearDown(_test=None):
    cleanup.tearDown()
    gc.collect()

def zodbSetUp(_test=None):
    setUp(_test)
    # zope.session is not strict-iro friendly at this time
    from zope.interface import ro
    ro.C3.STRICT_IRO = False
    # We don't establish the securitypolicy, so zope.app.appsetup
    # complains by logging. Silence that.
    import logging
    logging.getLogger('zope.app.appsetup').setLevel(logging.CRITICAL)
    from nti.webhooks.testing import ZODBFixture
    ZODBFixture.setUp()

def zodbTearDown(_test=None):
    from zope.interface import ro
    from nti.webhooks.testing import ZODBFixture
    ro.C3.STRICT_IRO = ro._ClassBoolFromEnv()
    ZODBFixture.tearDown()
    tearDown(_test)

def test_suite():
    doctest_flags = (
        doctest.NORMALIZE_WHITESPACE
        | doctest.IGNORE_EXCEPTION_DETAIL
        | doctest.ELLIPSIS
    )

    def read(abs_path):
        with open(abs_path, 'r') as f:
            return f.read()

    def pick_fixture(abs_path):
        contents = read(abs_path)
        if 'zodbSetUp' in contents:
            return {
                'setUp': zodbSetUp,
                'tearDown': zodbTearDown
            }
        return {
            'setUp': setUp,
            'tearDown': tearDown
        }

    def make_doctest(path_rel_to_docs):
        if not path_rel_to_docs.endswith('.rst'):
            path_rel_to_docs = path_rel_to_docs + '.rst'
        abs_path = os.path.join(docs_dir, path_rel_to_docs)
        rel_to_here = os.path.relpath(abs_path, here_dir)
        test = doctest.DocFileSuite(
            rel_to_here,
            optionflags=doctest_flags,
            **pick_fixture(abs_path)
        )
        return test

    t = make_doctest

    return unittest.TestSuite((
        t('configuration'),
        t('static'),
        t('static-persistent'),
        t('security'),
        t('delivery_attempts'),
        t('subscription_security'),
        t('customizing_payloads'),
        t('dynamic'),
        t('dynamic/customizing_for'),
        t('events'),
        t('externalization'),
        t('removing_subscriptions'),
        doctest.DocTestSuite('nti.webhooks._schema', optionflags=doctest_flags),
    ))
