from .BaseAPI import BaseAPI

class BulkEodSplitsDividendsDataAPI(BaseAPI):

    def get_eod_splits_dividends_data(self, api_token: str, country = 'US', type = None, date = None,
                                   symbols = None, filter = None):
        
        endpoint = 'eod-bulk-last-day'
        uri = f'{country}'

        query_string = ''

        if type is not None:
            query_string += '&type=' + str(type)
        if date is not None:
            query_string += '&date=' + str(date)
        if symbols:
            query_string += '&symbols=' + str(symbols)
        if filter is not None:
            query_string += '&filter=' + str(filter)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)
