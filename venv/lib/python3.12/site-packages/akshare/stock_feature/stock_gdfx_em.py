# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/3/26 21:15
Desc: 东方财富网-数据中心-股东分析
https://data.eastmoney.com/gdfx/
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_gdfx_free_holding_statistics_em(
    date: str = "20210630",
) -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股统计-十大流通股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "STATISTICS_TIMES,COOPERATION_HOLDER_MARK",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_COOPFREEHOLDERS_ANALYSIS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(HOLDNUM_CHANGE_TYPE="001")(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "-",
        "股东名称",
        "股东类型",
        "-",
        "统计次数",
        "公告日后涨幅统计-10个交易日-平均涨幅",
        "公告日后涨幅统计-10个交易日-最大涨幅",
        "公告日后涨幅统计-10个交易日-最小涨幅",
        "公告日后涨幅统计-30个交易日-平均涨幅",
        "公告日后涨幅统计-30个交易日-最大涨幅",
        "公告日后涨幅统计-30个交易日-最小涨幅",
        "公告日后涨幅统计-60个交易日-平均涨幅",
        "公告日后涨幅统计-60个交易日-最大涨幅",
        "公告日后涨幅统计-60个交易日-最小涨幅",
        "持有个股",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "统计次数",
            "公告日后涨幅统计-10个交易日-平均涨幅",
            "公告日后涨幅统计-10个交易日-最大涨幅",
            "公告日后涨幅统计-10个交易日-最小涨幅",
            "公告日后涨幅统计-30个交易日-平均涨幅",
            "公告日后涨幅统计-30个交易日-最大涨幅",
            "公告日后涨幅统计-30个交易日-最小涨幅",
            "公告日后涨幅统计-60个交易日-平均涨幅",
            "公告日后涨幅统计-60个交易日-最大涨幅",
            "公告日后涨幅统计-60个交易日-最小涨幅",
            "持有个股",
        ]
    ]
    big_df["统计次数"] = pd.to_numeric(big_df["统计次数"])
    big_df["公告日后涨幅统计-10个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-10个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-10个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-最小涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-最小涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-最小涨幅"]
    )
    return big_df


def stock_gdfx_holding_statistics_em(date: str = "20210930") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股统计-十大股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "STATISTICS_TIMES,COOPERATION_HOLDER_MARK",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_COOPHOLDERS_ANALYSIS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(HOLDNUM_CHANGE_TYPE="001")(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "-",
        "股东名称",
        "股东类型",
        "-",
        "统计次数",
        "公告日后涨幅统计-10个交易日-平均涨幅",
        "公告日后涨幅统计-10个交易日-最大涨幅",
        "公告日后涨幅统计-10个交易日-最小涨幅",
        "公告日后涨幅统计-30个交易日-平均涨幅",
        "公告日后涨幅统计-30个交易日-最大涨幅",
        "公告日后涨幅统计-30个交易日-最小涨幅",
        "公告日后涨幅统计-60个交易日-平均涨幅",
        "公告日后涨幅统计-60个交易日-最大涨幅",
        "公告日后涨幅统计-60个交易日-最小涨幅",
        "持有个股",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "统计次数",
            "公告日后涨幅统计-10个交易日-平均涨幅",
            "公告日后涨幅统计-10个交易日-最大涨幅",
            "公告日后涨幅统计-10个交易日-最小涨幅",
            "公告日后涨幅统计-30个交易日-平均涨幅",
            "公告日后涨幅统计-30个交易日-最大涨幅",
            "公告日后涨幅统计-30个交易日-最小涨幅",
            "公告日后涨幅统计-60个交易日-平均涨幅",
            "公告日后涨幅统计-60个交易日-最大涨幅",
            "公告日后涨幅统计-60个交易日-最小涨幅",
            "持有个股",
        ]
    ]
    big_df["统计次数"] = pd.to_numeric(big_df["统计次数"])
    big_df["公告日后涨幅统计-10个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-10个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-10个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-10个交易日-最小涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-30个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-30个交易日-最小涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-平均涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-平均涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-最大涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-最大涨幅"]
    )
    big_df["公告日后涨幅统计-60个交易日-最小涨幅"] = pd.to_numeric(
        big_df["公告日后涨幅统计-60个交易日-最小涨幅"]
    )
    return big_df


