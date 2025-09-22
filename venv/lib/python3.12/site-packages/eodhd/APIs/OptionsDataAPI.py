
from .BaseAPI import BaseAPI

class OptionsDataAPI(BaseAPI):

    def get_options_data(self, api_token: str, ticker, date_to = None, date_from = None, 
                         trade_date_to = None, trade_date_from = None, contract_name = None):
        
        endpoint = 'options'
        if ticker.strip() == "" or ticker is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        
        uri = f'{ticker}'

        query_string = ''

        if date_to is not None:
            query_string += '&to=' + str(date_to)
        if date_from is not None:
            query_string += '&from=' + str(date_from)
        if trade_date_from is not None:
            query_string += '&trade_date_from=' + str(trade_date_from)
        if trade_date_to is not None:
            query_string += '&trade_date_to=' + str(trade_date_to)
        if contract_name is not None:
            query_string += '&contract_name=' + str(contract_name)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)