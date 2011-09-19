#!/usr/bin/env python
"""
[**SockJS-protocol**](https://github.com/majek/sockjs-protocol) is an
effort to define a protocol between in-browser
[SockJS-client](https://github.com/majek/sockjs-client) and its
server-side counterparts, like
[SockJS-node](https://github.com/majek/sockjs-client). This should
help others to write alternative server implementations.


This protocol definition is also a runnable test suite, do run it
against your server implementation. Supporting all the tests doesn't
guarantee that SockJS client will work flawlessly, end-to-end tests
using real browsers are always required.
"""
import re
import unittest2 as unittest
from utils import GET, POST, POST_async
import uuid


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

To run this tests server pointed by `base_url` needs to support
following services:

 - `echo` - responds with identical data as received
 - `disabled_websocket_echo` - identical to `echo`, but with websockets disabled
 - `close` - server immediately closes the session

This tests should not be run more often than once in five seconds -
many tests operate on the same (named) sessions and they need to have
enough time to timeout.
"""
test_top_url = 'http://localhost:8080'
base_url = test_top_url + '/echo'
close_base_url = test_top_url + '/close'


# Static URLs
# ===========

class Test(unittest.TestCase):
    # We are going to test several `404/not found` pages. They should
    # have no body and no content-type.
    def verify404(self, r):
        self.assertEqual(r.status, 404)
        self.assertFalse(r['content-type'])
        self.assertFalse(r.body)

    # In some cases `405/method not allowed` is more appropriate.
    def verify405(self, r):
        self.assertEqual(r.status, 405)
        self.assertFalse(r['content-type'])
        self.assertFalse(r.body)

# Greeting url: `/`
# ----------------
class BaseUrlGreeting(Test):
    # The most important part of the url scheme, is without doubt, the
    # top url. Make sure the greeting is valid.
    def test_greeting(self):
        r = GET(base_url)
        self.assertEqual(r.status, 200)
        self.assertEqual(r['content-type'], 'text/plain; charset=UTF-8')
        self.assertEqual(r.body, 'Welcome to SockJS!\n')

    # Other simple requests should return 404.
    def test_notFound(self):
        for suffix in ['/a', '/a.html', '//', '///', '/a/a', '/a/a/', '/a',
                       '/a/']:
            self.verify404(GET(base_url + suffix))


"""
IFrame page: `/iframe*.html`
----------------------------
"""
class IframePage(Test):
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
                       '/iframe.HTML', '/iframe.xml', '/iframe-/.html']:
            r = GET(base_url + suffix)
            self.verify404(r)

    # The '/iframe.html' page and its variants must give `200/ok` and be
    # served with 'text/html' content type.
    def verify(self, url):
        r = GET(url)
        self.assertEqual(r.status, 200)
        self.assertEqual(r['content-type'], 'text/html; charset=UTF-8')
        # The iframe page must be strongly cacheable, supply
        # Cache-Control, Expires and Etag headers and avoid
        # Last-Modified header.
        self.assertTrue(re.search('public', r['Cache-Control']))
        self.assertTrue(re.search('max-age=[1-9][0-9]{6}', r['Cache-Control']),
                        "max-age must be large, one year (31536000) is best")
        self.assertTrue(r['Expires'])
        self.assertTrue(r['ETag'])
        self.assertFalse(r['last-modified'])

        # Body must be exactly as specified, with the exception of
        # `sockjs_url`, which should be configurable.
        match = self.iframe_body.match(r.body.strip())
        self.assertTrue(match)
        # `Sockjs_url` must be a valid url and should utilize caching.
        sockjs_url = match.group('sockjs_url')
        self.assertTrue(sockjs_url.startswith('/') or
                        sockjs_url.startswith('http'))
        return r


    # The iframe page must be strongly cacheable. ETag headers must
    # not change too often. Server must support 'if-none-match'
    # requests.
    def test_cacheability(self):
        r1 = GET(base_url + '/iframe.html')
        r2 = GET(base_url + '/iframe.html')
        self.assertEqual(r1['etag'], r2['etag'])

        r = GET(base_url + '/iframe.html', {'If-None-Match': r1['etag']})
        self.assertEqual(r.status, 304)
        self.assertFalse(r['content-type'])
        self.assertFalse(r.body)


# Session URLs
# ============

# Top session URL: `/<server>/<session>`
# --------------------------------------
#
# The session between the client and the server is always initialized
# by the client. The client chooses `server_id`, which should be a
# three digit number: 000 to 999. It can be supplied by user or
# randomly generated. The main reason for this parameter is to make it
# easier to configure load balancer - and enable sticky sessions based
# on first part of the url.
#
# Second parameter `session_id` must be a random string, unique for
# every session.
#
# A session is identified by only `session_id`. `server_id` is a
# parameter for load balancer and can be safely ignored by the server.
#
# It is undefined what happens when two clients share the same
# `session_id`. It is a client responsibility to choose identifier
# with enough entropy.
class SessionURLs(Test):

    # The server must accept any value in `server` and `session` fields.
    def test_anyValue(self):
        self.verify('/a/a')
        for session_part in ['/_/_', '/1/1', '/abcdefgh_i-j%20/abcdefg_i-j%20']:
            self.verify(session_part)

    # To test session URLs we're going to use `xhr-polling` transport
    # facilitites.
    def verify(self, session_part):
        r = POST(base_url + session_part + '/xhr')
        self.assertEqual(r.body, 'o\n')
        self.assertEqual(r.status, 200)


    # But not an empty string, anything containing dots or paths with
    # less or more parts.
    def test_invalidPaths(self):
        for suffix in ['//', '/a./a', '/a/a.', '/./.' ,'/', '///']:
            self.verify404(GET(base_url + suffix + '/xhr'))
            self.verify405(POST(base_url + suffix + '/xhr'))

# Protocol and framing
# --------------------
#
# SockJS tries to stay API-compatible with WebSockets, but not on the
# network layer. For technical reasons SockJS must introduce custom
# framing and simple custom protocol.
#
# To explain the protocol we'll use `xhr-polling` transport
# facilitites.
class Protocol(Test):
    # When server receives a request with unknown `session_id` it must
    # recognize that as request for a new session. When server opens a
    # new sesion it must immediately send an frame containing a letter
    # `o`.
    def test_simpleSession(self):
        trans_url = base_url + '/000/' + str(uuid.uuid4())
        r = POST(trans_url + '/xhr')
        "New line is a frame delimiter specific for xhr-polling"
        self.assertEqual(r.body, 'o\n')
        self.assertEqual(r.status, 200)

        # After a session was established the server needs to accept
        # requests for sending messages.
        "Xhr-polling accepts messages as a list of JSON-encoded strings."
        payload = '["a"]'
        r = POST(trans_url + '/xhr_send', body=payload)
        self.assertFalse(r.body)
        self.assertEqual(r.status, 204)

        "We're using echo service - we can receive our message"
        r = POST(trans_url + '/xhr')
        self.assertEqual(r.body, 'm"a"\n')
        self.assertEqual(r.status, 200)

        # Sending messages to not existing sessions is invalid.
        payload = '["a"]'
        r = POST(base_url + '/000/bad_session/xhr_send', body=payload)
        self.assertFalse(r.body)
        self.assertEqual(r.status, 404)

        # The session must time out after 5 seconds of not having a
        # receiving connection. The server must send a heartbeat frame
        # every 25 seconds. The heartbeat frame contains a single `h`
        # character. This delays may be configurable.
        pass
        # The server may not allow two receiving connections to wait
        # on a single session. In such case the server must send a
        # close frame to the new connection.
        r1 = POST_async(trans_url + '/xhr')
        r2 = POST(trans_url + '/xhr')
        r1.close()
        self.assertEqual(r2.body, 'c[2010,"Another connection still open"]\n')
        self.assertEqual(r2.status, 200)

    # The server may terminate the connection, passing error code and
    # message.
    def test_closeSession(self):
        trans_url = close_base_url + '/000/' + str(uuid.uuid4())
        POST(trans_url + '/xhr')
        r = POST(trans_url + '/xhr')
        self.assertEqual(r.body, 'c[3000,"Go away!"]\n')
        self.assertEqual(r.status, 200)

        # Until the timeout occurs, the server must constantly serve
        # the close message.
        r = POST(trans_url + '/xhr')
        self.assertEqual(r.body, 'c[3000,"Go away!"]\n')
        self.assertEqual(r.status, 200)


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

