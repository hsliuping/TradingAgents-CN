#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/8/20 20:00
Desc: 东方财富网-数据中心-研究报告-东方财富分析师指数
https://data.eastmoney.com/invest/invest/list.html
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm
from akshare.utils.cons import headers


def stock_analyst_rank_em(year: str = "2024") -> pd.DataFrame:
    """
    东方财富网-数据中心-研究报告-东方财富分析师指数-东方财富分析师指数
    https://data.eastmoney.com/invest/invest/list.html
    :param year: 从 2015 年至今
    :type year: str
    :return: 东方财富分析师指数
    :rtype: pandas.DataFrame
    """
    url = "https://data.eastmoney.com/dataapi/invest/list"
    params = {
        "sortColumns": "YEAR_YIELD",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_ANALYST_INDEX_RANK",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(YEAR="{year}")',
        "distinct": "ANALYST_CODE",
        "limit": "top100",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        data_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, data_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = list(range(1, len(big_df) + 1))
    big_df.columns = [
        "序号",
        "分析师ID",
        "分析师名称",
        "更新日期",
        "年度",
        "分析师单位",
        "_",
        "年度指数",
        f"{year}年收益率",
        "3个月收益率",
        "6个月收益率",
        "12个月收益率",
        "成分股个数",
        f"{year}最新个股评级-股票名称",
        "_",
        f"{year}最新个股评级-股票代码",
        "_",
        "行业代码",
        "行业",
    ]
    big_df = big_df[
        [
            "序号",
            "分析师名称",
            "分析师单位",
            "年度指数",
            f"{year}年收益率",
            "3个月收益率",
            "6个月收益率",
            "12个月收益率",
            "成分股个数",
            f"{year}最新个股评级-股票名称",
            f"{year}最新个股评级-股票代码",
            "分析师ID",
            "行业代码",
            "行业",
            "更新日期",
            "年度",
        ]
    ]
    big_df["更新日期"] = pd.to_datetime(big_df["更新日期"], errors="coerce").dt.date
    big_df["年度指数"] = pd.to_numeric(big_df["年度指数"], errors="coerce")
    big_df[f"{year}年收益率"] = pd.to_numeric(
        big_df[f"{year}年收益率"], errors="coerce"
    )
    big_df["3个月收益率"] = pd.to_numeric(big_df["3个月收益率"], errors="coerce")
    big_df["6个月收益率"] = pd.to_numeric(big_df["6个月收益率"], errors="coerce")
    big_df["12个月收益率"] = pd.to_numeric(big_df["12个月收益率"], errors="coerce")
    big_df["成分股个数"] = pd.to_numeric(big_df["成分股个数"], errors="coerce")
    return big_df


def stock_analyst_detail_em(
    analyst_id: str = "11000200926", indicator: str = "最新跟踪成分股"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-研究报告-东方财富分析师指数-东方财富分析师指数2020最新排行-分析师详情
    https://data.eastmoney.com/invest/invest/11000257131.html
    :param analyst_id: 分析师 ID, 从 ak.stock_analyst_rank_em() 获取
    :type analyst_id: str
    :param indicator: choice of {"最新跟踪成分股", "历史跟踪成分股", "历史指数"}
    :type indicator: str
    :return: 具体指标的数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter.eastmoney.com/special/api/data/v1/get"
    if indicator == "最新跟踪成分股":
        params = {
            "reportName": "RPT_RESEARCHER_NTCSTOCK",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "sortColumns": "CHANGE_DATE",
            "sortTypes": "-1",
            "pageNumber": "1",
            "pageSize": "1000",
            "filter": f'(ANALYST_CODE="{analyst_id}")',
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = list(range(1, len(temp_df) + 1))
        temp_df.columns = [
            "序号",
            "最新评级日期",
            "-",
            "-",
            "-",
            "-",
            "股票代码",
            "-",
            "股票名称",
            "调入日期",
            "当前评级名称",
            "成交价格(前复权)",
            "最新价格",
            "阶段涨跌幅",
        ]
        temp_df = temp_df[
            [
                "序号",
                "股票代码",
                "股票名称",
                "调入日期",
                "最新评级日期",
                "当前评级名称",
                "成交价格(前复权)",
                "最新价格",
                "阶段涨跌幅",
            ]
        ]
        temp_df["调入日期"] = pd.to_datetime(
            temp_df["调入日期"], errors="coerce"
        ).dt.date
        temp_df["最新评级日期"] = pd.to_datetime(
            temp_df["最新评级日期"], errors="coerce"
        ).dt.date
        temp_df["成交价格(前复权)"] = pd.to_numeric(
            temp_df["成交价格(前复权)"], errors="coerce"
        )
        temp_df["最新价格"] = pd.to_numeric(temp_df["最新价格"], errors="coerce")
        temp_df["阶段涨跌幅"] = pd.to_numeric(temp_df["阶段涨跌幅"], errors="coerce")
        return temp_df
    elif indicator == "历史跟踪成分股":
        params = {
            "reportName": "RPT_RESEARCHER_HISTORYSTOCK",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "sortColumns": "CHANGE_DATE",
            "sortTypes": "-1",
            "pageNumber": "1",
            "pageSize": "1000",
            "filter": f'(ANALYST_CODE="{analyst_id}")',
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = list(range(1, len(temp_df) + 1))
        temp_df.columns = [
            "序号",
            "-",
            "-",
            "-",
            "股票代码",
            "-",
            "股票名称",
            "调入日期",
            "调出日期",
            "调入时评级名称",
            "调出原因",
            "累计涨跌幅",
        ]
        temp_df = temp_df[
            [
                "序号",
                "股票代码",
                "股票名称",
                "调入日期",
                "调出日期",
                "调入时评级名称",
                "调出原因",
                "累计涨跌幅",
            ]
        ]
        temp_df["调入日期"] = pd.to_datetime(
            temp_df["调入日期"], errors="coerce"
        ).dt.date
        temp_df["调出日期"] = pd.to_datetime(
            temp_df["调出日期"], errors="coerce"
        ).dt.date
        temp_df["累计涨跌幅"] = pd.to_numeric(temp_df["累计涨跌幅"], errors="coerce")
        return temp_df
    elif indicator == "历史指数":
        params = {
            "reportName": "RPT_RESEARCHER_DETAILS",
            "columns": "ALL",
            "sortColumns": "TRADE_DATE",
            "sortTypes": "-1",
            "filter": f'(ANALYST_CODE="{analyst_id}")',
            "source": "WEB",
            "client": "WEB",
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        temp_df = temp_df[
            [
                "TRADE_DATE",
                "INDEX_HVALUE",
            ]
        ]
        temp_df.columns = ["date", "value"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        temp_df.sort_values(["date"], inplace=True, ignore_index=True)
        return temp_df


if __name__ == "__main__":
    stock_analyst_rank_em_df = stock_analyst_rank_em(year="2024")
    print(stock_analyst_rank_em_df)

    stock_analyst_detail_em_df = stock_analyst_detail_em(
        analyst_id="11000200926", indicator="最新跟踪成分股"
    )
    print(stock_analyst_detail_em_df)

    stock_analyst_detail_em_df = stock_analyst_detail_em(
        analyst_id="11000200926", indicator="历史跟踪成分股"
    )
    print(stock_analyst_detail_em_df)

    stock_analyst_detail_em_df = stock_analyst_detail_em(
        analyst_id="11000200926", indicator="历史指数"
    )
    print(stock_analyst_detail_em_df)