def stock_gdfx_free_holding_change_em(date: str = "20210930") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股变动统计-十大流通股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "HOLDER_NUM,HOLDER_NEW",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_FREEHOLDERS_BASIC_INFO",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "-",
        "股东名称",
        "-",
        "股东类型",
        "-",
        "-",
        "-",
        "期末持股只数统计-总持有",
        "期末持股只数统计-新进",
        "期末持股只数统计-增加",
        "期末持股只数统计-减少",
        "期末持股只数统计-不变",
        "-",
        "流通市值统计",
        "持有个股",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "期末持股只数统计-总持有",
            "期末持股只数统计-新进",
            "期末持股只数统计-增加",
            "期末持股只数统计-不变",
            "期末持股只数统计-减少",
            "流通市值统计",
            "持有个股",
        ]
    ]
    big_df["期末持股只数统计-总持有"] = pd.to_numeric(
        big_df["期末持股只数统计-总持有"], errors="coerce"
    )
    big_df["期末持股只数统计-新进"] = pd.to_numeric(
        big_df["期末持股只数统计-新进"], errors="coerce"
    )
    big_df["期末持股只数统计-增加"] = pd.to_numeric(
        big_df["期末持股只数统计-增加"], errors="coerce"
    )
    big_df["期末持股只数统计-不变"] = pd.to_numeric(
        big_df["期末持股只数统计-不变"], errors="coerce"
    )
    big_df["期末持股只数统计-减少"] = pd.to_numeric(
        big_df["期末持股只数统计-减少"], errors="coerce"
    )
    big_df["流通市值统计"] = pd.to_numeric(big_df["流通市值统计"], errors="coerce")
    return big_df


def stock_gdfx_holding_change_em(date: str = "20210930") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股变动统计-十大股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "HOLDER_NUM,HOLDER_NEW",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_HOLDERS_BASIC_INFO",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "-",
        "股东名称",
        "-",
        "股东类型",
        "-",
        "-",
        "-",
        "期末持股只数统计-总持有",
        "期末持股只数统计-新进",
        "期末持股只数统计-增加",
        "期末持股只数统计-减少",
        "期末持股只数统计-不变",
        "-",
        "-",
        "持有个股",
        "流通市值统计",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "期末持股只数统计-总持有",
            "期末持股只数统计-新进",
            "期末持股只数统计-增加",
            "期末持股只数统计-不变",
            "期末持股只数统计-减少",
            "流通市值统计",
            "持有个股",
        ]
    ]
    big_df["期末持股只数统计-总持有"] = pd.to_numeric(big_df["期末持股只数统计-总持有"])
    big_df["期末持股只数统计-新进"] = pd.to_numeric(big_df["期末持股只数统计-新进"])
    big_df["期末持股只数统计-增加"] = pd.to_numeric(big_df["期末持股只数统计-增加"])
    big_df["期末持股只数统计-不变"] = pd.to_numeric(big_df["期末持股只数统计-不变"])
    big_df["期末持股只数统计-减少"] = pd.to_numeric(big_df["期末持股只数统计-减少"])
    big_df["流通市值统计"] = pd.to_numeric(big_df["流通市值统计"])
    return big_df


