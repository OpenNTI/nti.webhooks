==================
 Delivery History
==================

.. testsetup::

   import logging
   logging.basicConfig(level=logging.FATAL)

.. currentmodule:: nti.webhooks.interfaces

All attempts at delivering a webhook are recorded as an object that
implements :class:`IWebhookDeliveryAttempt`.
For static subscriptions, these are only in memory on a single
machine, but :doc:`persistent, dynamic, subscriptions <dynamic>` that
record their history more durably are also possible.

Delivery always occurs as a result of committing a transaction, and
the resulting attempt object is stored in the corresponding
subscription object.

Types of Delivery Attempts
==========================

There are three types of delivery attempts: pending, unsuccessful, and
successful. A pending attempt is one that hasn't yet been resolved,
while the other two have been resolved.

Successful Delivery Attempts
----------------------------

Successful delivery attempts are the most interesting. Lets look at one of
those and describe the `IWebhookDeliveryAttempt`. We begin by
defining a subscription.

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <webhooks:staticSubscription
   ...             to="https://example.com/some/path"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)

Now we can access the subscription. Because delivery attempts are
stored in the subscription, it has a length of 0 at this time.

.. doctest::

   >>> from zope import component
   >>> from nti.webhooks import interfaces
   >>> sub_manager = component.getUtility(interfaces.IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']
   >>> len(subscription)
   0

To avoid actually trying to talk to example.com, we'll be using some mocks.

.. doctest::

   >>> from nti.webhooks.testing import mock_delivery_to
   >>> mock_delivery_to('https://example.com/some/path', method='POST', status=200)

Now we will create the object, broadcast the event to engage the
subscription, and commit the transaction to send the hook. A helper to
do that is already defined.

.. literalinclude:: delivery_helper.py

.. doctest::

   >>> from delivery_helper import deliver_some
   >>> deliver_some(note=u'/some/request/path')

In the background, the `IWebhookDeliveryManager` is busy invoking the hook. We need to wait for it to
finish, and then we can examine our delivery attempt:

.. doctest::

   >>> from delivery_helper import wait_for_deliveries
   >>> wait_for_deliveries()


Attempt Details
~~~~~~~~~~~~~~~

The subscription now has an attempt recorded in the form of an
``IWebhookDeliveryAttempt``. The attempt records some basic details,
such as the overall status, and an associated message.

.. important::

   Attempts are immutable. They are created and managed entirely by
   the system and mutation attempts are not allowed.

.. doctest::

   >>> len(subscription)
   1
   >>> attempt = subscription.pop()
   >>> from zope.interface import verify
   >>> verify.verifyObject(interfaces.IWebhookDeliveryAttempt, attempt)
   True
   >>> attempt.status
   'successful'
   >>> print(attempt.message)
   200 OK

Also attached to the attempt is some debugging information. This
information is intended for internal use and is not
:term:`externalized`. The exact details may change over time, but some
information is always present.

.. doctest::

   >>> internal_info = attempt.internal_info
   >>> internal_info.originated
   DeliveryOriginationInfo(pid=..., hostname=..., createdTime=..., transaction_note=...'/some/request/path')
   >>> internal_info.exception_history
   ()


An important attribute of the attempt is the ``request``; this
attribute (an `IWebhookDeliveryAttemptRequest`) provides information
about the HTTP request as it went on the wire.

.. doctest::

   >>> verify.verifyObject(interfaces.IWebhookDeliveryAttemptRequest, attempt.request)
   True
   >>> print(attempt.request.url)
   https://example.com/some/path
   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '94',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks ...'}
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'zope.container.folder.Folder'>"}

(If you're curious about that "NonExternalizableObject" business, then see :doc:`customizing_payloads`.)

Another important attribute is the ``response`` (an
`IWebhookDeliveryAttemptResponse`), which captures information about
the data received from the :term:`target`.

.. doctest::

   >>> verify.verifyObject(interfaces.IWebhookDeliveryAttemptResponse, attempt.response)
   True
   >>> attempt.response.status_code
   200
   >>> print(attempt.response.reason)
   OK
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.response.headers.items()})
   {'Content-Type': 'text/plain'}
   >>> print(attempt.response.content)
   <BLANKLINE>
   >>> attempt.response.elapsed
   datetime.timedelta(...)

