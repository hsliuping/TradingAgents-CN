#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/9/20 15:30
Desc: 东方财富-数据中心-年报季报-业绩快报-三大报表
资产负债表
https://data.eastmoney.com/bbsj/202003/zcfz.html
利润表
https://data.eastmoney.com/bbsj/202003/lrb.html
现金流量表
https://data.eastmoney.com/bbsj/202003/xjll.html
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_zcfz_em(date: str = "20240331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报-资产负债表
    https://data.eastmoney.com/bbsj/202003/zcfz.html
    :param date: choice of {"20200331", "20200630", "20200930", "20201231", "..."}; 从 20100331 开始
    :type date: str
    :return: 资产负债表
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_FN_BALANCE",
        "columns": "ALL",
        "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE!="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], join="outer", ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "股票代码",
        "_",
        "_",
        "股票简称",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "公告日期",
        "_",
        "资产-总资产",
        "_",
        "资产-货币资金",
        "_",
        "资产-应收账款",
        "_",
        "资产-存货",
        "_",
        "负债-总负债",
        "负债-应付账款",
        "_",
        "负债-预收账款",
        "_",
        "股东权益合计",
        "_",
        "资产-总资产同比",
        "负债-总负债同比",
        "_",
        "资产负债率",
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
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "资产-货币资金",
            "资产-应收账款",
            "资产-存货",
            "资产-总资产",
            "资产-总资产同比",
            "负债-应付账款",
            "负债-预收账款",
            "负债-总负债",
            "负债-总负债同比",
            "资产负债率",
            "股东权益合计",
            "公告日期",
        ]
    ]

    big_df["资产-货币资金"] = pd.to_numeric(big_df["资产-货币资金"], errors="coerce")
    big_df["资产-应收账款"] = pd.to_numeric(big_df["资产-应收账款"], errors="coerce")
    big_df["资产-存货"] = pd.to_numeric(big_df["资产-存货"], errors="coerce")
    big_df["资产-总资产"] = pd.to_numeric(big_df["资产-总资产"], errors="coerce")
    big_df["资产-总资产同比"] = pd.to_numeric(
        big_df["资产-总资产同比"], errors="coerce"
    )
    big_df["负债-应付账款"] = pd.to_numeric(big_df["负债-应付账款"], errors="coerce")
    big_df["负债-预收账款"] = pd.to_numeric(big_df["负债-预收账款"], errors="coerce")
    big_df["负债-总负债"] = pd.to_numeric(big_df["负债-总负债"], errors="coerce")
    big_df["负债-总负债同比"] = pd.to_numeric(
        big_df["负债-总负债同比"], errors="coerce"
    )
    big_df["资产负债率"] = pd.to_numeric(big_df["资产负债率"], errors="coerce")
    big_df["股东权益合计"] = pd.to_numeric(big_df["股东权益合计"], errors="coerce")
    big_df["股东权益合计"] = pd.to_numeric(big_df["股东权益合计"], errors="coerce")
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    return big_df


