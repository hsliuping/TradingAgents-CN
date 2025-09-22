#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/12/14 15:00
Desc: 东方财富网站-天天基金网-基金数据-开放式基金净值
https://fund.eastmoney.com/manager/default.html#dt14;mcreturnjson;ftall;pn20;pi1;scabbname;stasc
1.基金经理基本数据, 建议包含:基金经理代码,基金经理姓名,从业起始日期,现任基金公司,管理资产总规模,上述数据可在"基金经理列表:
https://fund.eastmoney.com/manager/default.html#dt14;mcreturnjson;ftall;pn20;pi1;scabbname;stasc 和
"基金经理理档案如:https://fund.eastmoney.com/manager/30040164.html 获取.
2.基金经理任职数据:可调取全部或特定经理,管理的基金数据,建议包含:基金经理代码,基金经理姓名,基金代码,基金简称,
经理位次(在当前基金的经理中排第几位),起始任职时间,截止任职时间,任职回报.在特定基金的经理信息中可以获取如:
https://fundf10.eastmoney.com/jjjl_001810.html
3.在接口：fund_basic"公募基金列表"增加数据"基金经理代码"(或第一基金经理代码),
"基金经理姓名"(或第一基金经理姓名),"当前基金经理人数","当前经理任职起始时间".
用户ID:269993
"""

import json
import math
import time
from io import StringIO

import pandas as pd
import py_mini_racer
import requests

from akshare.utils import demjson
from akshare.utils.cons import headers
from akshare.utils.tqdm import get_tqdm


def fund_purchase_em() -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-基金申购状态
    https://fund.eastmoney.com/Fund_sgzt_bzdm.html#fcode,asc_1
    :return: 基金申购状态
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Data/Fund_JJJZ_Data.aspx"
    params = {
        "t": "8",
        "page": "1,50000",
        "js": "reData",
        "sort": "fcode,asc",
    }
    r = requests.get(url, params=params, headers=headers)
    data_text = r.text
    data_json = demjson.decode(data_text.strip("var reData="))
    temp_df = pd.DataFrame(data_json["datas"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "基金类型",
        "最新净值/万份收益",
        "最新净值/万份收益-报告时间",
        "申购状态",
        "赎回状态",
        "下一开放日",
        "购买起点",
        "日累计限定金额",
        "-",
        "-",
        "手续费",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "基金类型",
            "最新净值/万份收益",
            "最新净值/万份收益-报告时间",
            "申购状态",
            "赎回状态",
            "下一开放日",
            "购买起点",
            "日累计限定金额",
            "手续费",
        ]
    ]
    temp_df["下一开放日"] = pd.to_datetime(
        temp_df["下一开放日"], errors="coerce"
    ).dt.date
    temp_df["最新净值/万份收益"] = pd.to_numeric(
        temp_df["最新净值/万份收益"], errors="coerce"
    )
    temp_df["购买起点"] = pd.to_numeric(temp_df["购买起点"], errors="coerce")
    temp_df["日累计限定金额"] = pd.to_numeric(
        temp_df["日累计限定金额"], errors="coerce"
    )
    temp_df["手续费"] = temp_df["手续费"].str.strip("%")
    temp_df["手续费"] = pd.to_numeric(temp_df["手续费"], errors="coerce")
    return temp_df


def fund_name_em() -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-所有基金的名称和类型
    https://fund.eastmoney.com/manager/default.html#dt14;mcreturnjson;ftall;pn20;pi1;scabbname;stasc
    :return: 所有基金的名称和类型
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/js/fundcode_search.js"
    r = requests.get(url, headers=headers)
    text_data = r.text
    data_json = demjson.decode(text_data.strip("var r = ")[:-1])
    temp_df = pd.DataFrame(data_json)
    temp_df.columns = ["基金代码", "拼音缩写", "基金简称", "基金类型", "拼音全称"]
    return temp_df


def fund_info_index_em(
    symbol: str = "沪深指数", indicator: str = "被动指数型"
) -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-基金信息-指数型
    https://fund.eastmoney.com/trade/zs.html
    :param symbol: choice of {"全部", "沪深指数", "行业主题", "大盘指数", "中盘指数", "小盘指数", "股票指数", "债券指数"}
    :type symbol: str
    :param indicator: choice of {"全部", "被动指数型", "增强指数型"}
    :type indicator: str
    :return: pandas.DataFrame
    :rtype: 基金信息-指数型
    """
    symbol_map = {
        "全部": "",
        "沪深指数": "053",
        "行业主题": "054",
        "大盘指数": "01",
        "中盘指数": "02",
        "小盘指数": "03",
        "股票指数": "050|001",
        "债券指数": "050|003",
    }
    indicator_map = {
        "全部": "",
        "被动指数型": "051",
        "增强指数型": "052",
    }
    url = "https://api.fund.eastmoney.com/FundTradeRank/GetRankList"
    if symbol in {"股票指数", "债券指数"}:
        params = {
            "ft": "zs",
            "sc": "1n",
            "st": "desc",
            "pi": "1",
            "pn": "10000",
            "cp": "",
            "ct": "",
            "cd": "",
            "ms": "",
            "fr": symbol_map[symbol].split("|")[0],
            "plevel": "",
            "fst": "",
            "ftype": symbol_map[symbol].split("|")[1],
            "fr1": indicator_map[indicator],
            "fl": "0",
            "isab": "1",
        }
    else:
        params = {
            "ft": "zs",
            "sc": "1n",
            "st": "desc",
            "pi": "1",
            "pn": "10000",
            "cp": "",
            "ct": "",
            "cd": "",
            "ms": "",
            "fr": symbol_map[symbol].split("|")[0],
            "plevel": "",
            "fst": "",
            "ftype": "",
            "fr1": indicator_map[indicator],
            "fl": "0",
            "isab": "1",
        }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Host": "api.fund.eastmoney.com",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/103.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    data_json = json.loads(data_json["Data"])
    temp_df = pd.DataFrame([item.split("|") for item in data_json["datas"]])
    temp_df.columns = [
        "基金代码",
        "基金名称",
        "-",
        "日期",
        "单位净值",
        "日增长率",
        "近1周",
        "近1月",
        "近3月",
        "近6月",
        "近1年",
        "近2年",
        "近3年",
        "今年来",
        "成立来",
        "-",
        "-",
        "-",
        "手续费",
        "-",
        "-",
        "-",
        "-",
        "-",
        "起购金额",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "基金代码",
            "基金名称",
            "单位净值",
            "日期",
            "日增长率",
            "近1周",
            "近1月",
            "近3月",
            "近6月",
            "近1年",
            "近2年",
            "近3年",
            "今年来",
            "成立来",
            "手续费",
            "起购金额",
        ]
    ]
    temp_df["跟踪标的"] = symbol
    temp_df["跟踪方式"] = indicator

    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
    temp_df["近1周"] = pd.to_numeric(temp_df["近1周"], errors="coerce")
    temp_df["近1月"] = pd.to_numeric(temp_df["近1月"], errors="coerce")
    temp_df["近3月"] = pd.to_numeric(temp_df["近3月"], errors="coerce")
    temp_df["近6月"] = pd.to_numeric(temp_df["近6月"], errors="coerce")
    temp_df["近1年"] = pd.to_numeric(temp_df["近1年"], errors="coerce")
    temp_df["近2年"] = pd.to_numeric(temp_df["近2年"], errors="coerce")
    temp_df["近3年"] = pd.to_numeric(temp_df["近3年"], errors="coerce")
    temp_df["今年来"] = pd.to_numeric(temp_df["今年来"], errors="coerce")
    temp_df["成立来"] = pd.to_numeric(temp_df["成立来"], errors="coerce")
    temp_df["手续费"] = pd.to_numeric(temp_df["手续费"], errors="coerce")
    return temp_df