Failed Delivery Attempts
------------------------

A delivery attempt fails when:

- The subscription was :term:`active`; and
- The subscription was :term:`applicable`; and
- Some error occurred communicating with :term:`target` (such errors
  include, but are not limited to, failed DNS lookups and HTTP error
  responses); OR
- Some error occurred handling the response from the target;
  note that in this case, the target might have processed things
  correctly.

It has the same ``request`` and ``response`` attributes as successful
attempts, but, depending on when the error occurred, one or both of
them may be `None`. Details on the reasons for the failure
may be found in the ``internal_info.exception_history``, if the HTTP
request wasn't able to complete.

We'll simulate some of these conditions using mocks. First, a failure
communicating with the remote server.

.. doctest::

   >>> from nti.webhooks.testing import http_requests_fail
   >>> with http_requests_fail():
   ...     deliver_some(note=u'this should fail remotely')
   ...     wait_for_deliveries()
   >>> len(subscription)
   1
   >>> attempt = subscription.pop()
   >>> attempt.status
   'failed'
   >>> print(attempt.message)
   Contacting the remote server experienced an unexpected error.
   >>> internal_info = attempt.internal_info
   >>> print(internal_info.originated.transaction_note)
   this should fail remotely
   >>> len(internal_info.exception_history)
   1
   >>> print(internal_info.exception_history[0])
   Traceback (most recent call last):
     Module nti.webhooks.delivery_manager...
   ...
   ...RequestException
   <BLANKLINE>

Next, a failure to process the response.

.. doctest::

   >>> from nti.webhooks.testing import processing_results_fail
   >>> with processing_results_fail():
   ...     deliver_some(note=u'this should fail locally')
   ...     wait_for_deliveries()
   >>> len(subscription)
   1
   >>> attempt = subscription.pop()
   >>> attempt.status
   'failed'
   >>> print(attempt.message)
   Unexpected error handling the response from the server.
   >>> internal_info = attempt.internal_info
   >>> print(internal_info.originated.transaction_note)
   this should fail locally
   >>> len(internal_info.exception_history)
   1
   >>> print(internal_info.exception_history[0])
   Traceback (most recent call last):
     Module nti.webhooks.delivery_manager...
   ...
   UnicodeError
   <BLANKLINE>

Pending Delivery Attempts
-------------------------

Pending delivery attempts are those scheduled for delivery
(typically). The ``request`` and ``response`` attributes will always
be `None`.


Limits On History
=================

Only a limited number of delivery attempts are stored for any given
subscription. Currently, a class (or instance!) attribute establishes
this limit, but in the future this may be changed to something more
flexible. In the future there may also be a limit of some sort
per-principal.

.. doctest::

   >>> from nti.webhooks.interfaces import ILimitedAttemptWebhookSubscription
   >>> from zope.interface import verify
   >>> verify.verifyObject(ILimitedAttemptWebhookSubscription, subscription)
   True
   >>> subscription.attempt_limit
   50
   >>> len(subscription)
   0

The limit doesn't apply to pending attempts, only to successful or
failed attempts. We can demonstrate this by switching to deferred
delivery (meaning all attempts stay pending until we wait for them),
creating a bunch of attempts, and looking at the length.

.. doctest::

   >>> from nti.webhooks.testing import begin_deferred_delivery
   >>> begin_deferred_delivery()
   >>> deliver_some(100)
   >>> len(subscription)
   100
   >>> list(set(attempt.status for attempt in subscription.values()))
   ['pending']

