# -*- coding:utf-8 -*- 

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request


class Client(object):
    def __init__(self, url=None, ref=None, cookie=None):
        self._ref = ref
        self._cookie = cookie
        self._url = url
        self._setOpener()
        
    def _setOpener(self):
        request = Request(self._url)
        request.add_header("Accept-Language", "en-US,en;q=0.5")
        request.add_header("Connection", "keep-alive")
#         request.add_header('Referer', self._ref)
        if self._cookie is not None:
            request.add_header("Cookie", self._cookie)
        request.add_header("User-Agent", 'Mozilla/5.0 (Windows NT 6.1; rv:37.0) Gecko/20100101 Firefox/37.0')
        self._request = request
        
    def gvalue(self):
        values = urlopen(self._request, timeout = 10).read()
        return values
