#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/12/26 18:30
Desc: 商品现货价格指数
https://finance.sina.com.cn/futuremarket/spotprice.shtml#titlePos_0
"""

import pandas as pd
import requests


def spot_goods(symbol: str = "波罗的海干散货指数") -> pd.DataFrame:
    """
    新浪财经-商品现货价格指数
    https://finance.sina.com.cn/futuremarket/spotprice.shtml#titlePos_0
    :param symbol: choice of {"波罗的海干散货指数", "钢坯价格指数", "澳大利亚粉矿价格"}
    :type symbol: str
    :return: 商品现货价格指数
    :rtype: pandas.DataFrame
    """
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/GoodsIndexService.get_goods_index"
    symbol_url_dict = {
        "波罗的海干散货指数": "BDI",
        "钢坯价格指数": "GP",
        "澳大利亚粉矿价格": "PB",
    }
    params = {"symbol": symbol_url_dict[symbol], "table": "0"}
    r = requests.get(url, params=params)
    r.encoding = "gbk"
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"]["data"])
    temp_df = temp_df[["opendate", "price", "zde", "zdf"]]
    temp_df.columns = ["日期", "指数", "涨跌额", "涨跌幅"]
    temp_df["日期"] = pd.to_datetime(
        temp_df["日期"], format="%Y-%m-%d", errors="coerce"
    ).dt.date
    temp_df["指数"] = pd.to_numeric(temp_df["指数"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df.dropna(inplace=True, ignore_index=True)
    return temp_df


if __name__ == "__main__":
    spot_goods_df = spot_goods(symbol="波罗的海干散货指数")
    print(spot_goods_df)
