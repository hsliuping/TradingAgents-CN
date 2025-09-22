import functools
from functools import lru_cache

from curl_cffi import requests
from bs4 import BeautifulSoup
import datetime

from frozendict import frozendict

from . import utils, cache
import threading

from .exceptions import YFRateLimitError, YFDataException

cache_maxsize = 64


def lru_cache_freezeargs(func):
    """
    Decorator transforms mutable dictionary and list arguments into immutable types
    Needed so lru_cache can cache method calls what has dict or list arguments.
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        args = tuple([frozendict(arg) if isinstance(arg, dict) else arg for arg in args])
        kwargs = {k: frozendict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        args = tuple([tuple(arg) if isinstance(arg, list) else arg for arg in args])
        kwargs = {k: tuple(v) if isinstance(v, list) else v for k, v in kwargs.items()}
        return func(*args, **kwargs)

    # copy over the lru_cache extra methods to this wrapper to be able to access them
    # after this decorator has been applied
    wrapped.cache_info = func.cache_info
    wrapped.cache_clear = func.cache_clear
    return wrapped


class SingletonMeta(type):
    """
    Metaclass that creates a Singleton instance.
    """
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            else:
                # Update the existing instance
                if 'session' in kwargs or (args and len(args) > 0):
                    session = kwargs.get('session') if 'session' in kwargs else args[0]
                    cls._instances[cls]._set_session(session)
                if 'proxy' in kwargs or (args and len(args) > 1):
                    proxy = kwargs.get('proxy') if 'proxy' in kwargs else args[1]
                    cls._instances[cls]._set_proxy(proxy)
            return cls._instances[cls]


class YfData(metaclass=SingletonMeta):
    """
    Have one place to retrieve data from Yahoo API in order to ease caching and speed up operations.
    Singleton means one session one cookie shared by all threads.
    """

    def __init__(self, session=None, proxy=None):
        self._crumb = None
        self._cookie = None

        # Default to using 'basic' strategy
        self._cookie_strategy = 'basic'
        # If it fails, then fallback method is 'csrf'
        # self._cookie_strategy = 'csrf'

        self._cookie_lock = threading.Lock()

        self._session, self._proxy = None, None
        self._set_session(session or requests.Session(impersonate="chrome"))
        self._set_proxy(proxy)

    def _set_session(self, session):
        if session is None:
            return

        try:
            session.cache
        except AttributeError:
            # Not caching
            self._session_is_caching = False
        else:
            # Is caching. This is annoying.
            # Can't simply use a non-caching session to fetch cookie & crumb,
            # because then the caching-session won't have cookie.
            self._session_is_caching = True
            # But since switch to curl_cffi, can't use requests_cache with it.
            raise YFDataException("request_cache sessions don't work with curl_cffi, which is necessary now for Yahoo API. Solution: stop setting session, let YF handle.")

        if not isinstance(session, requests.session.Session):
            raise YFDataException(f"Yahoo API requires curl_cffi session not {type(session)}. Solution: stop setting session, let YF handle.")

        with self._cookie_lock:
            self._session = session
            if self._proxy is not None:
                self._session.proxies = self._proxy

    def _set_proxy(self, proxy=None):
        with self._cookie_lock:
            if proxy is not None:
                proxy = {'http': proxy, 'https': proxy} if isinstance(proxy, str) else proxy
            else:
                proxy = {}
            self._proxy = proxy
            self._session.proxies = proxy

    def _set_cookie_strategy(self, strategy, have_lock=False):
        if strategy == self._cookie_strategy:
            return
        if not have_lock:
            self._cookie_lock.acquire()

        try:
            if self._cookie_strategy == 'csrf':
                utils.get_yf_logger().debug(f'toggling cookie strategy {self._cookie_strategy} -> basic')
                self._session.cookies.clear()
                self._cookie_strategy = 'basic'
            else:
                utils.get_yf_logger().debug(f'toggling cookie strategy {self._cookie_strategy} -> csrf')
                self._cookie_strategy = 'csrf'
            self._cookie = None
            self._crumb = None
        except Exception:
            self._cookie_lock.release()
            raise

        if not have_lock:
            self._cookie_lock.release()

    @utils.log_indent_decorator
    def _save_cookie_curlCffi(self):
        if self._session is None:
            return False
        cookies = self._session.cookies.jar._cookies
        if len(cookies) == 0:
            return False
        yh_domains = [k for k in cookies.keys() if 'yahoo' in k]
        if len(yh_domains) > 1:
            # Possible when cookie fetched with CSRF method. Discard consent cookie.
            yh_domains = [k for k in yh_domains if 'consent' not in k]
        if len(yh_domains) > 1:
            utils.get_yf_logger().debug(f'Multiple Yahoo cookies, not sure which to cache: {yh_domains}')
            return False
        if len(yh_domains) == 0:
            return False
        yh_domain = yh_domains[0]
        yh_cookie = {yh_domain: cookies[yh_domain]}
        cache.get_cookie_cache().store('curlCffi', yh_cookie)
        return True

    @utils.log_indent_decorator
    def _load_cookie_curlCffi(self):
        if self._session is None:
            return False
        cookie_dict = cache.get_cookie_cache().lookup('curlCffi')
        if cookie_dict is None or len(cookie_dict) == 0:
            return False
        cookies = cookie_dict['cookie']
        domain = list(cookies.keys())[0]
        cookie = cookies[domain]['/']['A3']
        expiry_ts = cookie.expires
        if expiry_ts > 2e9:
            # convert ms to s
            expiry_ts //= 1e3
        expiry_dt = datetime.datetime.fromtimestamp(expiry_ts, tz=datetime.timezone.utc)
        expired = expiry_dt < datetime.datetime.now(datetime.timezone.utc)
        if expired:
            utils.get_yf_logger().debug('cached cookie expired')
            return False
        self._session.cookies.jar._cookies.update(cookies)
        self._cookie = cookie
        return True

    @utils.log_indent_decorator
    def _get_cookie_basic(self, timeout=30):
        if self._cookie is not None:
            utils.get_yf_logger().debug('reusing cookie')
            return True
        elif self._load_cookie_curlCffi():
            utils.get_yf_logger().debug('reusing persistent cookie')
            return True

        # To avoid infinite recursion, do NOT use self.get()
        # - 'allow_redirects' copied from @psychoz971 solution - does it help USA?
        try:
            self._session.get(
                url='https://fc.yahoo.com',
                timeout=timeout,
                allow_redirects=True)
        except requests.exceptions.DNSError:
            # Possible because url on some privacy/ad blocklists
            return False
        self._save_cookie_curlCffi()
        return True

    @utils.log_indent_decorator
    def _get_crumb_basic(self, timeout=30):
        if self._crumb is not None:
            utils.get_yf_logger().debug('reusing crumb')
            return self._crumb

        if not self._get_cookie_basic():
            return None
        # - 'allow_redirects' copied from @psychoz971 solution - does it help USA?
        get_args = {
            'url': "https://query1.finance.yahoo.com/v1/test/getcrumb",
            'timeout': timeout,
            'allow_redirects': True
        }
        if self._session_is_caching:
            get_args['expire_after'] = self._expire_after
            crumb_response = self._session.get(**get_args)
        else:
            crumb_response = self._session.get(**get_args)
        self._crumb = crumb_response.text
        if crumb_response.status_code == 429 or "Too Many Requests" in self._crumb:
            utils.get_yf_logger().debug(f"Didn't receive crumb {self._crumb}")
            raise YFRateLimitError()

        if self._crumb is None or '<html>' in self._crumb:
            utils.get_yf_logger().debug("Didn't receive crumb")
            return None

        utils.get_yf_logger().debug(f"crumb = '{self._crumb}'")
        return self._crumb

    @utils.log_indent_decorator
    def _get_cookie_and_crumb_basic(self, timeout):
        if not self._get_cookie_basic(timeout):
            return None
        return self._get_crumb_basic(timeout)

    @utils.log_indent_decorator
    def _get_cookie_csrf(self, timeout):
        if self._cookie is not None:
            utils.get_yf_logger().debug('reusing cookie')
            return True

        elif self._load_cookie_curlCffi():
            utils.get_yf_logger().debug('reusing persistent cookie')
            self._cookie = True
            return True

        base_args = {
            'timeout': timeout}

        get_args = {**base_args, 'url': 'https://guce.yahoo.com/consent'}
        try:
            if self._session_is_caching:
                get_args['expire_after'] = self._expire_after
                response = self._session.get(**get_args)
            else:
                response = self._session.get(**get_args)
        except requests.exceptions.ChunkedEncodingError:
            # No idea why happens, but handle nicely so can switch to other cookie method.
            utils.get_yf_logger().debug('_get_cookie_csrf() encountering requests.exceptions.ChunkedEncodingError, aborting')
            return False

        soup = BeautifulSoup(response.content, 'html.parser')
        csrfTokenInput = soup.find('input', attrs={'name': 'csrfToken'})
        if csrfTokenInput is None:
            utils.get_yf_logger().debug('Failed to find "csrfToken" in response')
            return False
        csrfToken = csrfTokenInput['value']
        utils.get_yf_logger().debug(f'csrfToken = {csrfToken}')
        sessionIdInput = soup.find('input', attrs={'name': 'sessionId'})
        sessionId = sessionIdInput['value']
        utils.get_yf_logger().debug(f"sessionId='{sessionId}")

        originalDoneUrl = 'https://finance.yahoo.com/'
        namespace = 'yahoo'
        data = {
            'agree': ['agree', 'agree'],
            'consentUUID': 'default',
            'sessionId': sessionId,
            'csrfToken': csrfToken,
            'originalDoneUrl': originalDoneUrl,
            'namespace': namespace,
        }
        post_args = {**base_args,
            'url': f'https://consent.yahoo.com/v2/collectConsent?sessionId={sessionId}',
            'data': data}
        get_args = {**base_args,
            'url': f'https://guce.yahoo.com/copyConsent?sessionId={sessionId}',
            'data': data}
        try:
            if self._session_is_caching:
                post_args['expire_after'] = self._expire_after
                get_args['expire_after'] = self._expire_after
                self._session.post(**post_args)
                self._session.get(**get_args)
            else:
                self._session.post(**post_args)
                self._session.get(**get_args)
        except requests.exceptions.ChunkedEncodingError:
            # No idea why happens, but handle nicely so can switch to other cookie method.
            utils.get_yf_logger().debug('_get_cookie_csrf() encountering requests.exceptions.ChunkedEncodingError, aborting')
        self._cookie = True
        self._save_cookie_curlCffi()
        return True

    @utils.log_indent_decorator
    def _get_crumb_csrf(self, timeout=30):
        # Credit goes to @bot-unit #1729

        if self._crumb is not None:
            utils.get_yf_logger().debug('reusing crumb')
            return self._crumb

        if not self._get_cookie_csrf(timeout):
            # This cookie stored in session
            return None

        get_args = {
            'url': 'https://query2.finance.yahoo.com/v1/test/getcrumb',
            'timeout': timeout}
        if self._session_is_caching:
            get_args['expire_after'] = self._expire_after
            r = self._session.get(**get_args)
        else:
            r = self._session.get(**get_args)
        self._crumb = r.text

        if r.status_code == 429 or "Too Many Requests" in self._crumb:
            utils.get_yf_logger().debug(f"Didn't receive crumb {self._crumb}")
            raise YFRateLimitError()

        if self._crumb is None or '<html>' in self._crumb or self._crumb == '':
            utils.get_yf_logger().debug("Didn't receive crumb")
            return None

        utils.get_yf_logger().debug(f"crumb = '{self._crumb}'")
        return self._crumb

    @utils.log_indent_decorator
    def _get_cookie_and_crumb(self, timeout=30):
        crumb, strategy = None, None

        utils.get_yf_logger().debug(f"cookie_mode = '{self._cookie_strategy}'")

        with self._cookie_lock:
            if self._cookie_strategy == 'csrf':
                crumb = self._get_crumb_csrf()
                if crumb is None:
                    # Fail
                    self._set_cookie_strategy('basic', have_lock=True)
                    crumb = self._get_cookie_and_crumb_basic(timeout)
            else:
                # Fallback strategy
                crumb = self._get_cookie_and_crumb_basic(timeout)
                if crumb is None:
                    # Fail
                    self._set_cookie_strategy('csrf', have_lock=True)
                    crumb = self._get_crumb_csrf()
            strategy = self._cookie_strategy
        return crumb, strategy

    @utils.log_indent_decorator
    def get(self, url, params=None, timeout=30):
        return self._make_request(url, request_method = self._session.get, params=params, timeout=timeout)

    @utils.log_indent_decorator
    def post(self, url, body, params=None, timeout=30):
        return self._make_request(url, request_method = self._session.post, body=body, params=params, timeout=timeout)

    @utils.log_indent_decorator
    def _make_request(self, url, request_method, body=None, params=None, timeout=30):
        # Important: treat input arguments as immutable.

        if len(url) > 200:
            utils.get_yf_logger().debug(f'url={url[:200]}...')
        else:
            utils.get_yf_logger().debug(f'url={url}')
        utils.get_yf_logger().debug(f'params={params}')

        if params is None:
            params = {}
        if 'crumb' in params:
            raise Exception("Don't manually add 'crumb' to params dict, let data.py handle it")

        crumb, strategy = self._get_cookie_and_crumb()
        if crumb is not None:
            crumbs = {'crumb': crumb}
        else:
            crumbs = {}

        request_args = {
            'url': url,
            'params': {**params, **crumbs},
            'timeout': timeout
        }

        if body:
            request_args['json'] = body

        response = request_method(**request_args)
        utils.get_yf_logger().debug(f'response code={response.status_code}')
        if response.status_code >= 400:
            # Retry with other cookie strategy
            if strategy == 'basic':
                self._set_cookie_strategy('csrf')
            else:
                self._set_cookie_strategy('basic')
            crumb, strategy = self._get_cookie_and_crumb(timeout)
            request_args['params']['crumb'] = crumb
            response = request_method(**request_args)
            utils.get_yf_logger().debug(f'response code={response.status_code}')

            # Raise exception if rate limited
            if response.status_code == 429:
                raise YFRateLimitError()

        return response

    @lru_cache_freezeargs
    @lru_cache(maxsize=cache_maxsize)
    def cache_get(self, url, params=None, timeout=30):
        return self.get(url, params, timeout)

    def get_raw_json(self, url, params=None, timeout=30):
        utils.get_yf_logger().debug(f'get_raw_json(): {url}')
        response = self.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
