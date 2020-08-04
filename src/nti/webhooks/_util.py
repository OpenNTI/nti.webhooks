# -*- coding: utf-8 -*-
"""
Small helper functions used in multiple places.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from calendar import timegm as dt_tuple_to_unix_ts
from datetime import datetime as DateTime
import io

from zope.exceptions import print_exception as zprint_exceptions
from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter

from nti.externalization.datetime import datetime_to_string

NativeStringIO = io.StringIO if str is not bytes else io.BytesIO
text_type = type(u'')

def print_exception_to_text(exc_info):
    f = NativeStringIO()
    zprint_exceptions(exc_info[0], exc_info[1], exc_info[2],
                      file=f, with_filenames=False)
    printed = f.getvalue()
    if isinstance(printed, bytes):
        result = printed.decode('latin-1')
    else:
        result = printed
    return result


class DCTimesMixin(object):
    """
    Provides an implementation of
    ``zope.dublincore.interfaces.IDCTimes`` in terms of the
    unix-timestamps in ``createdTime`` and ``lastModified``.

    If you extend this class, and you use
    ``zope.schema.fieldproperty.createFieldProperties`` with an interface that
    includes ``IDCTimes``, then be sure to specify ``created`` and ``modified`` to the
    ``omit`` argument::

            createFieldProperties(IWebhookDeliveryAttemptRequest,
                                  omit=('created', 'modified'))
    """

    @property
    def created(self):
        return DateTime.utcfromtimestamp(self.createdTime)

    @created.setter
    def created(self, new_dt):
        self.createdTime = dt_tuple_to_unix_ts(new_dt.utctimetuple())

    @property
    def modified(self):
        return DateTime.utcfromtimestamp(self.lastModified)

    @modified.setter
    def modified(self, new_dt):
        self.lastModified = dt_tuple_to_unix_ts(new_dt.utctimetuple())


class PartialZopeDublinCoreAdapter(DCTimesMixin,
                                   ZDCAnnotatableAdapter):
    """
    Implementation of ``zope.dublincore.interfaces.IZopeDublinCore``
    that implements the modification and creation dates using the
    underlying unix timestamps.
    """

    # The date properties are returned as ISO8601 strings.

    def CreationDate(self):
        return datetime_to_string(self.created).toExternalObject()

    def ModificationDate(self):
        return datetime_to_string(self.modified).toExternalObject()
