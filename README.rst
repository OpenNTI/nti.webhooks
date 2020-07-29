==============
 nti.webhooks
==============

.. image:: https://travis-ci.org/NextThought/nti.webhooks.svg?branch=master
   :target: https://travis-ci.org/NextThought/nti.webhooks

.. image:: https://coveralls.io/repos/github/NextThought/nti.webhooks/badge.svg?branch=master
   :target: https://coveralls.io/github/NextThought/nti.webhooks?branch=master

.. image:: https://readthedocs.org/projects/ntiwebhooks/badge/?version=latest
   :target: https://ntiwebhooks.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status


This package provides the infrastructure and delivery mechanisms for a
server to support webhook delivery. For complete details and the
changelog, see the `documentation
<http://ntiwebhooks.readthedocs.io/>`_.

.. sphinx-include-begin-prelude

Webhooks
========

Webhooks are HTTPS requests from one party --- the source --- to
another party, the destination. These requests are one-way: the source
sends the request to the destination, and aside from conforming that
the request was received, takes no further action (the request's
response from the destination is irrelevant). These requests are sent
from the source to let the destination know that something has
happened: a new entity (or resource, in the REST sense) has been
created, an old one updated or deleted, etc. Such requests typically
carry a payload in the body providing information about the action
(usually the representation of the affected resource). Destinations
are identified via complete URL; destinations may expect to be
informed of events affecting one, several, or all possible types of
entities handled by the source.

This Package
============

This package is installed in a source server and manages
the registration and sending of webhooks. The registrations may be
either static, or they may be dynamic, as in the case of `REST Hooks
<http://resthooks.org>`_, where individual "subscriptions" may be
started and stopped.

This package is intended to integrate with highly event-driven
applications using `zope.event <https://zopeevent.readthedocs.io>`_,
that define their resources using `zope.interface
<https://zopeinterface.readthedocs.io>`_, manage event delivery,
resource adaptation, and dependency injection using `zope.component
<https://zopecomponent.readthedocs.io>`_, and (optionally) implement a
hierarchy of component registries using `zope.site
<https://zopesite.readthedocs.io>`_ and `nti.site
<https://ntisite.readthedocs.io>`_. Data persistence is provided
through `persistent objects <https://persistent.readthedocs.io>`_,
typically with `ZODB <https://zodb-docs.readthedocs.io>`_.

Data Model (Subscription Combinations)
--------------------------------------

One of the motivating examples of this package is integration with
`Zapier <https://zapier.com>`_ and more generally the notion of `REST
Hooks <http://resthooks.org>`_.

In this model, a configuration on a *server* (origin) that sends data
to a *target* URL when events occur is called a *subscription.*
Subscriptions are meant to include:

#. An event name (or names) the subscription includes;
#. A parent user or account relationship;
#. A target URL; and
#. Active vs inactive state.

Subscription lookup must be performant, so the user and event name
information for subscriptions should be fast to find.

Here, event names are defined to "use the noun.verb dot syntax, IE:
contact.create or lead.delete)." Using ``zope.event`` and
``zope.component,`` this translates to the pair of object type or
interface, and event type or interface. For example,
``(IContentContainer, IObjectAddedEvent).``

Zapier generates a unique target URL for each event name, so to get
created (added), modified, and deleted resources for a single type of
object there will be three different target URLs and thus three
different subscriptions. In general, there's an *N* x *M* expansion of
object types and event types to target URLs or subscriptions.

This package implements this model directly. (You can of course use
umbrella interfaces applied to multiple object or event types to send
related events to a single subscription.) Aggregating data views of
"all webhook deliveries for a type of object" or "all webhook
deliveries for a type of event" for presentation purposes could
be written, but isn't particularly natural given how its set up now.

An important outcome of this model is that there's no need for any
given HTTP request to explicitly include something that identifies the
type of event; the default dialect (see below) assume that the URL
includes everything the receiver needs for that and doesn't do
anything like add an X-NTI-EventType header or add something to the
JSON body. It can be a URL parameter or a whole different URL, doesn't
matter.

.. sphinx-include-after-prelude

Out Of Scope
============

Certain concerns are out of scope for this package (but other packages
built upon this package my provide them). These include, but are not
limited to:

- Providing a user interface for managing subscriptions.
- Providing an HTTPS API for managing subscriptions. This package
  provides the underlying data storage, but accepting parameters, etc,
  and marshaling them into the correct Python calls, is not a concern
  here.
- Providing a user interface or HTTPS API for viewing webhook audit
  logs.
- Enabling webhooks to fire only for specific objects. This package
  deals with scopes (sites) and kinds of objects, not individual instances.

