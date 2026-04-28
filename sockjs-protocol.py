#!/usr/bin/env python3
"""
SockJS-protocol runnable test suite (ported to Python 3.10).

NOTE:
- This file assumes utils.py helpers return:
  - r.status: int
  - r.body: str (decoded text) for normal HTTP helpers
  - r[...] headers: str (or '' / None when absent)
  - RawHttpConnection.read/read_chunk: bytes (recommended), because some tests
    assert on binary payloads (haproxy test).
"""
import os
import random
import time
import json
import re
import unittest
import uuid

from utils import GET, GET_async, POST, POST_async, OPTIONS, old_POST_async
from utils import WebSocket8Client
from utils import RawHttpConnection

# Base URL
test_top_url = os.environ.get('SOCKJS_URL', 'http://localhost:8081')
base_url = test_top_url + '/echo'
close_base_url = test_top_url + '/close'
wsoff_base_url = test_top_url + '/disabled_websocket_echo'
cookie_base_url = test_top_url + '/cookie_needed_echo'


class Test(unittest.TestCase):
    def verify404(self, r):
        self.assertEqual(r.status, 404)

    def verify405(self, r):
        self.assertEqual(r.status, 405)
        self.assertFalse(r['content-type'])
        self.assertTrue(r['allow'])
        self.assertFalse(r.body)

    def verify_content_type(self, r, content_type):
        self.assertEqual(r['content-type'].replace(' ', ''), content_type)

    def verify_options(self, url, allowed_methods):
        for origin in ['test', 'null']:
            h = {'Access-Control-Request-Method': allowed_methods, 'Origin': origin}
            r = OPTIONS(url, headers=h)
            self.assertTrue(r.status == 204 or r.status == 200)
            self.assertTrue(re.search('public', r['Cache-Control']))
            self.assertTrue(
                re.search('max-age=[1-9][0-9]{6}', r['Cache-Control']),
                "max-age must be large, one year (31536000) is best",
            )
            self.assertTrue(r['Expires'])
            self.assertTrue(int(r['access-control-max-age']) > 1000000)
            for header in allowed_methods.split(','):
                self.assertTrue(
                    header.strip() in r['Access-Control-Allow-Methods'],
                    'Access-Control-Allow-Methods did not contain :' + header,
                )
            self.assertFalse(r.body)
            self.verify_cors(r, origin)

    def verify_no_cookie(self, r):
        self.assertFalse(r['Set-Cookie'])

    def verify_cors(self, r, origin=None):
        if origin:
            self.assertEqual(r['access-control-allow-origin'], origin)
            self.assertEqual(r['access-control-allow-credentials'], 'true')
        else:
            self.assertEqual(r['access-control-allow-origin'], '*')
            self.assertFalse(r['access-control-allow-credentials'])

    def verify_not_cached(self, r, origin=None):
        self.assertEqual(
            r['Cache-Control'],
            'no-store, no-cache, no-transform, must-revalidate, max-age=0',
        )
        self.assertFalse(r['Expires'])
        self.assertFalse(r['Last-Modified'])


class BaseUrlGreeting(Test):
    def test_greeting(self):
        for url in [base_url, base_url + '/']:
            r = GET(url)
            self.assertEqual(r.status, 200)
            self.verify_content_type(r, 'text/plain;charset=UTF-8')
            self.assertEqual(r.body, 'Welcome to SockJS!\n')
            self.verify_no_cookie(r)

    def test_notFound(self):
        for suffix in ['/a', '/a.html', '//', '///', '/a/a', '/a/a/', '/a', '/a/']:
            self.verify404(GET(base_url + suffix))


