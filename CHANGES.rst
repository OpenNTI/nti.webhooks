=========
 Changes
=========

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
