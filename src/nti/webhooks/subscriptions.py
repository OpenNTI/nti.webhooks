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
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.interface import providedBy
from zope.interface.interfaces import IRegistered
from zope.interface.interfaces import IUnregistered

from zope.component.globalregistry import BaseGlobalComponents
from zope.component.persistentregistry import PersistentComponents

from zope.authentication.interfaces import IAuthentication
from zope.authentication.interfaces import IUnauthenticatedPrincipal
from zope.authentication.interfaces import PrincipalLookupError
from zope.annotation import IAttributeAnnotatable

from zope.lifecycleevent import IObjectRemovedEvent

from zope.security.interfaces import IPermission
from zope.security.management import newInteraction
from zope.security.management import queryInteraction
from zope.security.management import endInteraction
from zope.security.management import checkPermission
from zope.security.testing import Participation

from zope.container.interfaces import INameChooser
from zope.container.btree import BTreeContainer
from zope.container.sample import SampleContainer
from zope.container.constraints import checkObject
from zope.cachedescriptors.property import CachedProperty

from nti.zodb.containers import time_to_64bit_int
from nti.zodb.minmax import NumericPropertyDefaultingToZero
from nti.zodb.minmax import NumericMinimum

from nti.schema.fieldproperty import createDirectFieldProperties
from nti.schema.schema import SchemaConfigured

from nti.webhooks import MessageFactory as _

from nti.webhooks.interfaces import IWebhookDialect
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import ILimitedAttemptWebhookSubscription
from nti.webhooks.interfaces import ILimitedApplicabilityPreconditionFailureWebhookSubscription
from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.interfaces import IWebhookDestinationValidator
from nti.webhooks.interfaces import IWebhookDeliveryAttemptResolvedEvent
from nti.webhooks.interfaces import IWebhookDeliveryAttemptFailedEvent
from nti.webhooks.interfaces import IWebhookSubscriptionApplicabilityPreconditionFailureLimitReached
from nti.webhooks.interfaces import WebhookSubscriptionApplicabilityPreconditionFailureLimitReached

from nti.webhooks.attempts import WebhookDeliveryAttempt
from nti.webhooks.attempts import PersistentWebhookDeliveryAttempt

from nti.webhooks._util import DCTimesMixin
from nti.webhooks._util import PersistentDCTimesMixin
from nti.webhooks._util import describe_class_or_specification

from persistent import Persistent

logger = __import__('logging').getLogger(__name__)

class _CheckObjectOnSetBTreeContainer(BTreeContainer):
    """
    Extending this makes you persistent.
    """
    # XXX: Taken from nti.containers. Should publish that package.

    def _setitemf(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetBTreeContainer, self)._setitemf(key, value)

class _CheckObjectOnSetSampleContainer(SampleContainer):
    """
    Non-persistent.
    """
    def __setitem__(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetSampleContainer, self).__setitem__(key, value)

    def _newContainerData(self):
        # We return a BTree so that iteration order is guaranteed.
        from BTrees import family64
        return family64.OO.BTree()


class IApplicableSubscriptionFactory(Interface): # pylint:disable=inherit-non-class
    """
    A private contract between the Subscription and its SubscriptionManager.

    This is only called on subscriptions that are already determined to be *active*;
    if the subscription is also *applicable*, then it should be returned. Otherwise,
    it should return None.

    This is called when we intend to attempt delivery, so it's a good time to take cleanup
    action if the subscription isn't applicable for reasons that aren't directly related
    to the *data* and the *event*, for example, if the principal cannot be found.
    """

    def __call__(data, event): # pylint:disable=no-self-argument,signature-differs
        """
        See class documentation.
        """


@implementer(ILimitedAttemptWebhookSubscription,
             ILimitedApplicabilityPreconditionFailureWebhookSubscription,
             IAttributeAnnotatable,
             IApplicableSubscriptionFactory)
