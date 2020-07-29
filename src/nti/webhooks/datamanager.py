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
from collections import defaultdict

from zope import component
from zope.interface import implementer
from transaction.interfaces import IDataManager
from persistent.interfaces import IPersistent

from nti.webhooks.interfaces import IWebhookDeliveryManager

def foreign_transaction(func):
    @functools.wraps(func)
    def dec(self, transaction):
        if self.transaction and self.transaction is not transaction:
            raise ValueError("Foreign transaction")
        func(self, transaction)

    return dec

class _DataManagerState(object):
    """
    Helper to hold intermediate data for the data manager.
    """

    #: A list of ``(data, event, subscription)`` tuples.
    all_subscriptions = None

    #: A dictionary of ``{data: {dialect: external_form}}``.
    #: This is to avoid externalizing a single data object more times
    #: than needed. TODO: Add a way to let the dialect let us know if it
    #: used the event or not so we can cache more efficiently?
    _data_to_ext_dialect = None

    #: A dictionary of subscription to list of delivery attempts.
    #: This has to be a list because a single subscription may fire
    #: for many events during a single transaction.
    subscription_to_delivery_attempt = None

    #: The ``IWebhookDeliveryManagerShipmentInfo`` object, once created.
    shipment_info = None

    def __init__(self, subscription_dict):
        # TODO: This was designed before we used the event to externalize.
        # Rethink and simplify.
        all_subscriptions = defaultdict(set)
        data_to_dialects = self._data_to_ext_dialect = defaultdict(dict)
        for (data, event), subscriptions in subscription_dict.items():
            all_subscriptions[(data, event)].update(subscriptions)
            data_to_dialects[data].update({sub.dialect: None for sub in subscriptions})

        self.all_subscriptions = [
            (data, event, sub)
            for (data, event), subscriptions in all_subscriptions.items()
            for sub in subscriptions
        ]

        sub_to_payload = self.subscription_to_payloads = defaultdict(list)
        for data, event, sub in self.all_subscriptions:
            sub_to_payload[sub].append(self._ext_data(data, event, sub))

        self.subscription_to_delivery_attempt = defaultdict(list)

    def _ext_data(self, data, event, subscription):
        dialect = subscription.dialect
        result = self._data_to_ext_dialect[data][dialect]
        if result is None:
            result = self._data_to_ext_dialect[data][dialect] = dialect.externalizeData(data, event)
        return result