In Scope/Features
=================

Certain concerns are very much in scope for this package, and this
package should provide a complete, easy to use solution that addresses
these concerns. Where necessary, if a concern cannot be addressed
directly by this package, extension points (interfaces and
``zope.component`` utilities) may be defined. These include, but are
not limited to:

- Resource Representation

  The on-the-wire form of the resources is built using
  `nti.externalization <https://ntiexternalization.readthedocs.io>`_.

  To allow customization of the external forms, a named externalizer
  is used; nti.externalization will fall back to the default
  externalizer if no externalizer of the given name is available. The
  default externalizer is named "webhook-delivery", but dialects may
  use something different.

- Alternate Webhook Dialects

  Webhooks are a general protocol and mostly interoperable. But to
  support cases where particular destinations have specific
  requirements, "dialects" are used. There is a default dialect and
  then there may be specializations of it. Each webhook subscription
  may have associated with it the name of a dialect to use. These
  dialects are found in the component registry. For example, a dialect
  may choose to use a different externalizer name such as
  "zapier-webhook-delivery".

- Transactional

  Webhooks should not be delivered if the ultimate creation or
  persistence of a resource failed. To this end, webhook delivery in
  this package is integrated with the `transaction
  <https://transaction.readthedocs.io>`_ package.

  Resources are externalized during a late phase of the transaction
  commit process; the details about the delivery are recorded and
  persisted, and only after the transaction is successfully committed
  does the HTTP request get made.

- Concurrency

  Webhook delivery and record keeping should be lightweight, and
  all actual network IO should proceed in a non-blocking fashion. This
  means that this package will spawn threads (or greenlets, using
  `gevent <http://www.gevent.org>`_.

- Error Handling/Failure Retry

  A limited amount of retry logic is provided by this package, but
  that does not extend to process boundaries. If the process hosting
  this package is killed while a delivery is pending, no automatic
  provision is made to resume delivery attempts in any other process.

  The API is present to allow that to be implemented, though.

- Auditing/Delivery History

  For each subscription, delivery attempts, status, and responses are
  stored in a ring-buffer like structure. This can be inspected to see
  if deliveries succeeded, failed, or never completed.

- Access Control on Deliveries

  Each subscription is associated with an ``IPrincipal`` that owns it.
  A request is only delivered to a subscription if the ``IPrincipal``
  that owns the subscription can access the entity, as determined by
  `zope.security <https://zopesecurity.readthedocs.io>`_.

- Access Control on Subscriptions

  While not enforced by this package, the above owner relationship
  will be used to provide role managers that grant read and read/write
  access to remove subscriptions only to the owner of the
  subscription.

  TODO: Make sure client packages can extend that to provide for admin
  access. So long as we don't DENY it should be fine.

- Hierarchy of Subscriptions

  Subscriptions are made within a particular Zope site (the closest
  enclosing site to a resource when a resource is subscribed to, or
  the currently active site otherwise). These sites may have parents.

  TODO: Work out the details of that.

  When an event is received that might result in webhook delivery,
  active subscriptions are checked for in the currently active site,
  as well as in the sites up the hierarchy of the resource itself. All
  applicable subscribers will get a delivery.

  For example, if the president of the company (an administrator)
  subscribes to "new user created" events at the global (root, base or
  "/") level, and a department head subscribes to "new user created"
  for their department ("/NOAA"), while a local office manager
  subscribes to events for their office ("/NOAA/NWS/OUN"), then
  creating a new user in the OKC office may send three deliveries, one
  to the manager, one to the secretary, and one to the president.

  .. note:: If there are identical subscribed URLs with differing permission
            requirements, then if access is granted for *any
            subscription*, the payload will be delivered.


  .. note:: While looking up both the resource and active site tree
            might seem complex, following both hierarchies is
            necessary in the event of operations that span multiple
            child sites. This is probably most common with bulk
            operations, but a simple example would be the president
            logging in to the root site, searching for and deleting
            all employees named "Bill." If one was in the OKC office
            and one was in the OUN office, the managers of both
            locations should get delivery.

- Converting From Object Events to Webhook Events

  TODO: Write me.

  This package needs to have a clear way to have client packages
  specify what events should produce webhook deliveries. The exact
  mechanism is TBD. Possibly clients are expected to use
  ``<classImplements>`` ZCML directives to apply marker interfaces? Or
  they might register a subscriber provided by this package for their
  own existing interfaces?

  We want this process, and the process of finding all active
  subscriptions, to be fast. I'm imagining something like view lookup,
  keeping active subscriptions in the various component registries?
  That doesn't work non-persistently.