def stock_gdfx_free_top_10_em(
    symbol: str = "sh688686", date: str = "20240930"
) -> pd.DataFrame:
    """
    东方财富网-个股-十大流通股东
    https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/Index?type=web&code=SH688686#sdltgd-0
    :param symbol: 带市场标识的股票代码
    :type symbol: str
    :param date: 报告期
    :type date: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    url = (
        "https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/PageSDLTGD"
    )
    params = {
        "code": f"{symbol.upper()}",
        "date": f"{'-'.join([date[:4], date[4:6], date[6:]])}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["sdltgd"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "名次",
        "-",
        "-",
        "-",
        "-",
        "股东名称",
        "股东性质",
        "股份类型",
        "持股数",
        "占总流通股本持股比例",
        "增减",
        "变动比率",
    ]
    temp_df = temp_df[
        [
            "名次",
            "股东名称",
            "股东性质",
            "股份类型",
            "持股数",
            "占总流通股本持股比例",
            "增减",
            "变动比率",
        ]
    ]
    temp_df["持股数"] = pd.to_numeric(temp_df["持股数"], errors="coerce")
    temp_df["占总流通股本持股比例"] = pd.to_numeric(
        temp_df["占总流通股本持股比例"], errors="coerce"
    )
    temp_df["变动比率"] = pd.to_numeric(temp_df["变动比率"], errors="coerce")
    return temp_df


def stock_gdfx_top_10_em(
    symbol: str = "sh688686", date: str = "20210630"
) -> pd.DataFrame:
    """
    东方财富网-个股-十大股东
    https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/Index?type=web&code=SH688686#sdgd-0
    :param symbol: 带市场标识的股票代码
    :type symbol: str
    :param date: 报告期
    :type date: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/PageSDGD"
    params = {
        "code": f"{symbol.upper()}",
        "date": f"{'-'.join([date[:4], date[4:6], date[6:]])}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["sdgd"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "名次",
        "-",
        "-",
        "-",
        "-",
        "股东名称",
        "股份类型",
        "持股数",
        "占总股本持股比例",
        "增减",
        "变动比率",
    ]
    temp_df = temp_df[
        [
            "名次",
            "股东名称",
            "股份类型",
            "持股数",
            "占总股本持股比例",
            "增减",
            "变动比率",
        ]
    ]
    temp_df["持股数"] = pd.to_numeric(temp_df["持股数"])
    temp_df["占总股本持股比例"] = pd.to_numeric(temp_df["占总股本持股比例"])
    temp_df["变动比率"] = pd.to_numeric(temp_df["变动比率"])
    return temp_df


def stock_gdfx_free_holding_detail_em(date: str = "20210930") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股明细-十大流通股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,SECURITY_CODE,HOLDER_RANK",
        "sortTypes": "-1,1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_F10_EH_FREEHOLDERS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "HOLDER_NAME": "股东名称",
            "HOLDER_TYPE": "股东类型",
            "SHARES_TYPE": "股份类型",
            "HOLDER_RANK": "股东排名",
            "SECURITY_CODE": "股票代码",
            "SECURITY_NAME_ABBR": "股票简称",
            "HOLD_NUM": "期末持股-数量",
            "FREE_HOLDNUM_RATIO": "期末持股-持股占流通股比",
            "XZCHANGE": "期末持股-数量变化",
            "CHANGE_RATIO": "期末持股-数量变化比例",
            "HOLDNUM_CHANGE_NAME": "期末持股-持股变动",
            "HOLDER_MARKET_CAP": "期末持股-流通市值",
            "END_DATE": "报告期",
            "UPDATE_DATE": "公告日",
            "REPORT_DATE_NAME": "报告名称",
        },
        inplace=True,
    )

    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "股票代码",
            "股票简称",
            "报告期",
            "期末持股-数量",
            "期末持股-数量变化",
            "期末持股-数量变化比例",
            "期末持股-持股变动",
            "期末持股-流通市值",
            "公告日",
        ]
    ]
    big_df["报告期"] = pd.to_datetime(big_df["报告期"], errors="coerce").dt.date
    big_df["公告日"] = pd.to_datetime(big_df["公告日"], errors="coerce").dt.date
    big_df["期末持股-数量"] = pd.to_numeric(big_df["期末持股-数量"], errors="coerce")
    big_df["期末持股-数量变化"] = pd.to_numeric(
        big_df["期末持股-数量变化"], errors="coerce"
    )
    big_df["期末持股-数量变化比例"] = pd.to_numeric(
        big_df["期末持股-数量变化比例"], errors="coerce"
    )
    big_df["期末持股-流通市值"] = pd.to_numeric(
        big_df["期末持股-流通市值"], errors="coerce"
    )
    return big_df


