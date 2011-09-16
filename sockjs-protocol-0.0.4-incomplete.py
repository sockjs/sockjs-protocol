#!/usr/bin/env python
"""
[**SockJS-protocol**](https://github.com/majek/sockjs-protocol) is an
effort to define a protocol between in-browser
[SockJS-client](https://github.com/majek/sockjs-client) and its
server-side counterparts, like
[SockJS-node](https://github.com/majek/sockjs-client). This should
help others to write alternative server implementations.


This protocol definition is also a runnable test suite, do run it
against your server implementation.

"""
import re
import sys
import unittest2 as unittest
from utils import GET


# Base URL
# ========

"""
The SockJS server provides one or more SockJS services. The services
are usually exposed with a simple url prefixes, like:
`http://localhost:8000/echo` or
`http://localhost:8000/broadcast`. We'll call this kind of url a
`base_url`. There is nothing wrong with base url being more complex,
like `http://localhost:8000/a/b/c/d/echo`. Base url should
never end with a slash.

Base url is the url that needs to be supplied to the SockJS client.

All paths under base url are controlled by SockJS server and are
defined by SockJS protocol.

SockJS protocol can be using either http or https.
"""
base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080/echo'


# Static URLs
# ===========

# Greeting url: `/`
# ----------------
class BaseUrlGreeting(unittest.TestCase):
    """
    The most important part of the url scheme, is without doubt, the top
    url. Make sure the greeting is valid.
    """
    def runTest(self):
        r = GET(base_url).load()
        self.assertEqual(r.status, 200)
        self.assertEqual(r['content-type'], 'text/plain')
        self.assertEqual(r.body, 'Welcome to SockJS!\n')


"""
IFrame page: `/iframe*.html`
----------------------------
"""
class IframePage(unittest.TestCase):
    """
    Some transports don't support cross domain communication
    (CORS). In order to support them we need to do a cross-domain
    trick: on remote (server) domain we serve an simple html page,
    that loads back SockJS client javascript and is able to
    communicate with the server withing the same domain.
    """
    iframe_body = re.compile('''
^<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <script>
    document.domain = document.domain;
    _sockjs_onload = function\(\){SockJS.bootstrap_iframe\(\);};
  </script>
  <script src="(?P<sockjs_url>[^"]*)"></script>
</head>
<body>
  <h2>Don't panic!</h2>
  <p>This is a SockJS hidden iframe. It's used for cross domain magic.</p>
</body>
<html>$
'''.strip())

    # SockJS server must provide this html page.
    def test_simpleUrl(self):
        self.verify(base_url + '/iframe.html')

    # To properly utilize caching, the same content must be served
    # for request which try to version the iframe. The server may want
    # to give slightly different answer for every SockJS client
    # revision.
    def test_versionedUrl(self):
        for suffix in ['/iframe-a.html', '/iframe-.html', '/iframe-0.1.2.html',
                       '/iframe-0.1.2abc-dirty.2144.html']:
            self.verify(base_url + suffix)

    # In some circumstances (`devel` set to true) client library
    # wants to skip caching altogether. That is achieved by
    # supplying a random query string.
    def test_queriedUrl(self):
        for suffix in ['/iframe-a.html?t=1234', '/iframe-0.1.2.html?t=123414',
                       '/iframe-0.1.2abc-dirty.2144.html?t=qweqweq123']:
            self.verify(base_url + suffix)

    # Malformed urls must give 404 answer.
    def test_invalidUrl(self):
        for suffix in ['/iframe.htm', '/iframe', '/IFRAME.HTML', '/IFRAME',
                       '/iframe.HTML', '/iframe.xml']:
            r = GET(base_url + suffix).load()
            self.assertEqual(r.status, 404)
            self.assertEqual(r['content-type'], None)
            self.assertEqual(r.body, '')

    # The '/iframe.html' page and its variants must give 200/ok and be
    # served with 'text/html' content type.
    def verify(self, url):
        r = GET(url).load()
        self.assertEqual(r.status, 200)
        self.assertEqual(r['content-type'], 'text/html')
        # Body must be exactly as specified, with the exception of
        # `sockjs_url`, which should be configurable.
        match = self.iframe_body.match(r.body.strip())
        self.assertTrue(match)
        # `Sockjs_url` must look like a valid url.
        sockjs_url = match.group('sockjs_url')
        self.assertTrue(sockjs_url.startswith('/') or
                        sockjs_url.startswith('http'))



# WebSocket protocols: `/*/*/websocket`
# -------------------------------------
import websocket

# The most important feature of SockJS is to support native WebSocket
# protocol. A decent SockJS server should support at least the
# following variants:
#
#   - hixie-75 (Chrome 4, Safari 5.0.0)
#   - hixie-76/hybi-00 (Chrome 6, Safari 5.0.1)
#   - hybi-07 (Firefox 6)
#   - hybi-10 (Firefox 7, Chrome 14)
#
# This tests only check hybi-76.
class Websockets(Test):
    # The web socket...
    def test_httpMethod(self):
        pass

    def test_disabledTransport(self):
        # User should be able to disable websocket transport
        # alltogether. This is useful when load balancer doesn't
        # support websocket protocol and we need to be able to reject
        # the transport immediately. This is achieved by returning 404
        # response on websocket transport url.
        pass

    def test_invaildConnectionHeader(self):
        # Some proxies and load balancers can rewrite 'Connection'
        # header, in such case websocket handshake should be treated
        # as invalid.
        pass

# Footnote
# ========

"""
Make this script runnable.
"""
if __name__ == '__main__':
    unittest.main()
