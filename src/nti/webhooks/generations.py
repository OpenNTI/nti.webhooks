# -*- coding: utf-8 -*-
"""
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

from transaction import TransactionManager

from zope import interface
from zope import component

from zope.processlifetime import IDatabaseOpened
from zope.generations.interfaces import IInstallableSchemaManager

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

    def __init__(self):
        self.__generation = None
        # XXX: When can we calculate the generation we need?
        # That might have to be in an IDatabaseOpened event
        self.__subscription_accumulator = []

    def evolve(self, context, generation):
        raise Exception

    def install(self, context):
        print("Asked to install")
        raise Exception

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
        stored_subscriptions = sorted(stored_subscriptions)
        if stored_subscriptions == self.__subscription_accumulator:
            self.__generation = stored_generation
        else:
            self.__generation = stored_generation + 1
        print("Generation", self.__generation)

@component.adapter(IDatabaseOpened)
def update_schema_manager(event):
    # Use a local transaction manager to sidestep any issues
    # with an active transaction or explicit mode.
    txm = TransactionManager(explicit=True)
    txm.begin()
    conn = event.database.open(txm)
    subscriptions, generation = conn.root().get(PersistentWebhookSchemaManager.key, ([], 0))
    txm.abort()
    conn.close()

    schema = component.getUtility(IPersistentWebhookSchemaManager)
    schema.compareSubscriptionsAndComputeGeneration(subscriptions, generation)
