# -*- coding: utf-8 -*-
"""
Default implementation of the delivery manager.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from concurrent import futures
import requests

from zope import interface
from zope.container.contained import Contained
from zope.cachedescriptors.property import Lazy

from nti.webhooks.interfaces import IWebhookDeliveryManager
from nti.webhooks.interfaces import IWebhookDeliveryManagerShipmentInfo

@interface.implementer(IWebhookDeliveryManagerShipmentInfo)
class ShipmentInfo(object):
    pass

class _TrivialShipmentInfo(ShipmentInfo):

    def __init__(self, subscriptions_and_attempts):
        # This doesn't handle persistent objects.
        self._sub_and_attempts = list(subscriptions_and_attempts)

    def deliver(self):
        for sub, attempt in self._sub_and_attempts:
            response = requests.post(sub.to, data=attempt.payload_data)
            attempt.status = 'successful' if response.ok else 'failed'
            # XXX: Store the full response status, data (to some limit) and headers.
            # We don't want to pickle the Response object to avoid depending on internal
            # details, we need to extract it.
            attempt.message = u'%s %s' % (response.status_code, response.reason)

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
        futures.wait(list(self.__tasks), timeout=timeout)

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
