# -*- coding: utf-8 -*-
"""
Small helper functions used in multiple places.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import io
from zope.exceptions import print_exception as zprint_exceptions

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
