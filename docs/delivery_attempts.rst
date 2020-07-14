==================
 Delivery History
==================

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
subscription, and commit the transaction to send the hook.

.. doctest::

   >>> import transaction
   >>> from zope import lifecycleevent
   >>> from zope.container.folder import Folder
   >>> _ = transaction.begin()
   >>> lifecycleevent.created(Folder())
   >>> transaction.commit()

In the background, the `IWebhookDeliveryManager` is busy invoking the hook. We need to wait for it to
finish, and then we can examine our delivery attempt:

.. doctest::

   >>> from zope import component
   >>> from nti.webhooks.interfaces import IWebhookDeliveryManager
   >>> component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()

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
- Some error occurred communicating with :term:`target`. Such errors
  include (but are not limited to) failed DNS lookups and HTTP error
  responses.

It has the same ``request`` and ``response`` attributes as successful
attempts, but, depending on when the error occurred, one or both of
them may be `None`.

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

   >>> subscription.attempt_limit
   50

The limit doesn't apply to pending attempts, only to successful or
failed attempts. We can demonstrate this by switching to deferred
delivery, creating a bunch of attempts, and looking at the length.

.. doctest::

   >>> from nti.webhooks.testing import begin_deferred_delivery
   >>> begin_deferred_delivery()
   >>> for _ in range(100):
   ...   _ = transaction.begin()
   ...   lifecycleevent.created(Folder())
   ...   transaction.commit()
   >>> len(subscription)
   100
   >>> list(set(attempt.status for attempt in subscription.values()))
   ['pending']

They're all pending. Now if we deliver them, the oldest pending
attempts will be completed, and as the newer attempts complete, they
will replace them.

.. doctest::

   >>> component.getUtility(interfaces.IWebhookDeliveryManager).waitForPendingDeliveries()
   >>> len(subscription)
   50
   >>> list(set(attempt.status for attempt in subscription.values()))
   ['successful']

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
