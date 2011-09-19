import urlparse
import httplib

class HttpResponse:
    def __init__(self, method, url, headers, body=None, async=False):
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
            conn.request(method, path, headers=headers)
        else:
            conn.request(method, path, headers=headers, body=body)
        if not async:
            self.load()

    def _get_status(self):
        return self.res.status
    status = property(_get_status)

    def __getitem__(self, key):
        return self.headers.get(key.lower())

    def load(self):
        self.res = self.conn.getresponse()
        self.headers = dict( (k.lower(), v) for k, v in self.res.getheaders() )
        self.body = self.res.read()
        self.conn.close()

    def close(self):
        self.conn.close()

def GET(url, headers={}):
    return HttpResponse('GET', url, headers)

def POST(url, headers={}, body=None):
    return HttpResponse('POST', url, headers, body)

def POST_async(url, headers={}, body=None):
    return HttpResponse('POST', url, headers, body, async=True)

