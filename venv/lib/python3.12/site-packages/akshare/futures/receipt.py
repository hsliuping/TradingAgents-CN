#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/21 15:00
Desc: 每日注册仓单数据
大连商品交易所, 上海期货交易所, 郑州商品交易所, 广州期货交易所
"""

import datetime
import re
import warnings
from io import BytesIO
from typing import List

import pandas as pd
import requests

from akshare.futures import cons
from akshare.futures.requests_fun import requests_link, pandas_read_html_link
from akshare.futures.symbol_var import chinese_to_english

calendar = cons.get_calendar()
shfe_20100126 = pd.DataFrame(
    {
        "var": ["CU", "AL", "ZN", "RU", "FU", "AU", "RB", "WR"],
        "receipt": [29783, 285396, 187713, 116435, 376200, 12, 145648, 0],
    }
)
shfe_20101029 = pd.DataFrame(
    {
        "var": ["CU", "AL", "ZN", "RU", "FU", "AU", "RB", "WR"],
        "receipt": [39214, 359729, 182562, 25990, 313600, 27, 36789, 0],
    }
)


def get_dce_receipt(date: str = None, vars_list: List = cons.contract_symbols):
    """
    大连商品交易所-注册仓单数据

    :param date: 开始日期: YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象, 为空时为当天
    :type date: str
    :param vars_list: 合约品种如 RB, AL等列表, 为空时为所有商品数据从 20060106开始，每周五更新仓单数据。直到20090407起，每交易日都更新仓单数据
    :type vars_list: list
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        return warnings.warn("vars_list: 必须是列表")
    date = cons.convert_date(date) if date is not None else datetime.date.today()
    if date.strftime("%Y%m%d") not in calendar:
        warnings.warn(f"{date.strftime('%Y%m%d')}非交易日")
        return None
    payload = {
        "weekQuotes.variety": "all",
        "year": date.year,
        "month": date.month - 1,  # 网站月份描述少 1 个月, 属于网站问题
        "day": date.day,
    }
    data = pandas_read_html_link(
        cons.DCE_RECEIPT_URL, method="post", data=payload, headers=cons.dce_headers
    )[0]
    records = pd.DataFrame()
    for x in data.to_dict(orient="records"):
        if isinstance(x["品种"], str):
            if x["品种"][-2:] == "小计":
                var = x["品种"][:-2]
                temp_data = {
                    "var": chinese_to_english(var),
                    "receipt": int(x["今日仓单量"]),
                    "receipt_chg": int(x["增减"]),
                    "date": date.strftime("%Y%m%d"),
                }
                records = pd.concat([records, pd.DataFrame(temp_data, index=[0])])

    if len(records.index) != 0:
        records.index = records["var"]
        vars_in_market = [i for i in vars_list if i in records.index]
        records = records.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_shfe_receipt_1(
    date: str = None, vars_list: List = cons.contract_symbols
) -> pd.DataFrame:
    """
    上海期货交易所-注册仓单数据-类型1
    适用 20081006 至 20140518(包括)、20100126、20101029日期交易所格式混乱，直接回复脚本中 pandas.DataFrame, 20100416、20130821日期交易所数据丢失
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象为空时为当天
    :type date: str
    :param vars_list: 合约品种如RB、AL等列表为空时为所有商品
    :type vars_list: list
    :return: 注册仓单数据-类型1
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        raise warnings.warn("symbol_list: 必须是列表")
    date = (
        cons.convert_date(date).strftime("%Y%m%d")
        if date is not None
        else datetime.date.today()
    )
    if date not in calendar:
        warnings.warn(f"{date.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    if date == "20100126":
        shfe_20100126["date"] = date
        return shfe_20100126
    elif date == "20101029":
        shfe_20101029["date"] = date
        return shfe_20101029
    elif date in ["20100416", "20130821"]:
        return warnings.warn("20100416、20130821交易所数据丢失")
    else:
        var_list = [
            "天然橡胶",
            "沥青仓库",
            "沥青厂库",
            "热轧卷板",
            "燃料油",
            "白银",
            "线材",
            "螺纹钢",
            "铅",
            "铜",
            "铝",
            "锌",
            "黄金",
            "锡",
            "镍",
        ]
        url = cons.SHFE_RECEIPT_URL_1 % date
        data = pandas_read_html_link(url)[0]
        indexes = [x for x in data.index if (data[0].tolist()[x] in var_list)]
        last_index = [x for x in data.index if "注" in str(data[0].tolist()[x])][0] - 1
        records = pd.DataFrame()
        for i in list(range(len(indexes))):
            if i != len(indexes) - 1:
                data_cut = data.loc[indexes[i] : indexes[i + 1] - 1, :]
            else:
                data_cut = data.loc[indexes[i] : last_index, :]
                data_cut = data_cut.fillna(method="pad")
            data_dict = dict()
            data_dict["var"] = chinese_to_english(data_cut[0].tolist()[0])
            data_dict["receipt"] = int(data_cut[2].tolist()[-1])
            data_dict["receipt_chg"] = int(data_cut[3].tolist()[-1])
            data_dict["date"] = date
            records = pd.concat([records, pd.DataFrame(data_dict, index=[0])])
    if len(records.index) != 0:
        records.index = records["var"]
        vars_in_market = [i for i in vars_list if i in records.index]
        records = records.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_shfe_receipt_2(
    date: str = None, vars_list: List = cons.contract_symbols
) -> pd.DataFrame:
    """
    上海商品交易所-注册仓单数据-类型2
    适用 20140519(包括)-至今
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type date: str
    :param vars_list: 合约品种如 RB、AL 等列表 为空时为所有商品
    :type vars_list: list
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        raise warnings.warn("symbol_list: 必须是列表")
    date = (
        cons.convert_date(date).strftime("%Y%m%d")
        if date is not None
        else datetime.date.today()
    )
    if date not in calendar:
        warnings.warn("%s 非交易日" % date.strftime("%Y%m%d"))
        return pd.DataFrame()
    url = cons.SHFE_RECEIPT_URL_20250701 % date
    r = requests_link(url, encoding="utf-8", headers=cons.shfe_headers)
    try:
        context = r.json()
    except:  # noqa: E722
        return pd.DataFrame()
    data = pd.DataFrame(context["o_cursor"])
    if len(data.columns) < 1:
        return pd.DataFrame()
    records = pd.DataFrame()
    for var in set(data["VARNAME"].tolist()):
        data_cut = data[data["VARNAME"] == var]
        if "BC" in var:
            data_dict = {
                "var": "BC",
                "receipt": int(data_cut["WRTWGHTS"].tolist()[-1]),
                "receipt_chg": int(data_cut["WRTCHANGE"].tolist()[-1]),
                "date": date,
            }
        else:
            data_dict = {
                "var": chinese_to_english(re.sub(r"\W|[a-zA-Z]", "", var)),
                "receipt": int(data_cut["WRTWGHTS"].tolist()[-1]),
                "receipt_chg": int(data_cut["WRTCHANGE"].tolist()[-1]),
                "date": date,
            }
        records = pd.concat([records, pd.DataFrame(data_dict, index=[0])])
        temp_records = (
            records.groupby("var")[["receipt", "receipt_chg"]].sum().reset_index()
        )
        temp_records["date"] = date
        records = temp_records
    if len(records.index) != 0:
        records.index = records["var"]
        vars_in_market = [i for i in vars_list if i in records.index]
        records = records.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_czce_receipt_1(date: str = None, vars_list: List = cons.contract_symbols):
    """
    郑州商品交易所-注册仓单数据
    适用 20080222 至 20100824(包括)
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type date: str
    :param vars_list: list
    :type vars_list: 合约品种如 CF、TA 等列表 为空时为所有商品
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    date = (
        cons.convert_date(date).strftime("%Y%m%d")
        if date is not None
        else datetime.date.today()
    )
    if date not in calendar:
        warnings.warn("%s非交易日" % date.strftime("%Y%m%d"))
        return None
    if date == "20090820":
        return pd.DataFrame()
    url = cons.CZCE_RECEIPT_URL_1 % date
    r = requests_link(url, encoding="utf-8", headers=cons.shfe_headers)
    context = r.text
    data = pd.read_html(context)[1]
    records = pd.DataFrame()
    indexes = [x for x in data.index if "品种：" in str(data[0].tolist()[x])]
    ends = [x for x in data.index if "总计" in str(data[0].tolist()[x])]
    for i in list(range(len(indexes))):
        if i != len(indexes) - 1:
            data_cut = data.loc[indexes[i] : ends[i], :]
            data_cut = data_cut.fillna(method="pad")
        else:
            data_cut = data.loc[indexes[i] :, :]
            data_cut = data_cut.fillna(method="pad")
        if "PTA" in data_cut[0].tolist()[0]:
            var = "TA"
        else:
            var = chinese_to_english(re.sub(r"[A-Z]+", "", data_cut[0].tolist()[0][3:]))
        if var == "CF":
            receipt = data_cut[6].tolist()[-1]
            receipt_chg = data_cut[7].tolist()[-1]
        else:
            receipt = data_cut[5].tolist()[-1]
            receipt_chg = data_cut[6].tolist()[-1]
        data_dict = {
            "var": var,
            "receipt": int(receipt),
            "receipt_chg": int(receipt_chg),
            "date": date,
        }
        records = pd.concat([records, pd.DataFrame(data_dict, index=[0])])
    if len(records.index) != 0:
        records.index = records["var"]
        vars_in_market = [i for i in vars_list if i in records.index]
        records = records.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_czce_receipt_2(date: str = None, vars_list: List = cons.contract_symbols):
    """
    郑州商品交易所-注册仓单数据
    http://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm
    适用 20100825(包括) - 20151111(包括)
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type date: str
    :param vars_list: 合约品种如 CF、TA 等列表为空时为所有商品
    :type vars_list: list
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        return warnings.warn("symbol_list: 必须是列表")
    date = (
        cons.convert_date(date).strftime("%Y%m%d")
        if date is not None
        else datetime.date.today()
    )
    if date not in calendar:
        warnings.warn("%s非交易日" % date.strftime("%Y%m%d"))
        return None
    url = cons.CZCE_RECEIPT_URL_2 % (date[:4], date)
    r = requests.get(url)
    r.encoding = "utf-8"
    data = pd.read_html(r.text)[3:]
    records = pd.DataFrame()
    for data_cut in data:
        if len(data_cut.columns) > 3:
            last_indexes = [
                x for x in data_cut.index if "注：" in str(data_cut[0].tolist()[x])
            ]
            if len(last_indexes) > 0:
                last_index = last_indexes[0] - 1
                data_cut = data_cut.loc[:last_index, :]
            if "PTA" in data_cut[0].tolist()[0]:
                var = "TA"
            else:
                strings = data_cut[0].tolist()[0]
                string = strings.split(" ")[0][3:]
                var = chinese_to_english(re.sub(r"[A-Z]+", "", string))
            data_cut.columns = data_cut.T[1].tolist()
            receipt = data_cut["仓单数量"].tolist()[-1]
            receipt_chg = data_cut["当日增减"].tolist()[-1]
            data_dict = {
                "var": var,
                "receipt": int(receipt),
                "receipt_chg": int(receipt_chg),
                "date": date,
            }
            records = pd.concat([records, pd.DataFrame(data_dict, index=[0])])
    if len(records.index) != 0:
        records.index = records["var"]
        vars_in_market = [i for i in vars_list if i in records.index]
        records = records.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_czce_receipt_3(
    date: str = None, vars_list: List = cons.contract_symbols
) -> pd.DataFrame:
    """
    郑州商品交易所-注册仓单数据
    适用 20151008-至今
    http://www.czce.com.cn/cn/jysj/cdrb/H770310index_1.htm
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type date: str
    :param vars_list: 合约品种如 CF、TA 等列表为空时为所有商品
    :type vars_list: list
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        return warnings.warn("vars_list: 必须是列表")
    date = (
        cons.convert_date(date).strftime("%Y%m%d")
        if date is not None
        else datetime.date.today()
    )
    if date not in calendar:
        warnings.warn("%s非交易日" % date.strftime("%Y%m%d"))
        return None
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataWhsheet.xls"
    r = requests_link(url, encoding="utf-8", headers=cons.shfe_headers)
    temp_df = pd.read_excel(BytesIO(r.content))
    temp_df = temp_df[
        [
            bool(1 - item)
            for item in [
                item if item is not pd.NA else False
                for item in temp_df.iloc[:, 0].str.contains("非农产品")
            ]
        ]
    ]
    temp_df.reset_index(inplace=True, drop=True)
    range_list_one = list(
        temp_df[
            [
                item if not pd.isnull(item) else False
                for item in temp_df.iloc[:, 0].str.contains("品种")
            ]
        ].index
    )
    range_list_two = list(
        temp_df[
            [
                item if not pd.isnull(item) else False
                for item in temp_df.iloc[:, 0].str.contains("品种")
            ]
        ].index
    )[1:]
    range_list_two.append(None)
    symbol_list = []
    receipt_list = []
    receipt_chg_list = []
    for page in range(len(range_list_one)):
        inner_df = temp_df[range_list_one[page] : range_list_two[page]]
        reg = re.compile(r"[A-Z]+")
        try:
            symbol = reg.findall(inner_df.iloc[0, 0])[0]
        except:  # noqa: E722
            continue
        symbol_list.append(symbol)
        inner_df.columns = inner_df.iloc[1, :]
        inner_df = inner_df.iloc[2:, :]
        inner_df = inner_df.dropna(axis=1, how="all")
        if symbol == "PTA":
            try:
                receipt_list.append(
                    inner_df["仓单数量(完税)"].iloc[-1]
                    + int(inner_df["仓单数量(保税)"].iloc[-1])
                )  # 20210316 TA 分为保税和完税
            except:  # noqa: E722
                receipt_list.append(0)
        elif symbol == "MA":
            try:
                try:
                    receipt_list.append(
                        inner_df["仓单数量(完税)"].iloc[-2]
                        + int(inner_df["仓单数量(保税)"].iloc[-2])
                    )  # 20210316 MA 分为保税和完税
                except:  # noqa: E722
                    receipt_list.append(
                        inner_df["仓单数量(完税)"].iloc[-2]
                    )  # 处理 MA 的特殊格式
            except:  # noqa: E722
                receipt_list.append(0)
        else:
            try:
                receipt_list.append(inner_df["仓单数量"].iloc[-1])
            except:  # noqa: E722
                receipt_list.append(0)
        if symbol == "MA":
            receipt_chg_list.append(inner_df["当日增减"].iloc[-2])
        else:
            receipt_chg_list.append(inner_df["当日增减"].iloc[-1])
    data_df = pd.DataFrame(
        [symbol_list, receipt_list, receipt_chg_list, [date] * len(receipt_chg_list)]
    ).T
    data_df.columns = ["var", "receipt", "receipt_chg", "date"]
    temp_list = data_df["var"].tolist()
    data_df["var"] = [item if item != "PTA" else "TA" for item in temp_list]
    if len(data_df.index) != 0:
        data_df.index = data_df["var"]
        vars_in_market = [i for i in vars_list if i in data_df.index]
        records = data_df.loc[vars_in_market, :]
    return records.reset_index(drop=True)


def get_gfex_receipt(
    date: str = None, vars_list: List = cons.contract_symbols
) -> pd.DataFrame:
    """
    广州期货交易所-注册仓单数据
    http://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml
    :param date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type date: str
    :param vars_list: 合约品种如 SI 等列表为空时为所有商品
    :type vars_list: list
    :return: 注册仓单数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        raise warnings.warn("vars_list: 必须是列表")
    date = cons.convert_date(date) if date is not None else datetime.date.today()
    if date.strftime("%Y%m%d") not in calendar:
        warnings.warn(f"{date.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    url = "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList"
    payload = {"gen_date": date.isoformat().replace("-", "")}
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "32",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.gfex.com.cn",
        "Origin": "http://www.gfex.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://www.gfex.com.cn/gfex/rihq/hqsj_tjsj.shtml",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "content-type": "application/x-www-form-urlencoded",
    }
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df = temp_df[temp_df["variety"].str.contains("小计")]
    result_df = temp_df[["wbillQty", "diff"]].copy()
    if result_df.empty:
        return pd.DataFrame()

    result_df.loc[:, "date"] = date.isoformat().replace("-", "")
    result_df.loc[:, "var"] = [
        item.upper() for item in temp_df["varietyOrder"].tolist()
    ]
    result_df.reset_index(drop=True, inplace=True)
    result_df.rename(
        columns={
            "wbillQty": "receipt",
            "diff": "receipt_chg",
        },
        inplace=True,
    )
    result_df = result_df[["var", "receipt", "receipt_chg", "date"]]
    result_df.set_index(keys=["var"], inplace=True)
    if "LC" not in result_df.index:
        vars_list.remove("LC")
    if "PS" not in result_df.index:
        vars_list.remove("PS")
    result_df = result_df.loc[vars_list, :]
    result_df.reset_index(inplace=True)
    return result_df


