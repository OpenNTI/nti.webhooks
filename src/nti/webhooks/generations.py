# -*- coding: utf-8 -*-
"""
Internal API only, not for public consumption.

    - We have an IInstallableSchemaManager global utility. ZCML
      directives register their arguments with this utility.

    - An AfterDatabaseOpened handler reads data from the root of the
      database about what is currently installed and calculates the
      difference.

      This information is used to calculate the generation we should use for
      the schema manager. It needs to handle initial installation of
      everything as well as adding and removing.

    - When AfterDatabaseOpenedWithRoot fires, our schema manager,
      which should be named so as to sort near the end, runs and
      performs required changes, recording what is actually installed
      in the root of the database.

While this might seem limited to one application or root per database,
it shouldn't be. The ZCML directives will include the full traversable
path to a site manager, starting from the root.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import difflib
import functools

from transaction import TransactionManager

from zope import interface
from zope import component
from zope.traversing import api as ztapi

from zope.processlifetime import IDatabaseOpened
from zope.generations.interfaces import IInstallableSchemaManager

from nti.webhooks.interfaces import IWebhookSubscriptionManager
from nti.webhooks.api import subscribe_in_site_manager

logger = __import__('logging').getLogger(__name__)

class IPersistentWebhookSchemaManager(IInstallableSchemaManager):
    """
    Interface to identify the nti.webhook schema manager.
    """

    # pylint:disable=no-self-argument

    def addSubscription(site_path, subscription_kwargs):
        """
        Record details about a subscription that should exist.
        """

    def compareSubscriptionsAndComputeGeneration(stored_subscriptions, stored_generation):
        """
        Given the subscription information previously stored, determine if
        we need a new generation.
        """

@functools.total_ordering
class SubscriptionDescriptor(object):

    def __init__(self, site_path, subscription_kwargs):
        # Site path must be absolute
        assert site_path.startswith('/')
        self.site_path = site_path
        self._subscription_kwargs = tuple(sorted(subscription_kwargs.items()))

    def find_site(self, root):
        # However, an absolute path wants to convert
        # the context argument (connection.root()) into
        # an ILocationInfo object so it can ask it what its root is.
        # That can't be done, by default. We could either provide an adapter
        # or a proxy, or we can just make the path non-absolute here, since
        # we're starting from the database root.
        site_path = self.site_path[1:]
        return ztapi.traverse(root, site_path)

    @property
    def subscription_kwargs(self):
        return dict(self._subscription_kwargs)

    def _comparison_args(self):
        return self.site_path, self._subscription_kwargs

    def __eq__(self, other):
        me = self._comparison_args()
        try:
            them = other._comparison_args()
        except AttributeError: # pragma: no cover
            return NotImplemented
        else:
            return me == them

    def __lt__(self, other):
        me = self._comparison_args()
        try:
            them = other._comparison_args()
        except AttributeError: # pragma: no cover
            return NotImplemented
        return me < them

    def __hash__(self):
        return hash(self._comparison_args())

    def __repr__(self):
        return repr(self._comparison_args())

    def matches(self, subscription):
        return all(
            getattr(subscription, k) == v
            for k, v
            in self.subscription_kwargs.items()
        )

class State(object):
    # Not persistent, we replace each time

    generation = 0

    def __init__(self):
        self._subscription_descriptors = []

    def add_subscription_descriptor(self, site_path, subscription_kwargs):
        self._subscription_descriptors.append(SubscriptionDescriptor(site_path,
                                                                     subscription_kwargs))

    @property
    def subscription_descriptors(self):
        # Sort on demand, in case sort order changes across persistence
        return tuple(sorted(self._subscription_descriptors))

    def __eq__(self, other):
        try:
            # Using the property on purpose. We want to be
            # sorted.
            return self.subscription_descriptors == other.subscription_descriptors
        except AttributeError: # pragma: no cover
            return NotImplemented


@interface.implementer(IPersistentWebhookSchemaManager)
class PersistentWebhookSchemaManager(object):

    key = 'nti.webhooks.generations.PersistentWebhookSchemaManager'

    #: The name for the schema manager utility
    utility_name = 'zzzz-nti.webhooks'

    #: The name for the subscription manager we install in a site.
    #: This differs from the one used for dynamic subscriptions; this is
    #: what makes it possible for us to safely remove matching subscriptions without
    #: fear of overlap with a dynamic subscription.
    subscription_manager_utility_name = 'ZCMLWebhookSubscriptionManager'

    def __init__(self):
        # The state that comes from ZCML
        self._pending_state = State()
        # The state out of the database
        self._stored_state = None
        # The finalized state. Moved from self._config_state
        self._finalized_state = None

    def _save_state(self, context):
        conn = context.connection
        conn.root()[self.key] = self._finalized_state

    def install(self, context):
        self._save_state(context)
        self._update(context.connection.root(),
                     (), self._finalized_state.subscription_descriptors, ())

    def evolve(self, context, generation):
        # Opcodes describe how to turn the first argument (a) into the
        # second argument (b)
        a = self._stored_state.subscription_descriptors
        b = self._finalized_state.subscription_descriptors

        class Differ(difflib.Differ):
            # A subclass of differ that doesn't try to do intraline
            # differences, and doesn't convert the items in the sequence
            # to strings. These methods are not in the HTML documentation, but they
            # do have docstrings.
            def _dump(self, tag, x, lo, hi):
                for i in range(lo, hi):
                    yield (tag, x[i])

            def _fancy_replace(self, a, alo, ahi, b, blo, bhi):
                return self._plain_replace(a, alo, ahi, b, blo, bhi)

        diff = Differ()
        kept = []
        additions = []
        removals = []
        for tag, descriptor in diff.compare(a, b):
            if tag == ' ':
                # Nothing to do. Yay!
                kept.append(descriptor)
            elif tag == '+':
                # Something to add
                additions.append(descriptor)
            elif tag == '-':
                # Something to remove
                removals.append(descriptor)

        self._update(context.connection.root(),
                     kept, additions, removals)
        self._save_state(context)

    def _find_existing_subscription(self, descriptor, root):
        # type: (SubscriptionDescriptor, dict) -> Subscription
        # TODO: Should we gracefully handle a missing site?
        site = descriptor.find_site(root)
        site_manager = site.getSiteManager()
        manager = site_manager.getUtility(IWebhookSubscriptionManager,
                                          name=self.subscription_manager_utility_name)
        # Names aren't reliable, they can be reused.
        for sub in manager.values():
            if descriptor.matches(sub):
                return sub
        return None

    def _update(self, root, keep, add, remove):
        for descriptor in add:
            site = descriptor.find_site(root)
            site_manager = site.getSiteManager()
            subscription = subscribe_in_site_manager(
                site_manager,
                descriptor.subscription_kwargs,
                utility_name=self.subscription_manager_utility_name,
            )
            logger.info("Installed %s in %s", subscription, descriptor.site_path)

        for descriptor in remove:
            sub = self._find_existing_subscription(descriptor, root)
            if sub is None: # pragma: no cover
                logger.error("Subscription to deactivate (%s) is missing", descriptor)
                continue
            logger.info("Deactivating subscription %s", sub)
            sub.__parent__.deactivateSubscription(sub)

        for descriptor in keep:
            sub = self._find_existing_subscription(descriptor, root)
            if sub is None: # pragma: no cover
                logger.error("Subscription to keep (%s) is missing", descriptor)


    @property
    def generation(self):
        return self._finalized_state.generation

    minimum_generation = generation

    def addSubscription(self, site_path, subscription_kwargs):
        self._pending_state.add_subscription_descriptor(site_path, subscription_kwargs)

    def compareSubscriptionsAndComputeGeneration(self, stored_state):
        self._stored_state = stored_state
        self._finalized_state = self._pending_state
        # End by resetting the accumulated subscriptions. We should only be
        # installed/evolved once per execution. This should only affect tests that
        # don't tear down zope.component fully between runs. We can't rely on
        # evolve or install to do this, because they may not run.
        self._pending_state = State()

        if stored_state == self._finalized_state:
            self._finalized_state.generation = stored_state.generation
        else:
            self._finalized_state.generation = stored_state.generation + 1


def get_schema_manager():
    return component.getUtility(IPersistentWebhookSchemaManager,
                                name=PersistentWebhookSchemaManager.utility_name)

@component.adapter(IDatabaseOpened)
def update_schema_manager(event):
    # Use a local transaction manager to sidestep any issues
    # with an active transaction or explicit mode.
    txm = TransactionManager(explicit=True)
    txm.begin()
    with contextlib.closing(event.database.open(txm)) as conn:
        state = conn.root().get(PersistentWebhookSchemaManager.key, State())
        txm.abort()

    schema = get_schema_manager()
    schema.compareSubscriptionsAndComputeGeneration(state)