def stock_gdfx_holding_detail_em(
    date: str = "20230331", indicator: str = "个人", symbol: str = "新进"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股明细-十大股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :param indicator: 股东类型; choice of {"个人", "基金", "QFII", "社保", "券商", "信托"}
    :type indicator: str
    :param symbol: 持股变动; choice of {"新进", "增加", "不变", "减少"}
    :type symbol: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE,RANK",
        "sortTypes": "-1,1,1",
        "pageSize": "50",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_HOLDERS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(HOLDER_NEWTYPE="{indicator}")(HOLDNUM_CHANGE_NAME="{symbol}")(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "HOLDER_NAME": "股东名称",
            "HOLDER_NEWTYPE": "股东类型",
            "RANK": "股东排名",
            "SECURITY_CODE": "股票代码",
            "SECURITY_NAME_ABBR": "股票简称",
            "END_DATE": "报告期",
            "HOLD_NUM": "期末持股-数量",
            "HOLD_NUM_CHANGE": "期末持股-数量变化",
            "HOLD_RATIO_CHANGE": "期末持股-数量变化比例",
            "HOLDNUM_CHANGE_NAME": "期末持股-持股变动",
            "HOLDER_MARKET_CAP": "期末持股-流通市值",
            "NOTICE_DATE": "公告日",
        },
        inplace=True,
    )

    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "股票代码",
            "股票简称",
            "报告期",
            "期末持股-数量",
            "期末持股-数量变化",
            "期末持股-数量变化比例",
            "期末持股-持股变动",
            "期末持股-流通市值",
            "公告日",
            "股东排名",
        ]
    ]
    big_df["报告期"] = pd.to_datetime(big_df["报告期"], errors="coerce").dt.date
    big_df["公告日"] = pd.to_datetime(big_df["公告日"], errors="coerce").dt.date
    big_df["期末持股-数量"] = pd.to_numeric(big_df["期末持股-数量"], errors="coerce")
    big_df["期末持股-数量变化"] = pd.to_numeric(
        big_df["期末持股-数量变化"], errors="coerce"
    )
    big_df["期末持股-数量变化比例"] = pd.to_numeric(
        big_df["期末持股-数量变化比例"], errors="coerce"
    )
    big_df["期末持股-流通市值"] = pd.to_numeric(
        big_df["期末持股-流通市值"], errors="coerce"
    )
    big_df["股东排名"] = pd.to_numeric(big_df["股东排名"], errors="coerce")
    return big_df


def stock_gdfx_free_holding_analyse_em(date: str = "20230930") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股分析-十大流通股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "UPDATE_DATE,SECURITY_CODE,HOLDER_RANK",
        "sortTypes": "-1,1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_CUSTOM_F10_EH_FREEHOLDERS_JOIN_FREEHOLDER_SHAREANALYSIS",
        "columns": "ALL;D10_ADJCHRATE,D30_ADJCHRATE,D60_ADJCHRATE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "HOLDER_NAME": "股东名称",
            "HOLDER_TYPE": "股东类型",
            "SECURITY_CODE": "股票代码",
            "SECURITY_NAME_ABBR": "股票简称",
            "END_DATE": "报告期",
            "HOLD_NUM": "期末持股-数量",
            "XZCHANGE": "期末持股-数量变化",
            "HOLD_RATIO_CHANGE": "期末持股-数量变化比例",
            "HOLDNUM_CHANGE_NAME": "期末持股-持股变动",
            "HOLDER_MARKET_CAP": "期末持股-流通市值",
            "UPDATE_DATE": "公告日",
            "D10_ADJCHRATE": "公告日后涨跌幅-10个交易日",
            "D30_ADJCHRATE": "公告日后涨跌幅-30个交易日",
            "D60_ADJCHRATE": "公告日后涨跌幅-60个交易日",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "股票代码",
            "股票简称",
            "报告期",
            "期末持股-数量",
            "期末持股-数量变化",
            "期末持股-数量变化比例",
            "期末持股-持股变动",
            "期末持股-流通市值",
            "公告日",
            "公告日后涨跌幅-10个交易日",
            "公告日后涨跌幅-30个交易日",
            "公告日后涨跌幅-60个交易日",
        ]
    ]
    big_df["报告期"] = pd.to_datetime(big_df["报告期"], errors="coerce").dt.date
    big_df["公告日"] = pd.to_datetime(big_df["公告日"], errors="coerce").dt.date
    big_df["期末持股-数量"] = pd.to_numeric(big_df["期末持股-数量"], errors="coerce")
    big_df["期末持股-数量变化"] = pd.to_numeric(
        big_df["期末持股-数量变化"], errors="coerce"
    )
    big_df["期末持股-数量变化比例"] = pd.to_numeric(
        big_df["期末持股-数量变化比例"], errors="coerce"
    )
    big_df["期末持股-流通市值"] = pd.to_numeric(
        big_df["期末持股-流通市值"], errors="coerce"
    )
    big_df["公告日后涨跌幅-10个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-10个交易日"], errors="coerce"
    )
    big_df["公告日后涨跌幅-30个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-30个交易日"], errors="coerce"
    )
    big_df["公告日后涨跌幅-60个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-60个交易日"], errors="coerce"
    )
    return big_df


