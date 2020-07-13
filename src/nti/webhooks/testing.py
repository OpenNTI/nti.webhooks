# -*- coding: utf-8 -*-
"""
Helpers for testing nti.webhooks.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import interface

import responses

from nti.testing.zodb import mock_db_trans
from nti.testing.zodb import ZODBLayer

from nti.webhooks.delivery_manager import IExecutorService


class UsingMocks(object):
    """
    Mocks :mod:`requests` using :mod:`responses`.

    This is similar to the context manager supplied with
    :mod:`responses`, but a little bit less ugly to use
    in doctests.

    Creating the object automatically establishes mocks. You must explicitly
    :meth:`finish` it to end the mocking.
    """


    def __init__(self, *args, **kwargs):
        self.mock = responses.RequestsMock()
        self.mock.start()
        self.add(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.mock, name)

    def finish(self):
        self.mock.stop()


class DoctestTransaction(mock_db_trans):
    """
    Like :class:`nti.testing.zodb.mock_db_trans`, but
    with methods that are prettier for use in doctests.
    """

    def begin(self):
        return self.__enter__()

    def finish(self):
        return self.__exit__(None, None, None)

class ZODBFixture(object):
    """
    Like :class:`nti.testing.zodb.ZODBLayer`, but
    not a layer and meant for doctests.
    """

    @classmethod
    def setUp(cls):
        for c in reversed(ZODBLayer.__mro__):
            if 'setUp' in c.__dict__:
                c.__dict__['setUp'].__func__(c)


    @classmethod
    def tearDown(cls):
        for c in ZODBLayer.__mro__:
            if 'tearDown' in c.__dict__:
                c.__dict__['tearDown'].__func__(c)


@interface.implementer(IExecutorService)
class SequentialExecutorService(object):
    """
    Runs tasks one at a time, and only when waited on.
    """
    def __init__(self):
        self.to_run = []

    def submit(self, func):
        self.to_run.append(func)

    def waitForPendingExecutions(self, timeout=None):
        funcs, self.to_run = list(self.to_run), []
        for func in funcs:
            func()

    def shutdown(self):
        self.to_run = None


class InterestingClass(object):
    """
    A class we refer to (and manipulate) in documentation.

    Do not depend on anything specific about this class
    other than its existence.
    """
