from .BaseAPI import BaseAPI

class FundamentalDataAPI(BaseAPI):

    def get_fundamentals_data(self, api_token: str, ticker: str):
        
        endpoint = 'fundamentals/'

        if ticker.strip() == "" or ticker is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, uri = ticker)
