"""apiclient.py"""

from json.decoder import JSONDecodeError
import sys
from enum import Enum
from datetime import datetime
from datetime import timedelta
from re import compile as re_compile
import pandas as pd
import numpy as np
from requests import get as requests_get
from requests import ConnectionError as requests_ConnectionError
from requests import Timeout as requests_Timeout
from requests.exceptions import HTTPError as requests_HTTPError
from rich.console import Console
from rich.progress import track

from eodhd.APIs import HistoricalDividendsAPI
from eodhd.APIs import HistoricalSplitsAPI
from eodhd.APIs import TechnicalIndicatorAPI
from eodhd.APIs import LiveStockPricesAPI
from eodhd.APIs import EconomicEventsDataAPI
from eodhd.APIs import InsiderTransactionsAPI
from eodhd.APIs import FundamentalDataAPI
from eodhd.APIs import BulkEodSplitsDividendsDataAPI
from eodhd.APIs import UpcomgingEarningsAPI
from eodhd.APIs import EarningTrendsAPI
from eodhd.APIs import UpcomingIPOsAPI
from eodhd.APIs import UpcomingSplitsAPI
from eodhd.APIs import MacroIndicatorsAPI
from eodhd.APIs import BondsFundamentalsAPI
from eodhd.APIs import ListOfExchangesAPI
from eodhd.APIs import TradingHours_StockMarketHolidays_SymbolsChangeHistoryAPI
from eodhd.APIs import StockMarketScreenerAPI
from eodhd.APIs import FinancialNewsAPI
from eodhd.APIs import OptionsDataAPI
from eodhd.APIs import IntradayDataAPI
from eodhd.APIs import EodHistoricalStockMarketDataAPI
from eodhd.APIs import StockMarketTickDataAPI
from eodhd.APIs import HistoricalMarketCapitalization

# minimal traceback
sys.tracebacklimit = 1


class Interval(Enum):
    """Enum: infraday"""

    MINUTE = "1m"
    FIVEMINUTES = "5m"
    HOUR = "1h"
    ONEDAY = "d"
    WEEK = "w"
    MONTH = "m"


class DateUtils:
    """Utility class"""

    @staticmethod
    def str2datetime(_datetime: str):
        """Convert yyyy-mm-dd hh:mm:ss to datetime"""

        # Validate string datetime
        prog = re_compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        if not prog.match(_datetime):
            raise ValueError("Incorrect datetime format: yyyy-mm-dd hh:mm:ss")

        return datetime.strptime(_datetime, "%Y-%m-%d %H:%M:%S")

    @staticmethod
    def str2epoch(_datetime: str):
        """Convert yyyy-mm-dd hh:mm:ss to datetime"""

        # Validate string datetime
        prog = re_compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        if not prog.match(_datetime):
            raise ValueError("Incorrect datetime format: yyyy-mm-dd hh:mm:ss")

        return int(datetime.strptime(_datetime, "%Y-%m-%d %H:%M:%S").timestamp())

    @staticmethod
    def previous_day_last_second():
        """Returns the last second of the previous day"""

        yesterday = datetime.today() - timedelta(days=1)
        return str(yesterday.date()) + " 23:59:59"

    @staticmethod
    def previous_day_last_minute():
        """Returns the last minute of the previous day"""

        yesterday = datetime.today() - timedelta(days=1)
        return str(yesterday.date()) + " 23:59:00"


