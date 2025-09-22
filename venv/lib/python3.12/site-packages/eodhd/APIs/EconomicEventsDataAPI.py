from .BaseAPI import BaseAPI

class EconomicEventsDataAPI(BaseAPI):

    def get_economic_events_data(self, api_token: str, date_from: str = None, date_to: str = None,
                                 country: str = None, comparison: str = None, offset: int = None, limit: int = None):
        
        endpoint = 'economic-events'

        query_string = ''

        if date_to is not None:
            query_string += "&to=" + date_to
        if date_from is not None:
            query_string += "&from=" + date_from
        if country is not None:
            query_string += "&country=" + country
        if comparison is not None:
            query_string += "&comparison=" + comparison
        if offset is not None:
            query_string += "&offset=" + str(offset)
        if limit is not None:
            query_string += "&limit=" + str(limit)
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)