def stock_gdfx_holding_analyse_em(date: str = "20230331") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东持股分析-十大股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param date: 报告期
    :type date: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE,RANK",
        "sortTypes": "-1,1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_CUSTOM_DMSK_HOLDERS_JOIN_HOLDER_SHAREANALYSIS",
        "columns": "ALL;D10_ADJCHRATE,D30_ADJCHRATE,D60_ADJCHRATE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(END_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "ORG_CODE": "-",
            "SECURITY_TYPE_CODE": "-",
            "END_DATE": "报告期",
            "HOLDER_CODE": "-",
            "HOLDER_NAME": "股东名称",
            "HOLD_NUM": "期末持股-数量",
            "HOLD_RATIO": "-",
            "HOLD_NUM_CHANGE": "期末持股-数量变化",
            "HOLD_RATIO_CHANGE": "期末持股-数量变化比例",
            "NOTICE_DATE": "公告日",
            "SECURITY_NAME_ABBR": "股票简称",
            "HOLDER_MARKET_CAP": "期末持股-流通市值",
            "HOLDNUM_CHANGE_NAME": "期末持股-持股变动",
            "HOLDER_TYPE_ORG": "股东类型",
            "D10_ADJCHRATE": "公告日后涨跌幅-10个交易日",
            "D30_ADJCHRATE": "公告日后涨跌幅-30个交易日",
            "D60_ADJCHRATE": "公告日后涨跌幅-60个交易日",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "股票代码",
            "股票简称",
            "报告期",
            "期末持股-数量",
            "期末持股-数量变化",
            "期末持股-数量变化比例",
            "期末持股-持股变动",
            "期末持股-流通市值",
            "公告日",
            "公告日后涨跌幅-10个交易日",
            "公告日后涨跌幅-30个交易日",
            "公告日后涨跌幅-60个交易日",
        ]
    ]
    big_df["公告日"] = pd.to_datetime(big_df["公告日"]).dt.date
    big_df["报告期"] = pd.to_datetime(big_df["报告期"]).dt.date
    big_df["期末持股-数量"] = pd.to_numeric(big_df["期末持股-数量"], errors="coerce")
    big_df["期末持股-数量变化"] = pd.to_numeric(
        big_df["期末持股-数量变化"], errors="coerce"
    )
    big_df["期末持股-数量变化比例"] = pd.to_numeric(
        big_df["期末持股-数量变化比例"], errors="coerce"
    )
    big_df["期末持股-流通市值"] = pd.to_numeric(
        big_df["期末持股-流通市值"], errors="coerce"
    )
    big_df["公告日后涨跌幅-10个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-10个交易日"], errors="coerce"
    )
    big_df["公告日后涨跌幅-30个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-30个交易日"], errors="coerce"
    )
    big_df["公告日后涨跌幅-60个交易日"] = pd.to_numeric(
        big_df["公告日后涨跌幅-60个交易日"], errors="coerce"
    )
    return big_df


