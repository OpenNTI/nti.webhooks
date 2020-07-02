# -*- coding: utf-8 -*-
"""
Implementations of :class:`nti.webhooks.interfaces.IWebhookDestinationValidator`

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import socket
try:
    from urllib.parse import urlsplit
except ImportError: # Py2
    from urlparse import urlsplit

from zope import interface

from nti.webhooks import interfaces

@interface.implementer(interfaces.IWebhookDestinationValidator)
class DefaultDestinationValidator(object):

    def validateTarget(self, target_url):
        parsed_url = urlsplit(target_url)
        if parsed_url.scheme != 'https':
            raise ValueError("Refusing to deliver to insecure destination")

        domain = parsed_url.netloc
        # Look it up, raise an exception if not found.
        # TODO: Caching.
        socket.getaddrinfo(domain, 'https')
