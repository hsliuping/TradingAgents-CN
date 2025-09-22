#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/10/23 13:00
Desc: 申万宏源研究-指数系列
https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
"""

import math

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def index_hist_sw(symbol: str = "801030", period: str = "day") -> pd.DataFrame:
    """
    申万宏源研究-指数发布-指数详情-指数历史数据
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex/releasedetail?code=801001&name=%E7%94%B3%E4%B8%8750
    :param symbol: 指数代码
    :type symbol: str
    :param period: choice of {"day", "week", "month"}
    :type period: str
    :return: 指数历史数据
    :rtype: pandas.DataFrame
    """
    period_map = {
        "day": "DAY",
        "week": "WEEK",
        "month": "MONTH",
    }
    url = "https://www.swsresearch.com/institute-sw/api/index_publish/trend/"
    params = {
        "swindexcode": symbol,
        "period": period_map[period],
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.rename(
        columns={
            "swindexcode": "代码",
            "bargaindate": "日期",
            "openindex": "开盘",
            "maxindex": "最高",
            "minindex": "最低",
            "closeindex": "收盘",
            "hike": "",
            "markup": "",
            "bargainamount": "成交量",
            "bargainsum": "成交额",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "代码",
            "日期",
            "收盘",
            "开盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def index_min_sw(symbol: str = "801001") -> pd.DataFrame:
    """
    申万宏源研究-指数发布-指数详情-指数分时数据
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex/releasedetail?code=801001&name=%E7%94%B3%E4%B8%8750
    :param symbol: 指数代码
    :type symbol: str
    :return: 指数分时数据
    :rtype: pandas.DataFrame
    """
    url = (
        "https://www.swsresearch.com/institute-sw/api/index_publish/details/timelines/"
    )
    params = {
        "swindexcode": symbol,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.rename(
        columns={
            "l1": "代码",
            "l2": "名称",
            "l8": "价格",
            "trading_date": "日期",
            "trading_time": "时间",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "代码",
            "名称",
            "价格",
            "日期",
            "时间",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["价格"] = pd.to_numeric(temp_df["价格"], errors="coerce")
    return temp_df


def index_component_sw(symbol: str = "801001") -> pd.DataFrame:
    """
    申万宏源研究-指数发布-指数详情-成分股
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex/releasedetail?code=801001&name=%E7%94%B3%E4%B8%8750
    :param symbol: 指数代码
    :type symbol: str
    :return: 成分股
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/institute-sw/api/index_publish/details/component_stocks/"
    params = {"swindexcode": symbol, "page": "1", "page_size": "10000"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["results"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "stockcode": "证券代码",
            "stockname": "证券名称",
            "newweight": "最新权重",
            "beginningdate": "计入日期",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "证券代码",
            "证券名称",
            "最新权重",
            "计入日期",
        ]
    ]
    temp_df["计入日期"] = pd.to_datetime(temp_df["计入日期"], errors="coerce").dt.date
    temp_df["最新权重"] = pd.to_numeric(temp_df["最新权重"], errors="coerce")
    return temp_df