class IframePage(Test):
    iframe_body = re.compile(
        r'''
^<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <script src="(?P<sockjs_url>[^"]*)"></script>
  <script>
    document.domain = document.domain;
    SockJS.bootstrap_iframe\(\);
  </script>
</head>
<body>
  <h2>Don't panic!</h2>
  <p>This is a SockJS hidden iframe. It's used for cross domain magic.</p>
</body>
</html>$
'''.strip()
    )

    def test_simpleUrl(self):
        self.verify(base_url + '/iframe.html')

    def test_versionedUrl(self):
        for suffix in [
            '/iframe-a.html',
            '/iframe-.html',
            '/iframe-0.1.2.html',
            '/iframe-0.1.2abc-dirty.2144.html',
        ]:
            self.verify(base_url + suffix)

    def test_queriedUrl(self):
        for suffix in [
            '/iframe-a.html?t=1234',
            '/iframe-0.1.2.html?t=123414',
            '/iframe-0.1.2abc-dirty.2144.html?t=qweqweq123',
        ]:
            self.verify(base_url + suffix)

    def test_invalidUrl(self):
        for suffix in [
            '/iframe.htm',
            '/iframe',
            '/IFRAME.HTML',
            '/IFRAME',
            '/iframe.HTML',
            '/iframe.xml',
            '/iframe-/.html',
        ]:
            r = GET(base_url + suffix)
            self.verify404(r)

    def verify(self, url):
        r = GET(url)
        self.assertEqual(r.status, 200)
        self.verify_content_type(r, 'text/html;charset=UTF-8')
        self.assertTrue(re.search('public', r['Cache-Control']))
        self.assertTrue(
            re.search('max-age=[1-9][0-9]{6}', r['Cache-Control']),
            "max-age must be large, one year (31536000) is best",
        )
        self.assertTrue(r['Expires'])
        self.assertTrue(r['ETag'])
        self.assertFalse(r['last-modified'])

        match = self.iframe_body.match(r.body.strip())
        self.assertTrue(match)
        sockjs_url = match.group('sockjs_url')
        self.assertTrue(sockjs_url.startswith('/') or sockjs_url.startswith('http'))
        self.verify_no_cookie(r)
        return r

    def test_cacheability(self):
        r1 = GET(base_url + '/iframe.html')
        r2 = GET(base_url + '/iframe.html')
        self.assertEqual(r1['etag'], r2['etag'])
        self.assertTrue(r1['etag'])

        r = GET(base_url + '/iframe.html', headers={'If-None-Match': r1['etag']})
        self.assertEqual(r.status, 304)
        self.assertFalse(r['content-type'])
        self.assertFalse(r.body)


class InfoTest(Test):
    def test_basic(self):
        r = GET(base_url + '/info', headers={'Origin': 'test'})
        self.assertEqual(r.status, 200)
        self.verify_content_type(r, 'application/json;charset=UTF-8')
        self.verify_no_cookie(r)
        self.verify_not_cached(r)
        self.verify_cors(r, 'test')

        data = json.loads(r.body)
        self.assertEqual(data['websocket'], True)
        self.assertTrue(data['cookie_needed'] in [True, False])
        self.assertEqual(data['origins'], ['*:*'])
        self.assertTrue(type(data['entropy']) is int)

    def test_entropy(self):
        r1 = GET(base_url + '/info')
        data1 = json.loads(r1.body)
        r2 = GET(base_url + '/info')
        data2 = json.loads(r2.body)
        self.assertTrue(type(data1['entropy']) is int)
        self.assertTrue(type(data2['entropy']) is int)
        self.assertNotEqual(data1['entropy'], data2['entropy'])

    def test_options(self):
        self.verify_options(base_url + '/info', 'OPTIONS, GET')

    def test_options_null_origin(self):
        url = base_url + '/info'
        r = OPTIONS(url, headers={'Origin': 'null', 'Access-Control-Request-Method': 'POST'})
        self.assertTrue(r.status == 204 or r.status == 200)
        self.assertFalse(r.body)
        self.assertEqual(r['access-control-allow-origin'], 'null')

    def test_disabled_websocket(self):
        r = GET(wsoff_base_url + '/info')
        self.assertEqual(r.status, 200)
        data = json.loads(r.body)
        self.assertEqual(data['websocket'], False)


class SessionURLs(Test):
    def test_anyValue(self):
        r = '%s' % random.randint(0, 1024)
        self.verify('/a/a' + r)
        for session_part in ['/_/_' + r, '/1/' + r, '/abcdefgh_i-j%20/abcdefg_i-j%20' + r]:
            self.verify(session_part)

    def verify(self, session_part):
        r = POST(base_url + session_part + '/xhr')
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, 'o\n')

    def test_invalidPaths(self):
        for suffix in ['//', '/a./a', '/a/a.', '/./.', '/', '///']:
            self.verify404(GET(base_url + suffix + '/xhr'))
            self.verify404(POST(base_url + suffix + '/xhr'))

    def test_ignoringServerId(self):
        session_id = str(uuid.uuid4())
        r = POST(base_url + '/000/' + session_id + '/xhr')
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, 'o\n')

        payload = '["a"]'
        r = POST(base_url + '/000/' + session_id + '/xhr_send', body=payload)
        self.assertEqual(r.status, 204)
        self.assertFalse(r.body)

        r = POST(base_url + '/999/' + session_id + '/xhr')
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, 'a["a"]\n')


