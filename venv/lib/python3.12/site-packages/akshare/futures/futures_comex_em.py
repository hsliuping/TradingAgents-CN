#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/11/15 18:00
Desc: 东方财富网-数据中心-期货期权-COMEX库存数据
https://data.eastmoney.com/pmetal/comex/by.html
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def futures_comex_inventory(symbol: str = "黄金") -> pd.DataFrame:
    """
    东方财富网-数据中心-期货期权-COMEX库存数据
    https://data.eastmoney.com/pmetal/comex/by.html
    :param symbol: choice of {"黄金", "白银"}
    :type symbol: str
    :return: COMEX库存数据
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "黄金": "EMI00069026",
        "白银": "EMI00069027",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_FUTUOPT_GOLDSIL",
        "columns": "ALL",
        "quoteColumns": "",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(INDICATOR_ID1="{symbol_map[symbol]}")(@STORAGE_TON<>"NULL")',
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "REPORT_DATE": "日期",
            "INDICATOR_NAME": "-",
            "INDICATOR_ID1": "-",
            "STORAGE_TON": f"COMEX{symbol}库存量-吨",
            "STORAGE_OUNCE": f"COMEX{symbol}库存量-盎司",
            "INDICATOR_ID2": "-",
            "NETPOSITION_TON": "-",
            "NETPOSITION_OUNCE": "-",
            "NETPOSITION_DOLLAR": "-",
            "INDICATOR_ID3": "-",
            "OPENPOSI_STOCK": "-",
            "OPENPOSTOCK_WECHANGE": "-",
            "OPENPOSI_STOCK_SUM": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "日期",
            f"COMEX{symbol}库存量-吨",
            f"COMEX{symbol}库存量-盎司",
        ]
    ]
    big_df[f"COMEX{symbol}库存量-吨"] = pd.to_numeric(
        big_df[f"COMEX{symbol}库存量-吨"], errors="coerce"
    )
    big_df[f"COMEX{symbol}库存量-盎司"] = pd.to_numeric(
        big_df[f"COMEX{symbol}库存量-盎司"], errors="coerce"
    )
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df.sort_values(["日期"], inplace=True, ignore_index=True)
    big_df["序号"] = range(1, len(big_df) + 1)
    return big_df


if __name__ == "__main__":
    futures_comex_inventory_df = futures_comex_inventory(symbol="黄金")
    print(futures_comex_inventory_df)
