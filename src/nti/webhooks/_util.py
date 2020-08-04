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

from persistent import Persistent

from zope.exceptions import print_exception as zprint_exceptions
from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter

from nti.externalization.datetime import datetime_to_string

from nti.zodb.persistentproperty import PersistentPropertyHolder
from nti.zodb.persistentproperty import PropertyHoldingPersistent
from nti.zodb import minmax

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

def describe_class_or_specification(obj):
    """
    Simple description of a class or interface/providedBy.
    """
    return obj.__name__ if obj is not None else 'None'

class _ModifiedProperty(PropertyHoldingPersistent):
    """
    A property for the ``IDCTImes`` attribute ``modified``.

    We act like the object in question is persistent, using a
    special NumericPropertyDefaultingToZero for ``lastModified``
    and never set ``_p_changed``. If the object isn't persistent, this doesn't
    matter. If the object is persistent, that property handles the details.
    """
    __slots__ = ()

    def __get__(self, inst, cls):
        if inst is None:
            return self
        return DateTime.utcfromtimestamp(inst.lastModified)

    def __set__(self, inst, new_dt):
        inst.lastModified = dt_tuple_to_unix_ts(new_dt.utctimetuple())

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

    modified = _ModifiedProperty()


class PersistentDCTimesMixin(PersistentPropertyHolder, DCTimesMixin):
    """
    A mixin for persistent classes, to implement ``IDCTimes`` with fewer
    conflicts.
    """

    lastModified = minmax.NumericPropertyDefaultingToZero('lastModified',
                                                          minmax.NumericMaximum,
                                                          as_number=True)

    # We don't do the same for createdTime; it shouldn't change.
    # createdTime = minmax.NumericPropertyDefaultingToZero('createdTime',
    #                                                      minmax.NumericMaximum,
    #                                                      as_number=True)

    def __new__(cls, *args, **kwargs):
        if issubclass(cls, Persistent) and not issubclass(cls, PersistentPropertyHolder): # pragma: no cover
            raise TypeError("ERROR: subclassing Persistent, but not PersistentPropertyHolder", cls)
        return super(PersistentDCTimesMixin, cls).__new__(cls, *args, **kwargs)


class PartialZopeDublinCoreAdapter(DCTimesMixin,
                                   ZDCAnnotatableAdapter):
    """
    Implementation of ``zope.dublincore.interfaces.IZopeDublinCore``
    that implements the modification and creation dates using the
    underlying unix timestamps.

    You need to add ``lastModified`` to your ``omit`` argument.
    """

    def __init__(self, context):
        self.context = context
        ZDCAnnotatableAdapter.__init__(self, context)

    def __getattr__(self, name):
        return getattr(self.context, name)

    # The date properties are returned as ISO8601 strings.

    def CreationDate(self):
        return datetime_to_string(self.created).toExternalObject()

    def ModificationDate(self):
        return datetime_to_string(self.modified).toExternalObject()
