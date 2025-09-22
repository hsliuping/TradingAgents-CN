#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/5/3 
Desc: 义乌小商品指数
目前可以通过这些接口直接请求到 JSON 数据
周价格指数：https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/history/piweek?gcCode=
月价格指数：https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/history/month?gcCode=
月景气指数：https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/history/bi?gcCode=
上涨：https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/get/rise
下跌：https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/get/drop
"""

import pandas as pd
import requests


def index_yw(symbol: str = "月景气指数") -> pd.DataFrame:
    """
    义乌小商品指数
    https://www.ywindex.com/Home/Product/index/
    :param symbol: choice of {"周价格指数", "月价格指数", "月景气指数"}
    :type symbol: str
    :return: 指数结果
    :rtype: pandas.DataFrame
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if symbol == "月景气指数":
        url = "https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/history/bi?gcCode="
        r = requests.get(url, verify=False)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df = temp_df[["indextimeno", "totalindex", "scopeindex", "benifitindex", "confidentindex"]]
        temp_df.columns = ["期数", "景气指数", "规模指数", "效益指数", "市场信心指数"]
        temp_df["期数"] = pd.to_datetime(temp_df["期数"], errors="coerce").dt.date
        temp_df["景气指数"] = pd.to_numeric(temp_df["景气指数"], errors="coerce")
        temp_df["规模指数"] = pd.to_numeric(temp_df["规模指数"], errors="coerce")
        temp_df["效益指数"] = pd.to_numeric(temp_df["效益指数"], errors="coerce")
        temp_df["市场信心指数"] = pd.to_numeric(
            temp_df["市场信心指数"], errors="coerce"
        )
        temp_df.sort_values(["期数"], inplace=True, ignore_index=True)
        return temp_df
    else:
        symbol_map = {
            "周价格指数": "piweek",
            "月价格指数": "month"
        }
        url = f"https://apiserver.chinagoods.com/yiwuindex/v1/active/industry/class/history/{symbol_map[symbol]}?gcCode="
        r = requests.get(url, verify=False)
        data_json = r.json()
        columns_name = {
            "indextimeno": "期数",
            "totalpriceindex": "价格指数",
            "stockdealpriceindex": "场内价格指数",
            "netdealpriceindex": "网上价格指数",
            "orderdealpriceindex": "订单价格指数",
            "outdealpriceindex": "出口价格指数",
        }
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = [columns_name[name] for name in temp_df.columns]
        temp_df["期数"] = pd.to_datetime(temp_df["期数"], errors="coerce").dt.date
        temp_df["价格指数"] = pd.to_numeric(temp_df["价格指数"], errors="coerce")
        temp_df["场内价格指数"] = pd.to_numeric(
            temp_df["场内价格指数"], errors="coerce"
        )
        temp_df["网上价格指数"] = pd.to_numeric(
            temp_df["网上价格指数"], errors="coerce"
        )
        temp_df["订单价格指数"] = pd.to_numeric(
            temp_df["订单价格指数"], errors="coerce"
        )
        temp_df["出口价格指数"] = pd.to_numeric(
            temp_df["出口价格指数"], errors="coerce"
        )
        temp_df.sort_values(by=["期数"], inplace=True, ignore_index=True)
        return temp_df


if __name__ == "__main__":
    index_yw_df = index_yw(symbol="周价格指数")
    print(index_yw_df)

    index_yw_df = index_yw(symbol="月价格指数")
    print(index_yw_df)

    index_yw_df = index_yw(symbol="月景气指数")
    print(index_yw_df)
    
