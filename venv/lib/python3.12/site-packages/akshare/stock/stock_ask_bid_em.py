#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/16 18:30
Desc: 东方财富-行情报价
https://quote.eastmoney.com/sz000001.html
"""

import pandas as pd
import requests


def stock_bid_ask_em(symbol: str = "000001") -> pd.DataFrame:
    """
    东方财富-行情报价
    https://quote.eastmoney.com/sz000001.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 行情报价
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    market_code = 1 if symbol.startswith("6") else 0
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": "f120,f121,f122,f174,f175,f59,f163,f43,f57,f58,f169,f170,f46,f44,f51,"
        "f168,f47,f164,f116,f60,f45,f52,f50,f48,f167,f117,f71,f161,f49,f530,"
        "f135,f136,f137,f138,f139,f141,f142,f144,f145,f147,f148,f140,f143,f146,"
        "f149,f55,f62,f162,f92,f173,f104,f105,f84,f85,f183,f184,f185,f186,f187,"
        "f188,f189,f190,f191,f192,f107,f111,f86,f177,f78,f110,f262,f263,f264,f267,"
        "f268,f255,f256,f257,f258,f127,f199,f128,f198,f259,f260,f261,f171,f277,f278,"
        "f279,f288,f152,f250,f251,f252,f253,f254,f269,f270,f271,f272,f273,f274,f275,"
        "f276,f265,f266,f289,f290,f286,f285,f292,f293,f294,f295",
        "secid": f"{market_code}.{symbol}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    tick_dict = {
        "sell_5": data_json["data"]["f31"],
        "sell_5_vol": data_json["data"]["f32"] * 100,
        "sell_4": data_json["data"]["f33"],
        "sell_4_vol": data_json["data"]["f34"] * 100,
        "sell_3": data_json["data"]["f35"],
        "sell_3_vol": data_json["data"]["f36"] * 100,
        "sell_2": data_json["data"]["f37"],
        "sell_2_vol": data_json["data"]["f38"] * 100,
        "sell_1": data_json["data"]["f39"],
        "sell_1_vol": data_json["data"]["f40"] * 100,
        "buy_1": data_json["data"]["f19"],
        "buy_1_vol": data_json["data"]["f20"] * 100,
        "buy_2": data_json["data"]["f17"],
        "buy_2_vol": data_json["data"]["f18"] * 100,
        "buy_3": data_json["data"]["f15"],
        "buy_3_vol": data_json["data"]["f16"] * 100,
        "buy_4": data_json["data"]["f13"],
        "buy_4_vol": data_json["data"]["f14"] * 100,
        "buy_5": data_json["data"]["f11"],
        "buy_5_vol": data_json["data"]["f12"] * 100,
        "最新": data_json["data"]["f43"],
        "均价": data_json["data"]["f71"],
        "涨幅": data_json["data"]["f170"],
        "涨跌": data_json["data"]["f169"],
        "总手": data_json["data"]["f47"],
        "金额": data_json["data"]["f48"],
        "换手": data_json["data"]["f168"],
        "量比": data_json["data"]["f50"],
        "最高": data_json["data"]["f44"],
        "最低": data_json["data"]["f45"],
        "今开": data_json["data"]["f46"],
        "昨收": data_json["data"]["f60"],
        "涨停": data_json["data"]["f51"],
        "跌停": data_json["data"]["f52"],
        "外盘": data_json["data"]["f49"],
        "内盘": data_json["data"]["f161"],
    }
    temp_df = pd.DataFrame.from_dict(tick_dict, orient="index")
    temp_df.reset_index(inplace=True)
    temp_df.columns = ["item", "value"]
    return temp_df


if __name__ == "__main__":
    stock_bid_ask_em_df = stock_bid_ask_em(symbol="000001")
    print(stock_bid_ask_em_df)
