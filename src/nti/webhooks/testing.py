# -*- coding: utf-8 -*-
"""
Helpers for testing nti.webhooks.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import responses

class UsingMocks(object):
    """
    Mocks :mod:`requests` using :mod:`responses`.

    This is similar to the context manager supplied with
    :mod:`responses`, but a little bit less ugly to use
    in doctests.

    Creating the object automatically establishes mocks. You must explicitly
    :meth:`finish` it to end the mocking.
    """


    def __init__(self, *args, **kwargs):
        self.mock = responses.RequestsMock()
        self.mock.start()
        self.add(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.mock, name)

    def finish(self):
        self.mock.stop()