They're all pending. This is a good time to note that iterating the
subscription does so in the order in which attempts were added, so the
oldest attempt is first.

.. doctest::

   >>> list(subscription) == sorted(subscription)
   True
   >>> all_attempts = list(subscription.values())
   >>> sorted_attempts = sorted(all_attempts, key=lambda attempt: attempt.createdTime)
   >>> all_attempts == sorted_attempts
   True
   >>> oldest_attempt = all_attempts[0]
   >>> attempt_50 = all_attempts[50]
   >>> oldest_attempt.createdTime < attempt_50.createdTime < all_attempts[-1].createdTime
   True

Now if we deliver them, the oldest pending attempts will be completed,
and as the newer attempts complete, they will replace them.

.. doctest::

   >>> wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts = list(subscription.values())
   >>> list(set(attempt.status for attempt in all_attempts))
   ['successful']
   >>> oldest_attempt in all_attempts
   False
   >>> attempt_50 in all_attempts
   True

Automatic Deactivation on Failures
----------------------------------

If the history is completely filled up with failures, whether from
validation errors, HTTP errors, or local processing errors, the
subscription will be automatically marked inactive and future
deliveries will not be attempted until it is manually activated again.

.. note:: At this time, pending deliveries are exempted from
          inactivating the subscription. This means a sudden large
          burst of pending deliveries could be scheduled and
          delivery attempted, even if all previous deliveries have failed.

HTTP Failures
~~~~~~~~~~~~~

Here, we'll demonstrate this for HTTP failures.

.. doctest::

   >>> subscription.active
   True
   >>> print(subscription.status_message)
   Active
   >>> with http_requests_fail():
   ...     deliver_some(100, note=u'this should fail remotely')
   ...     wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts = list(subscription.values())
   >>> list(set(attempt.status for attempt in all_attempts))
   ['failed']
   >>> subscription.active
   False
   >>> print(subscription.status_message)
   Delivery suspended due to too many delivery failures.

Attempting more deliveries of course doesn't change this deactivated subscription
in any way.

.. doctest::

   >>> deliver_some(100)
   >>> wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts == list(subscription.values())
   True

Local Failures
~~~~~~~~~~~~~~

Next, we'll demonstrate the same thing for processing failures. We must first
clear and re-enable the subscription.

.. doctest::

   >>> def resetSubscription():
   ...     sub_manager.activateSubscription(subscription)
   ...     print(subscription.active)
   ...     print(subscription.status_message)
   ...     subscription.clear()
   >>> resetSubscription()
   True
   Active

With that out of the way, we can simulate processing failures, and show the same
outcome as for HTTP failures.

.. doctest::

   >>> with processing_results_fail():
   ...     deliver_some(100, note=u'this should fail locally')
   ...     wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts = list(subscription.values())
   >>> list(set(attempt.status for attempt in all_attempts))
   ['failed']
   >>> subscription.active
   False
   >>> print(subscription.status_message)
   Delivery suspended due to too many delivery failures.
   >>> deliver_some(100)
   >>> wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts == list(subscription.values())
   True

Validation Failures
~~~~~~~~~~~~~~~~~~~

Finally, the same results occur for validation failures.

.. doctest::

   >>> resetSubscription()
   True
   Active
   >>> from nti.webhooks.testing import target_validation_fails
   >>> with target_validation_fails():
   ...     deliver_some(100, note=u'this should fail validation')
   ...     wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts = list(subscription.values())
   >>> list(set(attempt.status for attempt in all_attempts))
   ['failed']
   >>> subscription.active
   False
   >>> print(subscription.status_message)
   Delivery suspended due to too many delivery failures.
   >>> deliver_some(100)
   >>> wait_for_deliveries()
   >>> len(subscription)
   50
   >>> all_attempts == list(subscription.values())
   True


.. todo:: Similar tests for repeatedly inapplicable subscriptions.

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
