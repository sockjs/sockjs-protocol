import urlparse
import httplib
from ws4py.client.threadedclient import WebSocketClient
import Queue

class HttpResponse:
    def __init__(self, method, url,
                 headers={}, body=None, async=False, load=True):
        headers = headers.copy()
        u = urlparse.urlparse(url)
        kwargs = {'timeout': None if async else 1.0}
        if u.scheme == 'http':
            conn = httplib.HTTPConnection(u.netloc, **kwargs)
        elif u.scheme == 'https':
            conn = httplib.HTTPSConnection(u.netloc, **kwargs)
        else:
            assert False, "Unsupported scheme " + u.scheme
        assert u.fragment == ''
        path = u.path + ('?' + u.query if u.query else '')
        self.conn = conn
        if not body:
            if method is 'POST':
                # The spec says: "Applications SHOULD use this field
                # to indicate the transfer-length of the message-body,
                # unless this is prohibited by the rules in section
                # 4.4."
                # http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.13
                # While httplib sets it only if there is body.
                headers['Content-Length'] = 0
            conn.request(method, path, headers=headers)
        else:
            if isinstance(body, unicode):
                body = body.encode('utf-8')
            conn.request(method, path, headers=headers, body=body)

        if load:
            if not async:
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
        self.headers = dict( (k.lower(), v) for k, v in self.res.getheaders() )
        self.body = self.res.read()
        self.close()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _async_load(self):
        self.res = self.conn.getresponse()
        self.headers = dict( (k.lower(), v) for k, v in self.res.getheaders() )

    def read(self):
        data =  self.res.read(10240)
        if data:
            return data
        else:
            self.close()
            return None

def GET(url, **kwargs):
    return HttpResponse('GET', url, **kwargs)

def GET_async(url, **kwargs):
    return HttpResponse('GET', url, async=True, **kwargs)

def POST(url, **kwargs):
    return HttpResponse('POST', url, **kwargs)

def POST_async(url, **kwargs):
    return HttpResponse('POST', url, async=True, **kwargs)

def OPTIONS(url, **kwargs):
    return HttpResponse('OPTIONS', url, **kwargs)


class WebSocket8Client(object):
    class ConnectionClosedException(Exception): pass

    def __init__(self, url):
        queue = Queue.Queue()
        self.queue = queue
        class IntWebSocketClient(WebSocketClient):
            def received_message(self, m):
                queue.put(unicode(str(m), 'utf-8'))
            def read_from_connection(self, amount):
                r = super(IntWebSocketClient, self).read_from_connection(amount)
                if not r:
                    queue.put(Ellipsis)
                return r
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
            r = self.queue.get(timeout=1.0)
            if r is Ellipsis:
                raise self.ConnectionClosedException()
            return r
        except:
            self.close()
            raise
