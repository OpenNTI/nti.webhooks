# -*- coding: utf-8 -*-
"""
Helpers for testing nti.webhooks.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from contextlib import contextmanager

from zope import interface
from zope import component

import responses
import fudge
from requests import RequestException

from nti.testing.zodb import mock_db_trans
from nti.testing.zodb import ZODBLayer

from nti.webhooks.delivery_manager import IExecutorService
from nti.webhooks.interfaces import IWebhookDestinationValidator
from nti.webhooks.interfaces import IWebhookDeliveryManager

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
        if args or kwargs:
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
        cls.db = ZODBLayer.db

    @classmethod
    def tearDown(cls):
        for c in ZODBLayer.__mro__:
            if 'tearDown' in c.__dict__:
                c.__dict__['tearDown'].__func__(c)
        cls.db = None

@interface.implementer(IExecutorService)
class SequentialExecutorService(object):
    """
    Runs tasks one at a time, and only when waited on.

    The preferred interface to this is :func:`begin_synchronous_delivery`.
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


def begin_synchronous_delivery():
    """
    Cause the global ``IWebhookDeliveryManager`` to begin delivering
    new shipments synchronously.

    All deliveries are queued until ``waitForPendingDeliveries`` is
    called; exceptions will be raised from that function.

    This remains in effect until the test is torn down with
    :mod:`zope.testing.cleanup`.
    """
    component.getUtility(IWebhookDeliveryManager).executor_service = SequentialExecutorService()

#: Alternate name for `begin_synchronous_delivery` that may
#: be more descriptive in some circumstances.
begin_deferred_delivery = begin_synchronous_delivery

_current_mocks = None

def mock_delivery_to(url, method='POST', status=200):
    global _current_mocks # pylint:disable=global-statement
    if _current_mocks is None:
        _current_mocks = UsingMocks()
    _current_mocks.add(method, url, status=status)


def _clear_mocks():
    global _current_mocks # pylint:disable=global-statement
    if _current_mocks is not None:
        _current_mocks.finish()
    _current_mocks = None

try:
    from zope.testing import cleanup # pylint:disable=ungrouped-imports
except ImportError: # pragma: no cover
    pass
else:
    cleanup.addCleanUp(_clear_mocks)

class InterestingClass(object):
    """
    A class we refer to (and manipulate) in documentation.

    Do not depend on anything specific about this class
    other than its existence.
    """

@contextmanager
def http_requests_fail():
    """
    A context manager, during which delivery attempts
    will fail with an exception from the HTTP layer.
    """
    with fudge.patch('requests.Session.send') as mock_send:
        mock_send.is_callable().raises(RequestException)
        yield

@contextmanager
def processing_results_fail():
    """
    A context manager, during which processing results
    of delivery attempts will fail with an unexpected
    exception.
    """
    path = 'nti.webhooks.delivery_manager.ShipmentInfo._fill_req_resp_from_request'
    with fudge.patch(path) as mock_proc:
        mock_proc.is_callable().raises(UnicodeError)
        yield

@interface.implementer(IWebhookDestinationValidator)
class _PhonyValidator(object):

    def validateTarget(self, to):
        raise Exception("Testing validation fails")

@contextmanager
def target_validation_fails():
    """
    A context manager, during which the default
    webhook validator will fail all target lookups.
    """
    gsm = component.getGlobalSiteManager()
    old_validator = gsm.queryUtility(IWebhookDestinationValidator)
    new_validator = _PhonyValidator()
    gsm.registerUtility(new_validator)
    try:
        yield
    finally:
        gsm.unregisterUtility(new_validator)
        if old_validator is not None:
            gsm.registerUtility(old_validator)

def wait_for_deliveries():
    """
    Queries the current :class:`nti.webhooks.interfaces.IWebhookDeliveryManager`
    and asks it to wait for all pending deliveries.
    """
    delivery_man = component.getUtility(IWebhookDeliveryManager)
    delivery_man.waitForPendingDeliveries()
