#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/6 15:00
Desc: 东方财富网-数据中心-研究报告-盈利预测
https://data.eastmoney.com/report/profitforecast.jshtml
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_profit_forecast_em(symbol: str = "") -> pd.DataFrame:
    """
    东方财富网-数据中心-研究报告-盈利预测
    https://data.eastmoney.com/report/profitforecast.jshtml
    :param symbol: "", 默认为获取全部数据; symbol="船舶制造", 则获取具体行业板块的数据;
    行业板块可以通过 ak.stock_board_industry_name_em() 接口获取
    :type symbol: str
    :return: 盈利预测
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_WEB_RESPREDICT",
        "columns": "WEB_RESPREDICT",
        "pageNumber": "1",
        "pageSize": "500",
        "sortTypes": "-1",
        "sortColumns": "RATING_ORG_NUM",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    if symbol:
        params.update({"filter": f'(INDUSTRY_BOARD="{symbol}")'})
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = int(data_json["result"]["pages"])
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
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

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    year1 = str(big_df["YEAR1"].mode().values[0])
    year2 = str(big_df["YEAR2"].mode().values[0])
    year3 = str(big_df["YEAR3"].mode().values[0])
    year4 = str(big_df["YEAR4"].mode().values[0])
    big_df.columns = [
        "序号",
        "-",
        "代码",
        "名称",
        "研报数",
        "机构投资评级(近六个月)-买入",
        "机构投资评级(近六个月)-增持",
        "机构投资评级(近六个月)-中性",
        "机构投资评级(近六个月)-减持",
        "机构投资评级(近六个月)-卖出",
        "-",
        "_",
        f"{year1}预测每股收益",
        "-",
        "_",
        f"{year2}预测每股收益",
        "-",
        "_",
        f"{year3}预测每股收益",
        "-",
        "_",
        f"{year4}预测每股收益",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "研报数",
            "机构投资评级(近六个月)-买入",
            "机构投资评级(近六个月)-增持",
            "机构投资评级(近六个月)-中性",
            "机构投资评级(近六个月)-减持",
            "机构投资评级(近六个月)-卖出",
            f"{year1}预测每股收益",
            f"{year2}预测每股收益",
            f"{year3}预测每股收益",
            f"{year4}预测每股收益",
        ]
    ]
    big_df["机构投资评级(近六个月)-买入"] = big_df[
        "机构投资评级(近六个月)-买入"
    ].fillna(0)
    big_df["机构投资评级(近六个月)-增持"] = big_df[
        "机构投资评级(近六个月)-增持"
    ].fillna(0)
    big_df["研报数"] = pd.to_numeric(big_df["研报数"], errors="coerce")
    big_df["机构投资评级(近六个月)-买入"] = pd.to_numeric(
        big_df["机构投资评级(近六个月)-买入"], errors="coerce"
    )
    big_df["机构投资评级(近六个月)-增持"] = pd.to_numeric(
        big_df["机构投资评级(近六个月)-增持"], errors="coerce"
    )
    big_df["机构投资评级(近六个月)-中性"] = pd.to_numeric(
        big_df["机构投资评级(近六个月)-中性"], errors="coerce"
    )
    big_df["机构投资评级(近六个月)-减持"] = pd.to_numeric(
        big_df["机构投资评级(近六个月)-减持"], errors="coerce"
    )
    big_df["机构投资评级(近六个月)-卖出"] = pd.to_numeric(
        big_df["机构投资评级(近六个月)-卖出"], errors="coerce"
    )
    big_df["机构投资评级(近六个月)-中性"] = big_df[
        "机构投资评级(近六个月)-中性"
    ].fillna(0)
    big_df["机构投资评级(近六个月)-减持"] = big_df[
        "机构投资评级(近六个月)-减持"
    ].fillna(0)
    big_df["机构投资评级(近六个月)-卖出"] = big_df[
        "机构投资评级(近六个月)-卖出"
    ].fillna(0)
    big_df[f"{year1}预测每股收益"] = pd.to_numeric(
        big_df[f"{year1}预测每股收益"], errors="coerce"
    )
    big_df[f"{year2}预测每股收益"] = pd.to_numeric(
        big_df[f"{year2}预测每股收益"], errors="coerce"
    )
    big_df[f"{year3}预测每股收益"] = pd.to_numeric(
        big_df[f"{year3}预测每股收益"], errors="coerce"
    )
    big_df[f"{year4}预测每股收益"] = pd.to_numeric(
        big_df[f"{year4}预测每股收益"], errors="coerce"
    )
    big_df.sort_values(["研报数"], ascending=False, inplace=True, ignore_index=True)
    big_df["序号"] = range(1, len(big_df) + 1)
    return big_df


if __name__ == "__main__":
    stock_profit_forecast_em_df = stock_profit_forecast_em(symbol="航运港口")
    print(stock_profit_forecast_em_df)
