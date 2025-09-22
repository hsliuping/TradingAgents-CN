#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/11/8 17:00
Desc: 董监高及相关人员持股变动
北京证券交易所-信息披露-监管信息-董监高及相关人员持股变动
https://www.bse.cn/disclosure/djg_sharehold_change.html
深圳证券交易所-信息披露-监管信息公开-董监高人员股份变动
https://www.szse.cn/disclosure/supervision/change/index.html
上海证券交易所-披露-监管信息公开-公司监管-董董监高人员股份变动
https://www.sse.com.cn/disclosure/credibility/supervision/change/
"""

import json

import pandas as pd
import requests
from tqdm import tqdm


def stock_share_hold_change_sse(symbol: str = "600000") -> pd.DataFrame:
    """
    上海证券交易所-披露-监管信息公开-公司监管-董董监高人员股份变动
    https://www.sse.com.cn/disclosure/credibility/supervision/change/
    :param symbol: choice of {"全部", "具体股票代码"}
    :type symbol: str
    :return: 董监高人员股份变动
    :rtype: pandas.DataFrame
    """
    url = "https://query.sse.com.cn/commonQuery.do"
    params = {
        "isPagination": "true",
        "pageHelp.pageSize": "100",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
        "sqlId": "COMMON_SSE_XXPL_CXJL_SSGSGFBDQK_S",
        "COMPANY_CODE": "",
        "NAME": "",
        "BEGIN_DATE": "1990-01-01",
        "END_DATE": "2050-01-01",
        "BOARDTYPE": "",
    }
    params if symbol == "全部" else params.update({"COMPANY_CODE": symbol})
    headers = {
        "Host": "query.sse.com.cn",
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
    }
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    total_page = data_json["pageHelp"]["pageCount"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageHelp.pageNo": page,
                "pageHelp.beginPage": page,
                "pageHelp.endPage": page,
            }
        )
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.rename(
        columns={
            "STOCK_TYPE": "股票种类",
            "COMPANY_ABBR": "公司名称",
            "NUM": "-",
            "CURRENT_AVG_PRICE": "本次变动平均价格",
            "CHANGE_DATE": "变动日期",
            "HOLDSTOCK_NUM": "变动后持股数",
            "NAME": "姓名",
            "CHANGE_REASON": "变动原因",
            "DUTY": "职务",
            "CURRENCY_TYPE": "货币种类",
            "COMPANY_CODE": "公司代码",
            "FORM_DATE": "填报日期",
            "CHANGE_NUM": "变动数",
            "CURRENT_NUM": "本次变动前持股数",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "公司代码",
            "公司名称",
            "姓名",
            "职务",
            "股票种类",
            "货币种类",
            "本次变动前持股数",
            "变动数",
            "本次变动平均价格",
            "变动后持股数",
            "变动原因",
            "变动日期",
            "填报日期",
        ]
    ]
    big_df["变动日期"] = pd.to_datetime(big_df["变动日期"], errors="coerce").dt.date
    big_df["填报日期"] = pd.to_datetime(big_df["填报日期"], errors="coerce").dt.date

    big_df["本次变动前持股数"] = pd.to_numeric(
        big_df["本次变动前持股数"], errors="coerce"
    )
    big_df["变动数"] = pd.to_numeric(big_df["变动数"], errors="coerce")
    big_df["本次变动平均价格"] = pd.to_numeric(
        big_df["本次变动平均价格"], errors="coerce"
    )
    big_df["变动后持股数"] = pd.to_numeric(big_df["变动后持股数"], errors="coerce")
    return big_df


def stock_share_hold_change_szse(symbol: str = "全部") -> pd.DataFrame:
    """
    深圳证券交易所-信息披露-监管信息公开-董监高人员股份变动
    https://www.szse.cn/disclosure/supervision/change/index.html
    :param symbol: choice of {"全部", "具体股票代码"}
    :type symbol: str
    :return: 董监高人员股份变动
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport/data"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
    }
    params = {
        "SHOWTYPE": "JSON",
        "CATALOGID": "1801_cxda",
        "TABKEY": "tab1",
        "PAGENO": "1",
        "random": "0.7874198771222201",
    }
    params if symbol == "全部" else params.update({"txtDMorJC": symbol})
    r = requests.get(url, headers=headers, params=params)
    data_json = r.json()
    total_page = data_json[0]["metadata"]["pagecount"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "PAGENO": page,
            }
        )
        r = requests.get(url, headers=headers, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json[0]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.rename(
        columns={
            "zqdm": "证券代码",
            "zqjc": "证券简称",
            "ggxm": "董监高姓名",
            "jyrq": "变动日期",
            "bdgs": "变动股份数量",
            "bdjj": "成交均价",
            "bdyy": "变动原因",
            "cgbdbl": "变动比例",
            "cgzs": "当日结存股数",
            "gdxm": "股份变动人姓名",
            "zw": "职务",
            "gxlb": "变动人与董监高的关系",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "证券代码",
            "证券简称",
            "董监高姓名",
            "变动日期",
            "变动股份数量",
            "成交均价",
            "变动原因",
            "变动比例",
            "当日结存股数",
            "股份变动人姓名",
            "职务",
            "变动人与董监高的关系",
        ]
    ]
    big_df["变动日期"] = pd.to_datetime(big_df["变动日期"], errors="coerce").dt.date
    big_df["变动股份数量"] = pd.to_numeric(big_df["变动股份数量"], errors="coerce")
    big_df["成交均价"] = pd.to_numeric(big_df["成交均价"], errors="coerce")
    big_df["变动比例"] = pd.to_numeric(big_df["变动比例"], errors="coerce")
    big_df["当日结存股数"] = big_df["当日结存股数"].str.replace(",", "")
    big_df["当日结存股数"] = pd.to_numeric(big_df["当日结存股数"], errors="coerce")
    return big_df


def stock_share_hold_change_bse(symbol: str = "430489") -> pd.DataFrame:
    """
    北京证券交易所-信息披露-监管信息-董监高及相关人员持股变动
    https://www.bse.cn/disclosure/djg_sharehold_change.html
    :param symbol: choice of {"全部", "具体股票代码"}
    :type symbol: str
    :return: 董监高及相关人员持股变动
    :rtype: pandas.DataFrame
    """
    symbol = symbol if symbol != "全部" else ""
    params = {
        "page": "0",
        "startTime": "",
        "endTime": "",
        "stockCode": symbol,
        "djgName": "",
        "ssgs": "1",
        "sortfield": "bean.change_date desc, bean.stock_code asc, bean.change_amount desc, bean.price",
        "sorttype": "desc",
    }
    url = "https://www.bse.cn/djgCgbdController/getDjgCgbdList.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/93.0.4577.63 Safari/537.36",
    }
    r = requests.get(url, headers=headers, params=params)
    data_text = r.text
    data_text = data_text.strip("null(").strip(")")
    data_json = json.loads(data_text)
    total_page = data_json[0]["result"]["totalPages"]
    big_df = pd.DataFrame()
    for page in tqdm(range(0, total_page), leave=False):
        params.update(
            {
                "page": page,
            }
        )
        r = requests.get(url, headers=headers, params=params)
        data_text = r.text
        data_text = data_text.strip("null(").strip(")")
        data_json = json.loads(data_text)
        temp_df = pd.DataFrame(data_json[0]["result"]["content"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.rename(
        columns={
            "changeAmount": "变动股数",
            "changeDate": "变动日期",
            "createTime": "-",
            "djgName": "姓名",
            "duty": "职务",
            "id": "-",
            "infoId": "-",
            "newAmount": "变动后持股数",
            "preAmount": "变动前持股数",
            "price": "变动均价",
            "reason": "变动原因",
            "ssgs": "-",
            "stockCode": "代码",
            "stockName": "简称",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "代码",
            "简称",
            "姓名",
            "职务",
            "变动日期",
            "变动股数",
            "变动前持股数",
            "变动后持股数",
            "变动均价",
            "变动原因",
        ]
    ]
    big_df["变动日期"] = pd.to_datetime(big_df["变动日期"], errors="coerce").dt.date
    big_df["变动股数"] = pd.to_numeric(big_df["变动股数"], errors="coerce")
    big_df["变动前持股数"] = pd.to_numeric(big_df["变动前持股数"], errors="coerce")
    big_df["变动后持股数"] = pd.to_numeric(big_df["变动后持股数"], errors="coerce")
    big_df["变动均价"] = pd.to_numeric(big_df["变动均价"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_share_hold_change_sse_df = stock_share_hold_change_sse(symbol="600000")
    print(stock_share_hold_change_sse_df)

    stock_share_hold_change_sse_df = stock_share_hold_change_sse(symbol="全部")
    print(stock_share_hold_change_sse_df)

    stock_share_hold_change_szse_df = stock_share_hold_change_szse(symbol="001308")
    print(stock_share_hold_change_szse_df)

    stock_share_hold_change_szse_df = stock_share_hold_change_szse(symbol="全部")
    print(stock_share_hold_change_szse_df)

    stock_share_hold_change_bse_df = stock_share_hold_change_bse(symbol="430489")
    print(stock_share_hold_change_bse_df)

    stock_share_hold_change_bse_df = stock_share_hold_change_bse(symbol="全部")
    print(stock_share_hold_change_bse_df)
