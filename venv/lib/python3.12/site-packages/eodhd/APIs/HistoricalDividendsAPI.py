from .BaseAPI import BaseAPI

class HistoricalDividendsAPI(BaseAPI):

    def get_historical_dividends_data(self, api_token: str, ticker: str, date_from: str = None, date_to: str = None):
        
        endpoint = 'div/'

        if ticker.strip() == "" or ticker is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")

        query_string = ''

        if date_to is not None:
            query_string += "&to=" + date_to
        if date_from is not None:
            query_string += "&from=" + date_from
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, uri = ticker, querystring = query_string)
