from .BaseAPI import BaseAPI

class EarningTrendsAPI(BaseAPI):

    def get_earning_trends_data(self, api_token: str, symbols):
        
        endpoint = 'calendar/trends'

        query_string = ''

        query_string += '&symbols=' + str(symbols)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)