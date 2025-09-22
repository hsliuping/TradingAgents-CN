#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/24 13:00
Desc: 东方财富网-数据中心-开放基金排行
https://fund.eastmoney.com/data/fundranking.html
名词解释
https://help.1234567.com.cn/list_236.html
"""

from datetime import datetime, date

import pandas as pd
import requests

from akshare.utils import demjson


def __one_year_ago(date_str: str) -> date:
    # 将字符串格式的日期转换为date对象
    given_date = date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))

    try:
        # 尝试直接设置为前一年，保持相同的月和日
        one_year_before = given_date.replace(year=given_date.year - 1)
    except ValueError:
        # 如果前一年没有相同的月和日（比如2月29日），则设置为2月28日
        one_year_before = given_date.replace(year=given_date.year - 1, day=28)

    return one_year_before


def fund_open_fund_rank_em(symbol: str = "全部") -> pd.DataFrame:
    """
    东方财富网-数据中心-开放基金排行
    https://fund.eastmoney.com/data/fundranking.html
    :param symbol: choice of {"全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"}
    :type symbol: str
    :return: 开放基金排行
    :rtype: pandas.DataFrame
    """
    current_date = datetime.now().date().isoformat()
    last_date = __one_year_ago(current_date.replace("-", "")).isoformat()
    url = "https://fund.eastmoney.com/data/rankhandler.aspx"
    type_map = {
        "全部": ["all", "1nzf"],
        "股票型": ["gp", "1nzf"],
        "混合型": ["hh", "1nzf"],
        "债券型": ["zq", "1nzf"],
        "指数型": ["zs", "1nzf"],
        "QDII": ["qdii", "1nzf"],
        "LOF": ["lof", "1nzf"],
        "FOF": ["fof", "1nzf"],
    }
    params = {
        "op": "ph",
        "dt": "kf",
        "ft": type_map[symbol][0],
        "rs": "",
        "gs": "0",
        "sc": type_map[symbol][1],
        "st": "desc",
        "sd": last_date,
        "ed": current_date,
        "qdii": "",
        "tabSubtype": ",,,,,",
        "pi": "1",
        "pn": "30000",
        "dx": "1",
        "v": "0.1591891419018292",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fundguzhi.html",
    }
    r = requests.get(url, params=params, headers=headers)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -1])
    temp_df = pd.DataFrame(data_json["datas"])
    temp_df = temp_df.iloc[:, 0].str.split(",", expand=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = list(range(1, len(temp_df) + 1))
    temp_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "_",
        "日期",
        "单位净值",
        "累计净值",
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
        "_",
        "_",
        "自定义",
        "_",
        "手续费",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "日期",
            "单位净值",
            "累计净值",
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
            "自定义",
            "手续费",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["累计净值"] = pd.to_numeric(temp_df["累计净值"], errors="coerce")
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
    temp_df["自定义"] = pd.to_numeric(temp_df["自定义"], errors="coerce")
    return temp_df


def fund_exchange_rank_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-场内交易基金排行
    https://fund.eastmoney.com/data/fbsfundranking.html
    :return: 场内交易基金数据
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/rankhandler.aspx"
    params = {
        "op": "ph",
        "dt": "fb",
        "ft": "ct",
        "rs": "",
        "gs": "0",
        "sc": "1nzf",
        "st": "desc",
        "pi": "1",
        "pn": "30000",
        "v": "0.1591891419018292",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fundguzhi.html",
    }
    r = requests.get(url, params=params, headers=headers)
    text_data = r.text
    json_data = demjson.decode(text_data[text_data.find("{") : -1])
    temp_df = pd.DataFrame(json_data["datas"])
    temp_df = temp_df.iloc[:, 0].str.split(",", expand=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = list(range(1, len(temp_df) + 1))
    temp_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "_",
        "日期",
        "单位净值",
        "累计净值",
        "近1周",
        "近1月",
        "近3月",
        "近6月",
        "近1年",
        "近2年",
        "近3年",
        "今年来",
        "成立来",
        "成立日期",
        "_",
        "_",
        "_",
        "_",
        "_",
        "类型",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "类型",
            "日期",
            "单位净值",
            "累计净值",
            "近1周",
            "近1月",
            "近3月",
            "近6月",
            "近1年",
            "近2年",
            "近3年",
            "今年来",
            "成立来",
            "成立日期",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["成立日期"] = pd.to_datetime(temp_df["成立日期"]).dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["累计净值"] = pd.to_numeric(temp_df["累计净值"], errors="coerce")
    temp_df["近1周"] = pd.to_numeric(temp_df["近1周"], errors="coerce")
    temp_df["近1月"] = pd.to_numeric(temp_df["近1月"], errors="coerce")
    temp_df["近3月"] = pd.to_numeric(temp_df["近3月"], errors="coerce")
    temp_df["近6月"] = pd.to_numeric(temp_df["近6月"], errors="coerce")
    temp_df["近1年"] = pd.to_numeric(temp_df["近1年"], errors="coerce")
    temp_df["近2年"] = pd.to_numeric(temp_df["近2年"], errors="coerce")
    temp_df["近3年"] = pd.to_numeric(temp_df["近3年"], errors="coerce")
    temp_df["今年来"] = pd.to_numeric(temp_df["今年来"], errors="coerce")
    temp_df["成立来"] = pd.to_numeric(temp_df["成立来"], errors="coerce")
    return temp_df


def fund_money_rank_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-货币型基金排行
    https://fund.eastmoney.com/data/hbxfundranking.html
    :return: 货币型基金排行
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/FundRank/GetHbRankList"
    params = {
        "intCompany": "0",
        "MinsgType": "",
        "IsSale": "1",
        "strSortCol": "SYL_1N",
        "orderType": "desc",
        "pageIndex": "1",
        "pageSize": "10000",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fundguzhi.html",
    }
    r = requests.get(url, params=params, headers=headers)
    json_data = r.json()
    temp_df = pd.DataFrame(json_data["Data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = list(range(1, len(temp_df) + 1))
    temp_df.columns = [
        "序号",
        "近1年",
        "近2年",
        "近3年",
        "近5年",
        "_",
        "_",
        "基金代码",
        "基金简称",
        "日期",
        "万份收益",
        "年化收益率7日",
        "_",
        "年化收益率14日",
        "年化收益率28日",
        "近1月",
        "近3月",
        "近6月",
        "今年来",
        "成立来",
        "_",
        "手续费",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "日期",
            "万份收益",
            "年化收益率7日",
            "年化收益率14日",
            "年化收益率28日",
            "近1月",
            "近3月",
            "近6月",
            "近1年",
            "近2年",
            "近3年",
            "近5年",
            "今年来",
            "成立来",
            "手续费",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["万份收益"] = pd.to_numeric(temp_df["万份收益"], errors="coerce")
    temp_df["年化收益率7日"] = pd.to_numeric(temp_df["年化收益率7日"], errors="coerce")
    temp_df["年化收益率14日"] = pd.to_numeric(
        temp_df["年化收益率14日"], errors="coerce"
    )
    temp_df["年化收益率28日"] = pd.to_numeric(
        temp_df["年化收益率28日"], errors="coerce"
    )
    temp_df["近1月"] = pd.to_numeric(temp_df["近1月"], errors="coerce")
    temp_df["近3月"] = pd.to_numeric(temp_df["近3月"], errors="coerce")
    temp_df["近6月"] = pd.to_numeric(temp_df["近6月"], errors="coerce")
    temp_df["近1年"] = pd.to_numeric(temp_df["近1年"], errors="coerce")
    temp_df["近2年"] = pd.to_numeric(temp_df["近2年"], errors="coerce")
    temp_df["近3年"] = pd.to_numeric(temp_df["近3年"], errors="coerce")
    temp_df["近5年"] = pd.to_numeric(temp_df["近5年"], errors="coerce")
    temp_df["今年来"] = pd.to_numeric(temp_df["今年来"], errors="coerce")
    temp_df["成立来"] = pd.to_numeric(temp_df["成立来"], errors="coerce")
    return temp_df


def fund_lcx_rank_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-理财基金排行
    # 该接口暂时没有数据
    https://fund.eastmoney.com/data/lcxfundranking.html#t;c0;r;sSYL_Z;ddesc;pn50;f;os1;
    :return: 理财基金排行
    :rtype: pandas.DataFrame
    """
    url = "https://api.fund.eastmoney.com/FundRank/GetLcRankList"
    params = {
        "intCompany": "0",
        "MinsgType": "undefined",
        "IsSale": "1",
        "strSortCol": "SYL_Z",
        "orderType": "desc",
        "pageIndex": "1",
        "pageSize": "50",
        "FBQ": "",
        "callback": "jQuery18303264654966943197_1603867158043",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fundguzhi.html",
    }
    r = requests.get(url, params=params, headers=headers)
    try:
        data_json = r.json()
    except:  # noqa: E722
        return pd.DataFrame()
    temp_df = pd.DataFrame(data_json["Data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = list(range(1, len(temp_df) + 1))
    temp_df.columns = [
        "序号",
        "近1周",
        "基金代码",
        "基金简称",
        "日期",
        "万份收益",
        "年化收益率-7日",
        "_",
        "年化收益率-14日",
        "年化收益率-28日",
        "近1月",
        "近3月",
        "近6月",
        "今年来",
        "成立来",
        "可购买",
        "手续费",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "日期",
            "万份收益",
            "年化收益率-7日",
            "年化收益率-14日",
            "年化收益率-28日",
            "近1周",
            "近1月",
            "近3月",
            "近6月",
            "今年来",
            "成立来",
            "可购买",
            "手续费",
        ]
    ]
    return temp_df


def fund_hk_rank_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-香港基金排行
    https://overseas.1234567.com.cn/FundList
    :return: 香港基金排行
    :rtype: pandas.DataFrame
    """
    format_date = datetime.now().date().isoformat()
    url = "https://overseas.1234567.com.cn/overseasapi/OpenApiHander.ashx"
    params = {
        "api": "HKFDApi",
        "m": "MethodFundList",
        "action": "1",
        "pageindex": "0",
        "pagesize": "5000",
        "dy": "1",
        "date1": format_date,
        "date2": format_date,
        "sortfield": "Y",
        "sorttype": "-1",
        "isbuy": "0",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/81.0.4044.138 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/fundguzhi.html",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["Data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = list(range(1, len(temp_df) + 1))
    temp_df.columns = [
        "序号",
        "_",
        "香港基金代码",
        "基金代码",
        "_",
        "基金简称",
        "可购买",
        "日期",
        "单位净值",
        "日增长率",
        "_",
        "近1周",
        "近1月",
        "近3月",
        "近6月",
        "近1年",
        "近2年",
        "近3年",
        "今年来",
        "成立来",
        "币种",
    ]
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "币种",
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
            "可购买",
            "香港基金代码",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
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
    temp_df["成立来"] = pd.to_numeric(temp_df["成立来"], errors="coerce")
    temp_df["可购买"] = temp_df["可购买"].map(
        lambda x: "可购买" if x == "1" else "不可购买"
    )
    return temp_df


if __name__ == "__main__":
    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="全部")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="股票型")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="混合型")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="债券型")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="指数型")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="QDII")
    print(fund_open_fund_rank_em_df)

    fund_open_fund_rank_em_df = fund_open_fund_rank_em(symbol="FOF")
    print(fund_open_fund_rank_em_df)

    fund_exchange_rank_em_df = fund_exchange_rank_em()
    print(fund_exchange_rank_em_df)

    fund_money_rank_em_df = fund_money_rank_em()
    print(fund_money_rank_em_df)

    fund_lcx_rank_em_df = fund_lcx_rank_em()
    print(fund_lcx_rank_em_df)

    fund_hk_rank_em_df = fund_hk_rank_em()
    print(fund_hk_rank_em_df)
