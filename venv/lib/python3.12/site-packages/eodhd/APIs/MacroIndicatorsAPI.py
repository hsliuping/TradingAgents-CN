
from .BaseAPI import BaseAPI

class MacroIndicatorsAPI(BaseAPI):

    def get_macro_indicators_data(self, api_token: str, country, indicator = None):
        
        endpoint = 'macro-indicator'
        uri = f'{country}'

        query_string = ''

        if indicator is not None:
            query_string += '&indicator=' + str(indicator)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)