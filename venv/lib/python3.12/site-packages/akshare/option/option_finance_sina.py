#!/usr/bin/env python
"""
Date: 2024/6/21 18:00
Desc: 新浪财经-股票期权
https://stock.finance.sina.com.cn/option/quotes.html
期权-中金所-沪深 300 指数
https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php
期权-上交所-50ETF
期权-上交所-300ETF
期权-上交所-500ETF
https://stock.finance.sina.com.cn/option/quotes.html
"""

import datetime
import json
from functools import lru_cache
from typing import Dict, List, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.option.option_em import option_current_em
from akshare.utils.func import set_df_columns


# 期权-中金所-上证50指数
def option_cffex_sz50_list_sina() -> Dict[str, List[str]]:
    """
    新浪财经-中金所-上证 50 指数-所有合约, 返回的第一个合约为主力合约
    目前新浪财经-中金所有上证 50 指数，沪深 300 指数和中证 1000 指数
    :return: 中金所-上证 50 指数-所有合约
    :rtype: dict
    """
    url = "https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php/ho/cffex"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    symbol = soup.find(attrs={"id": "option_symbol"}).find_all("li")[0].text
    temp_attr = soup.find(attrs={"id": "option_suffix"}).find_all("li")
    contract = [item.text for item in temp_attr]
    return {symbol: contract}


# 期权-中金所-沪深300指数
def option_cffex_hs300_list_sina() -> Dict[str, List[str]]:
    """
    新浪财经-中金所-沪深 300 指数-所有合约, 返回的第一个合约为主力合约
    目前新浪财经-中金所有沪深 300 指数和中证 1000 指数
    :return: 中金所-沪深300指数-所有合约
    :rtype: dict
    """
    url = "https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    symbol = soup.find(attrs={"id": "option_symbol"}).find_all("li")[1].text
    temp_attr = soup.find(attrs={"id": "option_suffix"}).find_all("li")
    contract = [item.text for item in temp_attr]
    return {symbol: contract}


def option_cffex_zz1000_list_sina() -> Dict[str, List[str]]:
    """
    新浪财经-中金所-中证 1000 指数-所有合约, 返回的第一个合约为主力合约
    目前新浪财经-中金所有沪深 300 指数和中证 1000 指数
    :return: 中金所-中证 1000 指数-所有合约
    :rtype: dict
    """
    url = "https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php/mo/cffex"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    symbol = soup.find(attrs={"id": "option_symbol"}).find_all("li")[2].text
    temp_attr = soup.find(attrs={"id": "option_suffix"}).find_all("li")
    contract = [item.text for item in temp_attr]
    return {symbol: contract}


