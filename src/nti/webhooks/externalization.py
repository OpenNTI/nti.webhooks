# -*- coding: utf-8 -*-
"""
Externalization support.

This includes helpers for the objects defined in this
package, as well as general helpers for other packages.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from nti.externalization.interfaces import ExternalizationPolicy

__all__ = [
    'ISSDateExternalizationPolicy',
]

#: An externalization policy that uses ISO 8601 date strings.
ISODateExternalizationPolicy = ExternalizationPolicy(
    use_iso8601_for_unix_timestamp=True
)