class AbstractSubscription(SchemaConfigured):
    """
    Subclasses need to extend a ``Container`` implementation.
    """
    for_ = permission_id = owner_id = dialect_id = when = None
    to = u''
    active = None
    createDirectFieldProperties(IWebhookSubscription)
    createDirectFieldProperties(ILimitedAttemptWebhookSubscription)

    __parent__ = None

    attempt_limit = 50
    applicable_precondition_failure_limit = 50
    fallback_to_unauthenticated_principal = True

    def __init__(self, **kwargs):
        self.createdTime = self.lastModified = time.time()
        SchemaConfigured.__init__(self, **kwargs)

    def keys(self):
        raise NotImplementedError

    def _setActive(self, active):
        # The public field is readonly; that only kicks in
        # when there is a value in the __dict__ already.
        self.__dict__.pop('active', None)
        self.active = active
        if active:
            # Back to the default message
            self.__dict__.pop('status_message', None)
            # Reset to 0
            del self._delivery_applicable_precondition_failed
        # TODO: If we need to, this would be a good place to notify specific
        # events about becoming in/active. The ``I[Un]Registered`` event we use to
        # call *this* function can be used, but isn't obvious (and the order may be
        # difficult to define).

    def pop(self):
        """Testing only. Removes and returns a random value."""
        k = list(self.keys())[0]
        v = self[k]
        del self[k]
        return v

    def clear(self):
        """Testing only. Removes all delivery attempts."""
        for k in list(self.keys()):
            del self[k]

    def _find_principal(self, data):
        principal = None
        for context in (data, None):
            auth = component.queryUtility(IAuthentication, context=context)
            if auth is None:
                continue

            try:
                principal = auth.getPrincipal(self.owner_id)
            except PrincipalLookupError:
                # If no principal by that name exists, use the
                # unauthenticatedPrincipal. This could return None. It
                # will still be replaced by the named principal in the
                # other IAuthentication, if need be.
                #
                # XXX: Using the unauthenticated principal when no
                # principal can be found is elegant. But it makes it
                # harder to deactivate broken subscriptions (we'd have
                # to spread this knowledge around a few functions).
                # That's why we allow disabling it, and why persistent
                # subscriptions disable it by default. Maybe there's
                # something better? Maybe spreading that knowledge is
                # the best we can do.
                if self.fallback_to_unauthenticated_principal:
                    principal = auth.unauthenticatedPrincipal()
            else:
                assert principal is not None
                break
        if principal is None and self.fallback_to_unauthenticated_principal:
            # Hmm. Either no IAuthentication found, or none of them found a
            # principal while also not having an unauthenticated principal.
            # In that case, we will fall back to the global IUnauthenticatedPrincipal as
            # defined by zope.principalregistry. This should typically not happen.
            principal = component.getUtility(IUnauthenticatedPrincipal)
        return principal

    def _find_permission(self, data):
        if self.permission_id is None:
            return None

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

        # No need for the distinction it makes here.
        return bool(self.__checkSecurity(data))

    def __checkSecurity(self, data):
        """
        Returns a boolean indicating whether *data* passes the security
        checks defined for this subscription.

        If we are not able to make the security check because the principal or
        permission we are supposed to use is not defined, returns the special
        (false) value `None`. This can be used to distinguish the case where
        access is denied by the security policy from the case where requested
        principals are missing.
        """
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
            return None

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

    # We only ever use the ``increment()`` method of this, *or* we
    # delete it (which works even if there's nothing in our ``__dict__``)
    # when we are making other changes, so subclasses do not have to be
    # ``PersistentPropertyHolder`` objects. (But they are.)
    _delivery_applicable_precondition_failed = NumericPropertyDefaultingToZero(
        '_delivery_applicable_precondition_failed',
        # We have to use NumericMinimum instead of NumericMaximum or
        # MergingCounter because we periodically reset to 0. And MergingCounter
        # has a bug when that happens. (https://github.com/NextThought/nti.zodb/issues/6)
        NumericMinimum,
    )

    def __call__(self, data, event):
        # We're assumed applicable for the data and event, no need to double
        # check that.
        assert self.active
        security_check = self.__checkSecurity(data)
        if security_check:
            # Yay, access granted!
            # TODO: Should we decrement the failure count here
            # (keeping a floor of 0)?
            return self
        # Boo, no access :(
        if security_check is None:
            # Failed to find the principal/permission. Something is wrong.
            failures = self._delivery_applicable_precondition_failed
            try:
                incr = failures.increment
            except AttributeError:
                # See https://github.com/NextThought/nti.zodb/issues/7
                failures.value += 1
            else:
                failures = incr()
            # XXX: JAM: Why did I think checking it here was the best thing, instead
            # of just sending the event every time a failure occurs? Was I trying to
            # cut down on the chance of misusing the failure property? Trying to cut down
            # on the number of events generated? Trying to reduce conflicts?
            if failures.value >= self.applicable_precondition_failure_limit:
                notify(WebhookSubscriptionApplicabilityPreconditionFailureLimitReached(
                    self,
                    failures))
        return None

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

        # Store the attempt (make it contained by this object) before we
        # conceivably change its status. Changing the status
        # can fire events, and we need to know the parent for those events to
        # work properly.

        # Choose names that are easily sortable, since that's
        # our iteration order.
        now = str(time_to_64bit_int(time.time()))
        name = INameChooser(self).chooseName(now, attempt) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = attempt

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


        return attempt

    def __repr__(self):
        return "<%s.%s at 0x%x to=%r for=%s when=%s>" % (
            self.__class__.__module__,
            self.__class__.__name__,
            id(self),
            self.to,
            describe_class_or_specification(self.for_),
            describe_class_or_specification(self.when),
        )