def option_cffex_sz50_spot_sina(symbol: str = "ho2303") -> pd.DataFrame:
    """
    中金所-上证 50 指数-指定合约-实时行情
    https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php/ho/cffex
    :param symbol: 合约代码; 用 ak.option_cffex_sz300_list_sina() 函数查看
    :type symbol: str
    :return: 中金所-上证 50 指数-指定合约-看涨看跌实时行情
    :rtype: pd.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    params = {
        "type": "futures",
        "product": "ho",
        "exchange": "cffex",
        "pinzhong": symbol,
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = json.loads(data_text[data_text.find("{") : data_text.rfind("}") + 1])
    option_call_df = pd.DataFrame(
        data_json["result"]["data"]["up"],
        columns=[
            "看涨合约-买量",
            "看涨合约-买价",
            "看涨合约-最新价",
            "看涨合约-卖价",
            "看涨合约-卖量",
            "看涨合约-持仓量",
            "看涨合约-涨跌",
            "行权价",
            "看涨合约-标识",
        ],
    )
    option_put_df = pd.DataFrame(
        data_json["result"]["data"]["down"],
        columns=[
            "看跌合约-买量",
            "看跌合约-买价",
            "看跌合约-最新价",
            "看跌合约-卖价",
            "看跌合约-卖量",
            "看跌合约-持仓量",
            "看跌合约-涨跌",
            "看跌合约-标识",
        ],
    )
    data_df = pd.concat(objs=[option_call_df, option_put_df], axis=1)
    data_df["看涨合约-买量"] = pd.to_numeric(data_df["看涨合约-买量"], errors="coerce")
    data_df["看涨合约-买价"] = pd.to_numeric(data_df["看涨合约-买价"], errors="coerce")
    data_df["看涨合约-最新价"] = pd.to_numeric(
        data_df["看涨合约-最新价"], errors="coerce"
    )
    data_df["看涨合约-卖价"] = pd.to_numeric(data_df["看涨合约-卖价"], errors="coerce")
    data_df["看涨合约-卖量"] = pd.to_numeric(data_df["看涨合约-卖量"], errors="coerce")
    data_df["看涨合约-持仓量"] = pd.to_numeric(
        data_df["看涨合约-持仓量"], errors="coerce"
    )
    data_df["看涨合约-涨跌"] = pd.to_numeric(data_df["看涨合约-涨跌"], errors="coerce")
    data_df["行权价"] = pd.to_numeric(data_df["行权价"], errors="coerce")
    data_df["看跌合约-买量"] = pd.to_numeric(data_df["看跌合约-买量"], errors="coerce")
    data_df["看跌合约-买价"] = pd.to_numeric(data_df["看跌合约-买价"], errors="coerce")
    data_df["看跌合约-最新价"] = pd.to_numeric(
        data_df["看跌合约-最新价"], errors="coerce"
    )
    data_df["看跌合约-卖价"] = pd.to_numeric(data_df["看跌合约-卖价"], errors="coerce")
    data_df["看跌合约-卖量"] = pd.to_numeric(data_df["看跌合约-卖量"], errors="coerce")
    data_df["看跌合约-持仓量"] = pd.to_numeric(
        data_df["看跌合约-持仓量"], errors="coerce"
    )
    data_df["看跌合约-涨跌"] = pd.to_numeric(data_df["看跌合约-涨跌"], errors="coerce")
    return data_df


def option_cffex_hs300_spot_sina(symbol: str = "io2204") -> pd.DataFrame:
    """
    中金所-沪深 300 指数-指定合约-实时行情
    https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php
    :param symbol: 合约代码; 用 option_cffex_hs300_list_sina 函数查看
    :type symbol: str
    :return: 中金所-沪深300指数-指定合约-看涨看跌实时行情
    :rtype: pd.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    params = {
        "type": "futures",
        "product": "io",
        "exchange": "cffex",
        "pinzhong": symbol,
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = json.loads(data_text[data_text.find("{") : data_text.rfind("}") + 1])
    option_call_df = pd.DataFrame(
        data_json["result"]["data"]["up"],
        columns=[
            "看涨合约-买量",
            "看涨合约-买价",
            "看涨合约-最新价",
            "看涨合约-卖价",
            "看涨合约-卖量",
            "看涨合约-持仓量",
            "看涨合约-涨跌",
            "行权价",
            "看涨合约-标识",
        ],
    )
    option_put_df = pd.DataFrame(
        data_json["result"]["data"]["down"],
        columns=[
            "看跌合约-买量",
            "看跌合约-买价",
            "看跌合约-最新价",
            "看跌合约-卖价",
            "看跌合约-卖量",
            "看跌合约-持仓量",
            "看跌合约-涨跌",
            "看跌合约-标识",
        ],
    )
    data_df = pd.concat(objs=[option_call_df, option_put_df], axis=1)
    data_df["看涨合约-买量"] = pd.to_numeric(data_df["看涨合约-买量"], errors="coerce")
    data_df["看涨合约-买价"] = pd.to_numeric(data_df["看涨合约-买价"], errors="coerce")
    data_df["看涨合约-最新价"] = pd.to_numeric(
        data_df["看涨合约-最新价"], errors="coerce"
    )
    data_df["看涨合约-卖价"] = pd.to_numeric(data_df["看涨合约-卖价"], errors="coerce")
    data_df["看涨合约-卖量"] = pd.to_numeric(data_df["看涨合约-卖量"], errors="coerce")
    data_df["看涨合约-持仓量"] = pd.to_numeric(
        data_df["看涨合约-持仓量"], errors="coerce"
    )
    data_df["看涨合约-涨跌"] = pd.to_numeric(data_df["看涨合约-涨跌"], errors="coerce")
    data_df["行权价"] = pd.to_numeric(data_df["行权价"], errors="coerce")
    data_df["看跌合约-买量"] = pd.to_numeric(data_df["看跌合约-买量"], errors="coerce")
    data_df["看跌合约-买价"] = pd.to_numeric(data_df["看跌合约-买价"], errors="coerce")
    data_df["看跌合约-最新价"] = pd.to_numeric(
        data_df["看跌合约-最新价"], errors="coerce"
    )
    data_df["看跌合约-卖价"] = pd.to_numeric(data_df["看跌合约-卖价"], errors="coerce")
    data_df["看跌合约-卖量"] = pd.to_numeric(data_df["看跌合约-卖量"], errors="coerce")
    data_df["看跌合约-持仓量"] = pd.to_numeric(
        data_df["看跌合约-持仓量"], errors="coerce"
    )
    data_df["看跌合约-涨跌"] = pd.to_numeric(data_df["看跌合约-涨跌"], errors="coerce")
    return data_df


def option_cffex_zz1000_spot_sina(symbol: str = "mo2208") -> pd.DataFrame:
    """
    中金所-中证 1000 指数-指定合约-实时行情
    https://stock.finance.sina.com.cn/futures/view/optionsCffexDP.php
    :param symbol: 合约代码; 用 option_cffex_zz1000_list_sina 函数查看
    :type symbol: str
    :return: 中金所-中证 1000 指数-指定合约-看涨看跌实时行情
    :rtype: pd.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    params = {
        "type": "futures",
        "product": "mo",
        "exchange": "cffex",
        "pinzhong": symbol,
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = json.loads(data_text[data_text.find("{") : data_text.rfind("}") + 1])
    option_call_df = pd.DataFrame(
        data_json["result"]["data"]["up"],
        columns=[
            "看涨合约-买量",
            "看涨合约-买价",
            "看涨合约-最新价",
            "看涨合约-卖价",
            "看涨合约-卖量",
            "看涨合约-持仓量",
            "看涨合约-涨跌",
            "行权价",
            "看涨合约-标识",
        ],
    )
    option_put_df = pd.DataFrame(
        data_json["result"]["data"]["down"],
        columns=[
            "看跌合约-买量",
            "看跌合约-买价",
            "看跌合约-最新价",
            "看跌合约-卖价",
            "看跌合约-卖量",
            "看跌合约-持仓量",
            "看跌合约-涨跌",
            "看跌合约-标识",
        ],
    )
    data_df = pd.concat(objs=[option_call_df, option_put_df], axis=1)
    data_df["看涨合约-买量"] = pd.to_numeric(data_df["看涨合约-买量"], errors="coerce")
    data_df["看涨合约-买价"] = pd.to_numeric(data_df["看涨合约-买价"], errors="coerce")
    data_df["看涨合约-最新价"] = pd.to_numeric(
        data_df["看涨合约-最新价"], errors="coerce"
    )
    data_df["看涨合约-卖价"] = pd.to_numeric(data_df["看涨合约-卖价"], errors="coerce")
    data_df["看涨合约-卖量"] = pd.to_numeric(data_df["看涨合约-卖量"], errors="coerce")
    data_df["看涨合约-持仓量"] = pd.to_numeric(
        data_df["看涨合约-持仓量"], errors="coerce"
    )
    data_df["看涨合约-涨跌"] = pd.to_numeric(data_df["看涨合约-涨跌"], errors="coerce")
    data_df["行权价"] = pd.to_numeric(data_df["行权价"], errors="coerce")
    data_df["看跌合约-买量"] = pd.to_numeric(data_df["看跌合约-买量"], errors="coerce")
    data_df["看跌合约-买价"] = pd.to_numeric(data_df["看跌合约-买价"], errors="coerce")
    data_df["看跌合约-最新价"] = pd.to_numeric(
        data_df["看跌合约-最新价"], errors="coerce"
    )
    data_df["看跌合约-卖价"] = pd.to_numeric(data_df["看跌合约-卖价"], errors="coerce")
    data_df["看跌合约-卖量"] = pd.to_numeric(data_df["看跌合约-卖量"], errors="coerce")
    data_df["看跌合约-持仓量"] = pd.to_numeric(
        data_df["看跌合约-持仓量"], errors="coerce"
    )
    data_df["看跌合约-涨跌"] = pd.to_numeric(data_df["看跌合约-涨跌"], errors="coerce")
    return data_df


def option_cffex_sz50_daily_sina(symbol: str = "ho2303P2350") -> pd.DataFrame:
    """
    新浪财经-中金所-上证 50 指数-指定合约-日频行情
    :param symbol: 具体合约代码(包括看涨和看跌标识), 可以通过 ak.option_cffex_sz50_spot_sina 中的 call-标识 获取
    :type symbol: str
    :return: 日频率数据
    :rtype: pd.DataFrame
    """
    year = datetime.datetime.now().year
    month = datetime.datetime.now().month
    day = datetime.datetime.now().day
    url = (
        f"https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}{year}_{month}_{day}"
        f"=/FutureOptionAllService.getOptionDayline"
    )
    params = {"symbol": symbol}
    r = requests.get(url, params=params)
    data_text = r.text
    data_df = pd.DataFrame(
        eval(data_text[data_text.find("[") : data_text.rfind("]") + 1])
    )
    data_df.columns = ["open", "high", "low", "close", "volume", "date"]
    data_df = data_df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    data_df["date"] = pd.to_datetime(data_df["date"], errors="coerce").dt.date
    data_df["open"] = pd.to_numeric(data_df["open"], errors="coerce")
    data_df["high"] = pd.to_numeric(data_df["high"], errors="coerce")
    data_df["low"] = pd.to_numeric(data_df["low"], errors="coerce")
    data_df["close"] = pd.to_numeric(data_df["close"], errors="coerce")
    data_df["volume"] = pd.to_numeric(data_df["volume"], errors="coerce")
    return data_df


def option_cffex_hs300_daily_sina(symbol: str = "io2202P4350") -> pd.DataFrame:
    """
    新浪财经-中金所-沪深300指数-指定合约-日频行情
    :param symbol: 具体合约代码(包括看涨和看跌标识), 可以通过 ak.option_cffex_hs300_spot_sina 中的 call-标识 获取
    :type symbol: str
    :return: 日频率数据
    :rtype: pd.DataFrame
    """
    year = datetime.datetime.now().year
    month = datetime.datetime.now().month
    day = datetime.datetime.now().day
    url = (
        f"https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}{year}_{month}_{day}"
        f"=/FutureOptionAllService.getOptionDayline"
    )
    params = {"symbol": symbol}
    r = requests.get(url, params=params)
    data_text = r.text
    data_df = pd.DataFrame(
        eval(data_text[data_text.find("[") : data_text.rfind("]") + 1])
    )
    data_df.columns = ["open", "high", "low", "close", "volume", "date"]
    data_df = data_df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    data_df["date"] = pd.to_datetime(data_df["date"], errors="coerce").dt.date
    data_df["open"] = pd.to_numeric(data_df["open"], errors="coerce")
    data_df["high"] = pd.to_numeric(data_df["high"], errors="coerce")
    data_df["low"] = pd.to_numeric(data_df["low"], errors="coerce")
    data_df["close"] = pd.to_numeric(data_df["close"], errors="coerce")
    data_df["volume"] = pd.to_numeric(data_df["volume"], errors="coerce")
    return data_df


def option_cffex_zz1000_daily_sina(
    symbol: str = "mo2208P6200",
) -> pd.DataFrame:
    """
    新浪财经-中金所-中证 1000 指数-指定合约-日频行情
    :param symbol: 具体合约代码(包括看涨和看跌标识), 可以通过 ak.option_cffex_zz1000_spot_sina 中的 call-标识 获取
    :type symbol: str
    :return: 日频率数据
    :rtype: pd.DataFrame
    """
    year = datetime.datetime.now().year
    month = datetime.datetime.now().month
    day = datetime.datetime.now().day
    url = (
        f"https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}{year}_{month}_{day}"
        f"=/FutureOptionAllService.getOptionDayline"
    )
    params = {"symbol": symbol}
    r = requests.get(url, params=params)
    data_text = r.text
    data_df = pd.DataFrame(
        eval(data_text[data_text.find("[") : data_text.rfind("]") + 1])
    )
    data_df.columns = ["open", "high", "low", "close", "volume", "date"]
    data_df = data_df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    data_df["date"] = pd.to_datetime(data_df["date"], errors="coerce").dt.date
    data_df["open"] = pd.to_numeric(data_df["open"], errors="coerce")
    data_df["high"] = pd.to_numeric(data_df["high"], errors="coerce")
    data_df["low"] = pd.to_numeric(data_df["low"], errors="coerce")
    data_df["close"] = pd.to_numeric(data_df["close"], errors="coerce")
    data_df["volume"] = pd.to_numeric(data_df["volume"], errors="coerce")
    return data_df


# 期权-上交所-50ETF
def option_sse_list_sina(symbol: str = "50ETF", exchange: str = "null") -> List[str]:
    """
    新浪财经-期权-上交所-50ETF-合约到期月份列表
    https://stock.finance.sina.com.cn/option/quotes.html
    :param symbol: 50ETF or 300ETF
    :type symbol: str
    :param exchange: null
    :type exchange: str
    :return: 合约到期时间
    :rtype: list
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionService.getStockName"
    params = {"exchange": f"{exchange}", "cate": f"{symbol}"}
    r = requests.get(url, params=params)
    data_json = r.json()
    date_list = data_json["result"]["data"]["contractMonth"]
    return ["".join(i.split("-")) for i in date_list][1:]


def option_sse_expire_day_sina(
    trade_date: str = "202102", symbol: str = "50ETF", exchange: str = "null"
) -> Tuple[str, int]:
    """
    指定到期月份指定品种的剩余到期时间
    :param trade_date: 到期月份: 202002, 20203, 20206, 20209
    :type trade_date: str
    :param symbol: 50ETF or 300ETF
    :type symbol: str
    :param exchange: null
    :type exchange: str
    :return: (到期时间, 剩余时间)
    :rtype: tuple
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionService.getRemainderDay"
    params = {
        "exchange": f"{exchange}",
        "cate": f"{symbol}",
        "date": f"{trade_date[:4]}-{trade_date[4:]}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    data = data_json["result"]["data"]
    if int(data["remainderDays"]) < 0:
        url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionService.getRemainderDay"
        params = {
            "exchange": f"{exchange}",
            "cate": f"{'XD' + symbol}",
            "date": f"{trade_date[:4]}-{trade_date[4:]}",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        data = data_json["result"]["data"]
    return data["expireDay"], int(data["remainderDays"])


def option_sse_codes_sina(
    symbol: str = "看涨期权",
    trade_date: str = "202202",
    underlying: str = "510050",
) -> pd.DataFrame:
    """
    上海证券交易所-所有看涨和看跌合约的代码

    :param symbol: choice of {"看涨期权", "看跌期权"}
    :type symbol: str
    :param trade_date: 期权到期月份
    :type trade_date: "202002"
    :param underlying: 标的产品代码 华夏上证 50ETF: 510050 or 华泰柏瑞沪深 300ETF: 510300
    :type underlying: str
    :return: 看涨看跌合约的代码
    :rtype: Tuple[List, List]
    """
    if symbol == "看涨期权":
        url = "".join(
            [
                "https://hq.sinajs.cn/list=OP_UP_",
                underlying,
                str(trade_date)[-4:],
            ]
        )
    else:
        url = "".join(
            [
                "https://hq.sinajs.cn/list=OP_DOWN_",
                underlying,
                str(trade_date)[-4:],
            ]
        )
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "hq.sinajs.cn",
        "Pragma": "no-cache",
        "Referer": "https://stock.finance.sina.com.cn/",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_temp = data_text.replace('"', ",").split(",")
    temp_list = [i[7:] for i in data_temp if i.startswith("CON_OP_")]
    temp_df = pd.DataFrame(temp_list)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "期权代码",
    ]
    return temp_df


def option_sse_spot_price_sina(symbol: str = "10003720") -> pd.DataFrame:
    """
    新浪财经-期权-期权实时数据
    :param symbol: 期权代码
    :type symbol: str
    :return: 期权量价数据
    :rtype: pandas.DataFrame
    """
    url = f"https://hq.sinajs.cn/list=CON_OP_{symbol}"
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "hq.sinajs.cn",
        "Pragma": "no-cache",
        "Referer": "https://stock.finance.sina.com.cn/",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_list = data_text[data_text.find('"') + 1 : data_text.rfind('"')].split(",")
    field_list = [
        "买量",
        "买价",
        "最新价",
        "卖价",
        "卖量",
        "持仓量",
        "涨幅",
        "行权价",
        "昨收价",
        "开盘价",
        "涨停价",
        "跌停价",
        "申卖价五",
        "申卖量五",
        "申卖价四",
        "申卖量四",
        "申卖价三",
        "申卖量三",
        "申卖价二",
        "申卖量二",
        "申卖价一",
        "申卖量一",
        "申买价一",
        "申买量一 ",
        "申买价二",
        "申买量二",
        "申买价三",
        "申买量三",
        "申买价四",
        "申买量四",
        "申买价五",
        "申买量五",
        "行情时间",
        "主力合约标识",
        "状态码",
        "标的证券类型",
        "标的股票",
        "期权合约简称",
        "振幅",
        "最高价",
        "最低价",
        "成交量",
        "成交额",
    ]
    data_df = pd.DataFrame(list(zip(field_list, data_list)), columns=["字段", "值"])
    return data_df


def option_sse_underlying_spot_price_sina(
    symbol: str = "sh510300",
) -> pd.DataFrame:
    """
    期权标的物的实时数据
    :param symbol: sh510050 or sh510300
    :type symbol: str
    :return: 期权标的物的信息
    :rtype: pandas.DataFrame
    """
    url = f"https://hq.sinajs.cn/list={symbol}"
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Host": "hq.sinajs.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://vip.stock.finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_list = data_text[data_text.find('"') + 1 : data_text.rfind('"')].split(",")
    field_list = [
        "证券简称",
        "今日开盘价",
        "昨日收盘价",
        "最近成交价",
        "最高成交价",
        "最低成交价",
        "买入价",
        "卖出价",
        "成交数量",
        "成交金额",
        "买数量一",
        "买价位一",
        "买数量二",
        "买价位二",
        "买数量三",
        "买价位三",
        "买数量四",
        "买价位四",
        "买数量五",
        "买价位五",
        "卖数量一",
        "卖价位一",
        "卖数量二",
        "卖价位二",
        "卖数量三",
        "卖价位三",
        "卖数量四",
        "卖价位四",
        "卖数量五",
        "卖价位五",
        "行情日期",
        "行情时间",
        "停牌状态",
    ]
    data_df = pd.DataFrame(list(zip(field_list, data_list)), columns=["字段", "值"])
    return data_df


def option_sse_greeks_sina(symbol: str = "10003045") -> pd.DataFrame:
    """
    期权基本信息表
    :param symbol: 合约代码
    :type symbol: str
    :return: 期权基本信息表
    :rtype: pandas.DataFrame
    """
    url = f"https://hq.sinajs.cn/list=CON_SO_{symbol}"
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Host": "hq.sinajs.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://vip.stock.finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_text = r.text
    data_list = data_text[data_text.find('"') + 1 : data_text.rfind('"')].split(",")
    field_list = [
        "期权合约简称",
        "成交量",
        "Delta",
        "Gamma",
        "Theta",
        "Vega",
        "隐含波动率",
        "最高价",
        "最低价",
        "交易代码",
        "行权价",
        "最新价",
        "理论价值",
    ]
    data_df = pd.DataFrame(
        list(zip(field_list, [data_list[0]] + data_list[4:])),
        columns=["字段", "值"],
    )
    return data_df


def option_sse_minute_sina(symbol: str = "10003720") -> pd.DataFrame:
    """
    指定期权品种在当前交易日的分钟数据, 只能获取当前交易日的数据, 不能获取历史分钟数据
    https://stock.finance.sina.com.cn/option/quotes.html
    :param symbol: 期权代码
    :type symbol: str
    :return: 指定期权的当前交易日的分钟数据
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionDaylineService.getOptionMinline"
    params = {"symbol": f"CON_OP_{symbol}"}
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://stock.finance.sina.com.cn/option/quotes.html",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "script",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = data_json["result"]["data"]
    data_df = pd.DataFrame(temp_df)
    data_df = set_df_columns(
        df=data_df, cols=["时间", "价格", "成交", "持仓", "均价", "日期"]
    )
    data_df = data_df[["日期", "时间", "价格", "成交", "持仓", "均价"]]
    data_df["日期"] = pd.to_datetime(data_df["日期"], errors="coerce").dt.date
    data_df["日期"] = data_df["日期"].ffill()
    data_df["价格"] = pd.to_numeric(data_df["价格"], errors="coerce")
    data_df["成交"] = pd.to_numeric(data_df["成交"], errors="coerce")
    data_df["持仓"] = pd.to_numeric(data_df["持仓"], errors="coerce")
    data_df["均价"] = pd.to_numeric(data_df["均价"], errors="coerce")
    return data_df


def option_sse_daily_sina(symbol: str = "10003889") -> pd.DataFrame:
    """
    指定期权的日频率数据
    :param symbol: 期权代码
    :type symbol: str
    :return: 指定期权的所有日频率历史数据
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/jsonp_v2.php//StockOptionDaylineService.getSymbolInfo"
    params = {"symbol": f"CON_OP_{symbol}"}
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://stock.finance.sina.com.cn/option/quotes.html",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "script",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_text = r.text
    data_json = json.loads(data_text[data_text.find("(") + 1 : data_text.rfind(")")])
    temp_df = pd.DataFrame(data_json)
    temp_df.columns = ["日期", "开盘", "最高", "最低", "收盘", "成交量"]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    return temp_df


def option_finance_minute_sina(symbol: str = "10002530") -> pd.DataFrame:
    """
    指定期权的分钟频率数据
    https://stock.finance.sina.com.cn/option/quotes.html
    :param symbol: 期权代码
    :type symbol: str
    :return: 指定期权的分钟频率数据
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionDaylineService.getFiveDayLine"
    params = {
        "symbol": f"CON_OP_{symbol}",
    }
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://stock.finance.sina.com.cn/option/quotes.html",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "script",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/97.0.4692.71 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_text = r.json()
    temp_df = pd.DataFrame()
    for item in data_text["result"]["data"]:
        temp_df = pd.concat(objs=[temp_df, pd.DataFrame(item)], ignore_index=True)
    temp_df.ffill(inplace=True)
    temp_df.columns = ["time", "price", "volume", "_", "average_price", "date"]
    temp_df = temp_df[["date", "time", "price", "average_price", "volume"]]
    temp_df["price"] = pd.to_numeric(temp_df["price"], errors="coerce")
    temp_df["average_price"] = pd.to_numeric(temp_df["average_price"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
    return temp_df


@lru_cache()
def __option_current_em() -> pd.DataFrame:
    inner_option_current_em_df = option_current_em()
    return inner_option_current_em_df


def option_minute_em(symbol: str = "MO2404-P-4450") -> pd.DataFrame:
    """
    东方财富网-行情中心-期权市场-分时行情
    https://wap.eastmoney.com/quote/stock/151.cu2404P61000.html
    :param symbol: 期权代码; 通过调用 ak.option_current_em() 获取
    :type symbol: str
    :return: 指定期权的分钟频率数据
    :rtype: pandas.DataFrame
    """
    inner_option_current_em_df = __option_current_em()
    inner_option_current_em_df["标识"] = (
        inner_option_current_em_df["市场标识"].astype(str)
        + "."
        + inner_option_current_em_df["代码"]
    )
    id_ = inner_option_current_em_df[inner_option_current_em_df["代码"] == symbol][
        "标识"
    ].values[0]
    url = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
    params = {
        "secid": id_,
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f17",
        "fields2": "f51,f53,f54,f55,f56,f57,f58",
        "iscr": "0",
        "iscca": "0",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "ndays": "1",
        "cb": "quotepushdata1",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = json.loads(data_text[data_text.find("(") + 1 : data_text.rfind(")")])
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["trends"]])
    temp_df.columns = ["time", "close", "high", "low", "volume", "amount", "-"]
    temp_df = temp_df[["time", "close", "high", "low", "volume", "amount"]]
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
    temp_df["amount"] = pd.to_numeric(temp_df["amount"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    option_cffex_sz50_list_sina_df = option_cffex_sz50_list_sina()
    print(option_cffex_sz50_list_sina_df)

    # 期权-中金所-沪深300指数
    option_cffex_hs300_list_sina_df = option_cffex_hs300_list_sina()
    print(option_cffex_hs300_list_sina_df)

    option_cffex_zz1000_list_sina_df = option_cffex_zz1000_list_sina()
    print(option_cffex_zz1000_list_sina_df)

    option_cffex_sz50_spot_sina_df = option_cffex_sz50_spot_sina(symbol="ho2303")
    print(option_cffex_sz50_spot_sina_df)

    option_cffex_hs300_spot_sina_df = option_cffex_hs300_spot_sina(symbol="io2209")
    print(option_cffex_hs300_spot_sina_df)

    option_cffex_zz1000_spot_sina_df = option_cffex_zz1000_spot_sina(symbol="mo2209")
    print(option_cffex_zz1000_spot_sina_df)

    option_cffex_sz50_daily_sina_df = option_cffex_sz50_daily_sina(symbol="ho2303P2350")
    print(option_cffex_sz50_daily_sina_df)

    option_cffex_hs300_daily_sina_df = option_cffex_hs300_daily_sina(
        symbol="io2202P4350"
    )
    print(option_cffex_hs300_daily_sina_df)

    option_cffex_zz1000_daily_sina_df = option_cffex_zz1000_daily_sina(
        symbol="mo2208P6200"
    )
    print(option_cffex_zz1000_daily_sina_df)

    # 期权-上交所-50ETF
    option_sse_list_sina_df = option_sse_list_sina(symbol="50ETF", exchange="null")
    print(option_sse_list_sina_df)

    option_sse_expire_day_sina_df = option_sse_expire_day_sina(
        trade_date="202308", symbol="50ETF", exchange="null"
    )
    print(option_sse_expire_day_sina_df)

    option_sse_codes_sina_df = option_sse_codes_sina(
        symbol="看跌期权", trade_date="202209", underlying="510050"
    )
    print(option_sse_codes_sina_df)

    option_sse_spot_price_sina_df = option_sse_spot_price_sina(symbol="10003686")
    print(option_sse_spot_price_sina_df)

    option_sse_underlying_spot_price_sina_df = option_sse_underlying_spot_price_sina(
        symbol="sh510300"
    )
    print(option_sse_underlying_spot_price_sina_df)

    option_sse_greeks_sina_df = option_sse_greeks_sina(symbol="10004023")
    print(option_sse_greeks_sina_df)

    option_sse_minute_sina_df = option_sse_minute_sina(symbol="10004023")
    print(option_sse_minute_sina_df)

    option_sse_daily_sina_df = option_sse_daily_sina(symbol="10004023")
    print(option_sse_daily_sina_df)

    option_finance_minute_sina_df = option_finance_minute_sina(symbol="10004023")
    print(option_finance_minute_sina_df)

    option_current_em_df = option_current_em()
    print(option_current_em_df)

    option_minute_em_df = option_minute_em(symbol="10008594")
    print(option_minute_em_df)
