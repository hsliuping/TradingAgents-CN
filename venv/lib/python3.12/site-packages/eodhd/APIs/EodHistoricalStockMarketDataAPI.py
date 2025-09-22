from .BaseAPI import BaseAPI

class EodHistoricalStockMarketDataAPI(BaseAPI):

    def get_eod_historical_stock_market_data(self, api_token: str, symbol: str, period: str, 
                                     from_date: str = None, to_date: str = None, order = None):

        possible_periods = ['d', 'w', 'm']
        
        endpoint = 'eod'

        if symbol.strip() == "" or symbol is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        if period not in possible_periods:
            raise ValueError("Interval must be in ['d', 'w', 'm'] values")
        
        uri = f'{symbol}'
        query_string = ''

        query_string += '&period=' + str(period)
        
        if from_date is not None: 
            query_string += '&from=' + str(from_date)
        if to_date is not None: 
            query_string += '&to=' + str(to_date)
        if order is not None: 
            query_string += '&order=' + str(order)

        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string, uri = uri)