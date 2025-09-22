from .BaseAPI import BaseAPI

class UpcomingSplitsAPI(BaseAPI):

    def get_upcoming_splits_data(self, api_token: str, from_date = None, to_date = None):
        
        endpoint = 'calendar/splits'

        query_string = ''

        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)