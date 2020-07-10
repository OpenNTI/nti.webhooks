# -*- coding: utf-8 -*-
"""
Default implementation of the delivery manager.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

from concurrent import futures

import requests

from zope import interface
from zope.container.contained import Contained
from zope.cachedescriptors.property import Lazy

from nti.webhooks.interfaces import IWebhookDeliveryManager
from nti.webhooks.interfaces import IWebhookDeliveryManagerShipmentInfo

logger = __import__('logging').getLogger(__name__)

text_type = type(u'')

@interface.implementer(IWebhookDeliveryManagerShipmentInfo)
class ShipmentInfo(object):
    pass

class _TrivialShipmentInfo(ShipmentInfo):

    def __init__(self, subscriptions_and_attempts):
        # This doesn't handle persistent objects.

        # Sort them by URL so that requests to the same host go together;
        # this may help with HTTP keepalive/pipeline?
        self._sub_and_attempts = sorted(subscriptions_and_attempts,
                                        key=lambda sub_attempt: sub_attempt[0].to)

    def deliver(self):
        # pylint:disable=broad-except
        with requests.Session() as http_session:
            for sub, attempt in self._sub_and_attempts:
                attempt.request.createdTime = time.time()
                try:
                    prepared_request = sub.dialect.prepareRequest(http_session, sub, attempt)
                    response = http_session.send(prepared_request)
                except Exception as ex:
                    logger.exception("Failed to deliver for attempt %s/%s", sub, attempt)
                    attempt.response = None
                    attempt.status = 'failed'
                    attempt.message = str(ex)
                    continue

                attempt.status = 'successful' if response.ok else 'failed'
                attempt.message = u'%s %s' % (response.status_code, response.reason)

                try:
                    self._fill_req_resp_from_request(attempt, response)
                    # This is generally a programming error, probably an encoding something
                    # or other.
                except Exception as ex:
                    logger.exception("Failed to parse response for attempt %s/%s", sub, attempt)
                    attempt.message = str(ex)

    if str is bytes:
        def _dict_to_text(self, headers):
            return {text_type(k): text_type(v) for k, v in headers.iteritems()}
    else:
        _dict_to_text = dict

    def _fill_req_resp_from_request(self, attempt, http_response):
        # This will ultimately run in a transaction of its own with access to the
        # database.
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
        req.headers = self._dict_to_text(http_request.headers)

        rsp.status_code = http_response.status_code
        rsp.reason = text_type(http_response.reason)
        rsp.headers = self._dict_to_text(http_response.headers)
        rsp.content = http_response.text # XXX: Catch decoding errors?
        rsp.elapsed = http_response.elapsed


class IExecutorService(interface.Interface):
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
        return _TrivialShipmentInfo(subscriptions_and_attempts)

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