def fund_open_fund_daily_em() -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-开放式基金净值
    https://fund.eastmoney.com/fund.html#os_0;isall_0;ft_;pt_1
    :return: 当前交易日的所有开放式基金净值数据
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Data/Fund_JJJZ_Data.aspx"
    params = {
        "t": "1",
        "lx": "1",
        "letter": "",
        "gsid": "",
        "text": "",
        "sort": "zdf,desc",
        "page": "1,50000",
        "dt": "1580914040623",
        "atfc": "",
        "onlySale": "0",
    }
    res = requests.get(url, params=params, headers=headers)
    text_data = res.text
    data_json = demjson.decode(text_data.strip("var db="))
    temp_df = pd.DataFrame(data_json["datas"])
    show_day = data_json["showday"]
    temp_df.columns = [
        "基金代码",
        "基金简称",
        "-",
        f"{show_day[0]}-单位净值",
        f"{show_day[0]}-累计净值",
        f"{show_day[1]}-单位净值",
        f"{show_day[1]}-累计净值",
        "日增长值",
        "日增长率",
        "申购状态",
        "赎回状态",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "手续费",
        "-",
        "-",
        "-",
    ]
    data_df = temp_df[
        [
            "基金代码",
            "基金简称",
            f"{show_day[0]}-单位净值",
            f"{show_day[0]}-累计净值",
            f"{show_day[1]}-单位净值",
            f"{show_day[1]}-累计净值",
            "日增长值",
            "日增长率",
            "申购状态",
            "赎回状态",
            "手续费",
        ]
    ]
    return data_df


