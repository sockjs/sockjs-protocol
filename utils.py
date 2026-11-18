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

import re
import socket
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import httplib_fork as httplib

from ws4py.client.threadedclient import WebSocketClient
import queue


# --- helpers ---

def _to_bytes(data: Any, encoding: str = "utf-8") -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode(encoding)
    # fallback (rare in these tests)
    return str(data).encode(encoding)


def _to_str(data: Any, encoding: str = "utf-8") -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data).decode(encoding, errors="replace")
    return str(data)


def recvline(s: socket.socket) -> bytes:
    b = bytearray()
    while True:
        c = s.recv(1)
        if not c:
            # EOF mid-line; return what we have
            return bytes(b)
        b.extend(c)
        if c == b"\n":
            return bytes(b)


# --- HTTPResponse (legacy; used only by old_POST_async in protocol tests) ---

class HttpResponse:
    def __init__(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
        async_: bool = False,
        load: bool = True,
    ):
        headers = (headers or {}).copy()
        u = urlparse(url)
        kwargs = {"timeout": 1.0}

        if u.scheme == "http":
            conn = httplib.HTTPConnection(u.netloc, **kwargs)
        elif u.scheme == "https":
            conn = httplib.HTTPSConnection(u.netloc, **kwargs)
        else:
            raise AssertionError("Unsupported scheme " + u.scheme)

        assert u.fragment == ""
        path = u.path + ("?" + u.query if u.query else "")
        self.conn = conn

        if body is None or body == b"" or body == "":
            if method == "POST":
                # httplib in some cases sets Content-Length only when there is a body.
                headers["Content-Length"] = "0"
            conn.request(method, path, headers=headers)
        else:
            conn.request(method, path, headers=headers, body=_to_bytes(body))

        if load:
            if not async_:
                self._load()
            else:
                self._async_load()

    @property
    def status(self) -> int:
        return self.res.status

    def __getitem__(self, key: str) -> Optional[str]:
        return self.headers.get(key.lower())

    def _load(self) -> None:
        self.res = self.conn.getresponse()
        self.headers = {k.lower(): v for (k, v) in self.res.getheaders()}
        self.body = _to_str(self.res.read())
        self.close()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def _async_load(self) -> None:
        self.res = self.conn.getresponse()
        self.headers = {k.lower(): v for (k, v) in self.res.getheaders()}

    def read(self) -> Optional[str]:
        data = self.res.read(10240)
        if data:
            return _to_str(data)
        self.close()
        return None


def old_POST_async(url: str, **kwargs) -> HttpResponse:
    # Preserve original API; translate async -> async_
    if "async" in kwargs:
        kwargs["async_"] = kwargs.pop("async")
    return HttpResponse("POST", url, async_=True, **kwargs)


# --- WebSocket8Client (ws4py) ---

class WebSocket8Client(object):
    class ConnectionClosedException(Exception):
        pass

    def __init__(self, url: str):
        q: "queue.Queue[Any]" = queue.Queue()
        self.queue = q

        class IntWebSocketClient(WebSocketClient):
            def received_message(self, m):
                # ws4py message -> bytes/str; normalize to str
                q.put(_to_str(bytes(m) if hasattr(m, "__bytes__") else str(m)))

            def closed(self, code, reason):
                q.put((code, reason))

        self.client = IntWebSocketClient(url)
        self.client.connect()

    def close(self):
        if self.client:
            self.client.running = False
            self.client.close()
            self.client._th.join()
            self.client = None

    def send(self, data):
        # ws4py can take str; keep as-is
        self.client.send(data)

    def recv(self):
        try:
            r = self.queue.get(timeout=1.0)
            if isinstance(r, tuple):
                ce = self.ConnectionClosedException()
                (ce.code, ce.reason) = r
                raise ce
            return r
        except Exception:
            self.close()
            raise


# --- Raw HTTP layer ---