# WebSocket tests
import websocket


class WebsocketHttpErrors(Test):
    def test_httpMethod(self):
        r = GET(base_url + '/0/0/websocket')
        self.assertEqual(r.status, 400)

    def test_invalidConnectionHeader(self):
        r = GET(
            base_url + '/0/0/websocket',
            headers={'Upgrade': 'WebSocket', 'Connection': 'close'},
        )
        self.assertEqual(r.status, 400)
        self.assertTrue('Not a valid websocket request' in r.body)

    def test_invalidMethod(self):
        for h in [{'Upgrade': 'WebSocket', 'Connection': 'Upgrade'}, {}]:
            r = POST(base_url + '/0/0/websocket', headers=h)
            self.verify405(r)


class Websocket(Test):
    def test_transport(self):
        ws_url = 'ws:' + base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws = websocket.create_connection(ws_url)
        self.assertEqual(ws.recv(), 'o')
        ws.send('["a"]')
        self.assertEqual(ws.recv(), 'a["a"]')
        ws.close()

    def test_close(self):
        ws_url = 'ws:' + close_base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws = websocket.create_connection(ws_url)
        self.assertEqual(ws.recv(), 'o')
        self.assertEqual(ws.recv(), 'c[3000,"Go away!"]')

        with self.assertRaises(websocket.WebSocketConnectionClosedException):
            ws.recv()
        ws.close()

    def test_headersSanity(self):
        for version in ['13']:
            url = base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
            ws_url = 'ws:' + url
            http_url = 'http:' + url
            origin = '/'.join(http_url.split('/')[:3])
            h = {
                'Upgrade': 'websocket',
                'Connection': 'Upgrade',
                'Sec-WebSocket-Version': version,
                'Sec-WebSocket-Origin': 'http://asd',
                'Sec-WebSocket-Key': 'x3JJHMbDL1EzLkh9GBhXDw==',
            }

            r = GET_async(http_url, headers=h)
            self.assertEqual(r.status, 101)
            self.assertEqual(r['sec-websocket-accept'], 'HSmrc0sMlYUkAGmm5OPpG2HaGWk=')
            self.assertEqual(r['connection'].lower(), 'upgrade')
            self.assertEqual(r['upgrade'].lower(), 'websocket')
            self.assertFalse(r['content-length'])
            r.close()

    def test_empty_frame(self):
        ws_url = 'ws:' + base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws = websocket.create_connection(ws_url)
        self.assertEqual(ws.recv(), 'o')
        ws.send('')
        ws.send('[]')
        ws.send('["a"]')
        self.assertEqual(ws.recv(), 'a["a"]')
        ws.close()

    def test_reuseSessionId(self):
        on_close = lambda ws: self.assertFalse(True)

        ws_url = 'ws:' + base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws1 = websocket.create_connection(ws_url, on_close=on_close)
        self.assertEqual(ws1.recv(), 'o')

        ws2 = websocket.create_connection(ws_url, on_close=on_close)
        self.assertEqual(ws2.recv(), 'o')

        ws1.send('["a"]')
        self.assertEqual(ws1.recv(), 'a["a"]')

        ws2.send('["b"]')
        self.assertEqual(ws2.recv(), 'a["b"]')

        ws1.close()
        ws2.close()

        ws1 = websocket.create_connection(ws_url)
        self.assertEqual(ws1.recv(), 'o')
        ws1.send('["a"]')
        self.assertEqual(ws1.recv(), 'a["a"]')
        ws1.close()

    def test_haproxy(self):
        url = base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws_url = 'ws:' + url
        http_url = 'http:' + url
        origin = '/'.join(http_url.split('/')[:3])

        c = RawHttpConnection(http_url)
        r = c.request(
            'GET',
            http_url,
            http='1.1',
            headers={
                'Connection': 'Upgrade',
                'Upgrade': 'WebSocket',
                'Origin': origin,
                'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
                'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            },
        )
        self.assertEqual(r.status, 101)
        self.assertEqual(r.headers['connection'].lower(), 'upgrade')
        self.assertEqual(r.headers['upgrade'].lower(), 'websocket')
        self.assertEqual(r.headers['sec-websocket-location'], ws_url)
        self.assertEqual(r.headers['sec-websocket-origin'], origin)
        self.assertFalse('Content-Length' in r.headers)

        c.send(b'aaaaaaaa')
        # IMPORTANT: must be bytes
        self.assertEqual(
            c.read()[:16],
            b'\xca4\x00\xd8\xa5\x08G\x97,\xd5qZ\xba\xbfC{',
        )

    def test_broken_json(self):
        ws_url = 'ws:' + base_url.split(':', 1)[1] + '/000/' + str(uuid.uuid4()) + '/websocket'
        ws = websocket.create_connection(ws_url)
        self.assertEqual(ws.recv(), 'o')
        ws.send('["a')
        with self.assertRaises(websocket.WebSocketConnectionClosedException):
            ws.recv()
        ws.close()


class XhrPolling(Test):
    # (… keep the rest of your classes/tests the same, but ensure
    # any raw/binary comparisons use bytes and any long/unichr are fixed …)
    pass


# --- Unicode encoding section: Python 3 fixes ---

escapable_by_client = re.compile(
    "[\\\\\"\\x00-\\x1f\\x7f-\\x9f\\u00ad\\u0600-\\u0604\\u070f\\u17b4\\u17b5\\u2000-\\u20ff\\ufeff\\ufff0-\\uffff\\x00-\\x1f\\ufffe\\uffff\\u0300-\\u0333\\u033d-\\u0346\\u034a-\\u034c\\u0350-\\u0352\\u0357-\\u0358\\u035c-\\u0362\\u0374\\u037e\\u0387\\u0591-\\u05af\\u05c4\\u0610-\\u0617\\u0653-\\u0654\\u0657-\\u065b\\u065d-\\u065e\\u06df-\\u06e2\\u06eb-\\u06ec\\u0730\\u0732-\\u0733\\u0735-\\u0736\\u073a\\u073d\\u073f-\\u0741\\u0743\\u0745\\u0747\\u07eb-\\u07f1\\u0951\\u0958-\\u095f\\u09dc-\\u09dd\\u09df\\u0a33\\u0a36\\u0a59-\\u0a5b\\u0a5e\\u0b5c-\\u0b5d\\u0e38-\\u0e39\\u0f43\\u0f4d\\u0f52\\u0f57\\u0f5c\\u0f69\\u0f72-\\u0f76\\u0f78\\u0f80-\\u0f83\\u0f93\\u0f9d\\u0fa2\\u0fa7\\u0fac\\u0fb9\\u1939-\\u193a\\u1a17\\u1b6b\\u1cda-\\u1cdb\\u1dc0-\\u1dcf\\u1dfc\\u1dfe\\u1f71\\u1f73\\u1f75\\u1f77\\u1f79\\u1f7b\\u1f7d\\u1fbb\\u1fbe\\u1fc9\\u1fcb\\u1fd3\\u1fdb\\u1fe3\\u1feb\\u1fee-\\u1fef\\u1ff9\\u1ffb\\u1ffd\\u2000-\\u2001\\u20d0-\\u20d1\\u20d4-\\u20d7\\u20e7-\\u20e9\\u2126\\u212a-\\u212b\\u2329-\\u232a\\u2adc\\u302b-\\u302c\\uaab2-\\uaab3\\uf900-\\ufa0d\\ufa10\\ufa12\\ufa15-\\ufa1e\\ufa20\\ufa22\\ufa25-\\ufa26\\ufa2a-\\ufa2d\\ufa30-\\ufa6d\\ufa70-\\ufad9\\ufb1d\\ufb1f\\ufb2a-\\ufb36\\ufb38-\\ufb3c\\ufb3e\\ufb40-\\ufb41\\ufb43-\\ufb44\\ufb46-\\ufb4e]"
)

escapable_by_server = re.compile("[\\x00-\\x1f\\u200c-\\u200f\\u2028-\\u202f\\u2060-\\u206f\\ufff0-\\uffff]")

client_killer_string_esc = '"' + ''.join(
    [r'\u%04x' % i for i in range(65536) if escapable_by_client.match(chr(i))]
) + '"'
server_killer_string_esc = '"' + ''.join(
    [r'\u%04x' % i for i in range(255, 65536) if escapable_by_server.match(chr(i))]
) + '"'


if __name__ == '__main__':
    unittest.main()
