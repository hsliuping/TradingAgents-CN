from typing import Any, Dict, Optional

import requests
from colorama import Fore


class HTTPClient:
    base_url: str
    api_key: str
    version: str

    def __init__(self, base_url: str, api_key: str, version: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.version = version

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Traceloop-SDK-Version": self.version,
        }

    def post(self, path: str, data: Dict[str, Any]) -> Any:
        """
        Make a POST request to the API
        """
        try:
            response = requests.post(f"{self.base_url}/v2/{path.lstrip('/')}", json=data, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(Fore.RED + f"Error making request to {path}: {str(e)}" + Fore.RESET)
            return None

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make a GET request to the API
        """
        try:
            response = requests.get(f"{self.base_url}/v2/{path.lstrip('/')}", params=params, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(Fore.RED + f"Error making request to {path}: {str(e)}" + Fore.RESET)
            return None