def fund_open_fund_info_em(
    symbol: str = "710001", indicator: str = "单位净值走势", period: str = "成立来"
) -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-开放式基金净值
    https://fund.eastmoney.com/fund.html
    :param symbol: 基金代码; 可以通过调用 ak.fund_open_fund_daily_em() 获取所有开放式基金代码
    :type symbol: str
    :param indicator: 需要获取的指标
    :type indicator: str
    :param period: "成立来"; choice of {"1月", "3月", "6月", "1年", "3年", "5年", "今年来", "成立来"}
    :type period: str
    :return: 指定基金指定指标的数据
    :rtype: pandas.DataFrame
    """
    from akshare.utils.cons import headers

    url = f"https://fund.eastmoney.com/pingzhongdata/{symbol}.js"  # 各类数据都在里面
    r = requests.get(url, headers=headers)
    data_text = r.text

    js_code = py_mini_racer.MiniRacer()
    js_code.eval(data_text)

    # 单位净值走势
    if indicator == "单位净值走势":
        data_json = js_code.execute("Data_netWorthTrend")
        temp_df = pd.DataFrame(data_json)
        if temp_df.empty:
            return pd.DataFrame()
        temp_df["x"] = pd.to_datetime(temp_df["x"], unit="ms", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        )
        temp_df["x"] = temp_df["x"].dt.date
        temp_df.columns = [
            "净值日期",
            "单位净值",
            "日增长率",
            "_",
        ]
        temp_df = temp_df[
            [
                "净值日期",
                "单位净值",
                "日增长率",
            ]
        ]
        temp_df["净值日期"] = pd.to_datetime(
            temp_df["净值日期"], errors="coerce"
        ).dt.date
        temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
        temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
        return temp_df

    # 累计净值走势
    if indicator == "累计净值走势":
        data_json = js_code.execute("Data_ACWorthTrend")
        temp_df = pd.DataFrame(data_json)
        if temp_df.empty:
            return pd.DataFrame()
        temp_df.columns = ["x", "y"]
        temp_df["x"] = pd.to_datetime(temp_df["x"], unit="ms", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        )
        temp_df["x"] = temp_df["x"].dt.date
        temp_df.columns = [
            "净值日期",
            "累计净值",
        ]
        temp_df = temp_df[
            [
                "净值日期",
                "累计净值",
            ]
        ]
        temp_df["净值日期"] = pd.to_datetime(
            temp_df["净值日期"], errors="coerce"
        ).dt.date
        temp_df["累计净值"] = pd.to_numeric(temp_df["累计净值"], errors="coerce")
        return temp_df

    # 累计收益率走势
    if indicator == "累计收益率走势":
        url = "https://api.fund.eastmoney.com/pinzhong/LJSYLZS"
        headers = {"Referer": "https://fund.eastmoney.com/"}
        period_map = {
            "1月": "m",
            "3月": "q",
            "6月": "hy",
            "1年": "y",
            "3年": "try",
            "5年": "fiy",
            "今年来": "sy",
            "成立来": "se",
        }
        params = {
            "fundCode": symbol,
            "indexcode": "000300",
            "type": period_map[period],
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["Data"][0]["data"])
        temp_df.columns = ["日期", "累计收益率"]
        temp_df["日期"] = pd.to_datetime(
            temp_df["日期"], unit="ms", utc=True
        ).dt.tz_convert("Asia/Shanghai")
        temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
        temp_df["累计收益率"] = pd.to_numeric(temp_df["累计收益率"], errors="coerce")
        return temp_df

    # 同类排名走势
    if indicator == "同类排名走势":
        data_json = js_code.execute("Data_rateInSimilarType")
        temp_df = pd.DataFrame(data_json)
        temp_df["x"] = pd.to_datetime(temp_df["x"], unit="ms", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        )
        temp_df["x"] = temp_df["x"].dt.date
        temp_df.columns = [
            "报告日期",
            "同类型排名-每日近三月排名",
            "总排名-每日近三月排名",
        ]
        temp_df = temp_df[
            [
                "报告日期",
                "同类型排名-每日近三月排名",
                "总排名-每日近三月排名",
            ]
        ]
        temp_df["报告日期"] = pd.to_datetime(
            temp_df["报告日期"], errors="coerce"
        ).dt.date
        temp_df["同类型排名-每日近三月排名"] = pd.to_numeric(
            temp_df["同类型排名-每日近三月排名"], errors="coerce"
        )
        temp_df["总排名-每日近三月排名"] = pd.to_numeric(
            temp_df["总排名-每日近三月排名"], errors="coerce"
        )
        return temp_df

    # 同类排名百分比
    if indicator == "同类排名百分比":
        data_json = js_code.execute("Data_rateInSimilarPersent")
        temp_df = pd.DataFrame(data_json)
        temp_df.columns = ["x", "y"]
        temp_df["x"] = pd.to_datetime(temp_df["x"], unit="ms", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        )
        temp_df["x"] = temp_df["x"].dt.date
        temp_df.columns = [
            "报告日期",
            "同类型排名-每日近3月收益排名百分比",
        ]
        temp_df = temp_df[
            [
                "报告日期",
                "同类型排名-每日近3月收益排名百分比",
            ]
        ]
        temp_df["报告日期"] = pd.to_datetime(
            temp_df["报告日期"], errors="coerce"
        ).dt.date
        temp_df["同类型排名-每日近3月收益排名百分比"] = pd.to_numeric(
            temp_df["同类型排名-每日近3月收益排名百分比"], errors="coerce"
        )
        return temp_df

    # 分红送配详情
    if indicator == "分红送配详情":
        url = f"https://fundf10.eastmoney.com/fhsp_{symbol}.html"
        r = requests.get(url, headers=headers)
        table_num = len(pd.read_html(StringIO(r.text)))
        if table_num == 3:
            temp_df = pd.read_html(StringIO(r.text))[1]
        else:
            temp_df = pd.read_html(StringIO(r.text))[0]
        if temp_df.iloc[0, 1] == "暂无分红信息!":
            return pd.DataFrame()
        else:
            return temp_df

    # 拆分详情
    if indicator == "拆分详情":
        url = f"https://fundf10.eastmoney.com/fhsp_{symbol}.html"
        r = requests.get(url, headers=headers)
        table_num = len(pd.read_html(StringIO(r.text)))
        if table_num == 3:
            temp_df = pd.read_html(StringIO(r.text))[2]
        else:
            temp_df = pd.read_html(StringIO(r.text))[1]
        if temp_df.iloc[0, 1] == "暂无拆分信息!":
            return pd.DataFrame()
        else:
            return temp_df
    return pd.DataFrame()


def fund_money_fund_daily_em() -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-货币型基金收益
    https://fund.eastmoney.com/HBJJ_pjsyl.html
    :return: 当前交易日的所有货币型基金收益数据
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/HBJJ_pjsyl.html"
    r = requests.get(url, headers=headers)
    r.encoding = "gb2312"
    show_day = pd.read_html(StringIO(r.text))[1].iloc[0, 5:11].tolist()
    temp_df = pd.read_html(StringIO(r.text))[1].iloc[1:, 2:]
    temp_df_columns = temp_df.iloc[0, :].tolist()[1:]
    temp_df = temp_df.iloc[1:, 1:]
    temp_df.columns = temp_df_columns
    temp_df["基金简称"] = temp_df["基金简称"].str.strip("基金吧档案")
    temp_df.columns = [
        "基金代码",
        "基金简称",
        f"{show_day[0]}-万份收益",
        f"{show_day[1]}-7日年化%",
        f"{show_day[2]}-单位净值",
        f"{show_day[3]}-万份收益",
        f"{show_day[4]}-7日年化%",
        f"{show_day[5]}-单位净值",
        "日涨幅",
        "成立日期",
        "基金经理",
        "手续费",
        "可购全部",
    ]
    return temp_df


def fund_money_fund_info_em(symbol: str = "000009") -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-货币型基金收益-历史净值数据
    https://fundf10.eastmoney.com/jjjz_004186.html
    :param symbol: 货币型基金代码, 可以通过 fund_money_fund_daily_em 来获取
    :type symbol: str
    :return: 东方财富网站-天天基金网-基金数据-货币型基金收益-历史净值数据
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
        "Host": "api.fund.eastmoney.com",
    }
    params = {
        "fundCode": symbol,
        "pageIndex": "1",
        "pageSize": "20",
        "startDate": "",
        "endDate": "",
        "_": round(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = math.ceil(int(data_json["TotalCount"]) / 20)
    tqdm = get_tqdm()
    big_list = []
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageIndex": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["Data"]["LSJZList"])
        big_list.append(temp_df)
    big_df = pd.concat(big_list, ignore_index=True)
    big_df.columns = [
        "净值日期",
        "每万份收益",
        "7日年化收益率",
        "_",
        "_",
        "_",
        "_",
        "申购状态",
        "赎回状态",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df.sort_values(by=["净值日期"], inplace=True, ignore_index=True)
    big_df = big_df[["净值日期", "每万份收益", "7日年化收益率", "申购状态", "赎回状态"]]
    big_df["净值日期"] = pd.to_datetime(big_df["净值日期"], errors="coerce").dt.date
    big_df["每万份收益"] = pd.to_numeric(big_df["每万份收益"], errors="coerce")
    big_df["7日年化收益率"] = pd.to_numeric(big_df["7日年化收益率"], errors="coerce")
    return big_df


def fund_financial_fund_daily_em() -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-理财型基金收益
    # 该接口暂无数据
    https://fund.eastmoney.com/lcjj.html#1_1__0__ljjz,desc_1_os1
    :return: 当前交易日的所有理财型基金收益
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/FundNetValue/GetLCJJJZ"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/lcjj.html",
    }
    params = {
        "letter": "",
        "jjgsid": "0",
        "searchtext": "",
        "sort": "ljjz,desc",
        "page": "1,100",
        "AttentionCodes": "",
        "cycle": "",
        "OnlySale": "1",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["Data"]["List"])
    if temp_df.empty:
        return pd.DataFrame()
    show_day = data_json["Data"]["showday"]
    data_df = temp_df[
        [
            "Id",
            "actualsyi",
            "cycle",
            "fcode",
            "kfr",
            "mui",
            "shortname",
            "syi",
            "zrmui",
            "zrsyi",
        ]
    ]
    data_df.columns = [
        "序号",
        "上一期年化收益率",
        "封闭期",
        "基金代码",
        "申购状态",
        f"{show_day[0]}-万份收益",
        "基金简称",
        f"{show_day[0]}-7日年华",
        f"{show_day[1]}-万份收益",
        f"{show_day[1]}-7日年华",
    ]
    data_df = data_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "上一期年化收益率",
            f"{show_day[0]}-万份收益",
            f"{show_day[0]}-7日年华",
            f"{show_day[1]}-万份收益",
            f"{show_day[1]}-7日年华",
            "封闭期",
            "申购状态",
        ]
    ]
    return data_df


def fund_financial_fund_info_em(symbol: str = "000134") -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-理财型基金收益-历史净值明细
    https://fundf10.eastmoney.com/jjjz_000791.html
    :param symbol: 理财型基金代码, 可以通过 ak.fund_financial_fund_daily_em() 来获取
    :type symbol: str
    :return: 东方财富网站-天天基金网-基金数据-理财型基金收益-历史净值明细
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
    }
    params = {
        "callback": "jQuery18307915911837995662_1588249228826",
        "fundCode": symbol,
        "pageIndex": "1",
        "pageSize": "10000",
        "startDate": "",
        "endDate": "",
        "_": round(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    text_data = r.text
    data_json = demjson.decode(text_data[text_data.find("{") : -1])
    temp_df = pd.DataFrame(data_json["Data"]["LSJZList"])
    temp_df.columns = [
        "净值日期",
        "单位净值",
        "累计净值",
        "_",
        "_",
        "_",
        "日增长率",
        "申购状态",
        "赎回状态",
        "_",
        "_",
        "_",
        "分红送配",
    ]
    temp_df = temp_df[
        [
            "净值日期",
            "单位净值",
            "累计净值",
            "日增长率",
            "申购状态",
            "赎回状态",
            "分红送配",
        ]
    ]
    temp_df.sort_values(["净值日期"], inplace=True, ignore_index=True)
    temp_df["净值日期"] = pd.to_datetime(temp_df["净值日期"]).dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["累计净值"] = pd.to_numeric(temp_df["累计净值"], errors="coerce")
    temp_df["日增长率"] = pd.to_numeric(temp_df["日增长率"], errors="coerce")
    return temp_df


def fund_graded_fund_daily_em() -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-分级基金净值
    https://fund.eastmoney.com/fjjj.html#1_1__0__zdf,desc_1
    :return: 当前交易日的所有分级基金净值
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/Data/Fund_JJJZ_Data.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fjjj.html",
    }
    params = {
        "t": "1",
        "lx": "9",
        "letter": "",
        "gsid": "0",
        "text": "",
        "sort": "zdf,desc",
        "page": "1,10000",
        "dt": "1580914040623",
        "atfc": "",
    }
    res = requests.get(url, params=params, headers=headers)
    text_data = res.text
    data_json = demjson.decode(text_data.strip("var db="))
    temp_df = pd.DataFrame(data_json["datas"])
    show_day = data_json["showday"]
    temp_df.columns = [
        "基金代码",
        "基金简称",
        "-",
        f"{show_day[0]}-单位净值",
        f"{show_day[0]}-累计净值",
        f"{show_day[1]}--单位净值",
        f"{show_day[1]}--累计净值",
        "日增长值",
        "日增长率",
        "市价",
        "折价率",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "手续费",
    ]
    data_df = temp_df[
        [
            "基金代码",
            "基金简称",
            f"{show_day[0]}-单位净值",
            f"{show_day[0]}-累计净值",
            f"{show_day[1]}--单位净值",
            f"{show_day[1]}--累计净值",
            "日增长值",
            "日增长率",
            "市价",
            "折价率",
            "手续费",
        ]
    ]
    return data_df


def fund_graded_fund_info_em(symbol: str = "150232") -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-分级基金净值-历史净值明细
    https://fundf10.eastmoney.com/jjjz_150232.html
    :param symbol: 分级基金代码, 可以通过 ak.fund_money_fund_daily_em() 来获取
    :type symbol: str
    :return: 东方财富网站-天天基金网-基金数据-分级基金净值-历史净值明细
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
    }
    params = {
        "fundCode": symbol,
        "pageIndex": "1",
        "pageSize": "20",
        "startDate": "",
        "endDate": "",
        "_": round(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = math.ceil(int(data_json["TotalCount"]) / 20)
    tqdm = get_tqdm()
    big_list = []
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageIndex": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["Data"]["LSJZList"])
        big_list.append(temp_df)
    big_df = pd.concat(big_list, ignore_index=True)
    big_df.columns = [
        "净值日期",
        "单位净值",
        "累计净值",
        "_",
        "_",
        "_",
        "日增长率",
        "申购状态",
        "赎回状态",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df.sort_values(by=["净值日期"], inplace=True, ignore_index=True)
    big_df = big_df[
        ["净值日期", "单位净值", "累计净值", "日增长率", "申购状态", "赎回状态"]
    ]
    big_df["净值日期"] = pd.to_datetime(big_df["净值日期"], errors="coerce").dt.date
    big_df["单位净值"] = pd.to_numeric(big_df["单位净值"], errors="coerce")
    big_df["累计净值"] = pd.to_numeric(big_df["累计净值"], errors="coerce")
    big_df["日增长率"] = pd.to_numeric(big_df["日增长率"], errors="coerce")
    return big_df


def fund_etf_fund_daily_em() -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-场内交易基金
    https://fund.eastmoney.com/cnjy_dwjz.html
    :return: 当前交易日的所有场内交易基金数据
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/cnjy_dwjz.html"
    r = requests.get(url, headers=headers)
    r.encoding = "gb2312"
    show_day = pd.read_html(StringIO(r.text))[1].iloc[0, 6:10].tolist()
    temp_df = pd.read_html(StringIO(r.text))[1].iloc[1:, 2:]
    temp_df_columns = temp_df.iloc[0, :].tolist()[1:]
    temp_df = temp_df.iloc[1:, 1:]
    temp_df.columns = temp_df_columns
    temp_df["基金简称"] = temp_df["基金简称"].str.strip("基金吧档案")
    temp_df.reset_index(inplace=True, drop=True)
    temp_df.columns = [
        "基金代码",
        "基金简称",
        "类型",
        f"{show_day[0]}-单位净值",
        f"{show_day[0]}-累计净值",
        f"{show_day[2]}-单位净值",
        f"{show_day[2]}-累计净值",
        "增长值",
        "增长率",
        "市价",
        "折价率",
    ]
    return temp_df


def fund_etf_fund_info_em(
    fund: str = "511280",
    start_date: str = "20000101",
    end_date: str = "20500101",
) -> pd.DataFrame:
    """
    东方财富网站-天天基金网-基金数据-场内交易基金-历史净值明细
    https://fundf10.eastmoney.com/jjjz_511280.html
    :param fund: 场内交易基金代码, 可以通过 fund_etf_fund_daily_em 来获取
    :type fund: str
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 结束统计时间
    :type end_date: str
    :return: 东方财富网站-天天基金网-基金数据-场内交易基金-历史净值明细
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{fund}.html",
    }
    params = {
        "fundCode": fund,
        "pageIndex": "1",
        "pageSize": "20",
        "startDate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "endDate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "_": round(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    total_page = math.ceil(data_json["TotalCount"] / 20)
    df_list = []
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageIndex": page})
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["Data"]["LSJZList"])
        df_list.append(temp_df)
    big_df = pd.concat(df_list)
    big_df.columns = [
        "净值日期",
        "单位净值",
        "累计净值",
        "_",
        "_",
        "_",
        "日增长率",
        "申购状态",
        "赎回状态",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        ["净值日期", "单位净值", "累计净值", "日增长率", "申购状态", "赎回状态"]
    ]
    big_df["净值日期"] = pd.to_datetime(big_df["净值日期"], errors="coerce").dt.date
    big_df["单位净值"] = pd.to_numeric(big_df["单位净值"], errors="coerce")
    big_df["累计净值"] = pd.to_numeric(big_df["累计净值"], errors="coerce")
    big_df["日增长率"] = pd.to_numeric(big_df["日增长率"], errors="coerce")
    big_df.sort_values(["净值日期"], inplace=True, ignore_index=True)
    return big_df


def fund_value_estimation_em(symbol: str = "全部") -> pd.DataFrame:
    """
    东方财富网-数据中心-净值估算
    https://fund.eastmoney.com/fundguzhi.html
    :param symbol: choice of {'全部', '股票型', '混合型', '债券型', '指数型', 'QDII', 'ETF联接', 'LOF', '场内交易基金'}
    :type symbol: str
    :return: 近期净值估算数据
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部": 1,
        "股票型": 2,
        "混合型": 3,
        "债券型": 4,
        "指数型": 5,
        "QDII": 6,
        "ETF联接": 7,
        "LOF": 8,
        "场内交易基金": 9,
    }
    url = "https://api.fund.eastmoney.com/FundGuZhi/GetFundGZList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }
    params = {
        "type": symbol_map[symbol],
        "sort": "3",
        "orderType": "desc",
        "canbuy": "0",
        "pageIndex": "1",
        "pageSize": "20000",
        "_": int(time.time() * 1000),
    }
    r = requests.get(url, params=params, headers=headers)
    json_data = r.json()
    temp_df = pd.DataFrame(json_data["Data"]["list"])
    value_day = json_data["Data"]["gzrq"]
    cal_day = json_data["Data"]["gxrq"]
    temp_df.columns = [
        "基金代码",
        "-",
        "-",
        "-",
        "-",
        "-",
        "基金类型",
        "-",
        "-",
        "-",
        "-",
        "估算日期",
        "-",
        "-",
        "-",
        "-",
        "_",
        "-",
        "-",
        "估算偏差",
        f"{cal_day}-估算数据-估算值",
        f"{cal_day}-估算数据-估算增长率",
        f"{cal_day}-公布数据-日增长率",
        f"{value_day}-单位净值",
        f"{cal_day}-公布数据-单位净值",
        "-",
        "基金名称",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "基金代码",
            "基金名称",
            f"{cal_day}-估算数据-估算值",
            f"{cal_day}-估算数据-估算增长率",
            f"{cal_day}-公布数据-单位净值",
            f"{cal_day}-公布数据-日增长率",
            "估算偏差",
            f"{value_day}-单位净值",
        ]
    ]
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.rename(columns={"index": "序号"}, inplace=True)
    return temp_df


def fund_hk_fund_hist_em(
    code: str = "1002200683", symbol: str = "历史净值明细"
) -> pd.DataFrame:
    """
    东方财富网-天天基金网-基金数据-香港基金-历史净值明细(分红送配详情)
    https://overseas.1234567.com.cn/f10/FundJz/968092#FHPS
    :param code: 通过 ak.fund_em_hk_rank() 获取
    :type code: str
    :param symbol: choice of {"历史净值明细", "分红送配详情"}
    :type symbol: str
    :return: 香港基金-历史净值明细(分红送配详情)
    :rtype: pandas.DataFrame
    """
    url = "https://overseas.1234567.com.cn/overseasapi/OpenApiHander.ashx"
    if symbol == "历史净值明细":
        params = {
            "api": "HKFDApi",
            "m": "MethodJZ",
            "hkfcode": f"{code}",
            "action": "2",
            "pageindex": "0",
            "pagesize": "1000",
            "date1": "",
            "date2": "",
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_one_df = pd.DataFrame(data_json["Data"])
        temp_one_df.columns = [
            "_",
            "_",
            "_",
            "净值日期",
            "单位净值",
            "_",
            "日增长值",
            "日增长率",
            "_",
            "单位",
            "_",
        ]
        temp_one_df = temp_one_df[
            [
                "净值日期",
                "单位净值",
                "日增长值",
                "日增长率",
                "单位",
            ]
        ]
    else:
        params = {
            "api": "HKFDApi",
            "m": "MethodJZ",
            "hkfcode": f"{code}",
            "action": "3",
            "pageindex": "0",
            "pagesize": "1000",
            "date1": "",
            "date2": "",
        }
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_one_df = pd.DataFrame(data_json["Data"])
        temp_one_df.columns = [
            "_",
            "_",
            "_",
            "_",
            "_",
            "年份",
            "分红金额",
            "除息日",
            "权益登记日",
            "分红发放日",
            "_",
            "单位",
            "_",
            "_",
        ]
        temp_one_df = temp_one_df[
            [
                "年份",
                "权益登记日",
                "除息日",
                "分红发放日",
                "分红金额",
                "单位",
            ]
        ]
    return temp_one_df


if __name__ == "__main__":
    fund_purchase_em_df = fund_purchase_em()
    print(fund_purchase_em_df)

    fund_name_em_df = fund_name_em()
    print(fund_name_em_df)

    fund_info_index_em_df = fund_info_index_em(symbol="债券指数", indicator="全部")
    print(fund_info_index_em_df)

    fund_open_fund_daily_em_df = fund_open_fund_daily_em()
    print(fund_open_fund_daily_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="710001", indicator="单位净值走势"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="502010", indicator="累计净值走势", period="成立来"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="710001", indicator="累计收益率走势", period="成立来"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="710001", indicator="同类排名走势"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="710001", indicator="同类排名百分比"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="014164", indicator="分红送配详情"
    )
    print(fund_open_fund_info_em_df)
    time.sleep(3)

    fund_open_fund_info_em_df = fund_open_fund_info_em(
        symbol="005561", indicator="拆分详情"
    )
    print(fund_open_fund_info_em_df)

    fund_money_fund_daily_em_df = fund_money_fund_daily_em()
    print(fund_money_fund_daily_em_df)

    fund_money_fund_info_em_df = fund_money_fund_info_em(symbol="000009")
    print(fund_money_fund_info_em_df)

    fund_financial_fund_daily_em_df = fund_financial_fund_daily_em()
    print(fund_financial_fund_daily_em_df)

    fund_financial_fund_info_em_df = fund_financial_fund_info_em(symbol="000134")
    print(fund_financial_fund_info_em_df)

    fund_graded_fund_daily_em_df = fund_graded_fund_daily_em()
    print(fund_graded_fund_daily_em_df)

    fund_graded_fund_info_em_df = fund_graded_fund_info_em(symbol="150232")
    print(fund_graded_fund_info_em_df)

    fund_etf_fund_daily_em_df = fund_etf_fund_daily_em()
    print(fund_etf_fund_daily_em_df)

    fund_etf_fund_info_em_df = fund_etf_fund_info_em(
        fund="511280", start_date="20000101", end_date="20500101"
    )
    print(fund_etf_fund_info_em_df)

    fund_value_estimation_em_df = fund_value_estimation_em(symbol="混合型")
    print(fund_value_estimation_em_df)

    fund_hk_fund_hist_em_df = fund_hk_fund_hist_em(
        code="1002200683", symbol="历史净值明细"
    )
    print(fund_hk_fund_hist_em_df)

    fund_hk_fund_hist_em_df = fund_hk_fund_hist_em(
        code="1002200683", symbol="分红送配详情"
    )
    print(fund_hk_fund_hist_em_df)