def __index_realtime_sw(symbol: str = "大类风格指数") -> pd.DataFrame:
    """
    申万宏源研究-申万指数-股票指数
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
    :param symbol: choice of {"大类风格指数", "金创指数"}
    :type symbol: str
    :return: 指数系列实时行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/insWechatSw/dflgOrJcIndex/pageList"
    payload = {
        "pageNo": 1,
        "pageSize": 10,
        "indexTypeName": symbol,
        "sortField": "",
        "rule": "",
        "indexType": 1,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.post(url, json=payload, headers=headers, verify=False)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df.rename(
        columns={
            "swIndexCode": "指数代码",
            "swIndexName": "指数名称",
            "lastCloseIndex": "昨收盘",
            "lastMarkup": "日涨跌幅",
            "yearMarkup": "年涨跌幅",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "指数代码",
            "指数名称",
            "昨收盘",
            "日涨跌幅",
            "年涨跌幅",
        ]
    ]
    temp_df["昨收盘"] = pd.to_numeric(temp_df["昨收盘"], errors="coerce")
    temp_df["日涨跌幅"] = pd.to_numeric(temp_df["日涨跌幅"], errors="coerce")
    temp_df["年涨跌幅"] = pd.to_numeric(temp_df["年涨跌幅"], errors="coerce")
    return temp_df


def index_realtime_sw(symbol: str = "二级行业") -> pd.DataFrame:
    """
    申万宏源研究-指数系列
    https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
    :param symbol: choice of {"市场表征", "一级行业", "二级行业", "风格指数", "大类风格指数", "金创指数"}
    :type symbol: str
    :return: 指数系列实时行情数据
    :rtype: pandas.DataFrame
    """
    if symbol in {"大类风格指数", "金创指数"}:
        temp_df = __index_realtime_sw(symbol)
        return temp_df
    url = "https://www.swsresearch.com/institute-sw/api/index_publish/current/"
    params = {"page": "1", "page_size": "50", "indextype": symbol}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 50)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers, verify=False)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["results"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "指数代码",
        "指数名称",
        "昨收盘",
        "今开盘",
        "成交额",
        "最高价",
        "最低价",
        "最新价",
        "成交量",
    ]
    big_df = big_df[
        [
            "指数代码",
            "指数名称",
            "昨收盘",
            "今开盘",
            "最新价",
            "成交额",
            "成交量",
            "最高价",
            "最低价",
        ]
    ]
    big_df["昨收盘"] = pd.to_numeric(big_df["昨收盘"], errors="coerce")
    big_df["今开盘"] = pd.to_numeric(big_df["今开盘"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["成交额"] = pd.to_numeric(big_df["成交额"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    return big_df


def index_analysis_daily_sw(
    symbol: str = "市场表征",
    start_date: str = "20221103",
    end_date: str = "20221103",
) -> pd.DataFrame:
    """
    申万宏源研究-指数分析
    https://www.swsresearch.com/institute_sw/allIndex/analysisIndex
    :param symbol: choice of {"市场表征", "一级行业", "二级行业", "风格指数"}
    :type symbol: str
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 指数分析
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_report/"
    params = {
        "page": "1",
        "page_size": "50",
        "index_type": symbol,
        "start_date": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "end_date": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "type": "DAY",
        "swindexcode": "all",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 50)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers, verify=False)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["results"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "swindexcode": "指数代码",
            "swindexname": "指数名称",
            "bargaindate": "发布日期",
            "closeindex": "收盘指数",
            "bargainamount": "成交量",
            "markup": "涨跌幅",
            "turnoverrate": "换手率",
            "pe": "市盈率",
            "pb": "市净率",
            "meanprice": "均价",
            "bargainsumrate": "成交额占比",
            "negotiablessharesum1": "流通市值",
            "negotiablessharesum2": "平均流通市值",
            "dp": "股息率",
        },
        inplace=True,
    )
    big_df["发布日期"] = pd.to_datetime(big_df["发布日期"], errors="coerce").dt.date
    big_df["收盘指数"] = pd.to_numeric(big_df["收盘指数"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"], errors="coerce")
    big_df["市净率"] = pd.to_numeric(big_df["市净率"], errors="coerce")
    big_df["均价"] = pd.to_numeric(big_df["均价"], errors="coerce")
    big_df["成交额占比"] = pd.to_numeric(big_df["成交额占比"], errors="coerce")
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"], errors="coerce")
    big_df["平均流通市值"] = pd.to_numeric(big_df["平均流通市值"], errors="coerce")
    big_df["股息率"] = pd.to_numeric(big_df["股息率"], errors="coerce")
    big_df.sort_values(by=["发布日期"], inplace=True, ignore_index=True)
    return big_df


def index_analysis_week_month_sw(symbol: str = "month") -> pd.DataFrame:
    """
    申万宏源研究-周/月报表-日期序列
    https://www.swsresearch.com/institute_sw/allIndex/analysisIndex
    :param symbol: choice of {"week", "month"}
    :type symbol: str
    :return: 日期序列
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/institute-sw/api/index_analysis/week_month_datetime/"
    params = {"type": symbol.upper()}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["bargaindate"] = pd.to_datetime(
        temp_df["bargaindate"], errors="coerce"
    ).dt.date
    temp_df.columns = ["date"]
    temp_df.sort_values(by=["date"], inplace=True, ignore_index=True)
    return temp_df


def index_analysis_weekly_sw(
    symbol: str = "市场表征",
    date: str = "20221104",
) -> pd.DataFrame:
    """
    申万宏源研究-指数分析-周报告
    https://www.swsresearch.com/institute_sw/allIndex/analysisIndex
    :param symbol: choice of {"市场表征", "一级行业", "二级行业", "风格指数"}
    :type symbol: str
    :param date: 查询日期; 通过调用 ak.index_analysis_week_month_sw(date="20221104") 接口获取
    :type date: str
    :return: 指数分析
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_reports/"
    params = {
        "page": "1",
        "page_size": "50",
        "index_type": symbol,
        "bargaindate": "-".join([date[:4], date[4:6], date[6:]]),
        "type": "WEEK",
        "swindexcode": "all",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 50)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers, verify=False)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["results"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "swindexcode": "指数代码",
            "swindexname": "指数名称",
            "bargaindate": "发布日期",
            "closeindex": "收盘指数",
            "bargainamount": "成交量",
            "markup": "涨跌幅",
            "turnoverrate": "换手率",
            "pe": "市盈率",
            "pb": "市净率",
            "meanprice": "均价",
            "bargainsumrate": "成交额占比",
            "negotiablessharesum1": "流通市值",
            "negotiablessharesum2": "平均流通市值",
            "dp": "股息率",
        },
        inplace=True,
    )
    big_df["发布日期"] = pd.to_datetime(big_df["发布日期"], errors="coerce").dt.date
    big_df["收盘指数"] = pd.to_numeric(big_df["收盘指数"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"], errors="coerce")
    big_df["市净率"] = pd.to_numeric(big_df["市净率"], errors="coerce")
    big_df["均价"] = pd.to_numeric(big_df["均价"], errors="coerce")
    big_df["成交额占比"] = pd.to_numeric(big_df["成交额占比"], errors="coerce")
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"], errors="coerce")
    big_df["平均流通市值"] = pd.to_numeric(big_df["平均流通市值"], errors="coerce")
    big_df["股息率"] = pd.to_numeric(big_df["股息率"], errors="coerce")

    big_df.sort_values(by=["发布日期"], inplace=True, ignore_index=True)
    return big_df


def index_analysis_monthly_sw(
    symbol: str = "市场表征",
    date: str = "20221031",
) -> pd.DataFrame:
    """
    申万宏源研究-指数分析-月报告
    https://www.swsresearch.com/institute_sw/allIndex/analysisIndex
    :param symbol: choice of {"市场表征", "一级行业", "二级行业", "风格指数"}
    :type symbol: str
    :param date: 查询日期; 通过调用 ak.index_analysis_week_month_sw() 接口获取
    :type date: str
    :return: 指数分析
    :rtype: pandas.DataFrame
    """
    url = "https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_reports/"
    params = {
        "page": "1",
        "page_size": "50",
        "index_type": symbol,
        "bargaindate": "-".join([date[:4], date[4:6], date[6:]]),
        "type": "MONTH",
        "swindexcode": "all",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers, verify=False)
    data_json = r.json()
    total_num = data_json["data"]["count"]
    total_page = math.ceil(total_num / 50)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params, headers=headers, verify=False)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["results"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "swindexcode": "指数代码",
            "swindexname": "指数名称",
            "bargaindate": "发布日期",
            "closeindex": "收盘指数",
            "bargainamount": "成交量",
            "markup": "涨跌幅",
            "turnoverrate": "换手率",
            "pe": "市盈率",
            "pb": "市净率",
            "meanprice": "均价",
            "bargainsumrate": "成交额占比",
            "negotiablessharesum1": "流通市值",
            "negotiablessharesum2": "平均流通市值",
            "dp": "股息率",
        },
        inplace=True,
    )
    big_df["发布日期"] = pd.to_datetime(big_df["发布日期"], errors="coerce").dt.date
    big_df["收盘指数"] = pd.to_numeric(big_df["收盘指数"], errors="coerce")
    big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"], errors="coerce")
    big_df["市净率"] = pd.to_numeric(big_df["市净率"], errors="coerce")
    big_df["均价"] = pd.to_numeric(big_df["均价"], errors="coerce")
    big_df["成交额占比"] = pd.to_numeric(big_df["成交额占比"], errors="coerce")
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"], errors="coerce")
    big_df["平均流通市值"] = pd.to_numeric(big_df["平均流通市值"], errors="coerce")
    big_df["股息率"] = pd.to_numeric(big_df["股息率"], errors="coerce")
    big_df.sort_values(by=["发布日期"], inplace=True, ignore_index=True)
    return big_df


if __name__ == "__main__":
    index_hist_sw_df = index_hist_sw(symbol="801193", period="day")
    print(index_hist_sw_df)

    index_min_sw_df = index_min_sw(symbol="801001")
    print(index_min_sw_df)

    index_component_sw_df = index_component_sw(symbol="801001")
    print(index_component_sw_df)

    index_realtime_sw_df = index_realtime_sw(symbol="市场表征")
    print(index_realtime_sw_df)

    index_analysis_daily_sw_df = index_analysis_daily_sw(
        symbol="市场表征", start_date="20241025", end_date="20241025"
    )
    print(index_analysis_daily_sw_df)

    index_analysis_week_month_sw_df = index_analysis_week_month_sw(symbol="month")
    print(index_analysis_week_month_sw_df)

    index_analysis_weekly_sw_df = index_analysis_weekly_sw(
        symbol="市场表征", date="20241025"
    )
    print(index_analysis_weekly_sw_df)

    index_analysis_monthly_sw_df = index_analysis_monthly_sw(
        symbol="市场表征", date="20240930"
    )
    print(index_analysis_monthly_sw_df)
