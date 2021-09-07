=========
 Changes
=========

0.0.6 (2021-09-07)
==================

- Make subscriptions, delivery attempts, delivery attempt requests,
  and delivery attempt responses have a ``mimeType`` value when
  externalized.

0.0.5 (2020-12-04)
==================

- Add support for Python 3.9.

- Principal IDs are no longer required to be URIs or dotted names. See
  `issue 21 <https://github.com/NextThought/nti.webhooks/issues/21>`_.

0.0.4 (2020-09-16)
==================

- Use a custom ``ITraverser`` when finding sites to install persistent
  ZCML subscriptions in. This traverser fires ``IBeforeTraverseEvent``
  notifications, letting subscribers to that (such as
  ``nti.site.subscribers.threadSiteSubscriber``) take action (such as
  making sites current when they're about to be traversed). This can
  help when the site path contains namespaces.


0.0.3 (2020-08-24)
==================

- Move permission definition to a separate file, ``permissions.zcml``,
  that is included by default. Use the ZCML ``<exclude>`` directive
  before including this package's configuration if you were
  experiencing configuration conflicts.


0.0.2 (2020-08-06)
==================

- Add a subscriber and methods to remove subscriptions when principals
  are deleted. See `PR 17
  <https://github.com/NextThought/nti.webhooks/pull/17>`_.


0.0.1 (2020-08-05)
==================

- Initial PyPI release.
