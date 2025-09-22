from .BaseAPI import BaseAPI

class UpcomgingEarningsAPI(BaseAPI):

    def get_upcoming_earnings_data(self, api_token: str, from_date = None, to_date = None, symbols = None):
        
        endpoint = 'calendar/earnings'

        query_string = ''

        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)
        if symbols:
            query_string += '&symbols=' + str(symbols)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)