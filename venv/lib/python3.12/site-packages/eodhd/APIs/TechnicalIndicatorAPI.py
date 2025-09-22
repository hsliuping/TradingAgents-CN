from .BaseAPI import BaseAPI



class TechnicalIndicatorAPI(BaseAPI):

    possible_functions = ['avgvol', 'avgvolccy', 'sma', 'ema', 'wma', 'volatility', 'stochastic',
                        'rsi', 'stddev', 'stochrsi', 'slope', 'dmi', 'adx', 'macd', 'atr',
                        'cci', 'sar', 'bbands', 'format_amibroker', 'splitadjusted']

    def get_technical_indicator_data(self, api_token: str, ticker: str, function: str, period: int = 50,
                                     date_from: str = None, date_to: str = None, order: str = 'a', 
                                     splitadjusted_only: str = '0', agg_period = None,
                                     fast_kperiod = None, slow_kperiod = None, slow_dperiod = None,
                                     fast_dperiod = None, fast_period = None, slow_period = None,
                                     signal_period = None, acceleration = None, maximum = None):
        endpoint = 'technical/'

        if ticker.strip() == "" or ticker is None:
            raise ValueError("Ticker is empty. You need to add ticker to args")
        
        if function.strip() == "" or function is None:
            raise ValueError("Function is empty. You need to add function to args")
        
        if function not in self.possible_functions:
            raise ValueError("Incorrect value for fanction parameter")
        
        query_string = f'&order={order}&splitadjusted_only={splitadjusted_only}&period={period}&function={function}'
        
        if date_to is not None:
            query_string += "&to=" + str(date_to)
        if date_from is not None:
            query_string += "&from=" + str(date_from)

        if function == 'splitadjusted':
            possible_agg_period = ['d', 'w', 'm']
            if agg_period is not None:
                if agg_period not in possible_agg_period:
                    raise ValueError("agg_period must be in ['d', 'w', 'm']")
                query_string += "&agg_period=" + str(agg_period)

        if function == 'stochastic':
            if fast_kperiod is not None:
                query_string += "&fast_kperiod=" + str(fast_kperiod)
            if slow_kperiod is not None:
                query_string += "&slow_kperiod=" + str(slow_kperiod)
            if slow_dperiod is not None:
                query_string += "&slow_dperiod=" + str(slow_dperiod)

        if function == 'stochrsi':
            if fast_kperiod is not None:
                query_string += "&fast_kperiod=" + str(fast_kperiod)
            if fast_dperiod is not None:
                query_string += "&fast_dperiod=" + str(fast_dperiod)
        
        if function == 'macd':
            if fast_period is not None:
                query_string += "&fast_period=" + str(fast_period)
            if slow_period is not None:
                query_string += "&slow_period=" + str(slow_period)
            if signal_period is not None:
                query_string += "&signal_period=" + str(signal_period)

        if function == 'sar':
            if acceleration is not None:
                query_string += "&acceleration=" + str(acceleration)
            if maximum is not None:
                query_string += "&maximum=" + str(maximum)

        return self._rest_get_method(api_key = api_token, endpoint = endpoint, uri = ticker, querystring = query_string)




