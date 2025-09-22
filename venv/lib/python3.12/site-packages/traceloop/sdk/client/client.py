import sys

from traceloop.sdk.annotation.user_feedback import UserFeedback
from .http import HTTPClient
from traceloop.sdk.version import __version__


class Client:
    """
    Traceloop Client for interacting with the Traceloop API.

    Applications should configure the client at startup time and continue to use it throughout the lifetime
    of the application, rather than creating instances on the fly. The best way to do this is with the
    singleton methods :func:`Traceloop.init()` and :func:`Traceloop.get()`. However, you may also call
    the constructor directly if you need to maintain multiple instances.
    """

    app_name: str
    api_endpoint: str
    api_key: str
    user_feedback: UserFeedback
    _http: HTTPClient

    def __init__(self, api_key: str, app_name: str = sys.argv[0], api_endpoint: str = "https://api.traceloop.com"):
        """
        Initialize a new Traceloop client.

        Args:
            api_key (str): Your Traceloop API key
            app_name (Optional[str], optional): The name of your application. Defaults to sys.argv[0].
            api_endpoint (Optional[str], optional): Custom API endpoint. Defaults to https://api.traceloop.com.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key is required")

        self.app_name = app_name
        self.api_endpoint = api_endpoint or "https://api.traceloop.com"
        self.api_key = api_key
        self._http = HTTPClient(base_url=self.api_endpoint, api_key=self.api_key, version=__version__)
        self.user_feedback = UserFeedback(self._http, self.app_name)
