from .BaseAPI import BaseAPI

class ListOfExchangesAPI(BaseAPI):

    def get_list_of_exchanges(self, api_token: str):
        
        endpoint = 'exchanges-list'

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint)
    
    def get_list_of_tickers(self, api_token: str, code, delisted = 1):

        endpoint = 'exchange-symbol-list'
        uri = f'{code}'

        query_string = ''

        query_string += '&delisted=' + str(delisted)
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)