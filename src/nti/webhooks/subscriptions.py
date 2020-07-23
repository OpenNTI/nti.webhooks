# -*- coding: utf-8 -*-
"""
Subscription implementations.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import time

from zope import component
from zope.interface import implementer
from zope.component.globalregistry import BaseGlobalComponents
from zope.component.persistentregistry import PersistentComponents

from zope.authentication.interfaces import IAuthentication
from zope.authentication.interfaces import IUnauthenticatedPrincipal
from zope.authentication.interfaces import PrincipalLookupError
from zope.annotation import IAttributeAnnotatable

from zope.security.interfaces import IPermission
from zope.security.management import newInteraction
from zope.security.management import queryInteraction
from zope.security.management import endInteraction
from zope.security.management import checkPermission
from zope.security.testing import Participation

from zope.container.interfaces import INameChooser
from zope.container.btree import BTreeContainer
from zope.container.constraints import checkObject
from zope.cachedescriptors.property import CachedProperty

from nti.zodb.containers import time_to_64bit_int
from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured

from nti.webhooks.interfaces import IWebhookDialect
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookDestinationValidator
from nti.webhooks.interfaces import IWebhookDeliveryAttemptResolvedEvent

from nti.webhooks.attempts import WebhookDeliveryAttempt
from nti.webhooks.attempts import PersistentWebhookDeliveryAttempt

from persistent import Persistent


class _CheckObjectOnSetBTreeContainer(BTreeContainer):
    # XXX: Taken from nti.containers. Should publish that package.

    def _setitemf(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetBTreeContainer, self)._setitemf(key, value)


@implementer(IWebhookSubscription, IAttributeAnnotatable)
class Subscription(SchemaConfigured, _CheckObjectOnSetBTreeContainer):
    """
    Default, non-persistent implementation of `IWebhookSubscription`.
    """
    for_ = permission_id = owner_id = dialect_id = when = None
    to = u''
    createDirectFieldProperties(IWebhookSubscription)

    attempt_limit = 50

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

        # Verify the destination. Fail early
        # if it doesn't pass.
        validator = component.getUtility(IWebhookDestinationValidator, u'', self)
        try:
            validator.validateTarget(self.to)
        except Exception: # pylint:disable=broad-except
            # The exception value can vary; it's not intended to be presented to end
            # users as-is
            attempt.message = (
                u'Verification of the destination URL failed. Please check the domain.'
            )
            attempt.internal_info.storeExceptionInfo(sys.exc_info())
            attempt.status = 'failed' # This could cause pruning

        # Store this once we have a final status. This could cause us to
        # exceed our limit by one.

        # Choose names that are easily sortable, since that's
        # our iteration order.
        now = str(time_to_64bit_int(time.time()))
        name = INameChooser(self).chooseName(now, attempt) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = attempt
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

    def __repr__(self):
        return Persistent.__repr__(self)

    def _p_repr(self):
        return Subscription.__repr__(self)

@component.adapter(IWebhookDeliveryAttemptResolvedEvent)
def prune_subscription_when_resolved(event):
    # type: (IWebhookDeliveryAttemptResolvedEvent) -> None
    attempt = event.object # type: WebhookDeliveryAttempt
    subscription = attempt.__parent__
    if subscription is None or len(subscription) <= subscription.attempt_limit:
        return

    # Copy to avoid concurrent modification. On PyPy, we've seen this
    # produce ``IndexError: list index out of range`` in some tests.
    # This can be reproduced in CPython using PURE_PYTHON mode.
    for key, stored_attempt in list(subscription.items()):
        if stored_attempt.resolved():
            del subscription[key]
            if len(subscription) <= subscription.attempt_limit:
                break



@implementer(IWebhookSubscriptionManager)
class PersistentWebhookSubscriptionManager(_CheckObjectOnSetBTreeContainer):


    def __init__(self):
        super(PersistentWebhookSubscriptionManager, self).__init__()
        self.registry = self._make_registry()

    def _make_registry(self):
        return PersistentComponents()

    def _new_Subscription(self, **kwargs):
        return PersistentSubscription(**kwargs)

    def createSubscription(self, **kwargs):
        subscription = self._new_Subscription(**kwargs)
        name_chooser = INameChooser(self)
        name = name_chooser.chooseName('', subscription) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = subscription

        self.registry.registerHandler(subscription, (subscription.for_, subscription.when),
                                      event=False)
        return subscription


class GlobalSubscriptionComponents(BaseGlobalComponents):
    """
    Exists to be pickled by name.
    """

global_subscription_registry = GlobalSubscriptionComponents('global_subscription_registry')


class GlobalWebhookSubscriptionManager(PersistentWebhookSubscriptionManager):

    def __init__(self, name):
        super(GlobalWebhookSubscriptionManager, self).__init__()
        self.__name__ = name

    def _make_registry(self):
        return global_subscription_registry

    def _new_Subscription(self, **kwargs):
        return Subscription(**kwargs)

    def __reduce__(self):
        # The global manager is pickled as a global object.
        return self.__name__


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
