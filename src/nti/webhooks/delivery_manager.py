# -*- coding: utf-8 -*-
"""
Default implementation of the delivery manager.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import time

from concurrent import futures

import requests

from zope import interface
from zope import component
from zope.container.contained import Contained
from zope.cachedescriptors.property import Lazy

from persistent.interfaces import IPersistent
from ZODB.interfaces import IDatabase

from nti.transactions.loop import TransactionLoop

from nti.webhooks import MessageFactory as _
from nti.webhooks._util import print_exception_to_text
from nti.webhooks._util import text_type

from nti.webhooks.interfaces import IWebhookDeliveryManager
from nti.webhooks.interfaces import IWebhookDeliveryManagerShipmentInfo

logger = __import__('logging').getLogger(__name__)


class _RunJobWithDatabase(TransactionLoop):
    _connection = None

    attempts = 10

    def run_handler(self, *args, **kwargs):
        return self.handler(self._connection, *args, **kwargs)

    def setUp(self):
        db = component.getUtility(IDatabase)
        self._connection = db.open()

    def tearDown(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None


class _PersistentAttemptGetter(object):
    __slots__ = (
        'oid',
        'database_name',
        'dialect',
        'to',
        'payload_data',
    )

    def __init__(self, sub, attempt):
        self.oid = attempt._p_oid
        self.database_name = attempt._p_jar.db().database_name
        self.dialect = sub.dialect
        self.to = sub.to
        self.payload_data = attempt.payload_data

    def __call__(self, connection):
        return connection.get_connection(self.database_name).get(self.oid)


class _TrivialAttemptGetter(object):
    __slots__ = (
        'sub',
        'attempt',
    )

    def __init__(self, sub, attempt):
        self.sub = sub
        self.attempt = attempt

    @property
    def dialect(self):
        return self.sub.dialect

    @property
    def to(self):
        return self.sub.to

    @property
    def payload_data(self):
        return self.attempt.payload_data

    def __call__(self, connection):
        return self.attempt


class _AttemptResult(object):
    __slots__ = (
        'createdTime',
        # attempt_getter is a callable(connection) that returns the attempt object.
        # For non-persistent attempts, this can be a simple closure;
        # for persistent attempts, it needs to be more complex.
        'attempt_getter',
        'http_response',
        'exception_string',
    )

    def __init__(self, attempt_getter):
        self.createdTime = None
        self.attempt_getter = attempt_getter
        self.http_response = None
        self.exception_string = None


@interface.implementer(IWebhookDeliveryManagerShipmentInfo)
class ShipmentInfo(object):

    def __init__(self, subscriptions_and_attempts):
        # Sort them by URL so that requests to the same host go together;
        # this may help with HTTP keepalive/pipeline?
        self._sub_and_attempts = sorted(subscriptions_and_attempts,
                                        key=lambda sub_attempt: sub_attempt[0].to)
        self._results = []
        self._had_persistent = False
        for sub, attempt in self._sub_and_attempts:
            if IPersistent.providedBy(attempt):
                self._had_persistent = True
                getter = _PersistentAttemptGetter(sub, attempt)
            else:
                getter = _TrivialAttemptGetter(sub, attempt)
            result = _AttemptResult(getter)
            self._results.append(result)

    def deliver(self):
        # Collects _AttemptResult objects.
        with requests.Session() as http_session:
            # We can't access any attributes of sub or attempt here, they may be
            # persistent and we're not in a transaction or having an open connection.
            for result in self._results:
                result.createdTime = time.time()
                try:
                    prepared_request = result.attempt_getter.dialect.prepareRequest(
                        http_session,
                        # Use the attempt_getter as a proxy for the
                        # subscription/attempt, since, if persistent,
                        # they cannot be accessed directly. Always do
                        # this, even if they're not persistent, for
                        # consistency. NOTE: These are not complete
                        # proxies, only providing the things that have
                        # been proven to be needed. Should probably
                        # introduce interfaces for this and update the
                        # prepareRequest method description.
                        result.attempt_getter,
                        result.attempt_getter)
                    response = http_session.send(prepared_request)
                except Exception: # pylint:disable=broad-except
                    # Remember, cannot access persistent attributes
                    logger.exception("Failed to deliver for hook to %s", result.attempt_getter.to)
                    result.exception_string = print_exception_to_text(sys.exc_info())
                else:
                    result.http_response = response

        # Now open the database long enough to store the results. We
        # don't use any site here, so per-site configuration for
        # things like event handlers isn't possible. TODO: We probably could,
        # we could look up the hierarchy of the attempt and put it in
        # the first site we find that way.
        if self._had_persistent:
            # ``had_persistent`` may be a worthless optimization, but it
            # simplifies some test scenarios a bit during initial bring-up.
            # TODO: Perhaps we want to just run one, or some limit,
            # at a time to decrease the chances of conflicts?
            runner = _RunJobWithDatabase(self._process_results)
            runner(self._results)
        else:
            self._process_results(None, self._results)

    REMOTE_EXCEPTION_MESSAGE = _(u'Contacting the remote server experienced an unexpected error.')
    LOCAL_EXCEPTION_MESSAGE = _(u'Unexpected error handling the response from the server.')

    @classmethod
    def _process_results(cls, connection, results):
        for result in results:
            attempt = result.attempt_getter(connection)
            attempt.request.createdTime = result.createdTime
            if result.exception_string:
                attempt.response = None
                attempt.message = cls.REMOTE_EXCEPTION_MESSAGE
                attempt.internal_info.storeExceptionText(result.exception_string)
                attempt.status = 'failed'
            else:
                try:
                    cls._fill_req_resp_from_request(attempt, result.http_response)
                    # This is generally a programming error, probably an encoding something
                    # or other.
                except Exception: # pylint:disable=broad-except
                    logger.exception("Failed to parse response for attempt %s", attempt)
                    attempt.message = cls.LOCAL_EXCEPTION_MESSAGE
                    attempt.internal_info.storeExceptionInfo(sys.exc_info())
                    attempt.status = 'failed'
                else:
                    attempt.status = 'successful' if result.http_response.ok else 'failed'


    if str is bytes:
        @staticmethod
        def _dict_to_text(headers):
            return {text_type(k): text_type(v) for k, v in headers.iteritems()}
    else:
        _dict_to_text = dict

    @classmethod
    def _fill_req_resp_from_request(cls, attempt, http_response):
        attempt.message = u'%s %s' % (http_response.status_code, http_response.reason)

        http_request = http_response.request # type: requests.PreparedRequest
        req = attempt.request
        rsp = attempt.response
        rsp.createdTime = time.time()

        req.url = http_request.url
        req.method = text_type(http_request.method)
        req.body = text_type(http_request.body) # XXX: Text/bytes. This uses default encoding.

        # XXX: What about stripping security sensitive headers from
        # request and response? I have a comment about that in the
        # interface definition. But as I was implementing, I couldn't
        # come up with a scenario where that actually matters
        # (currently). Outgoing hook deliveries include no
        # authentication, so there's nothing on that side, and no
        # reason to expect that a response will include anything
        # either.
        #
        # I looked at hooks configured for several different services
        # and didn't find anything that needed to be dropped.
        #
        # We'll know more as we make real-life deliveries.
        req.headers = cls._dict_to_text(http_request.headers)

        rsp.status_code = http_response.status_code
        rsp.reason = text_type(http_response.reason)
        rsp.headers = cls._dict_to_text(http_response.headers)
        rsp.content = http_response.text # XXX: Catch decoding errors?
        rsp.elapsed = http_response.elapsed


class IExecutorService(interface.Interface):
    """
    Internal interface for testing. See :class:`nti.webhooks.testing.SequentialExecutorService`
    for the alternate implementation.
    """
    # pylint:disable=inherit-non-class,no-self-argument,no-method-argument
    def submit(func):
        """
        Submit a job to run. Execution may or may not commence
        in the background. Tracks tasks that have been submitted and not yet
        finished.
        """

    def waitForPendingExecutions(timeout=None):
        """
        Wait for all tasks that have been submitted but not yet finished
        to finish.
        ``submit``, wait for them all to finish. If any one of them
        raises an exception, this method should raise an exception.
        """

    def shutdown():
        """
        Stop accepting new tasks.
        """

@interface.implementer(IExecutorService)
class ThreadPoolExecutorService(object):

    def __init__(self):
        self.pending_tasks = []
        self.executor = futures.ThreadPoolExecutor(thread_name_prefix='WebhookDeliveryManager')

    def submit(self, func):
        future = self.executor.submit(func) # pylint:disable=no-member
        # Thread safety: We're relying on the GIL here to make
        # appending and removal atomic and possible across threads.
        self.pending_tasks.append(future)
        future.add_done_callback(self.pending_tasks.remove)

    def waitForPendingExecutions(self, timeout=None):
        # Thread safety: We're relying on the GIL to make copying the list
        # of futures atomic. It's probably important to pass a new list here
        # so that it doesn't mutate out from under the waiter as things finish.
        # Note that this waits only for tasks that were already submitted.
        t = list(self.pending_tasks)
        done, not_done = futures.wait(t, timeout=timeout)
        assert not not_done, not_done
        assert len(done) == len(t), (done, t)
        for future in done:
            # If any of them raised an exception, re-raise it.
            # This only gets the first exception, unfortunately.
            future.result()

    def shutdown(self):
        self.executor.shutdown()


@interface.implementer(IWebhookDeliveryManager)
class DefaultDeliveryManager(Contained):

    def __init__(self, name):
        self.__name__ = name
        self.__parent__ = None

    def __reduce__(self):
        return self.__name__

    @Lazy
    def executor_service(self):
        # Delay creating a thread pool until used to allow for monkey-patching
        return ThreadPoolExecutorService()

    def createShipmentInfo(self, subscriptions_and_attempts):
        return ShipmentInfo(subscriptions_and_attempts)

    def acceptForDelivery(self, shipment_info):
        assert isinstance(shipment_info, ShipmentInfo)
        self.executor_service.submit(shipment_info.deliver) # pylint:disable=no-member

    def waitForPendingDeliveries(self, timeout=None):
        self.executor_service.waitForPendingExecutions(timeout) # pylint:disable=no-member

    def _reset(self):
        # Called for test cleanup.
        exec_service = self.__dict__.pop('executor_service', None)
        if exec_service is not None:
            exec_service.shutdown()

# Name string must match variable identifier for pickling
global_delivery_manager = DefaultDeliveryManager('global_delivery_manager')

@interface.implementer(IWebhookDeliveryManager)
def getGlobalDeliveryManager():
    return global_delivery_manager

try:
    from zope.testing.cleanup import addCleanUp # pylint:disable=ungrouped-imports
except ImportError: # pragma: no cover
    pass
else:
    addCleanUp(global_delivery_manager._reset) # pylint:disable=protected-access