def stock_gdfx_free_holding_teamwork_em(symbol: str = "社保") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东协同-十大流通股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param symbol: 全部; choice of {"全部", "个人", "基金", "QFII", "社保", "券商", "信托"}
    :type symbol: str
    :return: 十大流通股东
    :rtype: pandas.DataFrame
    """
    symbol_dict = {} if symbol == "全部" else {"filter": f'(HOLDER_TYPE="{symbol}")'}
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "COOPERAT_NUM,HOLDER_NEW,COOPERAT_HOLDER_NEW",
        "sortTypes": "-1,-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_COOPFREEHOLDER",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    params.update(symbol_dict)
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "股东名称",
        "股东类型",
        "-",
        "协同股东名称",
        "协同股东类型",
        "协同次数",
        "-",
        "个股详情",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "协同股东名称",
            "协同股东类型",
            "协同次数",
            "个股详情",
        ]
    ]
    big_df["协同次数"] = pd.to_numeric(big_df["协同次数"], errors="coerce")
    return big_df


def stock_gdfx_holding_teamwork_em(symbol: str = "社保") -> pd.DataFrame:
    """
    东方财富网-数据中心-股东分析-股东协同-十大股东
    https://data.eastmoney.com/gdfx/HoldingAnalyse.html
    :param symbol: 全部; choice of {"全部", "个人", "基金", "QFII", "社保", "券商", "信托"}
    :type symbol: str
    :return: 十大股东
    :rtype: pandas.DataFrame
    """
    symbol_dict = {} if symbol == "全部" else {"filter": f'(HOLDER_TYPE="{symbol}")'}
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "COOPERAT_NUM,HOLDER_NEW,COOPERAT_HOLDER_NEW",
        "sortTypes": "-1,-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_TENHOLDERS_COOPHOLDERS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    params.update(symbol_dict)
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "股东名称",
        "股东类型",
        "-",
        "协同股东名称",
        "协同股东类型",
        "协同次数",
        "-",
        "个股详情",
    ]
    big_df = big_df[
        [
            "序号",
            "股东名称",
            "股东类型",
            "协同股东名称",
            "协同股东类型",
            "协同次数",
            "个股详情",
        ]
    ]
    big_df["协同次数"] = pd.to_numeric(big_df["协同次数"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_gdfx_free_holding_statistics_em_df = stock_gdfx_free_holding_statistics_em(
        date="20210930"
    )
    print(stock_gdfx_free_holding_statistics_em_df)

    stock_gdfx_holding_statistics_em_df = stock_gdfx_holding_statistics_em(
        date="20210930"
    )
    print(stock_gdfx_holding_statistics_em_df)

    stock_gdfx_free_holding_change_em_df = stock_gdfx_free_holding_change_em(
        date="20210930"
    )
    print(stock_gdfx_free_holding_change_em_df)

    stock_gdfx_holding_change_em_df = stock_gdfx_holding_change_em(date="20210930")
    print(stock_gdfx_holding_change_em_df)

    stock_gdfx_free_top_10_em_df = stock_gdfx_free_top_10_em(
        symbol="sz000420", date="20220331"
    )
    print(stock_gdfx_free_top_10_em_df)

    stock_gdfx_top_10_em_df = stock_gdfx_top_10_em(symbol="sh688686", date="20210630")
    print(stock_gdfx_top_10_em_df)

    stock_gdfx_free_holding_detail_em_df = stock_gdfx_free_holding_detail_em(
        date="20210930"
    )
    print(stock_gdfx_free_holding_detail_em_df)

    stock_gdfx_holding_detail_em_df = stock_gdfx_holding_detail_em(date="20230331")
    print(stock_gdfx_holding_detail_em_df)

    stock_gdfx_free_holding_analyse_em_df = stock_gdfx_free_holding_analyse_em(
        date="20230930"
    )
    print(stock_gdfx_free_holding_analyse_em_df)

    stock_gdfx_holding_analyse_em_df = stock_gdfx_holding_analyse_em(date="20220331")
    print(stock_gdfx_holding_analyse_em_df)

    stock_gdfx_free_holding_teamwork_em_df = stock_gdfx_free_holding_teamwork_em()
    print(stock_gdfx_free_holding_teamwork_em_df)

    stock_gdfx_holding_teamwork_em_df = stock_gdfx_holding_teamwork_em(symbol="社保")
    print(stock_gdfx_holding_teamwork_em_df)
