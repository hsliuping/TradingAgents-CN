import json
import requests

from finnhub.exceptions import FinnhubAPIException
from finnhub.exceptions import FinnhubRequestException


class Client:
    API_URL = "https://api.finnhub.io/api/v1"
    DEFAULT_TIMEOUT = 10

    def __init__(self, api_key, proxies=None):
        self._session = self._init_session(api_key, proxies)

    @staticmethod
    def _init_session(api_key, proxies):
        session = requests.session()
        session.headers.update({"Accept": "application/json",
                                "User-Agent": "finnhub/python"})
        session.params["token"] = api_key
        if proxies is not None:
            session.proxies.update(proxies)

        return session

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _request(self, method, path, **kwargs):
        uri = "{}/{}".format(self.API_URL, path)
        kwargs["timeout"] = kwargs.get("timeout", self.DEFAULT_TIMEOUT)
        kwargs["params"] = self._format_params(kwargs.get("params", {}))

        response = getattr(self._session, method)(uri, **kwargs)
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response):
        if not response.ok:
            raise FinnhubAPIException(response)

        try:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            if 'text/csv' in content_type:
                return response.text
            if 'text/plain' in content_type:
                return response.text
            raise FinnhubRequestException("Invalid Response: {}".format(response.text))
        except ValueError:
            raise FinnhubRequestException("Invalid Response: {}".format(response.text))

    @staticmethod
    def _merge_two_dicts(first, second):
        result = first.copy()
        result.update(second)
        return result

    @staticmethod
    def _format_params(params):
        return {k: json.dumps(v) if isinstance(v, bool) else v for k, v in params.items()}

    def _get(self, path, **kwargs):
        return self._request("get", path, **kwargs)

    @property
    def api_key(self):
        return self._session.params.get("token")

    @api_key.setter
    def api_key(self, token):
        self._session.params["token"] = token

    def covid19(self):
        return self._get("/covid19/us")

    def company_profile(self, **params):
        return self._get("/stock/profile", params=params)

    def company_profile2(self, **params):
        return self._get("/stock/profile2", params=params)

    def aggregate_indicator(self, symbol, resolution):
        return self._get("/scan/technical-indicator", params={
            "symbol": symbol,
            "resolution": resolution,
        })

    def crypto_exchanges(self):
        return self._get("/crypto/exchange")

    def forex_exchanges(self):
        return self._get("/forex/exchange")

    def press_releases(self, symbol, _from=None, to=None):
        return self._get("/press-releases", params={
            "symbol": symbol,
            "from": _from,
            "to": to
        })

    def company_executive(self, symbol):
        return self._get("/stock/executive", params={"symbol": symbol})

    def stock_dividends(self, symbol, _from=None, to=None):
        return self._get("/stock/dividend", params={
            "symbol": symbol,
            "from": _from,
            "to": to
        })

    def stock_basic_dividends(self, symbol):
        return self._get("/stock/dividend2", params={"symbol": symbol})

    def stock_symbols(self, exchange, mic=None, security_type=None, currency=None):
        return self._get("/stock/symbol",
                         params={"exchange": exchange, 'mic': mic, 'securityType': security_type, 'currency': currency})

    def recommendation_trends(self, symbol):
        return self._get("/stock/recommendation", params={"symbol": symbol})

    def price_target(self, symbol):
        return self._get("/stock/price-target", params={"symbol": symbol})

    def upgrade_downgrade(self, symbol=None, _from=None, to=None):
        return self._get("/stock/upgrade-downgrade", params={'symbol': symbol, 'from': _from, 'to': to})

    def option_chain(self, **params):
        return self._get("/stock/option-chain", params=params)

    def company_peers(self, symbol):
        return self._get("/stock/peers", params={"symbol": symbol})

    def company_basic_financials(self, symbol, metric):
        return self._get("/stock/metric", params={
            "symbol": symbol,
            "metric": metric
        })

    def financials(self, symbol, statement, freq):
        return self._get("/stock/financials", params={
            "symbol": symbol,
            "statement": statement,
            "freq": freq
        })

    def financials_reported(self, **params):
        return self._get("/stock/financials-reported", params=params)

    def fund_ownership(self, symbol, limit=None):
        return self._get("/stock/fund-ownership", params={
            "symbol": symbol,
            "limit": limit
        })

    def company_earnings(self, symbol, limit=None):
        return self._get("/stock/earnings", params={
            "symbol": symbol,
            "limit": limit
        })

    def company_revenue_estimates(self, symbol, freq=None):
        return self._get("/stock/revenue-estimate", params={
            "symbol": symbol,
            "freq": freq
        })

    def company_ebitda_estimates(self, symbol, freq=None):
        return self._get("/stock/ebitda-estimate", params={
            "symbol": symbol,
            "freq": freq
        })

    def company_ebit_estimates(self, symbol, freq=None):
        return self._get("/stock/ebit-estimate", params={
            "symbol": symbol,
            "freq": freq
        })

    def company_eps_estimates(self, symbol, freq=None):
        return self._get("/stock/eps-estimate", params={
            "symbol": symbol,
            "freq": freq
        })

    def exchange(self):
        return self._get("/stock/exchange")

    def filings(self, symbol='', cik='', access_number='', form='', _from='', to=''):
        return self._get("/stock/filings",
                         params={"symbol": symbol, "cik": cik, "accessNumber": access_number, "form": form,
                                 "from": _from, "to": to})

    def stock_symbol(self, **params):
        return self._get("/stock/symbol", params=params)

    def quote(self, symbol):
        return self._get("/quote", params={
            "symbol": symbol
        })

    def transcripts(self, _id):
        return self._get("/stock/transcripts", params={"id": _id})

    def transcripts_list(self, symbol):
        return self._get("/stock/transcripts/list", params={"symbol": symbol})

    def sim_index(self, **params):
        return self._get("/stock/similarity-index", params=params)

    def stock_candles(self, symbol, resolution, _from, to, **kwargs):
        params = self._merge_two_dicts({
            "symbol": symbol,
            "resolution": resolution,
            "from": _from,
            "to": to
        }, kwargs)

        return self._get("/stock/candle", params=params)

    def stock_tick(self, symbol, date, limit, skip, _format='json', **kwargs):
        params = self._merge_two_dicts({
            "symbol": symbol,
            "date": date,
            "limit": limit,
            "skip": skip,
            "format": _format
        }, kwargs)

        return self._get("/stock/tick", params=params)

    def stock_nbbo(self, symbol, date, limit, skip, _format='json', **kwargs):
        params = self._merge_two_dicts({
            "symbol": symbol,
            "date": date,
            "limit": limit,
            "skip": skip,
            "format": _format
        }, kwargs)

        return self._get("/stock/bbo", params=params)

    def forex_rates(self, **params):
        return self._get("/forex/rates", params=params)

    def forex_symbols(self, exchange):
        return self._get("/forex/symbol", params={
            "exchange": exchange
        })

    def forex_candles(self, symbol, resolution, _from, to, _format='json'):
        return self._get("/forex/candle", params={
            "symbol": symbol,
            "resolution": resolution,
            "from": _from,
            "to": to,
            "format": _format
        })

    def crypto_symbols(self, exchange):
        return self._get("/crypto/symbol", params={"exchange": exchange})

    def crypto_candles(self, symbol, resolution, _from, to, _format='json'):
        return self._get("/crypto/candle", params={
            "symbol": symbol,
            "resolution": resolution,
            "from": _from,
            "to": to,
            "format": _format
        })

    def pattern_recognition(self, symbol, resolution):
        return self._get("/scan/pattern", params={
            "symbol": symbol,
            "resolution": resolution
        })

    def support_resistance(self, symbol, resolution):
        return self._get("/scan/support-resistance", params={
            "symbol": symbol,
            "resolution": resolution
        })

    def technical_indicator(self, symbol, resolution, _from, to, indicator, indicator_fields=None):
        indicator_fields = indicator_fields or {}
        params = self._merge_two_dicts({
            "symbol": symbol,
            "resolution": resolution,
            "from": _from,
            "to": to,
            "indicator": indicator
        }, indicator_fields)

        return self._get("/indicator", params=params)

    def stock_splits(self, symbol, _from, to):
        return self._get("/stock/split", params={
            "symbol": symbol,
            "from": _from,
            "to": to
        })

    def general_news(self, category, min_id=0):
        return self._get("/news", params={
            "category": category,
            "minId": min_id
        })

    def company_news(self, symbol, _from, to):
        return self._get("/company-news", params={
            "symbol": symbol,
            "from": _from,
            "to": to
        })

    def news_sentiment(self, symbol):
        return self._get("/news-sentiment", params={
            "symbol": symbol
        })

    def ownership(self, symbol, limit=None):
        return self._get("/stock/ownership", params={
            "symbol": symbol,
            "limit": limit
        })

    def country(self):
        return self._get("/country")

    def economic_code(self):
        return self._get("/economic/code")

    def economic_data(self, code):
        return self._get("/economic", params={"code": code})

    def calendar_economic(self, _from=None, to=None):
        return self._get("/calendar/economic", params={
            "from": _from,
            "to": to
        })

    def earnings_calendar(self, _from, to, symbol, international=False):
        return self._get("/calendar/earnings", params={
            "from": _from,
            "to": to,
            "symbol": symbol,
            "international": international
        })

    def ipo_calendar(self, _from, to):
        return self._get("/calendar/ipo", params={
            "from": _from,
            "to": to
        })

    def indices_const(self, **params):
        return self._get("/index/constituents", params=params)

    def indices_hist_const(self, **params):
        return self._get("/index/historical-constituents", params=params)

    def etfs_profile(self, symbol=None, isin=None):
        return self._get("/etf/profile", params={"symbol": symbol, "isin": isin})

    def etfs_holdings(self, symbol=None, isin=None, skip=None, date=None):
        return self._get("/etf/holdings", params={"symbol": symbol, "isin": isin, "skip": skip, "date": date})

    def etfs_sector_exp(self, symbol):
        return self._get("/etf/sector", params={"symbol": symbol})

    def etfs_country_exp(self, symbol):
        return self._get("/etf/country", params={"symbol": symbol})

    def international_filings(self, symbol="", country=""):
        return self._get("/stock/international-filings", params={"symbol": symbol, "country": country})

    def sec_sentiment_analysis(self, access_number):
        return self._get("/stock/filings-sentiment", params={"accessNumber": access_number})

    def sec_similarity_index(self, symbol="", cik="", freq="annual"):
        return self._get("/stock/similarity-index", params={"symbol": symbol, "cik": cik, "freq": freq})

    def last_bid_ask(self, symbol):
        return self._get("/stock/bidask", params={"symbol": symbol})

    def fda_calendar(self):
        return self._get("/fda-advisory-committee-calendar")

    def symbol_lookup(self, query):
        return self._get("/search", params={"q": query})

    def stock_insider_transactions(self, symbol, _from=None, to=None):
        return self._get("/stock/insider-transactions", params={"symbol": symbol, "from": _from, "to": to})

    def mutual_fund_profile(self, symbol=None, isin=None):
        return self._get("/mutual-fund/profile", params={"symbol": symbol, "isin": isin})

    def mutual_fund_holdings(self, symbol=None, isin=None, skip=None):
        return self._get("/mutual-fund/holdings", params={"symbol": symbol, "isin": isin, "skip": skip})

    def mutual_fund_sector_exp(self, symbol):
        return self._get("/mutual-fund/sector", params={"symbol": symbol})

    def mutual_fund_country_exp(self, symbol):
        return self._get("/mutual-fund/country", params={"symbol": symbol})

    def mutual_fund_eet(self, isin):
        return self._get("/mutual-fund/eet", params={"isin": isin})

    def mutual_fund_eet_pai(self, isin):
        return self._get("/mutual-fund/eet-pai", params={"isin": isin})

    def stock_revenue_breakdown(self, symbol, cik=""):
        return self._get("/stock/revenue-breakdown", params={"symbol": symbol, "cik": cik})

    def stock_social_sentiment(self, symbol, _from=None, to=None):
        return self._get("/stock/social-sentiment", params={"symbol": symbol, "from": _from, "to": to})

    def stock_investment_theme(self, theme):
        return self._get("/stock/investment-theme", params={"theme": theme})

    def stock_supply_chain(self, symbol):
        return self._get("/stock/supply-chain", params={"symbol": symbol})

    def company_esg_score(self, symbol):
        return self._get("/stock/esg", params={"symbol": symbol})

    def company_historical_esg_score(self, symbol):
        return self._get("/stock/historical-esg", params={"symbol": symbol})

    def historical_market_cap(self, symbol, _from=None, to=None):
        return self._get("/stock/historical-market-cap", params={"symbol": symbol, "from": _from, "to": to})

    def company_earnings_quality_score(self, symbol, freq):
        return self._get("/stock/earnings-quality-score", params={"symbol": symbol, 'freq': freq})

    def crypto_profile(self, symbol):
        return self._get("/crypto/profile", params={"symbol": symbol})

    def stock_uspto_patent(self, symbol, _from=None, to=None):
        return self._get("/stock/uspto-patent", params={"symbol": symbol, "from": _from, "to": to})

    def stock_visa_application(self, symbol, _from=None, to=None):
        return self._get("/stock/visa-application", params={"symbol": symbol, "from": _from, "to": to})

    def stock_insider_sentiment(self, symbol, _from, to):
        return self._get("/stock/insider-sentiment", params={"symbol": symbol, "from": _from, "to": to})

    def stock_lobbying(self, symbol, _from, to):
        return self._get("/stock/lobbying", params={"symbol": symbol, "from": _from, "to": to})

    def bond_profile(self, **params):
        return self._get("/bond/profile", params=params)

    def bond_price(self, isin, _from, to):
        return self._get("/bond/price", params={"isin": isin, "from": _from, "to": to})

    def stock_usa_spending(self, symbol, _from, to):
        return self._get("/stock/usa-spending", params={"symbol": symbol, "from": _from, "to": to})

    def sector_metric(self, region):
        return self._get("/sector/metrics", params={"region": region})

    def price_metrics(self, symbol, date=''):
        return self._get("/stock/price-metric", params={"symbol": symbol, "date": date})

    def symbol_change(self, _from, to):
        return self._get("/ca/symbol-change", params={"from": _from, "to": to})

    def isin_change(self, _from, to):
        return self._get("/ca/isin-change", params={"from": _from, "to": to})

    def institutional_profile(self, cik=''):
        return self._get("/institutional/profile", params={"cik": cik})

    def institutional_portfolio(self, cik, _from, to):
        return self._get("/institutional/portfolio", params={"cik": cik, "from": _from, "to": to})

    def institutional_ownership(self, symbol, cusip, _from, to):
        return self._get("/institutional/ownership", params={"symbol": symbol, "cusip": cusip, "from": _from, "to": to})

    def congressional_trading(self, symbol, _from, to):
        return self._get("/stock/congressional-trading", params={"symbol": symbol, "from": _from, "to": to})

    def bond_tick(self, isin, date, limit, skip, exchange='trace', _format='json', **kwargs):
        params = self._merge_two_dicts({
            "isin": isin,
            "date": date,
            "limit": limit,
            "skip": skip,
            "exchange": exchange,
            "format": _format
        }, kwargs)

        return self._get("/bond/tick", params=params)

    def bond_yield_curve(self, code):
        return self._get("/bond/yield-curve", params={'code': code})

    def market_status(self, exchange):
        return self._get("/stock/market-status", params={'exchange': exchange})

    def market_holiday(self, exchange):
        return self._get("/stock/market-holiday", params={'exchange': exchange})

    def historical_employee_count(self, symbol, _from, to):
        return self._get("/stock/historical-employee-count", params={"symbol": symbol, "from": _from, "to": to})

    def airline_price_index(self, airline, _from, to):
        return self._get("/airline/price-index", params={"airline": airline, "from": _from, "to": to})

    def earnings_call_live(self, _from, to, symbol=""):
        return self._get("/stock/earnings-call-live", params={"symbol": symbol, "from": _from, "to": to})

    def stock_presentation(self, symbol):
        return self._get("/stock/presentation", params={"symbol": symbol})

    def stock_revenue_breakdown2(self, symbol):
        return self._get("/stock/revenue-breakdown2", params={"symbol": symbol})

    def bank_branch(self, symbol):
        return self._get("/bank-branch", params={"symbol": symbol})
