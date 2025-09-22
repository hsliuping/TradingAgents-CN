from .BaseAPI import BaseAPI

class StockMarketScreenerAPI(BaseAPI):

    def stock_market_screener(self, api_token: str, sort = None, filters = None, limit = None, signals = None, offset = None):

        endpoint = 'screener'

        query_string = ''

        if sort is not None:
            query_string += '&sort=' + str(sort)
        if filters is not None:
            query_string += '&filters=' + str(filters).replace('\'', '\"')
        if limit is not None:
          query_string += '&limit=' + str(limit)
        if signals is not None:
          query_string += '&signals=' + str(signals)
        if offset is not None:
          query_string += '&offset=' + str(offset)

        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)