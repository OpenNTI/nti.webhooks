=================
 Externalization
=================

The subscription object and the items it contains (delivery attempts
and their requests and responses) can be externalized using
:mod:`nti.externalization`.

.. note::

   Subscription managers are not currently defined for
   externalization.

.. note::

   This is uni-directional. They can be externalized, but there is no
   direct support for internalizing them (updating them from external
   data). Conceptually, the delivery attempt and what it contains is
   immutable. Other than changing its active status (which is handled
   via other means) there is no use-case for mutating a subscription
   at this time.

Externalizing a subscription externalizes all contained delivery
attempts. Since there is a strict limit on the number of attempts it
can contain, this is not expected to pose a practical problem.

Externalizing a Subscription
============================

Let's see what it looks like when we externalize a subscription.

First, we define the subscription.

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
   >>> from zope import component
   >>> from nti.webhooks import interfaces
   >>> sub_manager = component.getUtility(interfaces.IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']

We'll fill in some interesting mock data by making a few delivery
attempts, one successful and one unsuccessful. To make it slightly
easier to read, we'll provide a simple payload adapter to customize the request body.

.. doctest::

   >>> from nti.webhooks.interfaces import IWebhookPayload
   >>> from zope.interface import implementer
   >>> from zope.component import adapter
   >>> @implementer(IWebhookPayload)
   ... @adapter(object)
   ... def single_adapter(employee):
   ...    return "PAYLOAD"
   >>> component.provideAdapter(single_adapter)

Ok, now we can make the deliveries.

.. doctest::

   >>> from nti.webhooks.testing import mock_delivery_to
   >>> from nti.webhooks.testing import begin_synchronous_delivery
   >>> begin_synchronous_delivery()
   >>> from delivery_helper import deliver_some
   >>> from delivery_helper import wait_for_deliveries
   >>> mock_delivery_to('https://example.com/some/path', method='POST', status=200)
   >>> mock_delivery_to('https://example.com/some/path', method='POST', status=404)
   >>> deliver_some(note=u'/some/request/path')
   >>> deliver_some(note=u'/another/request/path')
   >>> wait_for_deliveries()

Externalizing the subscription now produces some useful data.

.. doctest::

   >>> from nti.externalization import to_external_object
   >>> from pprint import pprint
   >>> ext_subscription = to_external_object(subscription)

To make it easier to digest, we'll look at the component objects one
at a time. First, we'll look at the subscription.

.. Sigh.Some unicode key name fixup for Python 2.

.. doctest::
   :hide:

   >>> def fixup(d):
   ...    for k in (u'Class', u'CreatedTime', u'Last Modified'):
   ...       if k in d:
   ...         v = d.pop(k)
   ...         d[str(k)] = v
   ...    bad_type = unicode if str is bytes else bytes
   ...    for k, v in d.items():
   ...        if isinstance(v, bad_type):
   ...          d[k] = v = str(v)
   ...        if isinstance(k, bad_type):
   ...          del d[k]
   ...          d[str(k)] = v
   >>> fixup(ext_subscription)
   >>> for d in ext_subscription['Contents']:
   ...    fixup(d)
   ...    fixup(d['request'])
   ...    fixup(d['response'])
   ...    fixup(d['request']['headers'])
   ...    fixup(d['response']['headers'])


.. Note the four character indent in the bodies to facilitate
   copying from failed output.

.. doctest::

    >>> ext_delivery_attempts = ext_subscription.pop('Contents')
    >>> pprint(ext_subscription)
    {'Class': 'Subscription',
     'CreatedTime': ...,
     'Last Modified': ...,
     'active': True,
     'attempt_limit': 50,
     'dialect_id': None,
     'for_': 'IContentContainer',
     'owner_id': None,
     'permission_id': None,
     'status_message': 'Active',
     'to': 'https://example.com/some/path',
     'when': 'IObjectCreatedEvent'}

Then the successful attempt:

.. doctest::

    >>> pprint(ext_delivery_attempts[0])
    {'Class': 'WebhookDeliveryAttempt',
     'CreatedTime': ...,
     'Last Modified': ...,
     'message': '200 OK',
     'request': {'Class': 'WebhookDeliveryAttemptRequest',
                 'CreatedTime': ...,
                 'Last Modified': ...,
                 'body': '"PAYLOAD"',
                 'headers': {'Accept': '*/*',
                             'Accept-Encoding': 'gzip, deflate',
                             'Connection': 'keep-alive',
                             'Content-Length': '9',
                             'Content-Type': 'application/json',
                             'User-Agent': 'nti.webhooks...'},
                 'method': 'POST',
                 'url': 'https://example.com/some/path'},
     'response': {'Class': 'WebhookDeliveryAttemptResponse',
                  'CreatedTime': ...,
                  'Last Modified': ...,
                  'content': '',
                  'elapsed': 'PT0...S',
                  'headers': {'Content-Type': 'text/plain'},
                  'reason': 'OK',
                  'status_code': 200},
     'status': 'successful'}

Followed by the failed attempt:

.. doctest::

    >>> pprint(ext_delivery_attempts[1])
    {'Class': 'WebhookDeliveryAttempt',
     'CreatedTime': ...,
     'Last Modified': ...,
     'message': '404 Not Found',
     'request': {'Class': 'WebhookDeliveryAttemptRequest',
                 'CreatedTime': ...,
                 'Last Modified': ...,
                 'body': '"PAYLOAD"',
                 'headers': {'Accept': '*/*',
                             'Accept-Encoding': 'gzip, deflate',
                             'Connection': 'keep-alive',
                             'Content-Length': '9',
                             'Content-Type': 'application/json',
                             'User-Agent': 'nti.webhooks...'},
                 'method': 'POST',
                 'url': 'https://example.com/some/path'},
     'response': {'Class': 'WebhookDeliveryAttemptResponse',
                  'CreatedTime': ...,
                  'Last Modified': ...,
                  'content': '',
                  'elapsed': 'PT0...S',
                  'headers': {'Content-Type': 'text/plain'},
                  'reason': 'Not Found',
                  'status_code': 404},
     'status': 'failed'}


.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
