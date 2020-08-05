===========================
 Customizing HTTP Requests
===========================

.. currentmodule:: nti.webhooks.dialect


Once an :term:`active` subscription matches and is :term:`applicable`
for a certain combination of object and event, eventually it's time to
create the actual HTTP request (body and headers) that will be
delivered to the target URL.

This document will outline how that is done, and discuss how to
customize that process. It will use :doc:`static subscriptions
<static>` to demonstrate, but these techniques are equally relevant
for :doc:`dynamic subscriptions <dynamic>`.

Let's begin by registering an example static subscription, and
refresh our memory of what the HTTP request looks like by default.
First, the imports and creation of the static subscription; we'll use
the objects defined in ``employees.py``:

.. literalinclude:: employees.py

.. doctest::

   >>> import transaction
   >>> from zope import lifecycleevent, component
   >>> from zope.container.folder import Folder
   >>> from employees import Employee
   >>> from zope.configuration import xmlconfig
   >>> from nti.webhooks.interfaces import IWebhookSubscriptionManager
   >>> from nti.webhooks.interfaces import IWebhookDeliveryManager
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
   ...             for="employees.Employee"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)
   >>> from nti.webhooks.testing import mock_delivery_to
   >>> mock_delivery_to('https://example.com/some/path')


Next, we :term:`trigger` the subscription and wait for it to be delivered.

.. doctest::

   >>> def trigger_delivery(factory=Employee, name=u'Bob', last_modified=None):
   ...    _ = transaction.begin()
   ...    employee = factory()
   ...    employee.__name__ = name
   ...    if last_modified: employee.LastModified = last_modified
   ...    lifecycleevent.created(employee)
   ...    transaction.commit()
   ...    component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()
   >>> trigger_delivery()

Finally, we can look at what we actually sent. It's not too pretty.