@implementer(IDataManager)
class WebhookDataManager(object):
    """
    Collects and manages subscriptions to deliver to.

    There should usually only be one of these joined to a transaction
    at any time. Use the class method :meth:`join_transaction` to
    accomplish this.
    """
    transaction = None
    _tpc_state = None

    @classmethod
    def join_transaction(cls, transaction_manager, data, event, subscriptions):
        """
        Add the *data*, *event* and *subscriptions* to the transaction
        being managed by the *transaction_manager*.

        If there is no data manager, one is created. Then the effect
        is the same as calling :meth:`add_subscriptions`.

        Returns the instance of this class that was either created or
        already joined to the transaction.

        :raises transaction.interfaces.NoTransaction: If the
            *transaction_manager* is operating in explicit mode, and
            has not begun a transaction.
        """
        tx = transaction_manager.get() # If not begun, this is an error.

        try:
            data_man = tx.data(cls)
        except KeyError:
            data_man = cls(transaction_manager, tx)
            tx.join(data_man)
            tx.set_data(cls, data_man)

        data_man.add_subscriptions(data, event, subscriptions)
        return data_man

    def __init__(self, transaction_manager, transaction):
        """
        :param transaction_manager: The current ``ITransactionManager`` we are joining.
        :param subscriptions: A sequence of ``IWebhookSubscription`` objects to
           join to the transaction. More may be added later, up until the time
           the transaction begins to commit. They will be de-duplicated at the last
           possible moment. This object does not check for them being active or even applicable;
           once they are joined to the transaction, they will be delivered.
        """
        self.transaction_manager = transaction_manager
        self._subscriptions = defaultdict(set)
        self._tpc_state = None
        self.transaction = transaction

    def add_subscriptions(self, data, event, subscriptions):
        """
        Add more subscriptions to the set managed by this object.

        Once two-phase-commit begins, this method is forbidden.

        TODO We may need a mechanism to say, if we got multiple event types for a single
        object, when and how to coalesce them. For example, given ObjectCreated and ObjectAdded
        events, we probably only want to broadcast one of them. This may be dialect specific?
        Or part of the subscription registration? A priority or 'supercedes' or something?
        For now, we just wind up discarding the event type and assume it's not important to the
        delivery.
        """
        # We don't enforce that you can't call this after TPC has begun.
        self._subscriptions[(data, event)].update(subscriptions)
        for subscription in subscriptions:
            # pylint:disable=protected-access
            if IPersistent.providedBy(subscription) and subscription._p_jar and subscription._p_oid:
                # See comment below for why we must do this.
                subscription._p_jar.register(subscription)


    # The sequence for two-phase-commit is
    # tpc_begin/commit/vote/finish (or abort). ZODB serializes objects
    # and sends them to the storage during ``commit()``; committing is
    # allowed to create new objects and register them with the
    # connection. ``vote()`` is used for conflict resolution. Because
    # predicting sortKeys and the order of resources is hard, we need
    # to make any modifications during ``tpc_begin()`` (*or* work with
    # objects to have them do things during their ``__getstate__()`` or
    # other pickle methods that add new objects to the connection
    # during object writing at ``commit()`` --- but that's pretty untenable).
    # This means that we need to add our attempts, and serialize all data, which
    # is recorded as part of the attempt, at ``tpc_begin()`` time.
    #
    # HOWEVER: If the Connection of an object was not previously joined
    # to the transaction, it's too late to join it in tpc_begin: The transaction
    # itself fails that ("expected txn status 'Active' but it is 'Committing'").
    # Thus mutating a persistent object can fail if creating the delivery attempt
    # is the first time an object from some connection has been mutated.
    #
    # We fix this by pre-emptively registering subscriptions with their connection,
    # which in turn registers with the transaction, as soon as they are added to this
    # data manager. Another approach would be to add a before-commit transaction hook
    # to the transaction that does the same thing.
    #
    # Another option might be to create the delivery attempt much earlier? But
    # that would forbid any attempt from coalescing events, wouldn't it.

    @foreign_transaction
    def tpc_begin(self, transaction):
        self.transaction = transaction
        self._tpc_state = state = _DataManagerState(self._subscriptions)
        for subscription, payloads in state.subscription_to_payloads.items():
            state.subscription_to_delivery_attempt[subscription].extend([
                subscription.createDeliveryAttempt(payload)
                for payload in payloads
            ])

    @foreign_transaction
    def commit(self, transaction):
        # Nothing to do here; the necessary storage bits will happen automatically.
        pass

    @foreign_transaction
    def tpc_vote(self, transaction):
        # We have nothing to vote on. If we got this far in tpc_begin without an error,
        # all the dialects were found and all the delivery attempts recorder (they will be
        # persisted too, if needed). Delivery can't stop now.
        #
        # The main thing we need to do is extract information from the persistent objects
        # so that the delivery manager doesn't have to. It's not safe to do so from
        # tpc_finish or later.
        delivery_man = component.getUtility(IWebhookDeliveryManager)
        self._tpc_state.shipment_info = delivery_man.createShipmentInfo(
            # Flatten the subscription/delivery attempt objects
            [(subscription, attempt)
             for subscription, attempts
             in self._tpc_state.subscription_to_delivery_attempt.items()
             for attempt in attempts
             if attempt.status == 'pending'
            ]
        )

    @foreign_transaction
    def tpc_finish(self, transaction):
        # Make the changes actually visible. This should never fail
        # or raise an exception.

        # What we want to do here is publish our `_tpc_state` to a global utility that's
        # responsible for actually making the webhook calls, and storing the results.
        # We need to find the persistent objects that are the delivery attempts and
        # only find them by OID when we are next in a Connection; as of now, they're no
        # good to us.
        delivery_man = component.getUtility(IWebhookDeliveryManager)
        delivery_man.acceptForDelivery(self._tpc_state.shipment_info)
        self._tpc_state = None

    @foreign_transaction
    def tpc_abort(self, transaction):
        # Called if some part of TPC failed.
        # XXX: For the non-persistent managers, we need to remove the
        # delivery attempt, because it never happened and we don't want to clog
        # up their limit on attempts.
        self.abort(transaction)

    def abort(self, tranasction):
        self.__init__(self.transaction_manager, None)

    def sortKey(self):
        return 'nti.webhooks.datamanager.WebhookDataManager'