def get_receipt(
    start_date: str = None,
    end_date: str = None,
    vars_list: List = cons.contract_symbols,
):
    """
    大宗商品-注册仓单数据
    :param start_date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date 对象 为空时为当天
    :type start_date: str
    :param end_date: 结束数据 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date 对象 为空时为当天
    :type end_date: str
    :param vars_list: 合约品种如 RB、AL 等列表为空时为所有商品
    :type vars_list: str
    :return: 展期收益率数据
    :rtype: pandas.DataFrame
    """
    if not isinstance(vars_list, list):
        return warnings.warn("vars_list: 必须是列表")
    start_date = (
        cons.convert_date(start_date)
        if start_date is not None
        else datetime.date.today()
    )
    end_date = (
        cons.convert_date(end_date)
        if end_date is not None
        else cons.convert_date(cons.get_latest_data_date(datetime.datetime.now()))
    )
    records = pd.DataFrame()
    while start_date <= end_date:
        if start_date.strftime("%Y%m%d") not in calendar:
            warnings.warn(f"{start_date.strftime('%Y%m%d')} 非交易日")
        else:
            print(start_date)
            for market, market_vars in cons.market_exchange_symbols.items():
                if market == "dce":
                    if start_date >= datetime.date(2009, 4, 7):
                        f = get_dce_receipt
                    else:
                        print("20090407 起，大连商品交易所每个交易日更新仓单数据")
                        f = None
                elif market == "shfe":
                    if (
                        datetime.date(2008, 10, 6)
                        <= start_date
                        <= datetime.date(2014, 5, 16)
                    ):
                        f = get_shfe_receipt_1
                    elif start_date > datetime.date(2014, 5, 16):
                        f = get_shfe_receipt_2
                    else:
                        f = None
                        print("20081006 起，上海期货交易所每个交易日更新仓单数据")
                elif market == "gfex":
                    if start_date > datetime.date(2022, 12, 22):
                        f = get_gfex_receipt
                    else:
                        f = None
                        print("20081006 起，上海期货交易所每个交易日更新仓单数据")
                elif market == "czce":
                    if (
                        datetime.date(2008, 3, 3)
                        <= start_date
                        <= datetime.date(2010, 8, 24)
                    ):
                        f = get_czce_receipt_1
                    elif (
                        datetime.date(2010, 8, 24)
                        < start_date
                        <= datetime.date(2015, 11, 11)
                    ):
                        f = get_czce_receipt_2
                    elif start_date > datetime.date(2015, 11, 11):
                        f = get_czce_receipt_3
                    else:
                        f = None
                        print("20080303 起，郑州商品交易所每个交易日更新仓单数据")
                get_vars = [var for var in vars_list if var in market_vars]
                if market != "cffex" and get_vars != []:
                    if f is not None:
                        records = pd.concat([records, f(start_date, get_vars)])
        start_date += datetime.timedelta(days=1)
    records.reset_index(drop=True, inplace=True)
    if records.empty:
        return records
    return records


if __name__ == "__main__":
    get_receipt_df = get_receipt(start_date="20250718", end_date="20250718")
    print(get_receipt_df)