def stock_zcfz_bj_em(date: str = "20240331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报-资产负债表
    https://data.eastmoney.com/bbsj/202003/zcfz.html
    :param date: choice of {"20200331", "20200630", "20200930", "20201231", "..."}; 从 20100331 开始
    :type date: str
    :return: 资产负债表
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_FN_BALANCE",
        "columns": "ALL",
        "filter": f"""(TRADE_MARKET_CODE="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], join="outer", ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "股票代码",
        "_",
        "_",
        "股票简称",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "公告日期",
        "_",
        "资产-总资产",
        "_",
        "资产-货币资金",
        "_",
        "资产-应收账款",
        "_",
        "资产-存货",
        "_",
        "负债-总负债",
        "负债-应付账款",
        "_",
        "负债-预收账款",
        "_",
        "股东权益合计",
        "_",
        "资产-总资产同比",
        "负债-总负债同比",
        "_",
        "资产负债率",
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
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "资产-货币资金",
            "资产-应收账款",
            "资产-存货",
            "资产-总资产",
            "资产-总资产同比",
            "负债-应付账款",
            "负债-预收账款",
            "负债-总负债",
            "负债-总负债同比",
            "资产负债率",
            "股东权益合计",
            "公告日期",
        ]
    ]

    big_df["资产-货币资金"] = pd.to_numeric(big_df["资产-货币资金"], errors="coerce")
    big_df["资产-应收账款"] = pd.to_numeric(big_df["资产-应收账款"], errors="coerce")
    big_df["资产-存货"] = pd.to_numeric(big_df["资产-存货"], errors="coerce")
    big_df["资产-总资产"] = pd.to_numeric(big_df["资产-总资产"], errors="coerce")
    big_df["资产-总资产同比"] = pd.to_numeric(
        big_df["资产-总资产同比"], errors="coerce"
    )
    big_df["负债-应付账款"] = pd.to_numeric(big_df["负债-应付账款"], errors="coerce")
    big_df["负债-预收账款"] = pd.to_numeric(big_df["负债-预收账款"], errors="coerce")
    big_df["负债-总负债"] = pd.to_numeric(big_df["负债-总负债"], errors="coerce")
    big_df["负债-总负债同比"] = pd.to_numeric(
        big_df["负债-总负债同比"], errors="coerce"
    )
    big_df["资产负债率"] = pd.to_numeric(big_df["资产负债率"], errors="coerce")
    big_df["股东权益合计"] = pd.to_numeric(big_df["股东权益合计"], errors="coerce")
    big_df["股东权益合计"] = pd.to_numeric(big_df["股东权益合计"], errors="coerce")
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    return big_df


def stock_lrb_em(date: str = "20240331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报-利润表
    https://data.eastmoney.com/bbsj/202003/lrb.html
    :param date: choice of {"20200331", "20200630", "20200930", "20201231", "..."}; 从 20100331 开始
    :type date: str
    :return: 利润表
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_FN_INCOME",
        "columns": "ALL",
        "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE!="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "股票代码",
        "_",
        "_",
        "股票简称",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "公告日期",
        "_",
        "净利润",
        "营业总收入",
        "营业总支出-营业总支出",
        "_",
        "营业总支出-营业支出",
        "_",
        "_",
        "营业总支出-销售费用",
        "营业总支出-管理费用",
        "营业总支出-财务费用",
        "营业利润",
        "利润总额",
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
        "_",
        "_",
        "_",
        "_",
        "_",
        "营业总收入同比",
        "_",
        "净利润同比",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "净利润",
            "净利润同比",
            "营业总收入",
            "营业总收入同比",
            "营业总支出-营业支出",
            "营业总支出-销售费用",
            "营业总支出-管理费用",
            "营业总支出-财务费用",
            "营业总支出-营业总支出",
            "营业利润",
            "利润总额",
            "公告日期",
        ]
    ]

    big_df["净利润"] = pd.to_numeric(big_df["净利润"], errors="coerce")
    big_df["净利润同比"] = pd.to_numeric(big_df["净利润同比"], errors="coerce")
    big_df["营业总收入"] = pd.to_numeric(big_df["营业总收入"], errors="coerce")
    big_df["营业总收入同比"] = pd.to_numeric(big_df["营业总收入同比"], errors="coerce")
    big_df["营业总支出-营业支出"] = pd.to_numeric(
        big_df["营业总支出-营业支出"], errors="coerce"
    )
    big_df["营业总支出-销售费用"] = pd.to_numeric(
        big_df["营业总支出-销售费用"], errors="coerce"
    )
    big_df["营业总支出-管理费用"] = pd.to_numeric(
        big_df["营业总支出-管理费用"], errors="coerce"
    )
    big_df["营业总支出-财务费用"] = pd.to_numeric(
        big_df["营业总支出-财务费用"], errors="coerce"
    )
    big_df["营业总支出-营业总支出"] = pd.to_numeric(
        big_df["营业总支出-营业总支出"], errors="coerce"
    )
    big_df["营业利润"] = pd.to_numeric(big_df["营业利润"], errors="coerce")
    big_df["利润总额"] = pd.to_numeric(big_df["利润总额"], errors="coerce")
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date

    return big_df


def stock_xjll_em(date: str = "20240331") -> pd.DataFrame:
    """
    东方财富-数据中心-年报季报-业绩快报-现金流量表
    https://data.eastmoney.com/bbsj/202003/xjll.html
    :param date: choice of {"20200331", "20200630", "20200930", "20201231", "..."}; 从 20100331 开始
    :type date: str
    :return: 现金流量表
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_FN_CASHFLOW",
        "columns": "ALL",
        "filter": f"""(SECURITY_TYPE_CODE in ("058001001","058001008"))(TRADE_MARKET_CODE!="069001017")
        (REPORT_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "股票代码",
        "_",
        "_",
        "股票简称",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "公告日期",
        "_",
        "经营性现金流-现金流量净额",
        "经营性现金流-净现金流占比",
        "_",
        "_",
        "_",
        "_",
        "投资性现金流-现金流量净额",
        "投资性现金流-净现金流占比",
        "_",
        "_",
        "_",
        "_",
        "融资性现金流-现金流量净额",
        "融资性现金流-净现金流占比",
        "净现金流-净现金流",
        "净现金流-同比增长",
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
            "股票代码",
            "股票简称",
            "净现金流-净现金流",
            "净现金流-同比增长",
            "经营性现金流-现金流量净额",
            "经营性现金流-净现金流占比",
            "投资性现金流-现金流量净额",
            "投资性现金流-净现金流占比",
            "融资性现金流-现金流量净额",
            "融资性现金流-净现金流占比",
            "公告日期",
        ]
    ]

    big_df["净现金流-净现金流"] = pd.to_numeric(
        big_df["净现金流-净现金流"], errors="coerce"
    )
    big_df["净现金流-同比增长"] = pd.to_numeric(
        big_df["净现金流-同比增长"], errors="coerce"
    )
    big_df["经营性现金流-现金流量净额"] = pd.to_numeric(
        big_df["经营性现金流-现金流量净额"], errors="coerce"
    )
    big_df["经营性现金流-净现金流占比"] = pd.to_numeric(
        big_df["经营性现金流-净现金流占比"], errors="coerce"
    )
    big_df["投资性现金流-现金流量净额"] = pd.to_numeric(
        big_df["投资性现金流-现金流量净额"], errors="coerce"
    )
    big_df["投资性现金流-净现金流占比"] = pd.to_numeric(
        big_df["投资性现金流-净现金流占比"], errors="coerce"
    )
    big_df["融资性现金流-现金流量净额"] = pd.to_numeric(
        big_df["融资性现金流-现金流量净额"], errors="coerce"
    )
    big_df["融资性现金流-净现金流占比"] = pd.to_numeric(
        big_df["融资性现金流-净现金流占比"], errors="coerce"
    )
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    return big_df


if __name__ == "__main__":
    stock_zcfz_em_df = stock_zcfz_em(date="20240331")
    print(stock_zcfz_em_df)

    stock_zcfz_bj_em_df = stock_zcfz_bj_em(date="20240331")
    print(stock_zcfz_bj_em_df)

    stock_lrb_em_df = stock_lrb_em(date="20240331")
    print(stock_lrb_em_df)

    stock_xjll_em_df = stock_xjll_em(date="20240331")
    print(stock_xjll_em_df)
