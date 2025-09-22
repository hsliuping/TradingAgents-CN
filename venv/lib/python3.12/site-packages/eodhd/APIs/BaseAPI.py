from json.decoder import JSONDecodeError
import sys
from requests import get as requests_get
from requests import ConnectionError as requests_ConnectionError
from requests import Timeout as requests_Timeout
from requests.exceptions import HTTPError as requests_HTTPError
from rich.console import Console

class BaseAPI:

    def __init__(self) -> None:
        self._api_url = "https://eodhd.com/api"
        self.console = Console()


    def _rest_get_method(self, api_key: str, endpoint: str = "", uri: str = "", querystring: str = ""):
        """Generic REST GET"""
        
        if endpoint.strip() == "":
            raise ValueError("endpoint is empty!")

        try:
            resp = requests_get(f"{self._api_url}/{endpoint}/{uri}?api_token={api_key}&fmt=json{querystring}")

            if resp.status_code != 200:
                try:
                    if "message" in resp.json():
                        resp_message = resp.json()["message"]
                    elif "errors" in resp.json():
                        self.console.log(resp.json())
                        sys.exit(1)
                    else:
                        resp_message = ""

                    message = f"({resp.status_code}) {self._api_url} - {resp_message}"
                    self.console.log(message)

                except JSONDecodeError as err:
                    self.console.log(err)

            try:
                resp.raise_for_status()

                return resp.json()

            except ValueError as err:
                self.console.log(err)

        except requests_ConnectionError as err:
            self.console.log(err)
        except requests_HTTPError as err:
            self.console.log(err)
        except requests_Timeout as err:
            self.console.log(err)
        return {}
