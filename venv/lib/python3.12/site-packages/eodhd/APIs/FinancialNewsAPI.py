from .BaseAPI import BaseAPI

class FinancialNewsAPI(BaseAPI):

    possible_tags = ['balance sheet', 'capital employed', 'class action', 'company announcement', 
                 'consensus eps estimate', 'consensus estimate', 'credit rating', 
                 'discounted cash flow', 'dividend payments', 'earnings estimate', 
                 'earnings growth', 'earnings per share', 'earnings release', 'earnings report', 
                 'earnings results', 'earnings surprise', 'estimate revisions', 'european regulatory news', 
                 'financial results', 'fourth quarter', 'free cash flow', 'future cash flows', 
                 'growth rate', 'initial public offering', 'insider ownership', 'insider transactions', 
                 'institutional investors', 'institutional ownership', 'intrinsic value', 
                 'market research reports', 'net income', 'operating income', 'present value', 
                 'press releases', 'price target', 'quarterly earnings', 'quarterly results', 
                 'ratings', 'research analysis and reports', 'return on equity', 'revenue estimates', 
                 'revenue growth', 'roce', 'roe', 'share price', 'shareholder rights', 'shareholder', 
                 'shares outstanding', 'strong buy', 'total revenue', 'zacks investment research', 'zacks rank']

    def financial_news(self, api_token: str, s = None, t = None, from_date = None, to_date = None, limit = None, offset = None):

        endpoint = 'news'

        query_string = ''

        if t is None and s is None:
            raise ValueError("s or t is empty. You need to add s or t to args")
        if t is not None and s is not None:
            query_string += '&s=' + str(s)
        elif s is not None and t is None:
            query_string += '&s=' + str(s)
        else:
            if t in self.possible_tags:
                query_string += '&t=' + str(t)
            else:
                raise ValueError("Incorrect value was fullfiled for s or t")
        if limit is not None:
          query_string += '&limit=' + str(limit)
        if offset is not None:
          query_string += '&offset=' + str(offset)
        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)

        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)
    
    def get_sentiment(self, api_token: str, s: str, from_date: str = None, to_date: str = None):

        endpoint = 'sentiments'

        query_string = ''

        if s is None:
            raise ValueError("s argument is empty. You need to add s to args")
        
        query_string += '&s=' + str(s)
        
        if from_date is not None:
            query_string += '&from=' + str(from_date)
        if to_date is not None:
            query_string += '&to=' + str(to_date)

        return self._rest_get_method(api_key = api_token, endpoint = endpoint, querystring = query_string)
