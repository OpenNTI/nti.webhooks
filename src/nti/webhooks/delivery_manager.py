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
        # this may help with HTTP keepalive/pipeline
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


@interface.implementer(IWebhookDeliveryManager)
class DefaultDeliveryManager(Contained):

    def __init__(self, name):
        self.__name__ = name
        self.__parent__ = None
        self.__tasks = []

    def __reduce__(self):
        return self.__name__

    @Lazy
    def _pool(self):
        # Delay creating a thread pool until used for monkey-patching
        return futures.ThreadPoolExecutor(thread_name_prefix='WebhookDeliveryManager')

    def createShipmentInfo(self, subscriptions_and_attempts):
        # TODO: Group by domain and re-use request sessions.
        return _TrivialShipmentInfo(subscriptions_and_attempts)

    def acceptForDelivery(self, shipment_info):
        assert isinstance(shipment_info, ShipmentInfo)
        future = self._pool.submit(shipment_info.deliver) # pylint:disable=no-member
        # Thread safety: We're relying on the GIL here to make
        # appending and removal atomic and possible across threads.
        self.__tasks.append(future)
        future.add_done_callback(self.__tasks.remove)

    def waitForPendingDeliveries(self, timeout=None):
        # Thread safety: We're relying on the GIL to make copying the list
        # of futures atomic. It's probably important to pass a new list here
        # so that it doesn't mutate out from under the waiter as things finish.
        # Note that this waits only for tasks that were already submitted.
        t = list(self.__tasks)
        done, not_done = futures.wait(t, timeout=timeout)
        assert not not_done, not_done
        assert len(done) == len(t), (done, t)

    def _reset(self):
        # Called for test cleanup.
        pool = self.__dict__.pop('_pool', None)
        self.__tasks = []
        if pool is not None:
            pool.shutdown()

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