class Subscription(_CheckObjectOnSetSampleContainer, AbstractSubscription, DCTimesMixin):
    def __init__(self, **kwargs):
        AbstractSubscription.__init__(self, **kwargs)
        _CheckObjectOnSetSampleContainer.__init__(self)

class PersistentSubscription(_CheckObjectOnSetBTreeContainer,
                             AbstractSubscription,
                             PersistentDCTimesMixin):
    """
    Persistent implementation of `IWebhookSubscription`
    """
    fallback_to_unauthenticated_principal = False

    def __init__(self, **kwargs):
        AbstractSubscription.__init__(self, **kwargs)
        _CheckObjectOnSetBTreeContainer.__init__(self)

    def _new_deliveryAttempt(self):
        return PersistentWebhookDeliveryAttempt()

    __repr__ = Persistent.__repr__
    _p_repr = AbstractSubscription.__repr__


def _subscription_full(subscription, strict):
    return ILimitedAttemptWebhookSubscription.providedBy(subscription) \
        and len(subscription) > (subscription.attempt_limit - (1 if strict else 0))


@component.adapter(IWebhookDeliveryAttemptResolvedEvent)
def prune_subscription_when_resolved(event):
    # type: (IWebhookDeliveryAttemptResolvedEvent) -> None
    attempt = event.object # type: WebhookDeliveryAttempt
    subscription = attempt.__parent__
    if not _subscription_full(subscription, False):
        return

    # Copy to avoid concurrent modification. On PyPy, we've seen this
    # produce ``IndexError: list index out of range`` in some tests.
    # This can be reproduced in CPython using PURE_PYTHON mode.
    count = 0
    for key, stored_attempt in list(subscription.items()):
        if stored_attempt.resolved():
            del subscription[key]
            count += 1
            if len(subscription) <= subscription.attempt_limit:
                break
    logger.debug(
        "Pruned %d old delivery attempts from subscription %s",
        count, subscription
    )


@component.adapter(IWebhookDeliveryAttemptFailedEvent)
def deactivate_subscription_when_all_failed(event):
    # type: (IWebhookDeliveryAttemptFailedEvent) -> None
    attempt = event.object # type: WebhookDeliveryAttempt
    subscription = attempt.__parent__
    if not _subscription_full(subscription, True):
        return

    # This is a very simple-minded approach. Something more featured
    # might involve a ratio of failed attempts? Over some sort of sliding window?
    # Or examining the time period?
    # This has to activate all the sub-objects, which could be expensive.
    # We could make the subscription use BTree Length objects to track
    # the various states.
    if all(attempt.failed() for attempt in subscription.values()):
        logger.info(
            "Deactivating webhook subscription %s due to too many delivery failures.",
            subscription,
        )
        manager = subscription.__parent__ # type:PersistentWebhookSubscriptionManager
        manager.deactivateSubscription(subscription)
        subscription.status_message = _(u'Delivery suspended due to too many delivery failures.')


@component.adapter(ILimitedApplicabilityPreconditionFailureWebhookSubscription,
                   IWebhookSubscriptionApplicabilityPreconditionFailureLimitReached)
def deactivate_subscription_when_applicable_limit_exceeded(subscription, event):
    # See comments in __call__. This is only sent when the limit is actually
    # exceeded.
    logger.info(
        "Deactivating webhook subscription %s due to too many precondition failures.",
        subscription,
    )

    manager = subscription.__parent__
    manager.deactivateSubscription(subscription)
    subscription.status_message = _(u'Delivery suspended due to too many precondition failures.')


