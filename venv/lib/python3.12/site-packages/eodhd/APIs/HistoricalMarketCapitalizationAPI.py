from .BaseAPI import BaseAPI

class HistoricalMarketCapitalization(BaseAPI):

    def get_historical_market_capitalization_data(self, api_token: str, ticker, from_date: str = None, to_date: str = None):
        
        endpoint = 'historical-market-cap'
        uri = f'{ticker}'

        query_string = ''

        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)
