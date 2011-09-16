import urlparse
import httplib

class HttpResponse:
    def __init__(self, method, url, headers):
        u = urlparse.urlparse(url)
        if u.scheme == 'http':
            conn = httplib.HTTPConnection(u.netloc)
        elif u.scheme == 'https':
            conn = httplib.HTTPSConnection(u.netloc)
        else:
            assert False, "Unsupported scheme " + u.scheme
        assert u.fragment == ''
        path = u.path + ('?' + u.query if u.query else '')
        self.conn = conn
        conn.request(method, path, headers=headers)
        self.res = conn.getresponse()
        self.headers = dict( (k.lower(), v) for k, v in self.res.getheaders() )

    def _get_status(self):
        return self.res.status
    status = property(_get_status)

    def __getitem__(self, key):
        return self.headers.get(key.lower())

    def load(self):
        self.body = self.res.read()
        self.conn.close()
        return self

def GET(url, headers={}):
    return HttpResponse('GET', url, headers)

def POST(url, headers={}):
    return HttpResponse('POST', url, headers)

