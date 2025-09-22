from .BaseAPI import BaseAPI

class BondsFundamentalsAPI(BaseAPI):

    def get_bonds_fundamentals_data(self, api_token: str, isin):
        
        endpoint = 'bond-fundamentals'
        uri = f'{isin}'

        query_string = ''
        if isin is None or isin == '':
            raise ValueError('isin cannot be empty')
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)
