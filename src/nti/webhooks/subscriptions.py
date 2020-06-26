# -*- coding: utf-8 -*-
"""
Subscription implementations.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import implementer
from zope.component.globalregistry import BaseGlobalComponents

from zope.container.interfaces import INameChooser
from zope.container.btree import BTreeContainer
from zope.container.constraints import checkObject

from nti.externalization.representation import WithRepr
from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionManager

from persistent import Persistent

@WithRepr
@implementer(IWebhookSubscription)
class Subscription(SchemaConfigured):
    """
    Default, non-persistent implementation of `IWebhookSubscription`.
    """
    createDirectFieldProperties(IWebhookSubscription)


class PersistentSubscription(Subscription, Persistent):
    """
    Persistent implementation of `IWebhookSubscription`
    """

class _CheckObjectOnSetBTreeContainer(BTreeContainer):
    # XXX: Taken from nti.containers. Should publish that package.

    def _setitemf(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetBTreeContainer, self)._setitemf(key, value)


class GlobalSubscriptionComponents(BaseGlobalComponents):
    """
    Exists to be pickled by name.
    """

global_subscription_registry = GlobalSubscriptionComponents('global_subscription_registry')

@implementer(IWebhookSubscriptionManager)
class GlobalWebhookSubscriptionManager(_CheckObjectOnSetBTreeContainer):

    def __init__(self, name):
        super(GlobalWebhookSubscriptionManager, self).__init__()
        self.registry = global_subscription_registry
        self.__name__ = name

    def __reduce__(self):
        # The global manager is pickled as a global object.
        return self.__name__

    def addSubscription(self, subscription):
        name_chooser = INameChooser(self)
        name = name_chooser.chooseName('', subscription) # too-many-function-args,assignment-from-no-return
        self[name] = subscription

        self.registry.registerHandler(subscription, (subscription.for_, subscription.when))

# The name string must match the variable name to pickle correctly
global_subscription_manager = GlobalWebhookSubscriptionManager('global_subscription_manager')

def getGlobalSubscriptionManager():
    return global_subscription_manager

def resetGlobals():
    global_subscription_manager.__init__('global_subscription_manager')
    global_subscription_registry.__init__('global_subscription_registry')

try:
    from zope.testing.cleanup import addCleanUp # pylint:disable=ungrouped-imports
except ImportError: # pragma: no cover
    pass
else:
    addCleanUp(resetGlobals)
    del addCleanUp