class CaseInsensitiveDict(object):
    def __init__(self, *args, **kwargs):
        self.lower: Dict[str, str] = {}
        self.d: Dict[str, str] = dict(*args, **kwargs)
        for k in list(self.d.keys()):
            self[k] = self.d[k]

    def __getitem__(self, key, *args, **kwargs):
        pkey = self.lower.setdefault(str(key).lower(), key)
        return self.d.__getitem__(pkey, *args, **kwargs)

    def __setitem__(self, key, *args, **kwargs):
        pkey = self.lower.setdefault(str(key).lower(), key)
        return self.d.__setitem__(pkey, *args, **kwargs)

    def items(self):
        for k in self.lower.values():
            yield (k, self[k])

    def __repr__(self):
        return repr(self.d)

    def __str__(self):
        return str(self.d)

    def get(self, key, *args, **kwargs):
        pkey = self.lower.setdefault(str(key).lower(), key)
        return self.d.get(pkey, *args, **kwargs)

    def __contains__(self, key):
        pkey = self.lower.setdefault(str(key).lower(), key)
        return pkey in self.d


class Response(object):
    def __repr__(self):
        return "<Response HTTP/%s %s %r %r>" % (
            self.http,
            self.status,
            self.description,
            self.headers,
        )

    def __str__(self):
        return repr(self)

    def __getitem__(self, key):
        return self.headers.get(key)

    def get(self, key, default=None):
        return self.headers.get(key, default)


class RawHttpConnection(object):
    def __init__(self, url: str):
        u = urlparse(url)
        port = u.port or (443 if u.scheme == "https" else 80)
        self.s = socket.create_connection((u.hostname, port), timeout=1)

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
        timeout: float = 1,
        http: str = "1.1",
    ) -> Response:
        headers = CaseInsensitiveDict(headers or {})
        if method == "POST":
            # original behavior: treat POST body as utf-8 text unless bytes passed
            if body is None:
                body_b = b""
            else:
                body_b = _to_bytes(body)
        else:
            body_b = _to_bytes(body) if body is not None else b""

        u = urlparse(url)
        host = u.hostname
        port = u.port
        headers["Host"] = f"{host}:{port}" if port else host

        if body is not None:
            headers["Content-Length"] = str(len(body_b))

        rel_url = url[url.find(u.path) :] if u.path else "/"

        req_lines = [f"{method} {rel_url} HTTP/{http}"]
        for k, v in headers.items():
            req_lines.append(f"{k}: {v}")
        req_lines.append("")
        req_lines.append("")

        self.send(("\r\n".join(req_lines)).encode("utf-8"))

        if body_b:
            self.send(body_b)

        head = recvline(self.s).decode("iso-8859-1", errors="replace")
        r = re.match(r"HTTP/(?P<version>\S+) (?P<status>\S+) (?P<description>.*)", head)
        if not r:
            raise Exception("Invalid HTTP response line: %r" % head)

        resp = Response()
        resp.http = r.group("version")
        resp.status = int(r.group("status"))
        resp.description = r.group("description").rstrip("\r\n")

        resp.headers = CaseInsensitiveDict()
        while True:
            header = recvline(self.s)
            if header in (b"\n", b"\r\n", b""):
                break
            line = header.decode("iso-8859-1", errors="replace")
            k, _, v = line.partition(":")
            resp.headers[k] = v.lstrip().rstrip("\r\n")

        return resp

    # --- bytes-level reads (needed for haproxy/binary assertions) ---

    def read_bytes(self, size: Optional[int] = None) -> bytes:
        if size is None:
            return self.s.recv(999999)

        data = bytearray()
        remaining = size
        while remaining > 0:
            c = self.s.recv(remaining)
            if not c:
                raise Exception("Socket closed!")
            remaining -= len(c)
            data.extend(c)
        return bytes(data)

    def read_till_eof_bytes(self) -> bytes:
        data = bytearray()
        while True:
            c = self.s.recv(999999)
            if not c:
                break
            data.extend(c)
        return bytes(data)

    def closed(self) -> bool:
        t = self.s.gettimeout()
        self.s.settimeout(0.1)
        try:
            b = self.s.recv(1)
            r = b == b""
            if not r:
                raise Exception("Socket not closed!")
            return True
        finally:
            self.s.settimeout(t)

    def read_chunk_bytes(self) -> bytes:
        line = recvline(self.s).rstrip(b"\r\n")
        n = int(line.decode("ascii"), 16) + 2  # plus trailing \r\n
        return self.read_bytes(n)[:-2]

    # --- compatibility str-level wrappers (used by HTTP helpers) ---

    def read(self, size: Optional[int] = None) -> str:
        return _to_str(self.read_bytes(size))

    def read_till_eof(self) -> str:
        return _to_str(self.read_till_eof_bytes())

    def read_chunk(self) -> str:
        return _to_str(self.read_chunk_bytes())

    def send(self, data: Any) -> None:
        self.s.sendall(_to_bytes(data))

    def close(self) -> None:
        self.s.close()


