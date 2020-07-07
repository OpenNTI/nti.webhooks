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

from zope.authentication.interfaces import IAuthentication
from zope.authentication.interfaces import IUnauthenticatedPrincipal
from zope.authentication.interfaces import PrincipalLookupError

from zope.security.interfaces import IPermission
from zope.security.management import newInteraction
from zope.security.management import queryInteraction
from zope.security.management import getInteraction
from zope.security.management import endInteraction
from zope.security.management import checkPermission
from zope.security.testing import Participation


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

    def pop(self):
        """Testing only. Removes and returns a random value."""
        k = list(self.keys())[0]
        v = self[k]
        del self[k]
        return v

    def _find_principal(self, data):
        principal = None
        for context in (data, None):
            auth = component.queryUtility(IAuthentication, context=context)
            if auth is None:
                continue

            try:
                principal = auth.getPrincipal(self.owner_id)
            except PrincipalLookupError:
                # If no principal by that name exists, use the unauthenticatedPrincipal.
                # This could return None. It will still be replaced by the
                # named principal in the other IAuthentication, if need be.
                principal = auth.unauthenticatedPrincipal()
            else:
                assert principal is not None
                break
        if principal is None:
            # Hmm. Either no IAuthentication found, or none of them found a
            # principal while also not having an unauthenticated principal.
            # In that case, we will fall back to the global IUnauthenticatedPrincipal as
            # defined by zope.principalregistry. This should typically not happen.
            principal = component.getUtility(IUnauthenticatedPrincipal)
        return principal

    def _find_permission(self, data):
        for context in (data, None):
            perm = component.queryUtility(IPermission, self.permission_id, context=context)
            if perm is not None:
                break
        return perm

    def isApplicable(self, data):
        if hasattr(self.for_, 'providedBy'):
            if not self.for_.providedBy(data):
                return False
        else:
            if not isinstance(data, self.for_): # pylint:disable=isinstance-second-argument-not-valid-type
                return False

        if not self.permission_id and not self.owner_id:
            # If no security is requested, we're good.
            return True

        # OK, now we need to find the permission and the principal.
        # Both should be found in the context of the data; if not
        # there, then check the currently installed site.
        principal = self._find_principal(data)
        permission = self._find_permission(data)

        if principal is None or permission is None:
            # A missing permission causes zope.security to grant full access.
            # It's treated the same as zope.Public. So don't let that happen.
            return False

        # Now, we need to set up the interaction and do the security check.
        participation = Participation(principal)
        current_interaction = queryInteraction()
        if current_interaction is not None:
            # Cool, we can add our participation to the interaction.
            current_interaction.add(participation)
        else:
            newInteraction(participation)

        try:
            # Yes, this needs the ID of the permission, not the permission object.
            return checkPermission(self.permission_id, data)
        finally:
            if current_interaction is not None:
                current_interaction.remove(participation)
            else:
                endInteraction()


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
        except Exception: # pylint:disable=broad-except
            attempt.status = 'failed'
            # The exception value can vary; it's not intended to be presented to end
            # users as-is
            # XXX: For internal verification, we need some place to store it.
            attempt.message = (
                u'Verification of the destination URL failed. Please check the domain.'
            )

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
