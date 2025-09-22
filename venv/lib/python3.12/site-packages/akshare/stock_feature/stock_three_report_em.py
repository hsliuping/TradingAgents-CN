# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/5/8 20:00
Desc: 东方财富-股票-财务分析
"""

from functools import lru_cache

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.tqdm import get_tqdm


@lru_cache()
def _stock_balance_sheet_by_report_ctype_em(symbol: str = "SH600519") -> str:
    """
    东方财富-股票-财务分析-资产负债表-按报告期-公司类型判断
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh601878#zcfzb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 东方财富-股票-财务分析-资产负债表-按报告期-公司类型判断
    :rtype: str
    """
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index"
    params = {"type": "web", "code": symbol.lower()}
    r = requests.get(url, params=params)
    soup = BeautifulSoup(r.text, features="lxml")
    company_type = soup.find(attrs={"id": "hidctype"})["value"]
    return company_type


def stock_balance_sheet_by_report_em(symbol: str = "SH600519") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-资产负债表-按报告期
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 资产负债表-按报告期
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "0",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "0",
            "reportType": "1",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_balance_sheet_by_yearly_em(symbol: str = "SH600036") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-资产负债表-按年度
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 资产负债表-按年度
    :rtype: pandas.DataFrame
    """
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbDateAjaxNew"
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol)
    params = {
        "companyType": company_type,
        "reportDateType": "1",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    try:
        temp_df = pd.DataFrame(data_json["data"])
    except:  # noqa: E722
        company_type = '3'
        params.update({"companyType": company_type})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(
        temp_df["REPORT_DATE"], errors="coerce"
    ).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "1",
            "reportType": "1",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_profit_sheet_by_report_em(symbol: str = "SH600519") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-利润表-报告期
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 利润表-报告期
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "0",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "0",
            "reportType": "1",
            "code": symbol,
            "dates": item,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_profit_sheet_by_yearly_em(symbol: str = "SH600519") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-利润表-按年度
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 利润表-按年度
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "1",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "1",
            "reportType": "1",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_profit_sheet_by_quarterly_em(
    symbol: str = "SH600519",
) -> pd.DataFrame:
    """
    东方财富-股票-财务分析-利润表-按单季度
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 利润表-按单季度
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "2",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "0",
            "reportType": "2",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_cash_flow_sheet_by_report_em(
    symbol: str = "SH600519",
) -> pd.DataFrame:
    """
    东方财富-股票-财务分析-现金流量表-按报告期
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 现金流量表-按报告期
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "0",
        "code": symbol,
    }
    r = requests.get(url, params=params, timeout=10)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "0",
            "reportType": "1",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_cash_flow_sheet_by_yearly_em(
    symbol: str = "SH600519",
) -> pd.DataFrame:
    """
    东方财富-股票-财务分析-现金流量表-按年度
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 现金流量表-按年度
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "1",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "1",
            "reportType": "1",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def stock_cash_flow_sheet_by_quarterly_em(
    symbol: str = "SH600519",
) -> pd.DataFrame:
    """
    东方财富-股票-财务分析-现金流量表-按单季度
    https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0
    :param symbol: 股票代码; 带市场标识
    :type symbol: str
    :return: 现金流量表-按单季度
    :rtype: pandas.DataFrame
    """
    company_type = _stock_balance_sheet_by_report_ctype_em(symbol=symbol)
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbDateAjaxNew"
    params = {
        "companyType": company_type,
        "reportDateType": "2",
        "code": symbol,
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df["REPORT_DATE"] = temp_df["REPORT_DATE"].astype(str)
    need_date = temp_df["REPORT_DATE"].tolist()
    sep_list = [",".join(need_date[i : i + 5]) for i in range(0, len(need_date), 5)]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for item in tqdm(sep_list, leave=False):
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/xjllbAjaxNew"
        params = {
            "companyType": company_type,
            "reportDateType": "0",
            "reportType": "2",
            "dates": item,
            "code": symbol,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        if "data" not in data_json.keys():
            break
        temp_df = pd.DataFrame(data_json["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    return big_df


def __get_report_date_list_delisted_em(symbol: str = "SZ000013") -> list:
    """
    东方财富-股票-财务分析-资产负债表-已退市股票-所有报告期
    https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013
    :param symbol: 已退市股票代码; 带市场标识
    :type symbol: str
    :return: 所有报告期
    :rtype: list
    """
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_GINCOME",
        "sty": "SECURITY_CODE,REPORT_DATE,REPORT_TYPE,REPORT_DATE_NAME",
        "filter": f'(SECURITY_CODE="{symbol[2:]}")',
        "p": "1",
        "ps": "200",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
        "v": "05767841728614413",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    report_date_list = [item[0] for item in temp_df["REPORT_DATE"].str.split(" ")]
    report_date_list = ["'" + item + "'" for item in report_date_list]
    return report_date_list


def stock_balance_sheet_by_report_delisted_em(symbol: str = "SZ000013") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-资产负债表-已退市股票-按报告期
    https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/zcfzb
    :param symbol: 已退市股票代码; 带市场标识
    :type symbol: str
    :return: 资产负债表-按报告期
    :rtype: pandas.DataFrame
    """
    report_date_list = __get_report_date_list_delisted_em(symbol)
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_GBALANCE",
        "sty": "F10_FINANCE_GBALANCE",
        "filter": f"""(SECUCODE="{symbol[2:]}.{symbol[:2]}")(REPORT_DATE in ({','.join(report_date_list)}))""",
        "p": "1",
        "ps": "200",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
        "v": "05767841728614413",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df.sort_values(
        by=["REPORT_DATE"], ascending=False, inplace=True, ignore_index=True
    )
    return temp_df


