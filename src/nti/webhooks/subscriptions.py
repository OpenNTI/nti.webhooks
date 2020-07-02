# -*- coding: utf-8 -*-
"""
Subscription implementations.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from zope import component
from zope.interface import implementer
from zope.component.globalregistry import BaseGlobalComponents

from zope.container.interfaces import INameChooser
from zope.container.btree import BTreeContainer
from zope.container.constraints import checkObject
from zope.cachedescriptors.property import CachedProperty

from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured

from nti.webhooks.interfaces import IWebhookDialect
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookDestinationValidator
from nti.webhooks.attempts import WebhookDeliveryAttempt
from nti.webhooks.attempts import PersistentWebhookDeliveryAttempt

from persistent import Persistent


class _CheckObjectOnSetBTreeContainer(BTreeContainer):
    # XXX: Taken from nti.containers. Should publish that package.

    def _setitemf(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetBTreeContainer, self)._setitemf(key, value)


@implementer(IWebhookSubscription)
class Subscription(SchemaConfigured, _CheckObjectOnSetBTreeContainer):
    """
    Default, non-persistent implementation of `IWebhookSubscription`.
    """
    for_ = permission_id = owner_id = dialect_id = when = None
    to = u''
    createDirectFieldProperties(IWebhookSubscription)

    MAXIMUM_LENGTH = 50

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)
        _CheckObjectOnSetBTreeContainer.__init__(self)

    def isApplicable(self, data):
        if hasattr(self.for_, 'providedBy'):
            if not self.for_.providedBy(data):
                return False
        else:
            if not isinstance(data, self.for_): # pylint:disable=isinstance-second-argument-not-valid-type
                return False

        if not self.permission_id or not self.owner_id:
            return True

        # TODO: Check the principal and the permission. Find the permission
        # by name in the registry, find the principal_id by name in the
        # registry, use the security policy to check access.
        # TODO: We probably need to do the principal lookup in the context of the data, just in case
        # there are local principal registries.
        return False

    @CachedProperty('dialect_id')
    def dialect(self):
        # Find the dialect with the given name, using our location
        # as the context to find the enclosing site manager.
        return component.getUtility(IWebhookDialect, self.dialect_id or u'', self)

    def _new_deliveryAttempt(self):
        return WebhookDeliveryAttempt()

    def createDeliveryAttempt(self, payload_data):
        attempt = self._new_deliveryAttempt()
        attempt.payload_data = payload_data
        name = INameChooser(self).chooseName('', attempt) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = attempt

        # Verify the destination. Fail early
        # if it doesn't pass.
        validator = component.getUtility(IWebhookDestinationValidator, u'', self)
        try:
            validator.validateTarget(self.to)
        except Exception as ex: # pylint:disable=broad-except
            attempt.status = 'failed'
            attempt.message = str(ex)

        return attempt

    def __repr__(self):
        return "<%s.%s at 0x%x to=%r for=%s when=%s>" % (
            self.__class__.__module__,
            self.__class__.__name__,
            id(self),
            self.to,
            self.for_.__name__,
            self.when.__name__
        )

class PersistentSubscription(Subscription, Persistent):
    """
    Persistent implementation of `IWebhookSubscription`
    """

    def _new_deliveryAttempt(self):
        return PersistentWebhookDeliveryAttempt()

    # XXX: _p_repr.

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
        name = name_chooser.chooseName('', subscription) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = subscription

        self.registry.registerHandler(subscription, (subscription.for_, subscription.when),
                                      event=False)

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
