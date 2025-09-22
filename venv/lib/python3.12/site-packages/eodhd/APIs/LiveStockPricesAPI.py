from .BaseAPI import BaseAPI

class LiveStockPricesAPI(BaseAPI):

    def get_live_stock_prices(self, api_token: str, ticker: str, s:str):
        
        endpoint = 'real-time/'
        query_string = ''

        if ticker.strip() == "" or ticker is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        
        if s is not None:
            query_string += '&s=' + str(s)


        return self._rest_get_method(api_key = api_token, endpoint = endpoint, uri = ticker, querystring=query_string)

