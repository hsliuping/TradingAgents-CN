from .BaseAPI import BaseAPI

class InsiderTransactionsAPI(BaseAPI):

    def get_insider_transactions_data(self, api_token: str, date_from: str = None, date_to: str = None,
                                 code: str = None, limit: int = None):
        
        endpoint = 'insider-transactions'

        query_string = ''

        if date_to is not None:
            query_string += "&to=" + date_to
        if date_from is not None:
            query_string += "&from=" + date_from
        if code is not None:
            query_string += "&code=" + code
        if limit is not None:
            query_string += "&limit=" + str(limit)
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)
