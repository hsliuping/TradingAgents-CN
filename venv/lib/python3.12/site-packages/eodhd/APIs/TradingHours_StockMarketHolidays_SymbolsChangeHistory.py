from .BaseAPI import BaseAPI

class TradingHours_StockMarketHolidays_SymbolsChangeHistoryAPI(BaseAPI):

    def get_details_trading_hours_stock_market_holidays(self, api_token: str, code, from_date = None, to_date = None):
        
        endpoint = 'exchange-details'
        uri = f'{code}'

        query_string = ''

        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)
        
        return self._rest_get_method(api_key = api_token, endpoint = endpoint, uri = uri, querystring = query_string)
    
    def symbol_change_history(self, api_token: str, from_date = None, to_date = None):

        endpoint = 'symbol-change-history'

        query_string = ''

        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)

        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)