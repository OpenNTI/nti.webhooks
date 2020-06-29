# -*- coding: utf-8 -*-
"""
The data manager is the active core of this package.

It's responsible for integrating with the transaction machinery to
schedule the sending of data.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools
import socket

from zope import component

from zope.interface import implementer
from transaction.interfaces import IDataManager

from nti.webhooks import MessageFactory as _
from nti.webhooks.interfaces import IWebhookDialect
from nti.webhooks.attempts import PersistentWebhookDeliveryAttempt

def foreign_transaction(func):
    @functools.wraps(func)
    def dec(self, transaction):
        if self.transaction and self.transaction is not transaction:
            raise ValueError("Foreign transaction")
        func(self, transaction)

    return dec

@implementer(IDataManager)
class WebhookDataManager(object):

    transaction = None
    _voted_data = None

    def __init__(self, transaction_manager, data, event, subscriptions):
        """
        :param transaction_manager: The current ``ITransactionManager`` we are joining.
        :param subscriptions: A sequence of ``IWebhookSubscription`` objects to
           join to the transaction. More may be added later, up until the time
           the transaction begins to commit. They will be de-duplicated at the last
           possible moment. This object does not check for them being active or even applicable;
           once they are joined to the transaction, they will be delivered.
        """
        self.transaction_manager = transaction_manager
        self._subscriptions = {(data, event): list(subscriptions)}

    def add_subscriptions(self, data, event, subscriptions):
        """
        Add more subscriptions to the set managed by this object.

        Once two-phase-commit begins, this method is forbidden.

        TODO We may need a mechanism to say, if we got multiple event types for a single
        object, when and how to coalesce them. For example, given ObjectCreated and ObjectAdded
        events, we probably only want to broadcast one of them. This may be dialect specific?
        Or part of the subscription registration? A priority or 'supercedes' or something?
        For now, we just count on people not registering events that way.
        """
        if self.transaction:
            raise ValueError("Already in transaction")
        try:
            self._subscriptions[(data, event)].extend(subscriptions)
        except KeyError:
            self._subscriptions[(data, event)] = list(subscriptions)


    @foreign_transaction
    def tpc_begin(self, transaction):
        self.transaction = transaction

    @foreign_transaction
    def tpc_vote(self, transaction):
        # Be sure we can find all the dialects.
        # Note that dialects may mean different things to different subscriptions.
        all_subscriptions = []
        for v in self._subscriptions.values():
            all_subscriptions.extend(v)

        dialects = {
            sub: component.getUtility(IWebhookDialect, sub.dialect_id or u'', sub)
            for sub in all_subscriptions
        }
        # Be sure we can find host names.
        hosts = {sub.netloc for sub in all_subscriptions}
        broken_hosts = set()
        for host in hosts:
            # TODO: gevent paralleize these?
            try:
                socket.getaddrinfo(host, None)
            except socket.error:
                broken_hosts.add(host)

        # Be sure we can serialize the data for each (distinct) dialect.
        serialized_data_by_dialect = {} # (dialect, data) -> data string
        serialized_data_by_sub = [] # (subscription, dialect, serialized_data)
        for (data, _event), subscriptions in self._subscriptions.items():
            for sub in subscriptions:
                if sub.netloc in broken_hosts:
                    # Record a broken delivery
                    sub.addDeliveryAttempt(
                        PersistentWebhookDeliveryAttempt(status='failed',
                                                         message=_(u"Failed to resolve hostname")))
                    continue
                dialect = dialects[sub]
                key = (dialect, data)
                try:
                    ext_data = serialized_data_by_dialect[key]
                except KeyError:
                    # TODO: What if externalizing depends on who is getting the data?
                    # (Which I think it may; the current user sometimes comes into play)
                    # Do we need to switch out the current user? What about the pyramid request?
                    ext_data = serialized_data_by_dialect[key] = dialect.externalizeData(data)

                serialized_data_by_sub.append((sub, dialect, ext_data))

        # Now, unify the URLs. For each URL in a subscription, collect the
        # distinct set of data to send. This is per-dialect.
        all_data = {} # (url, dialect) -> ext_data
        for subscription, dialect, ext_data in serialized_data_by_sub:
            key = (subscription.to, dialect)
            if key not in all_data:
                all_data[key] = ext_data
            else:
                # TODO: This requires deterministic output from the seriaizer,
                # such as sorting keys.
                assert all_data[key] == ext_data

        # XXX: Record pending deliveries for all these subscriptions.
        # XXX: Because we're writing data here, maybe we need to happen earlier?
        # Or maybe this needs to happen in a hook? Concerned about making it properly
        # visible to ZODB connections.
        self._voted_data = all_data

    @foreign_transaction
    def tpc_finish(self, transaction):
        pass

    @foreign_transaction
    def tpc_abort(self, transaction):
        pass

    def abort(self, tranasction):
        self.transaction = None
        self._subscriptions = None

    @foreign_transaction
    def commit(self, transaction):
        pass

    def sortKey(self):
        return 'nti.webhooks.datamanager.WebhookDataManager'
