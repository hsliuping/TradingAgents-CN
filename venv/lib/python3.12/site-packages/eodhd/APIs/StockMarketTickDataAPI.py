from .BaseAPI import BaseAPI

class StockMarketTickDataAPI(BaseAPI):

    def get_stock_market_tick_data(self, api_token: str, symbol: str, from_timestamp: str, to_timestamp: str, limit: int):
        
        endpoint = 'ticks'

        query_string = ''

        if symbol is None:
            raise ValueError("symbol is empty. Need to add symbol to args")
        if from_timestamp is None:
            raise ValueError("from_timestamp is empty. Need to add from_timestamp to args")
        if to_timestamp is None:
            raise ValueError("to_timestamp is empty. Need to add to_timestamp to args")

        query_string += '&s=' + str(symbol)
        query_string += '&from=' + str(from_timestamp)
        query_string += '&to=' + str(to_timestamp)

        if limit is not None:
            query_string += '&limit=' + str(limit)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)