class APIClient:
    """API class"""

    def __init__(self, api_key: str) -> None:
        # Validate API key
        prog = re_compile(r"^[A-z0-9.]{16,32}$")
        if api_key != "demo" and not prog.match(api_key):
            raise ValueError("API key is invalid")

        self._api_key = api_key
        self._api_url = "https://eodhd.com/api"

        self.console = Console()

    def _rest_get(self, endpoint: str = "", uri: str = "", querystring: str = "") -> pd.DataFrame():
        """Generic REST GET"""

        if endpoint.strip() == "":
            raise ValueError("endpoint is empty!")

        try:
            resp = requests_get(f"{self._api_url}/{endpoint}/{uri}?api_token={self._api_key}&fmt=json{querystring}")

            if resp.status_code != 200:
                try:
                    if "message" in resp.json():
                        resp_message = resp.json()["message"]
                    elif "errors" in resp.json():
                        self.console.log(resp.json())
                        sys.exit(1)
                    else:
                        resp_message = ""

                    message = f"({resp.status_code}) {self._api_url} - {resp_message}"
                    self.console.log(message)

                except JSONDecodeError as err:
                    self.console.log(err)

            try:
                resp.raise_for_status()

                if isinstance(resp.json(), list):
                    return pd.DataFrame.from_dict(resp.json())
                else:
                    return pd.DataFrame(resp.json(), index=[0])

            except ValueError as err:
                self.console.log(err)

        except requests_ConnectionError as err:
            self.console.log(err)
        except requests_HTTPError as err:
            self.console.log(err)
        except requests_Timeout as err:
            self.console.log(err)
        return pd.DataFrame()

    def get_exchanges(self) -> pd.DataFrame:
        """Get supported exchanges"""

        return self._rest_get("exchanges-list")

    def get_exchange_symbols(self, uri: str = "", delisted=False) -> pd.DataFrame:
        """Get supported exchange symbols"""

        try:
            if uri.strip() == "":
                raise ValueError("endpoint uri is empty!")

            if delisted:
                return self._rest_get("exchange-symbol-list", uri, "&delisted=1")

            return self._rest_get("exchange-symbol-list", uri)
        except ValueError as err:
            self.console.log(err)
            return pd.DataFrame()

    def get_historical_data(
        self,
        symbol: str,
        interval: str = Interval,
        iso8601_start: str = "",
        iso8601_end: str = "",
        results: int = 300,
    ) -> pd.DataFrame:
        """Initiates a REST API call"""

        # validate symbol
        prog = re_compile(r"^[A-z0-9-$\.+]{1,48}$")
        if not prog.match(symbol):
            raise ValueError(f"Symbol is invalid: {symbol}")

        # replace "." with "-" in markets
        if symbol.count(".") == 2:
            symbol = symbol.replace(".", "-", 1)

        # validate interval
        try:
            Interval(interval)
        except ValueError as err:
            self.console.log(err)
            return pd.DataFrame()

        # init dataframe
        df_data = pd.DataFrame()

        if interval == "d" or interval == "w" or interval == "m":
            # api expects epoch time

            re_date_only = re_compile(r"^\d{4}\-\d{2}-\d{2}$")
            re_iso8601 = re_compile(r"^\d{4}\-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

            if iso8601_end == "" or ((iso8601_end != "" and not re_iso8601.match(iso8601_end)) and (iso8601_end != "" and not re_date_only.match(iso8601_end))):
                date_to = datetime.today().date()
            else:
                try:
                    if re_date_only.match(iso8601_end):
                        date_to = datetime.strptime(iso8601_end, "%Y-%m-%d").date()
                    elif re_iso8601.match(iso8601_end):
                        date_to = datetime.strptime(iso8601_end, "%Y-%m-%dT%H:%M:%S").date()
                    else:
                        date_to = datetime.today().date()
                except ValueError:
                    self.console.log("invalid end date (yyyy-mm-ddThh-mm-ss OR yyyy-mm-dd):", iso8601_end)
                    sys.exit()

            if iso8601_start == "" or ((iso8601_start != "" and not re_iso8601.match(iso8601_start)) and (iso8601_start != "" and not re_date_only.match(iso8601_start))):
                if interval == "1m":
                    date_from = date_to - timedelta(minutes=(results - 1))
                elif interval == "5m":
                    date_from = date_to - timedelta(minutes=((results * 5) - 1))
                elif interval == "1h":
                    date_from = date_to - timedelta(hours=(results - 1))
                else:
                    date_from = date_to - timedelta(days=(results - 1))
            else:
                try:
                    if re_date_only.match(iso8601_start):
                        date_from = datetime.strptime(iso8601_start, "%Y-%m-%d").date()
                    elif re_iso8601.match(iso8601_start):
                        date_from = datetime.strptime(iso8601_start, "%Y-%m-%dT%H:%M:%S").date()
                    else:
                        date_from = datetime.today().date()
                except ValueError:
                    self.console.log("invalid start date (yyyy-mm-ddThh-mm-ss OR yyyy-mm-dd):", iso8601_start)
                    sys.exit()

            df_data = self._rest_get("eod", symbol, f"&period={interval}&from={str(date_from)}&to={str(date_to)}")

            if len(df_data) == 0:
                columns_eod = [
                    "symbol",
                    "interval",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adjusted_close",
                    "volume",
                ]
                return pd.DataFrame(columns=columns_eod)

            if iso8601_start == "" and iso8601_end == "":
                df_data = df_data.tail(results)
            elif iso8601_start != "" and iso8601_end == "":
                df_data = df_data.head(results)

            df_data["symbol"] = symbol
            df_data["interval"] = interval

            # convert dataframe to a time series
            if interval == "d" or interval == "w" or interval == "m":
                tsidx = pd.DatetimeIndex(pd.to_datetime(df_data["date"]).dt.strftime("%Y-%m-%d"))
                df_data.set_index(tsidx, inplace=True)
                df_data = df_data.drop(columns=["date"])
            else:
                tsidx = pd.DatetimeIndex(pd.to_datetime(df_data["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S"))
                df_data.set_index(tsidx, inplace=True)
                df_data = df_data.drop(columns=["datetime"])

            df_data.columns = [
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "symbol",
                "interval",
            ]

            # set object type to display large floats
            df_data.fillna(0, inplace=True)
            df_data["open"] = df_data["open"].astype(object)
            df_data["high"] = df_data["high"].astype(object)
            df_data["low"] = df_data["low"].astype(object)
            df_data["close"] = df_data["close"].astype(object)
            df_data["adjusted_close"] = df_data["adjusted_close"].astype(object)
            df_data["volume"] = df_data["volume"].astype(object)

            return df_data[
                [
                    "symbol",
                    "interval",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adjusted_close",
                    "volume",
                ]
            ]

        elif interval == "1m" or interval == "5m" or interval == "1h":
            # api expects date in yyyy-mm-dd format

            re_date_only = re_compile(r"^\d{4}\-\d{2}-\d{2}$")
            re_iso8601 = re_compile(r"^\d{4}\-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
            re_epoch = re_compile(r"^\d{10}$")

            if iso8601_end == "" or ((iso8601_end != "" and not re_iso8601.match(iso8601_end)) and (iso8601_end != "" and not re_date_only.match(iso8601_end))):
                date_to = str(int(datetime.today().timestamp()))
            else:
                try:
                    if re_date_only.match(iso8601_end):
                        date_to = str(int(datetime.strptime(iso8601_end, "%Y-%m-%d").timestamp()))
                    elif re_iso8601.match(iso8601_end):
                        date_to = str(int(datetime.strptime(iso8601_end, "%Y-%m-%dT%H:%M:%S").timestamp()))
                    elif re_epoch.match(iso8601_end):
                        date_to = str(iso8601_end)
                    else:
                        date_to = str(int(datetime.today().timestamp()))
                except ValueError:
                    self.console.log("invalid end date (yyyy-mm-ddThh-mm-ss OR yyyy-mm-dd OR nnnnnnnnnn):", iso8601_end)
                    sys.exit()
            
            LIMIT_FOR_1M = 120 # Limit for 1m interval
            if iso8601_start == "" or ((iso8601_start != "" and not re_iso8601.match(iso8601_start)) and (iso8601_start != "" and not re_date_only.match(iso8601_start))):
                if interval == "d":
                    date_from = str(int((datetime.fromtimestamp(int(date_to)) - timedelta(days=(results - 1))).timestamp()))
                elif interval == "w":
                    date_from = str(int((datetime.fromtimestamp(int(date_to)) - timedelta(weeks=((results - 1) - 1))).timestamp()))
                elif interval == "m":
                    date_from = str(int((datetime.fromtimestamp(int(date_to)) - timedelta(months=(results - 1))).timestamp()))
                else:
                    date_from = str(int((datetime.fromtimestamp(int(date_to)) - timedelta(days=(LIMIT_FOR_1M))).timestamp()))
            else:
                try:
                    if re_date_only.match(iso8601_start):
                        date_from = str(int(datetime.strptime(iso8601_start, "%Y-%m-%d").timestamp()))
                    elif re_iso8601.match(iso8601_start):
                        date_from = str(int(datetime.strptime(iso8601_start, "%Y-%m-%dT%H:%M:%S").timestamp()))
                    else:
                        date_from = str(int(datetime.today().timestamp()))
                except ValueError:
                    self.console.log("invalid start date (yyyy-mm-ddThh-mm-ss OR yyyy-mm-dd OR nnnnnnnnnn):", iso8601_start)
                    sys.exit()

            df_data = self._rest_get("intraday", symbol, f"&interval={interval}&from={str(date_from)}&to={str(date_to)}")

            if len(df_data) == 0:
                columns_eod = [
                    "symbol",
                    "interval",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adjusted_close",
                    "volume",
                ]
                return pd.DataFrame(columns=columns_eod)

            if iso8601_start == "" and iso8601_end == "":
                df_data = df_data.tail(results)
            elif iso8601_start != "" and iso8601_end == "":
                df_data = df_data.head(results)

            df_data["symbol"] = symbol
            df_data["interval"] = interval

            # convert dataframe to a time series
            if interval == "d" or interval == "w" or interval == "m":
                tsidx = pd.DatetimeIndex(pd.to_datetime(df_data["date"]).dt.strftime("%Y-%m-%d"))
                df_data.set_index(tsidx, inplace=True)
                df_data = df_data.drop(columns=["date"])
            else:
                tsidx = pd.DatetimeIndex(pd.to_datetime(df_data["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S"))
                df_data.set_index(tsidx, inplace=True)
                df_data = df_data.drop(columns=["datetime"])

            df_data.columns = [
                "epoch",
                "gmtoffset",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "symbol",
                "interval",
            ]

            # set object type to display large floats
            df_data.fillna(0, inplace=True)
            df_data["gmtoffset"] = df_data["gmtoffset"].astype(object)
            df_data["epoch"] = df_data["epoch"].astype(object)
            df_data["open"] = df_data["open"].astype(object)
            df_data["high"] = df_data["high"].astype(object)
            df_data["low"] = df_data["low"].astype(object)
            df_data["close"] = df_data["close"].astype(object)
            df_data["volume"] = df_data["volume"].astype(object)

            return df_data[
                [
                    "epoch",
                    "gmtoffset",
                    "symbol",
                    "interval",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ]

        else:
            self.console.log("invalid interval (1m, 5m, 1h, 1d, w, m):", iso8601_start)
            sys.exit()

    def get_historical_dividends_data(self, ticker, date_to=None, date_from=None) -> list:
        """Available args:
        ticker (required) - consists of two parts: [SYMBOL_NAME].[EXCHANGE_ID]. Example: AAPL.US
        date_from (not required) - date from with format Y-m-d. Example: 2000-01-01
        date_to (not required) - date from with format Y-m-d. Example: 2000-01-01
        If you skip date_from or date_to then you’ll get the maximum available data for the symbol.
        For more information visit: https://eodhistoricaldata.com/financial-apis/api-splits-dividends/
        """

        api_call = HistoricalDividendsAPI()
        return api_call.get_historical_dividends_data(api_token=self._api_key, ticker=ticker, date_from=date_from, date_to=date_to)

    def get_historical_splits_data(self, ticker, date_to=None, date_from=None) -> list:
        """Available args:
        ticker (required) - consists of two parts: [SYMBOL_NAME].[EXCHANGE_ID]. Example: AAPL.US
        date_from (not required) - date from with format Y-m-d. Example: 2000-01-01
        date_to (not required) - date from with format Y-m-d. Example: 2000-01-01
        If you skip date_from or date_to then you’ll get the maximum available data for the symbol.
        For more information visit: https://eodhistoricaldata.com/financial-apis/api-splits-dividends/
        """

        api_call = HistoricalSplitsAPI()
        return api_call.get_historical_splits_data(api_token=self._api_key, ticker=ticker, date_from=date_from, date_to=date_to)

    def get_technical_indicator_data(
        self,
        ticker: str,
        function: str,
        period: int = 50,
        date_from: str = None,
        date_to: str = None,
        order: str = "a",
        splitadjusted_only: str = "0",
        agg_period: str = None,
        fast_kperiod: int = None,
        slow_kperiod: int = None,
        slow_dperiod: int = None,
        fast_dperiod: int = None,
        fast_period: int = None,
        slow_period: int = None,
        signal_period: int = None,
        acceleration: float = None,
        maximum: float = None
    ) -> list:
        """Available args:
        ticker (required) - consists of two parts: [SYMBOL_NAME].[EXCHANGE_ID]. Example: AAPL.US
        function (required) – the function that will be applied to data series to get technical indicator data.
            All possible values for function parameter:
                                    ['avgvol', 'avgvolccy', 'sma', 'ema', 'wma', 'volatility', 'stochastic',
                                    'rsi', 'stddev', 'stochrsi', 'slope', 'dmi', 'adx', 'macd', 'atr',
                                    'cci', 'sar', 'bbands', 'format_amibroker', 'splitadjusted']
            Description for possible functions you get here:
            https://eodhistoricaldata.com/financial-apis/technical-indicators-api/
        period - the number of data points used to calculate each moving average value.
            Valid range from 2 to 100000 with the default value - 50.
        date_from (not required) - date from with format Y-m-d. Example: 2000-01-01
        date_to (not required) - date from with format Y-m-d. Example: 2000-01-01
        order - use 'a' for ascending dates (from old to new) and 'd' for descending dates (from new to old).
            By default, dates are shown in ascending order.
        splitadjusted_only - default value is '0'.
            By default, we calculate data for some functions by closes adjusted with splits and dividends.
            If you need to calculate the data by closes adjusted only with splits, set this parameter to '1'.
            Works with the following functions: sma, ema, wma, volatility, rsi, slope, and macd.

        For some functions can be used additional parameters:
        1. For splitadjusted:
            agg_period [optional] – aggregation period. Default value – 'd'. Possible values: d – daily, w – weekly, m – monthly.
        2. For stochastic:
            fast_kperiod [optional] – Fast K-period, the default value is 14. Valid range from 2 to 100000.
            slow_kperiod [optional] – Slow K-period, the default value is 3. Valid range from 2 to 100000.
            slow_dperiod [optional] – Slow D-period, the default value is 3. Valid range from 2 to 100000.
        3. For stochrsi:
            fast_kperiod [optional] – Fast K-period, the default value is 14. Valid range from 2 to 100000.
            fast_dperiod [optional] – Fast D-period, the default value is 14. Valid range from 2 to 100000.
        4. For macd:
            fast_period [optional] – the default value is 12. Valid range from 2 to 100000.
            slow_period [optional] – the default value is 26. Valid range from 2 to 100000.
            signal_period [optional] – the default value is 9. Valid range from 2 to 100000.
        5. For sar:
            acceleration [optional] – Acceleration Factor used up to the Maximum value. Default value – 0.02.
            maximum [optional] – Acceleration Factor Maximum value. Default value – 0.20.
        For those functions use this parameters to set periods.
        """

        api_call = TechnicalIndicatorAPI()
        return api_call.get_technical_indicator_data(
            api_token=self._api_key,
            ticker=ticker,
            function=function,
            period=period,
            date_from=date_from,
            date_to=date_to,
            order=order,
            splitadjusted_only=splitadjusted_only,
            agg_period=agg_period,
            fast_kperiod=fast_kperiod,
            slow_kperiod=slow_kperiod,
            slow_dperiod=slow_dperiod,
            fast_dperiod=fast_dperiod,
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            acceleration=acceleration,
            maximum=maximum
        )

    def get_live_stock_prices(self, ticker, date_to=None, date_from=None, s=None) -> list:
        """Available args:
        ticker (required) - consists of two parts: [SYMBOL_NAME].[EXCHANGE_ID]. Example: AAPL.US
        s (not required) - add “s=” parameter to your function and you will be able to get data for multiple
            tickers at one request, all tickers should be separated with a comma. For example:
            api.get_live_stock_prices(ticker = "AAPL.US", s="VTI,EUR.FOREX")
        For more information visit: https://eodhistoricaldata.com/financial-apis/live-realtime-stocks-api/
        """

        api_call = LiveStockPricesAPI()
        return api_call.get_live_stock_prices(api_token=self._api_key, ticker=ticker, s=s)

    def get_economic_events_data(
        self,
        date_from: str = None,
        date_to: str = None,
        country: str = None,
        comparison: str = None,
        offset: int = None,
        limit: int = None,
    ) -> list:
        """Available args:
        date_from (not required) - date from with format Y-m-d. Example: 2000-01-01
        date_to (not required) - date from with format Y-m-d. Example: 2000-01-01
        country (not required) - The country code is in ISO 3166 format, has 2 symbols
        comparison (not required) - Possible values: mom, qoq, yoy
        offset (not required) - Possible values from 0 to 1000. Default value: 0
        limit (not required) - Possible values from 0 to 1000. Default value: 50.
        For more information visit: https://eodhistoricaldata.com/financial-apis/economic-events-data-api/
        """

        api_call = EconomicEventsDataAPI()
        return api_call.get_economic_events_data(
            api_token=self._api_key,
            date_from=date_from,
            date_to=date_to,
            country=country,
            comparison=comparison,
            offset=offset,
            limit=limit,
        )

    def get_insider_transactions_data(
        self,
        date_from: str = None,
        date_to: str = None,
        code: str = None,
        limit: int = None,
    ) -> list:
        """Available args:
        date_from (not required) - date from with format Y-m-d. Example: 2000-01-01
        date_to (not required) - date from with format Y-m-d. Example: 2000-01-01
        code (not required) - to get the data only for Apple Inc (AAPL), use AAPL.US or AAPL ticker code.
            By default, all possible symbols will be displayed.
        limit (not required) - the limit for entries per result, from 1 to 1000. Default value: 100.
        For more information visit: https://eodhistoricaldata.com/financial-apis/insider-transactions-api/
        """

        api_call = InsiderTransactionsAPI()
        return api_call.get_insider_transactions_data(
            api_token=self._api_key,
            date_from=date_from,
            date_to=date_to,
            code=code,
            limit=limit,
        )

    def get_fundamentals_data(self, ticker: str) -> list:
        """Available args:
        ticker (required) - consists of two parts: [SYMBOL_NAME].[EXCHANGE_ID]. Example: AAPL.US
        For more information visit: https://eodhistoricaldata.com/financial-apis/stock-etfs-fundamental-data-feeds/
        """

        api_call = FundamentalDataAPI()
        return api_call.get_fundamentals_data(api_token=self._api_key, ticker=ticker)

    def get_eod_splits_dividends_data(self, country="US", type=None, date=None, symbols=None, filter=None) -> list:
        """Available args:
        type (not required) - can get splits, empty or dividends.
            for splits function returns all splits for US stocks in bulk for a particular day
            for dividends function returns all dividends for US stocks in bulk for a particular day
            if type will remain empty then returns end-of-day data for US stocks in bulk for a particular day
        date (not required) - By default, the data for last trading day will be downloaded, but if you need any specific date
            you can add parameter
        symbols (not required) - To download last day data for several symbols, for example,
            for MSFT and AAPL, you can add the ‘symbols’ parameter. For non-US tickers,
            you should use the exchange code, for example, BMW.XETRA or SAP.F
            If you want get data for several codes you need to input in the next type of format: AAPL,BMW.XETRA,SAP.F
        For more information visit: https://eodhistoricaldata.com/financial-apis/bulk-api-eod-splits-dividends/
        """

        api_call = BulkEodSplitsDividendsDataAPI()
        return api_call.get_eod_splits_dividends_data(
            api_token=self._api_key,
            country=country,
            type=type,
            date=date,
            symbols=symbols,
            filter=filter,
        )

    def get_upcoming_earnings_data(self, from_date=None, to_date=None, symbols=None) -> list:
        """Available args:
        from_date (not required) - Format: YYYY-MM-DD. The start date for earnings data, if not provided, today will be used.
        to_date (not required) - Format: YYYY-MM-DD. The end date for earnings data, if not provided, today + 7 days will be used.
        symbols (not required) - OPTIONAL. You can request specific symbols to get historical and upcoming data.
            If ‘symbols’ used, then ‘from’ and ‘to’ parameters will be ignored.
            You can use one symbol: ‘AAPL.US’ or several symbols separated by a comma: ‘AAPL.US, MS’
        For more information visit: https://eodhistoricaldata.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits/#Upcoming_Earnings_API
        """

        api_call = UpcomgingEarningsAPI()
        return api_call.get_upcoming_earnings_data(
            api_token=self._api_key,
            from_date=from_date,
            to_date=to_date,
            symbols=symbols,
        )

    def get_earning_trends_data(self, symbols) -> list:
        """Available args:
        symbols (required) - You can request specific symbols to get historical and upcoming data.
            f ‘symbols’ used, then ‘from’ and ‘to’ parameters will be ignored.
            ou can use one symbol: ‘AAPL.US’ or several symbols separated by a comma: ‘AAPL.US, MS’
        For more information visit: https://eodhistoricaldata.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits/#Earnings_Trends_API
        """
        api_call = EarningTrendsAPI()
        return api_call.get_earning_trends_data(api_token=self._api_key, symbols=symbols)

    def get_upcoming_IPOs_data(self, from_date=None, to_date=None) -> list:
        """Available args:
        from_date (not required) - Format: YYYY-MM-DD. The start date for ipos data, if not provided, today will be used.
        to_date (not required) - Format: YYYY-MM-DD. The end date for ipos data, if not provided, today + 7 days will be used.
        For more information visit: https://eodhistoricaldata.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits/#Upcoming_Earnings_API
        """

        api_call = UpcomingIPOsAPI()
        return api_call.get_upcoming_IPOs_data(api_token=self._api_key, from_date=from_date, to_date=to_date)

    def get_upcoming_splits_data(self, from_date=None, to_date=None) -> list:
        """Available args:
        from_date (not required) - Format: YYYY-MM-DD. The start date for splits data, if not provided, today will be used.
        to_date (not required) - Format: YYYY-MM-DD. The end date for splits data, if not provided, today + 7 days will be used.
        For more information visit: https://eodhistoricaldata.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits/#Upcoming_Earnings_API
        """

        api_call = UpcomingSplitsAPI()
        return api_call.get_upcoming_splits_data(api_token=self._api_key, from_date=from_date, to_date=to_date)

    def get_macro_indicators_data(self, country, indicator=None) -> list:
        """Available args:
        country (required) - Defines the country for which the indicator will be shown.
            The country should be defined in the Alpha-3 ISO format. Possible values: USA, FRA, DEU…
        indicator (not required) - Defines which macroeconomics data indicator will be shown.
            See the list of possible indicators below. The default value is ‘gdp_current_usd‘.
        All possible indicators will be avaliable on: https://eodhistoricaldata.com/financial-apis/macroeconomics-data-and-macro-indicators-api/
        """

        api_call = MacroIndicatorsAPI()
        return api_call.get_macro_indicators_data(api_token=self._api_key, country=country, indicator=indicator)

    def get_bonds_fundamentals_data(self, isin=None) -> list:
        """Available args:
        isin - An International Securities Identification Number, in current function isin may be cusip-code.
            Other IDs are not supported at the moment.
        For more information visit: https://eodhistoricaldata.com/financial-apis/bonds-fundamentals-and-historical-api/
        """

        api_call = BondsFundamentalsAPI()
        return api_call.get_bonds_fundamentals_data(api_token=self._api_key, isin=isin)

    def get_list_of_exchanges(self):
        """Available args:
        Function returns list of avaliable exchanges
        """

        api_call = ListOfExchangesAPI()
        return api_call.get_list_of_exchanges(api_token=self._api_key)

    def get_list_of_tickers(self, code, delisted=0):
        """Available args:
        delisted (not required) - by default, this API provides only tickers that were active at least a month ago,
            to get the list of inactive (delisted) tickers please use the parameter “delisted=1”
        code (required) - For US exchanges you can also get all US tickers,
            then you should use the ‘US’ exchange code and tickers only for the particular exchange,
            the list of possible US exchanges to request:'US', 'NYSE', 'NASDAQ', 'BATS', 'OTCQB', 'PINK', 'OTCQX',
            'OTCMKTS', 'NMFQS', 'NYSE MKT', 'OTCBB', 'OTCGREY', 'BATS', 'OTC'
        For more information visit: https://eodhistoricaldata.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours/
        """

        api_call = ListOfExchangesAPI()
        return api_call.get_list_of_tickers(api_token=self._api_key, delisted=delisted, code=code)

    def get_details_trading_hours_stock_market_holidays(self, code, from_date=None, to_date=None):
        """Available args:
            Use the exchange code from the API endpoint.
        For more information visit: https://eodhistoricaldata.com/financial-apis/exchanges-api-trading-hours-and-stock-market-holidays/
        """

        api_call = TradingHours_StockMarketHolidays_SymbolsChangeHistoryAPI()
        return api_call.get_details_trading_hours_stock_market_holidays(api_token=self._api_key, code=code, from_date=from_date, to_date=to_date)

    def symbol_change_history(self, from_date=None, to_date=None):
        """Available args:
        from and to (not required) - the format is ‘YYYY-MM-DD’.
            If you need data from Jul 22, 2022, to Aug 10, 2022, you should use from=2022-07-22 and to=2022-08-10.
        For more information visit: https://eodhistoricaldata.com/financial-apis/exchanges-api-trading-hours-and-stock-market-holidays/
        """
        api_call = TradingHours_StockMarketHolidays_SymbolsChangeHistoryAPI()
        return api_call.symbol_change_history(api_token=self._api_key, from_date=from_date, to_date=to_date)

    def stock_market_screener(self, sort=None, filters=None, limit=None, signals=None, offset=None):
        """Available args:
        filters (not required) - Usage: filters=[[“field1”, “operation1”, value1],[“field2”, “operation2”, value2] , … ].
            Filters out tickers by different fields.
        signals (not required) - Usage: signals=signal1,signal2,…,signalN. Filter out tickers by signals, the calculated fields.
        sort (not required) - Usage: sort=field_name.(asc|desc). Sorts all fields with type ‘Number’ in ascending/descending order.
        limit (not required) - The number of results should be returned with the query.
            Default value: 50, minimum value: 1, maximum value: 100.
        offset (not required) - The offset of the data. Default value: 0, minimum value: 0, maximum value: 1000.
            For example, to get 100 symbols starting from 200 you should use limit=100 and offset=200.
        """

        api_call = StockMarketScreenerAPI()
        return api_call.stock_market_screener(
            api_token=self._api_key,
            filters=filters,
            limit=limit,
            signals=signals,
            offset=offset,
            sort=sort,
        )

    def financial_news(self, s=None, t=None, from_date=None, to_date=None, limit=None, offset=None):
        """Available args:
        s (required if t empty) - The ticker code to get news for.
        t (required if s empty) - The tag to get news on a given topic.
        limit (not required) - The number of results should be returned with the query.
            Default value: 50, minimum value: 1, maximum value: 1000.
        offset (not required) - The offset of the data. Default value: 0, minimum value: 0.
            For example, to get 100 symbols starting from 200 you should use limit=100 and offset=200.
        from and to (not required) - the format is ‘YYYY-MM-DD’.
            If you need data from Mar 1, 2021, to Mar 10, 2021, you should use from=2021-03-01 and to=2021-03-10.
        """
        api_call = FinancialNewsAPI()
        return api_call.financial_news(
            api_token=self._api_key,
            limit=limit,
            from_date=from_date,
            to_date=to_date,
            offset=offset,
            s=s,
            t=t,
        )

    def get_options_data(
        self,
        ticker,
        date_to=None,
        date_from=None,
        trade_date_to=None,
        trade_date_from=None,
        contract_name=None,
    ):
        """
        Stock options data for top US stocks from NYSE and NASDAQ, the data for Options starts from April 2018.
        Options data is updated daily; however,
        the API does not provide a history for options contracts prices or other related data.
        That means: for each contract, there is only the current price, bid/ask, etc.

        1. IMPORTANT! For backward compatibility, you should use the from parameter with any value before the expiration date,
        the API recommends '2000-01-01'.

        2. Note: option greeks and some additional value are available only for options with expiration date Feb 15, 2019, or later.

        Available args:
            ticker(string): Required - Could be any supported symbol. No default value.
            date_to(DateTime) and date_from(DateTime): Optional - the beginning and end of the desired dates.
            trade_date_from(DateTime): Optional - filters OPTIONS by lastTradeDateTime. Default value is blank.
            trade_date_to(DateTime): Optional - filters OPTIONS by lastTradeDateTime. Default value is blank.
            contract_name(string): Optional - Name of a particular contract.
        """
        api_call = OptionsDataAPI()
        return api_call.get_options_data(
            api_token=self._api_key,
            ticker=ticker,
            date_to=date_to,
            date_from=date_from,
            trade_date_to=trade_date_to,
            trade_date_from=trade_date_from,
            contract_name=contract_name,
        )

    def get_intraday_historical_data(
        self,
        symbol,
        interval='5m',
        from_unix_time=None,
        to_unix_time=None
    ):
        """
        IMPORTANT: data for all exchanges is provided in the UTC timezone, with Unix timestamps.

        Available args:
            symbol(string): Required - consists of two parts: {SYMBOL_NAME}.{EXCHANGE_ID},
                then you can use, for example, AAPL.MX for Mexican Stock Exchange. or AAPL.US for NASDAQ
            interval(string) Optional - the possible intervals: ‘5m’ for 5-minutes, ‘1h’ for 1 hour, and ‘1m’ for 1-minute intervals.
            from_unix_time(string) and to_unix_time(string): Optional - Parameters should be passed in UNIX time with UTC timezone, for example,
                these values are correct: “from=1627896900&to=1630575300” and correspond to
                ‘ 2021-08-02 09:35:00 ‘ and ‘ 2021-09-02 09:35:00 ‘.
                The maximum periods between ‘from’ and ‘to’ are 120 days for 1-minute intervals,
                600 days for 5-minute intervals and
                7200 days for 1-hour intervals
                (please note, especially with the 1-hour interval, this is the maximum theoretically possible length).
                Without ‘from’ and ‘to’ specified, the length of the data obtained is the last 120 days.

        List of supported exchanges: https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours/
        For more information visit: https://eodhd.com/financial-apis/intraday-historical-data-api/
        """
        api_call = IntradayDataAPI()
        return api_call.get_intraday_historical_data(
            api_token=self._api_key,
            symbol=symbol,
            interval=interval,
            to_unix_time=to_unix_time,
            from_unix_time=from_unix_time
        )

    def get_eod_historical_stock_market_data(
        self,
        symbol,
        period='d',
        from_date=None,
        to_date=None,
        order=None
    ):
        """
        Available args:
            symbol(string): Required - consists of two parts: {SYMBOL_NAME}.{EXCHANGE_ID},
                then you can use, for example, AAPL.MX for Mexican Stock Exchange. or AAPL.US for NASDAQ
            period(string) Optional - use 'd' for daily, 'w' for weekly, 'm' for monthly prices. By default, daily prices will be shown.
            from_date and to_date - the format is 'YYYY-MM-DD'.
                If you need data from Jan 5, 2017, to Feb 10, 2017, you should use from=2017-01-05 and to=2017-02-10.
            order(string) Optional - use ‘a’ for ascending dates (from old to new), ‘d’ for descending dates (from new to old).
                By default, dates are shown in ascending order.

        List of supported exchanges: https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours/
        For more information visit: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes/
        """
        api_call = EodHistoricalStockMarketDataAPI()
        return api_call.get_eod_historical_stock_market_data(
            api_token=self._api_key,
            symbol=symbol,
            period=period,
            to_date=to_date,
            from_date=from_date,
            order=order
        )

    def get_stock_market_tick_data(
        self,
        symbol,
        from_timestamp,
        to_timestamp,
        limit=None
    ):
        """
        Available args:
            symbol - for example, AAPL.US, consists of two parts: {SYMBOL_NAME}.{EXCHANGE_ID}. 
                This API works only for US exchanges for the moment, 
                then you can use 'AAPL' or 'AAPL.US' to get the data as well for other US tickers.
            from_timestamp and to_timestamp - use these parameters to filter data by datetime.
                Parameters should be passed in UNIX time with UTC timezone,
                for example, these values are correct: “from=1627896900&to=1630575300” and
                correspond to ' 2021-08-02 09:35:00 ' and ' 2021-09-02 09:35:00 '.
            limit - the maximum number of ticks will be provided.
        """
        api_call = StockMarketTickDataAPI()
        return api_call.get_stock_market_tick_data(
            api_token=self._api_key,
            symbol=symbol,
            to_timestamp=to_timestamp,
            from_timestamp=from_timestamp,
            limit=limit
        )
    
    def get_sentiment(
        self,
        s,
        from_date=None,
        to_date=None
    ):
        """
        Available args:
            s [REQUIRED] -  parameter to your URL and you will be able to get data for multiple tickers at one request, 
                            all tickers should be separated with a comma.
            from_date and to_date [NOT REQUIRED] - the format is ‘YYYY-MM-DD’. 
                            If you need data from Jan 5, 2022 to Feb 10, 2022, you should use from=2022-01-05 and to=2022-02-10.
            For more information visit: https://eodhd.com/financial-apis/sentimental-data-financial-api/
            List of supported exchanges: https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours/
        """

        api_call = FinancialNewsAPI()
        return api_call.get_sentiment(
            api_token=self._api_key,
            s=s,
            from_date=from_date,
            to_date=to_date
        )

    def get_historical_market_capitalization_data(
        self,
        ticker,
        from_date=None,
        to_date=None
    ):
        """
        Available args:
            ticker [REQUIRED] -  is the ticker code and it consists of two parts: {SYMBOL_NAME}.{EXCHANGE_ID}, 
                        you can use a US ticker code with or without the exchange part (AAPL or AAPL.US)
            from_date and to_date [NOT REQUIRED] - the format is ‘YYYY-MM-DD’. 
                            If you need data from Jan 5, 2022 to Feb 10, 2022, you should use from=2022-01-05 and to=2022-02-10.
            For more information visit: https://eodhd.com/financial-apis/historical-market-capitalization-api/
        """

        api_call = HistoricalMarketCapitalization()
        return api_call.get_historical_market_capitalization_data(
            api_token=self._api_key,
            ticker=ticker,
            from_date=from_date,
            to_date=to_date
        )

class ScannerClient:
    """Scanner class"""

    def __init__(self, api_key: str) -> None:
        # Validate API key
        prog = re_compile(r"^[A-z0-9.]{16,32}$")
        if api_key != "demo" and not prog.match(api_key):
            raise ValueError("API key is invalid")

        self.api = APIClient(api_key)

    def scan_markets(
        self,
        market_type: str = "CC",
        interval: str = Interval,
        quote_currency: str = "USD",
        request_limit: int = 5000,
    ):
        """Scan markets"""

        if request_limit < 0 or request_limit > 100000:
            raise ValueError("request limit is out of bounds!")

        df_dataset = pd.DataFrame()

        resp = self.api.get_exchange_symbols(market_type)
        symbol_list = resp[resp.Code.str.endswith(f"-{quote_currency}", na=False)].Code.to_numpy()

        if request_limit > 0:
            # truncate symbol list to request limit minus symbol list request
            symbol_list = symbol_list[0 : request_limit - 1]

        for symbol in track(symbol_list, description="Processing..."):
            df_data = self.api.get_historical_data(f"{symbol}.{market_type}", interval)
            if len(df_data) >= 200:
                df_data["sma50"] = df_data.adjusted_close.rolling(50, min_periods=1).mean()
                df_data["sma200"] = df_data.adjusted_close.rolling(200, min_periods=1).mean()
                df_data["bull_market"] = df_data.sma50 >= df_data.sma200

                df_data["ema12"] = df_data.adjusted_close.ewm(span=12, adjust=False).mean()
                df_data["ema26"] = df_data.adjusted_close.ewm(span=26, adjust=False).mean()
                df_data.loc[df_data["ema12"] > df_data["ema26"], "next_action"] = "sell"
                df_data["next_action"].fillna("buy", inplace=True)

                high_low = df_data["high"] - df_data["low"]
                high_close = abs(df_data["high"] - df_data["adjusted_close"].shift())
                low_close = abs(df_data["low"] - df_data["adjusted_close"].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                df_data["atr14"] = true_range.rolling(14).sum() / 14
                df_data["atr14_pcnt"] = (df_data["atr14"] / df_data["adjusted_close"] * 100).round(2)

                df_dataset = df_dataset.append(df_data.tail(1))

        # drop infinite values
        df_dataset.replace([np.inf, -np.inf], np.nan, inplace=True)
        df_dataset.dropna(subset=["atr14_pcnt"], inplace=True)

        df_dataset.sort_values(
            by=["bull_market", "next_action", "volume", "atr14_pcnt"],
            ascending=[False, True, False, False],
            inplace=True,
        )
        df_dataset.to_csv("dataset.csv")

        return df_dataset
