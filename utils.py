from urllib.parse import urlparse
import http.client as httplib
from ws4py.client.threadedclient import WebSocketClient
import queue
import socket
import re


class HttpResponse:
    def __init__(
        self, method, url, headers=None, body=None, async_=False, load=True
    ):
        headers = (headers or {}).copy()
        u = urlparse(url)
        kwargs = {'timeout': 1.0}

        if u.scheme == 'http':
            conn = httplib.HTTPConnection(u.netloc, **kwargs)
        elif u.scheme == 'https':
            conn = httplib.HTTPSConnection(u.netloc, **kwargs)
        else:
            raise AssertionError("Unsupported scheme " + u.scheme)

        assert u.fragment == ''
        path = u.path + ('?' + u.query if u.query else '')
        self.conn = conn

        if body is None or body == '' or body == b'':
            if method == 'POST':
                headers['Content-Length'] = '0'
            conn.request(method, path, headers=headers)
        else:
            if isinstance(body, str):
                body = body.encode('utf-8')
            conn.request(method, path, headers=headers, body=body)

        if load:
            if not async_:
                self._load()
            else:
                self._async_load()

    def _get_status(self):
        return self.res.status

    status = property(_get_status)

    def __getitem__(self, key):
        return self.headers.get(key.lower())

    def _load(self):
        self.res = self.conn.getresponse()
        self.headers = {
            k.lower(): v for k, v in self.res.getheaders()
        }
        self.body = self.res.read().decode('utf-8', errors='replace')
        self.close()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _async_load(self):
        self.res = self.conn.getresponse()
        self.headers = {
            k.lower(): v for k, v in self.res.getheaders()
        }

    def read(self):
        data = self.res.read(10240)
        if data:
            return data.decode('utf-8', errors='replace')
        self.close()
        return None


def old_POST_async(url, **kwargs):
    # `async` was a valid parameter name in Python 2, but is reserved in Python 3.
    kwargs.pop('async', None)
    return HttpResponse('POST', url, async_=True, **kwargs)


class WebSocket8Client(object):
    class ConnectionClosedException(Exception):
        pass

    def __init__(self, url):
        self.queue = queue.Queue()
        message_queue = self.queue

        class IntWebSocketClient(WebSocketClient):
            def received_message(self, message):
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                else:
                    message = str(message)
                message_queue.put(message)

            def closed(self, code, reason):
                message_queue.put((code, reason))

        self.client = IntWebSocketClient(url)
        self.client.connect()

    def close(self):
        if self.client:
            self.client.running = False
            self.client.close()
            self.client._th.join()
            self.client = None

    def send(self, data):
        self.client.send(data)

    def recv(self):
        try:
            result = self.queue.get(timeout=1.0)
            if isinstance(result, tuple):
                exc = self.ConnectionClosedException()
                exc.code, exc.reason = result
                raise exc
            return result
        except Exception:
            self.close()
            raise


def recvline(sock):
    data = bytearray()
    while True:
        char = sock.recv(1)
        if not char:
            return bytes(data)
        data.extend(char)
        if char == b'\n':
            return bytes(data)


class CaseInsensitiveDict(object):
    def __init__(self, *args, **kwargs):
        self.lower = {}
        self.d = dict(*args, **kwargs)
        for key in self.d:
            self[key] = self.d[key]

    def __getitem__(self, key, *args, **kwargs):
        actual_key = self.lower.setdefault(key.lower(), key)
        return self.d.__getitem__(actual_key, *args, **kwargs)

    def __setitem__(self, key, *args, **kwargs):
        actual_key = self.lower.setdefault(key.lower(), key)
        return self.d.__setitem__(actual_key, *args, **kwargs)

    def items(self):
        for key in self.lower.values():
            yield key, self[key]

    def __repr__(self):
        return repr(self.d)

    def __str__(self):
        return str(self.d)

    def get(self, key, *args, **kwargs):
        actual_key = self.lower.setdefault(key.lower(), key)
        return self.d.get(actual_key, *args, **kwargs)

    def __contains__(self, key):
        actual_key = self.lower.setdefault(key.lower(), key)
        return actual_key in self.d


class Response(object):
    def __repr__(self):
        return '<Response HTTP/%s %s %r %r>' % (
            self.http, self.status, self.description, self.headers)

    def __str__(self):
        return repr(self)

    def __getitem__(self, key):
        return self.headers.get(key)

    def get(self, key, default=None):
        return self.headers.get(key, default)


