#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/11 22:00
Desc: 东方财富网-经济数据-银行间拆借利率
https://data.eastmoney.com/shibor/shibor.aspx
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def rate_interbank(
    market: str = "上海银行同业拆借市场",
    symbol: str = "Shibor人民币",
    indicator: str = "隔夜",
):
    """
    东方财富-拆借利率一览-具体市场的具体品种的具体指标的拆借利率数据
    具体 market 和 symbol 参见: https://data.eastmoney.com/shibor/shibor.aspx?m=sg&t=88&d=99333&cu=sgd&type=009065&p=79
    :param market: choice of {"上海银行同业拆借市场", "中国银行同业拆借市场", "伦敦银行同业拆借市场", "欧洲银行同业拆借市场", "香港银行同业拆借市场", "新加坡银行同业拆借市场"}
    :type market: str
    :param symbol: choice of {"Shibor人民币", "Chibor人民币", "Libor英镑", "***", "Sibor美元"}
    :type symbol: str
    :param indicator: choice of {"隔夜", "1周", "2周", "***", "1年"}
    :type indicator: str
    :return: 具体市场的具体品种的具体指标的拆借利率数据
    :rtype: pandas.DataFrame
    """
    market_map = {
        "上海银行同业拆借市场": "001",
        "中国银行同业拆借市场": "002",
        "伦敦银行同业拆借市场": "003",
        "欧洲银行同业拆借市场": "004",
        "香港银行同业拆借市场": "005",
        "新加坡银行同业拆借市场": "006",
    }
    symbol_map = {
        "Shibor人民币": "CNY",
        "Chibor人民币": "CNY",
        "Libor英镑": "GBP",
        "Libor欧元": "EUR",
        "Libor美元": "USD",
        "Libor日元": "JPY",
        "Euribor欧元": "EUR",
        "Hibor美元": "USD",
        "Hibor人民币": "CNH",
        "Hibor港币": "HKD",
        "Sibor星元": "SGD",
        "Sibor美元": "USD",
    }
    indicator_map = {
        "隔夜": "001",
        "1周": "101",
        "2周": "102",
        "3周": "103",
        "1月": "201",
        "2月": "202",
        "3月": "203",
        "4月": "204",
        "5月": "205",
        "6月": "206",
        "7月": "207",
        "8月": "208",
        "9月": "209",
        "10月": "210",
        "11月": "211",
        "1年": "301",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_IMP_INTRESTRATEN",
        "columns": "REPORT_DATE,REPORT_PERIOD,IR_RATE,CHANGE_RATE,INDICATOR_ID,"
        "LATEST_RECORD,MARKET,MARKET_CODE,CURRENCY,CURRENCY_CODE",
        "quoteColumns": "",
        "filter": f"""(MARKET_CODE="{market_map[market]}")(CURRENCY_CODE="{symbol_map[symbol]}")
        (INDICATOR_ID="{indicator_map[indicator]}")""",
        "pageNumber": "1",
        "pageSize": "500",
        "sortTypes": "-1",
        "sortColumns": "REPORT_DATE",
        "source": "WEB",
        "client": "WEB",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
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
                "p": page,
                "pageNo": page,
                "pageNum": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "报告日",
        "-",
        "利率",
        "涨跌",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "报告日",
            "利率",
            "涨跌",
        ]
    ]
    big_df["报告日"] = pd.to_datetime(big_df["报告日"], errors="coerce").dt.date
    big_df["利率"] = pd.to_numeric(big_df["利率"], errors="coerce")
    big_df["涨跌"] = pd.to_numeric(big_df["涨跌"], errors="coerce")
    big_df.sort_values(["报告日"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


if __name__ == "__main__":
    rate_interbank_shanghai_df = rate_interbank(
        market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="3月"
    )
    print(rate_interbank_shanghai_df)