.. doctest::

   >>> sub_manager = component.getUtility(IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']
   >>> attempt = subscription.pop()
   >>> attempt.response.status_code
   200
   >>> print(attempt.request.url)
   https://example.com/some/path
   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '84',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks...'}
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'employees.Employee'>"}


Customizing The Body
====================

There are a few different ways to customize the body, and they can be
applied at the same time.

The first way to customize the body is to register an adapter
producing an :class:`~nti.webhooks.interfaces.IWebhookPayload`. The
adapter can be an adapter for just the object, or it can be a
multi-adapter from the object and the event that triggered the
subscription. By default, both an adapter named
:attr:`.DefaultWebhookDialect.externalizer_name` and the unnamed
adapter are attempted. When such an adapter is found, its value is
externalized instead of the target of the event.

.. note::

   While a single adapter is frequently enough, multi-adapters are allowed
   in case the context of the event matters. For example, one might wish to
   externalize something different when an object is created versus when it is
   modified or deleted.

.. important::

   The security checks described in :doc:`security` apply to the object of the
   triggering event, *not* the adapted value.

Single Adapters
---------------

Working from lowest priority to highest priority, let's demonstrate some adapters.

First, an adapter for a single object with no name.

.. doctest::

   >>> from zope.interface import implementer
   >>> from zope.component import adapter
   >>> from nti.webhooks.interfaces import IWebhookPayload
   >>> @implementer(IWebhookPayload)
   ... @adapter(Employee)
   ... def single_adapter(employee):
   ...    return employee.__name__
   >>> component.provideAdapter(single_adapter)

Triggering the event now produces a different body.

.. doctest::

   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "Bob"
   >>> trigger_delivery(name=u'Susan')
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "Susan"

Higher priority is a named adapter.

.. doctest::

   >>> from zope.component import named
   >>> @implementer(IWebhookPayload)
   ... @adapter(Employee)
   ... @named("webhook-delivery")
   ... def named_single_adapter(folder):
   ...     return "An Employee"
   >>> component.provideAdapter(named_single_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "An Employee"

Of course, if the object already provides ``IWebhookPayload``,
then it is returned directly without using those adapters.

.. doctest::

   >>> @implementer(IWebhookPayload)
   ... class PayloadFactory(Employee):
   ...    """An employee that is its own payload."""
   >>> trigger_delivery(factory=PayloadFactory)
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'PayloadFactory'>"}

Multi-adapters
--------------

Multi-adapters are the highest priority. They take precedence over the object itself
being a ``IWebhookPayload`` already.

The unnamed adapter for the event and the object is higher priority than the named single
adapter or the object itself.

.. doctest::

   >>> from zope.lifecycleevent.interfaces import IObjectCreatedEvent
   >>> @implementer(IWebhookPayload)
   ... @adapter(Employee, IObjectCreatedEvent)
   ... def multi_adapter(employee, event):
   ...    return "employee-and-event"
   >>> component.provideAdapter(multi_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "employee-and-event"

Finally, the highest priority is a named multi-adapter.

.. doctest::

   >>> from zope.lifecycleevent.interfaces import IObjectCreatedEvent
   >>> @implementer(IWebhookPayload)
   ... @adapter(Employee, IObjectCreatedEvent)
   ... @named("webhook-delivery")
   ... def named_multi_adapter(employee, event):
   ...    return "named-employee-and-event"
   >>> component.provideAdapter(named_multi_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "named-employee-and-event"


Cleanup
-------

Let's remove all those adapters and get back to a base state.

.. doctest::

   >>> gsm = component.getGlobalSiteManager()
   >>> gsm.unregisterAdapter(named_multi_adapter, name=named_multi_adapter.__component_name__)
   True
   >>> gsm.unregisterAdapter(multi_adapter)
   True
   >>> gsm.unregisterAdapter(named_single_adapter, name=named_single_adapter.__component_name__)
   True
   >>> gsm.unregisterAdapter(single_adapter)
   True

Webhook Dialects
================

Another way to customize the body, and much more, is to write a
:term:`dialect`. Every subscription is associated, by name, with a
dialect. Dialects are registered utilities that implement
:class:`nti.webhooks.interfaces.IWebhookDialect`; there is a global
default (the empty name, '') dialect implemented in
:class:`.DefaultWebhookDialect`. When defining new dialects, you
should extend this class. In fact, the behaviour defined above is
implemented by this class in its
:meth:`.DefaultWebhookDialect.produce_payload` method.

.. important::

   Dialects must not be persistent objects. They may be used outside
   of contexts where ZODB is available.

.. note::

   Much of what is done next with custom code can also be done with
   ZCML. See :ref:`zcmldialect` for details.

Setting the Body
----------------

One easy way to customize the body is to use named externalizers. The
default dialect uses an externalizer with the name given in
:attr:`~.DefaultWebhookDialect.externalizer_name`; a subclass can
change this by setting it on the class object. We'll demonstrate by
first defining and registering a
:mod:`IInternalObjectExternalizer <nti.externalization.interfaces>` with a custom name.

.. doctest::

   >>> from nti.externalization.interfaces import IInternalObjectExternalizer
   >>> from nti.externalization import to_standard_external_dictionary
   >>> @implementer(IInternalObjectExternalizer)
   ... @adapter(Employee)
   ... @named('webhook-testing')
   ... class EmployeeExternalizer(object):
   ...     def __init__(self, context):
   ...         self.context = context
   ...     def toExternalObject(self, **kwargs):
   ...         std = to_standard_external_dictionary(self.context, **kwargs)
   ...         std['Class'] = 'Employee'
   ...         std['Name'] = self.context.__name__
   ...         return std
   >>> component.provideAdapter(EmployeeExternalizer)

Next, we'll create a dialect that uses this externalizer, and register it:

.. doctest::

   >>> from nti.webhooks.dialect import DefaultWebhookDialect
   >>> @named('webhook-testing')
   ... class TestDialect(DefaultWebhookDialect):
   ...     externalizer_name = 'webhook-testing'
   >>> component.provideUtility(TestDialect())

We then alter the subscription to use this dialect:

.. doctest::

   >>> subscription.dialect_id = 'webhook-testing'

Now when we trigger the subscription, we use this externalizer:

.. doctest::

   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "Employee", "Name": "Bob"}


.. rubric:: Customizing the Body With Externalization Policies

Making smaller tweaks can be accomplished by adjusting the
externalization policy that's used. By default, the externalization
policy, named in
:attr:`~.DefaultWebhookDialect.externalizer_policy_name`, produces
ISO8601 strings for values stored as Unix timestamps (seconds since
the epoch).

.. doctest::

   >>> trigger_delivery(last_modified=123456789.0)
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "Employee", "Last Modified": "1973-11-29T21:33:09Z", "Name": "Bob"}

The best way to adjust this is to set the ``externalizer_policy_name``
to a different value. A unicode string should refere to a registered
externalization policy component. If we set it to ``None``, the
default policy (which outputs the timestamps as numbers) is used.

.. doctest::

   >>> TestDialect.externalizer_policy_name = None
   >>> trigger_delivery(last_modified=123456789.0)
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "Employee", "Last Modified": 123456789.0, "Name": "Bob"}


Setting Headers
---------------

The dialect is also responsible for customizing aspects of the HTTP request,
including headers, authentication, and the method. Our previous attempt used the
default values for these things:

.. doctest::

   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '66',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks ...'}

Lets apply some simple customizations and send again.

.. doctest::
   :hide:

   >>> mock_delivery_to('https://example.com/some/path', 'PUT')

.. doctest::

   >>> TestDialect.http_method = 'PUT'
   >>> TestDialect.user_agent = 'doctests'
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.method)
   PUT
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '36',
    'Content-Type': 'application/json',
    'User-Agent': 'doctests'}

.. _zcmldialect:

Defining A Dialect Using ZCML
-----------------------------

For the simple cases that are customizations of the strings defined by
the `DefaultWebhookDialect`, you can use a ZCML directive to define them.

.. autointerface:: nti.webhooks.zcml.IDialectDirective
   :noindex:

We can repeat the above example using just ZCML.

.. doctest::

   >>> from nti.webhooks.subscriptions import resetGlobals
   >>> resetGlobals()
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <webhooks:webhookDialect
   ...             name='zcml-dialect'
   ...             externalizer_name='webhook-testing'
   ...             externalizer_policy_name=''
   ...             http_method='PUT'
   ...             user_agent='zcml-tests' />
   ...   <webhooks:staticSubscription
   ...             dialect='zcml-dialect'
   ...             to="https://example.com/some/path"
   ...             for="employees.Employee"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)
   >>> subscription = sub_manager['Subscription']
   >>> trigger_delivery(last_modified=123456789.0)
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "Employee", "Last Modified": 123456789.0, "Name": "Bob"}
   >>> print(attempt.request.method)
   PUT
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '66',
    'Content-Type': 'application/json',
    'User-Agent': 'zcml-tests'}


.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