class RawHttpConnection(object):
    def __init__(self, url):
        parsed_url = urlparse(url)
        port = parsed_url.port
        if port is None:
            port = 443 if parsed_url.scheme == 'https' else 80
        self.s = socket.create_connection(
            (parsed_url.hostname, port), timeout=1
        )

    def request(self, method, url, headers=None, body=None, timeout=1, http="1.1"):
        headers = CaseInsensitiveDict(headers or {})
        parsed_url = urlparse(url)

        if method == 'POST':
            body_bytes = (body or '').encode('utf-8') if isinstance(body, str) else (body or b'')
        elif isinstance(body, str):
            body_bytes = body.encode('utf-8')
        else:
            body_bytes = body or b''

        host = parsed_url.hostname
        if parsed_url.port:
            host += ':' + str(parsed_url.port)
        headers['Host'] = host

        if body is not None:
            headers['Content-Length'] = str(len(body_bytes))

        rel_url = url[url.find(parsed_url.path):] if parsed_url.path else '/'
        request_lines = ["%s %s HTTP/%s" % (method, rel_url, http)]
        for key, value in headers.items():
            request_lines.append("%s: %s" % (key, value))
        request_lines.extend(['', ''])
        self.send('\r\n'.join(request_lines))

        if body_bytes:
            self.send(body_bytes)

        head = recvline(self.s).decode('iso-8859-1')
        match = re.match(
            r'HTTP/(?P<version>\S+) (?P<status>\S+) (?P<description>.*)',
            head
        )
        if not match:
            raise Exception('Invalid HTTP response line: %r' % head)

        response = Response()
        response.http = match.group('version')
        response.status = int(match.group('status'))
        response.description = match.group('description').rstrip('\r\n')

        response.headers = CaseInsensitiveDict()
        while True:
            header = recvline(self.s)
            if header in (b'\n', b'\r\n', b''):
                break
            key, _, value = header.decode('iso-8859-1').partition(':')
            response.headers[key] = value.lstrip().rstrip('\r\n')

        return response

    def read_bytes(self, size=None):
        if size is None:
            return self.s.recv(999999)

        data = bytearray()
        while size > 0:
            chunk = self.s.recv(size)
            if not chunk:
                raise Exception('Socket closed!')
            size -= len(chunk)
            data.extend(chunk)
        return bytes(data)

    def read(self, size=None):
        data = self.read_bytes(size)
        return data.decode('utf-8', errors='replace')

    def read_till_eof(self):
        data = bytearray()
        while True:
            chunk = self.s.recv(999999)
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data).decode('utf-8', errors='replace')

    def closed(self):
        previous_timeout = self.s.gettimeout()
        self.s.settimeout(0.1)
        try:
            result = self.s.recv(1) == b''
            if not result:
                raise Exception('Socket not closed!')
            return True
        finally:
            self.s.settimeout(previous_timeout)

    def read_chunk(self):
        line = recvline(self.s).rstrip(b'\r\n')
        chunk_size = int(line, 16) + 2  # Include trailing CRLF.
        return self.read_bytes(chunk_size)[:-2].decode(
            'utf-8', errors='replace'
        )

    def send(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.s.sendall(data)

    def close(self):
        self.s.close()


def SynchronousHttpRequest(method, url, **kwargs):
    connection = RawHttpConnection(url)
    response = connection.request(method, url, **kwargs)

    if response.get('Transfer-Encoding', '').lower() == 'chunked':
        chunks = []
        while True:
            chunk = connection.read_chunk()
            if len(chunk) == 0:
                break
            chunks.append(chunk)
        response.body = ''.join(chunks)
    elif response.get('Content-Length', ''):
        content_length = int(response['Content-Length'])
        response.body = connection.read(content_length)
    elif 'close' in [
        value.strip()
        for value in response.get('Connection', '').lower().split(',')
    ]:
        response.body = connection.read_till_eof()
    elif response.status in [101, 304, 204] or (
        response.status == 200 and method == 'OPTIONS'
    ):
        response.body = ''
    else:
        raise Exception(
            str(response.status) + ' ' + str(response.headers)
            + ' No Transfer-Encoding:chunked nor Content-Length nor '
            'Connection:Close!'
        )

    connection.close()
    return response


def GET(url, **kwargs):
    return SynchronousHttpRequest('GET', url, **kwargs)


def POST(url, **kwargs):
    return SynchronousHttpRequest('POST', url, **kwargs)


def OPTIONS(url, **kwargs):
    return SynchronousHttpRequest('OPTIONS', url, **kwargs)


def AsynchronousHttpRequest(method, url, **kwargs):
    connection = RawHttpConnection(url)
    response = connection.request(method, url, **kwargs)

    if response.get('Transfer-Encoding', '').lower() == 'chunked':
        def read():
            return connection.read_chunk()
        response.read = read
    elif response.get('Content-Length', ''):
        content_length = int(response['Content-Length'])

        def read():
            return connection.read(content_length)
        response.read = read
    elif (
        'close' in [
            value.strip()
            for value in response.get('Connection', '').lower().split(',')
        ]
        or response.status == 101
    ):
        def read():
            return connection.read()
        response.read = read
    else:
        raise Exception(
            str(response.status) + ' ' + str(response.headers)
            + ' No Transfer-Encoding:chunked nor Content-Length nor '
            'Connection:Close!'
        )

    def close():
        connection.close()

    response.close = close
    return response


def GET_async(url, **kwargs):
    return AsynchronousHttpRequest('GET', url, **kwargs)


def POST_async(url, **kwargs):
    return AsynchronousHttpRequest('POST', url, **kwargs)