class AbstractWebhookSubscriptionManager(object):

    def __init__(self):
        super(AbstractWebhookSubscriptionManager, self).__init__()
        self.registry = self._make_registry()
        self.createdTime = self.lastModified = time.time()

    def _make_registry(self):
        raise NotImplementedError

    def _new_Subscription(self, **kwargs):
        raise NotImplementedError

    def createSubscription(self, to=None, for_=None, when=None,
                           owner_id=None, permission_id=None,
                           dialect_id=None):
        subscription = self._new_Subscription(to=to, for_=for_, when=when, owner_id=owner_id,
                                              permission_id=permission_id, dialect_id=dialect_id)
        name_chooser = INameChooser(self)
        name = name_chooser.chooseName('', subscription) # pylint:disable=too-many-function-args,assignment-from-no-return
        self[name] = subscription

        self.activateSubscription(subscription)

        return subscription

    def activateSubscription(self, subscription):
        if subscription.__parent__ is not self:
            raise AssertionError
        # active subscriptions are managed as 'subscription adapters'.
        # This lets us use the ``subscribers()`` API to treat them as
        # callable factories that return None if they are not
        # applicable. (Compare with 'handlers', which, while callable,
        # aren't treated as factories and have no return value). The
        # major difference is that we need to provide a *provided* argument so that
        # we can replicate it when we call ``subscribers``.
        self.registry.registerSubscriptionAdapter(subscription,
                                                  (subscription.for_, subscription.when),
                                                  IWebhookSubscription)
        return True

    def deactivateSubscription(self, subscription):
        if subscription.__parent__ is not self:
            raise AssertionError
        return self.registry.unregisterSubscriptionAdapter(subscription,
                                                           (subscription.for_, subscription.when),
                                                           IWebhookSubscription)

    def activeSubscriptions(self, data, event):
        # pylint:disable=no-member
        return self.registry.adapters.subscriptions((providedBy(data), providedBy(event)),
                                                    IWebhookSubscription)

    def subscriptionsToDeliver(self, data, event):
        return self.registry.subscribers((data, event), IWebhookSubscription)


@component.adapter(IWebhookSubscription, IRegistered)
def sync_active_status_registered(subscription, _event):
    # type: (Subscription, Any) -> None
    subscription._setActive(True) # pylint:disable=protected-access


@component.adapter(IWebhookSubscription, IUnregistered)
def sync_active_status_unregistered(subscription, _event):
    subscription._setActive(False) # pylint:disable=protected-access


@component.adapter(IWebhookSubscription, IObjectRemovedEvent)
def deactivate_subscription_when_removed(subscription, event):
    event.oldParent.deactivateSubscription(subscription)

class GlobalSubscriptionComponents(BaseGlobalComponents):
    """
    Exists to be pickled by name.
    """

global_subscription_registry = GlobalSubscriptionComponents('global_subscription_registry')

@implementer(IWebhookSubscriptionManager)
class GlobalWebhookSubscriptionManager(AbstractWebhookSubscriptionManager,
                                       _CheckObjectOnSetSampleContainer,
                                       DCTimesMixin):

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


@implementer(IWebhookSubscriptionManager)
class PersistentWebhookSubscriptionManager(AbstractWebhookSubscriptionManager,
                                           PersistentDCTimesMixin,
                                           _CheckObjectOnSetBTreeContainer):

    def __init__(self):
        super(PersistentWebhookSubscriptionManager, self).__init__()
        self.registry = self._make_registry()

    def _make_registry(self):
        return PersistentComponents()

    def _new_Subscription(self, **kwargs):
        return PersistentSubscription(**kwargs)

# The name string must match the variable name to pickle correctly
global_subscription_manager = GlobalWebhookSubscriptionManager('global_subscription_manager')

def getGlobalSubscriptionManager():
    return global_subscription_manager

def resetGlobals():
    global_subscription_manager.__dict__.clear()
    global_subscription_manager.__init__('global_subscription_manager')
    global_subscription_registry.__init__('global_subscription_registry')

try:
    from zope.testing.cleanup import addCleanUp # pylint:disable=ungrouped-imports
except ImportError: # pragma: no cover
    pass
else:
    addCleanUp(resetGlobals)
    del addCleanUp
