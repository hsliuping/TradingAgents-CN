#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/7/24 18:30
Desc: currencybeacon 提供的外汇数据
该网站需要先注册后获取 API 使用
https://currencyscoop.com/
"""

import pandas as pd
import requests


def currency_latest(
    base: str = "USD", symbols: str = "", api_key: str = ""
) -> pd.DataFrame:
    """
    Latest data from currencyscoop.com
    https://currencyscoop.com/api-documentation
    :param base: The base currency you would like to use for your rates
    :type base: str
    :param symbols: A list of currencies you will like to see the rates for. You can refer to a list all supported currencies here
    :type symbols: str
    :param api_key: Account -> Account Details -> API KEY (use as password in external tools)
    :type api_key: str
    :return: Latest data of base currency
    :rtype: pandas.DataFrame
    """
    params = {"base": base, "symbols": symbols, "api_key": api_key}
    url = "https://api.currencyscoop.com/v1/latest"
    r = requests.get(url, params=params)
    temp_df = pd.DataFrame.from_dict(r.json()["response"])
    temp_df["date"] = pd.to_datetime(temp_df["date"])
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "currency"}, inplace=True)
    return temp_df


def currency_history(
    base: str = "USD", date: str = "2023-02-03", symbols: str = "", api_key: str = ""
) -> pd.DataFrame:
    """
    Latest data from currencyscoop.com
    https://currencyscoop.com/api-documentation
    :param base: The base currency you would like to use for your rates
    :type base: str
    :param date: Specific date, e.g., "2020-02-03"
    :type date: str
    :param symbols: A list of currencies you will like to see the rates for. You can refer to a list all supported currencies here
    :type symbols: str
    :param api_key: Account -> Account Details -> API KEY (use as password in external tools)
    :type api_key: str
    :return: Latest data of base currency
    :rtype: pandas.DataFrame
    """
    params = {"base": base, "date": date, "symbols": symbols, "api_key": api_key}
    url = "https://api.currencyscoop.com/v1/historical"
    r = requests.get(url, params=params)
    temp_df = pd.DataFrame.from_dict(r.json()["response"])
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "currency"}, inplace=True)
    return temp_df


def currency_time_series(
    base: str = "USD",
    start_date: str = "2023-02-03",
    end_date: str = "2023-03-04",
    symbols: str = "",
    api_key: str = "",
) -> pd.DataFrame:
    """
    Time-series data from currencyscoop.com
    P.S. need special authority
    https://currencyscoop.com/api-documentation
    :param base: The base currency you would like to use for your rates
    :type base: str
    :param start_date: Specific date, e.g., "2020-02-03"
    :type start_date: str
    :param end_date: Specific date, e.g., "2020-02-03"
    :type end_date: str
    :param symbols: A list of currencies you will like to see the rates for. You can refer to a list all supported currencies here
    :type symbols: str
    :param api_key: Account -> Account Details -> API KEY (use as password in external tools)
    :type api_key: str
    :return: Latest data of base currency
    :rtype: pandas.DataFrame
    """
    params = {
        "base": base,
        "api_key": api_key,
        "start_date": start_date,
        "end_date": end_date,
        "symbols": symbols,
    }
    url = "https://api.currencyscoop.com/v1/timeseries"
    r = requests.get(url, params=params)
    temp_df = pd.DataFrame.from_dict(r.json()["response"])
    temp_df = temp_df.T
    temp_df.reset_index(inplace=True)
    temp_df.rename(columns={"index": "date"}, inplace=True)
    temp_df["date"] = pd.to_datetime(temp_df["date"]).dt.date
    return temp_df


def currency_currencies(c_type: str = "fiat", api_key: str = "") -> pd.DataFrame:
    """
    currencies data from currencyscoop.com
    https://currencyscoop.com/api-documentation
    :param c_type: now only "fiat" can return data
    :type c_type: str
    :param api_key: Account -> Account Details -> API KEY (use as password in external tools)
    :type api_key: str
    :return: Latest data of base currency
    :rtype: pandas.DataFrame
    """
    params = {"type": c_type, "api_key": api_key}
    url = "https://api.currencyscoop.com/v1/currencies"
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["response"])
    return temp_df


def currency_convert(
    base: str = "USD",
    to: str = "CNY",
    amount: str = "10000",
    api_key: str = "",
) -> pd.DataFrame:
    """
    currencies data from currencyscoop.com
    https://currencyscoop.com/api-documentation
    :param base: The base currency you would like to use for your rates
    :type base: str
    :param to: The currency you would like to use for your rates
    :type to: str
    :param amount: The amount of base currency
    :type amount: str
    :param api_key: Account -> Account Details -> API KEY (use as password in external tools)
    :type api_key: str
    :return: Latest data of base currency
    :rtype: pandas.Series
    """
    params = {
        "from": base,
        "to": to,
        "amount": amount,
        "api_key": api_key,
    }
    url = "https://api.currencyscoop.com/v1/convert"
    r = requests.get(url, params=params)
    temp_se = pd.Series(r.json()["response"])
    temp_se["timestamp"] = pd.to_datetime(temp_se["timestamp"], unit="s")
    temp_df = temp_se.to_frame()
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


if __name__ == "__main__":
    currency_latest_df = currency_latest(base="USD", api_key="")
    print(currency_latest_df)

    currency_history_df = currency_history(base="USD", date="2023-02-03", api_key="")
    print(currency_history_df)

    currency_time_series_df = currency_time_series(
        base="USD",
        start_date="2023-02-03",
        end_date="2023-03-04",
        symbols="",
        api_key="",
    )
    print(currency_time_series_df)

    currency_currencies_df = currency_currencies(c_type="fiat", api_key="")
    print(currency_currencies_df)

    currency_convert_se = currency_convert(
        base="USD", to="CNY", amount="10000", api_key=""
    )
    print(currency_convert_se)
