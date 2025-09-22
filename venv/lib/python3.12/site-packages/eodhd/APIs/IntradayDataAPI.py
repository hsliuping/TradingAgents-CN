from .BaseAPI import BaseAPI

class IntradayDataAPI(BaseAPI):

    def get_intraday_historical_data(self, api_token: str, symbol: str, interval: str, 
                                     from_unix_time: str = None, to_unix_time: str = None):

        possible_intervals = ['5m', '1h', '1m']
        
        endpoint = 'intraday'

        if symbol.strip() == "" or symbol is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        if interval not in possible_intervals:
            raise ValueError("Interval must be in ['5m', '1h', '1m'] values")
        
        uri = f'{symbol}'
        query_string = ''

        query_string += '&interval=' + str(interval)
        
        if from_unix_time is not None: 
            query_string += '&from=' + str(from_unix_time)
        if to_unix_time is not None: 
            query_string += '&to=' + str(to_unix_time)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)