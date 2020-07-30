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

from transaction import TransactionManager

from zope import interface
from zope import component
from zope.traversing import api as ztapi

from zope.processlifetime import IDatabaseOpened
from zope.generations.interfaces import IInstallableSchemaManager

from nti.webhooks.api import subscribe_in_site_manager

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


@interface.implementer(IPersistentWebhookSchemaManager)
class PersistentWebhookSchemaManager(object):

    key = 'nti.webhooks.generations.PersistentWebhookSchemaManager'
    utility_name = 'zzzz-nti.webhooks'

    def __init__(self):
        self.__generation = None
        self.__subscription_accumulator = []

    def evolve(self, context, generation):
        pass

    def install(self, context):
        conn = context.connection
        root = conn.root()
        # Save what we're doing
        subs = tuple(sorted(self.__subscription_accumulator))
        conn.root()[self.key] = (subs, self.generation)

        for site_path, sub_kwargs in subs:
            # The path argument must be absolute.
            assert site_path.startswith(u'/')
            # However, an absolute path wants to convert
            # the context argument (connection.root()) into
            # an ILocationInfo object so it can ask it what its root is.
            # That can't be done, by default. We could either provide an adapter
            # or a proxy, or we can just make the path non-absolute here, since
            # we're starting from the database root.
            site_path = site_path[1:]
            sub_kwargs = dict(sub_kwargs)
            site = ztapi.traverse(root, site_path)
            site_manager = site.getSiteManager()
            subscribe_in_site_manager(site_manager, **sub_kwargs)

        # End by resetting the accumulated subscriptions. We should only be
        # installed/evolved once per execution. This should only affect tests that
        # don't tear down zope.component fully between runs.
        self.__subscription_accumulator = []

    @property
    def generation(self):
        return self.__generation

    minimum_generation = generation

    def addSubscription(self, site_path, subscription_kwargs):
        self.__subscription_accumulator.append(
            (site_path, sorted(subscription_kwargs.items()))
        )

    def compareSubscriptionsAndComputeGeneration(self, stored_subscriptions, stored_generation):
        # re-sort, just in case sort order changed
        stored_subscriptions = tuple(sorted(stored_subscriptions))
        accum_subscriptions = tuple(sorted(self.__subscription_accumulator))
        if stored_subscriptions == accum_subscriptions:
            self.__generation = stored_generation
        else:
            self.__generation = stored_generation + 1


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
        subscriptions, generation = conn.root().get(PersistentWebhookSchemaManager.key, ([], 0))
        txm.abort()

    schema = get_schema_manager()
    schema.compareSubscriptionsAndComputeGeneration(subscriptions, generation)