def stock_profit_sheet_by_report_delisted_em(symbol: str = "SZ000013") -> pd.DataFrame:
    """
    东方财富-股票-财务分析-利润表-已退市股票-按报告期
    https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/lrb
    :param symbol: 已退市股票代码; 带市场标识
    :type symbol: str
    :return: 利润表-按报告期
    :rtype: pandas.DataFrame
    """
    report_date_list = __get_report_date_list_delisted_em(symbol)
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_GINCOME",
        "sty": "APP_F10_GINCOME",
        "filter": f"""(SECUCODE="{symbol[2:]}.{symbol[:2]}")(REPORT_DATE in ({','.join(report_date_list)}))""",
        "p": "1",
        "ps": "200",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
        "v": "05767841728614413",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df.sort_values(
        by=["REPORT_DATE"], ascending=False, inplace=True, ignore_index=True
    )
    return temp_df


def stock_cash_flow_sheet_by_report_delisted_em(
    symbol: str = "SZ000013",
) -> pd.DataFrame:
    """
    东方财富-股票-财务分析-现金流量表-已退市股票-按报告期
    https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/xjllb
    :param symbol: 已退市股票代码; 带市场标识
    :type symbol: str
    :return: 现金流量表-按报告期
    :rtype: pandas.DataFrame
    """
    report_date_list = __get_report_date_list_delisted_em(symbol)
    url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_GCASHFLOW",
        "sty": "APP_F10_GCASHFLOW",
        "filter": f"""(SECUCODE="{symbol[2:]}.{symbol[:2]}")(REPORT_DATE in ({','.join(report_date_list)}))""",
        "p": "1",
        "ps": "200",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
        "v": "05767841728614413",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df["REPORT_DATE"] = pd.to_datetime(temp_df["REPORT_DATE"]).dt.date
    temp_df.sort_values(
        by=["REPORT_DATE"], ascending=False, inplace=True, ignore_index=True
    )
    return temp_df


if __name__ == "__main__":
    stock_balance_sheet_by_report_em_df = stock_balance_sheet_by_report_em(
        symbol="SH600519"
    )
    print(stock_balance_sheet_by_report_em_df)

    stock_balance_sheet_by_yearly_em_df = stock_balance_sheet_by_yearly_em(
        symbol="SH600519"
    )
    print(stock_balance_sheet_by_yearly_em_df)

    stock_profit_sheet_by_report_em_df = stock_profit_sheet_by_report_em(
        symbol="SH600519"
    )
    print(stock_profit_sheet_by_report_em_df)

    stock_profit_sheet_by_yearly_em_df = stock_profit_sheet_by_yearly_em(
        symbol="SH600519"
    )
    print(stock_profit_sheet_by_yearly_em_df)

    stock_profit_sheet_by_quarterly_em_df = stock_profit_sheet_by_quarterly_em(
        symbol="SH600519"
    )
    print(stock_profit_sheet_by_quarterly_em_df)

    stock_cash_flow_sheet_by_report_em_df = stock_cash_flow_sheet_by_report_em(
        symbol="SH600519"
    )
    print(stock_cash_flow_sheet_by_report_em_df)

    stock_cash_flow_sheet_by_yearly_em_df = stock_cash_flow_sheet_by_yearly_em(
        symbol="SH601398"
    )
    print(stock_cash_flow_sheet_by_yearly_em_df)

    stock_cash_flow_sheet_by_quarterly_em_df = stock_cash_flow_sheet_by_quarterly_em(
        symbol="SH601398"
    )
    print(stock_cash_flow_sheet_by_quarterly_em_df)

    stock_balance_sheet_by_report_delisted_em_df = (
        stock_balance_sheet_by_report_delisted_em(symbol="SZ000013")
    )
    print(stock_balance_sheet_by_report_delisted_em_df)

    stock_profit_sheet_by_report_delisted_em_df = (
        stock_profit_sheet_by_report_delisted_em(symbol="SZ000013")
    )
    print(stock_profit_sheet_by_report_delisted_em_df)

    stock_cash_flow_sheet_by_report_delisted_em_df = (
        stock_cash_flow_sheet_by_report_delisted_em(symbol="SZ000013")
    )
    print(stock_cash_flow_sheet_by_report_delisted_em_df)