# --- HTTP helper functions used by the protocol test suite ---

def SynchronousHttpRequest(method: str, url: str, **kwargs) -> Response:
    c = RawHttpConnection(url)
    r = c.request(method, url, **kwargs)

    if r.get("Transfer-Encoding", "").lower() == "chunked":
        chunks = []
        while True:
            chunk = c.read_chunk()
            if len(chunk) == 0:
                break
            chunks.append(chunk)
        r.body = "".join(chunks)

    elif r.get("Content-Length", ""):
        cl = int(r["Content-Length"])
        r.body = c.read_bytes(cl).decode("utf-8", errors="replace")

    elif "close" in [k.strip() for k in r.get("Connection", "").lower().split(",")]:
        r.body = c.read_till_eof_bytes().decode("utf-8", errors="replace")

    else:
        # Whitelist statuses that may not need a response
        if r.status in [101, 304, 204] or (r.status == 200 and method == "OPTIONS"):
            r.body = ""
        else:
            raise Exception(
                f"{r.status} {r.headers} "
                "No Transfer-Encoding:chunked nor Content-Length nor Connection:Close!"
            )

    c.close()
    return r


def GET(url: str, **kwargs) -> Response:
    return SynchronousHttpRequest("GET", url, **kwargs)


def POST(url: str, **kwargs) -> Response:
    return SynchronousHttpRequest("POST", url, **kwargs)


def OPTIONS(url: str, **kwargs) -> Response:
    return SynchronousHttpRequest("OPTIONS", url, **kwargs)


def AsynchronousHttpRequest(method: str, url: str, **kwargs) -> Response:
    c = RawHttpConnection(url)
    r = c.request(method, url, **kwargs)

    if r.get("Transfer-Encoding", "").lower() == "chunked":

        def read() -> str:
            return c.read_chunk()

        r.read = read

    elif r.get("Content-Length", ""):
        cl = int(r["Content-Length"])

        def read() -> str:
            # NOTE: not truly streaming; matches old behavior
            return c.read_bytes(cl).decode("utf-8", errors="replace")

        r.read = read

    elif ("close" in [k.strip() for k in r.get("Connection", "").lower().split(",")]) or (
        r.status == 101
    ):

        def read() -> Optional[str]:
            b = c.read_bytes()
            if b:
                return b.decode("utf-8", errors="replace")
            return None

        r.read = read

    else:
        raise Exception(
            f"{r.status} {r.headers} "
            "No Transfer-Encoding:chunked nor Content-Length nor Connection:Close!"
        )

    def close() -> None:
        c.close()

    r.close = close
    return r


def GET_async(url: str, **kwargs) -> Response:
    return AsynchronousHttpRequest("GET", url, **kwargs)


def POST_async(url: str, **kwargs) -> Response:
    return AsynchronousHttpRequest("POST", url, **kwargs)
