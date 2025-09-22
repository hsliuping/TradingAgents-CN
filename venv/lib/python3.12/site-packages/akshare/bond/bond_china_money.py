#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/27 16:00
Desc: 收盘收益率曲线历史数据
https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1
"""

from functools import lru_cache

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def __bond_register_service() -> requests.Session:
    """
    将服务注册到网站中，则该 IP 在 24 小时内可以直接访问
    https://www.chinamoney.com.cn
    :return: 访问过的 Session
    :rtype: requests.Session
    """
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
    }
    session.get(
        url="https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1",
        headers=headers,
    )
    cookies_dict = session.cookies.get_dict()
    cookies_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
    # 此处需要通过未访问的游览器，首次打开
    # https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1
    # 页面进行人工获取
    data = {"key": "TThwSjc2NWkzV0VSOVRzOA=="}
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "22",
        "Cookie": cookies_str,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.chinamoney.com.cn",
        "Origin": "https://www.chinamoney.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    session.post(
        url="https://www.chinamoney.com.cn/dqs/rest/cm-u-rbt/apply",
        data=data,
        headers=headers,
    )

    # 20231127 新增部分 https://github.com/akfamily/akshare/issues/4299
    cookies_dict = session.cookies.get_dict()
    cookies_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
    headers = {
        "Accept": "application/json, text/javascript, /; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en",
        "Connection": "keep-alive",
        "Content-Length": "0",
        "Cookie": cookies_str,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.chinamoney.com.cn",
        "Origin": "https://www.chinamoney.com.cn",
        "Referer": "https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    session.post(
        url="https://www.chinamoney.com.cn/lss/rest/cm-s-account/getSessionUser",
        headers=headers,
    )
    return session


@lru_cache()
def bond_china_close_return_map() -> pd.DataFrame:
    """
    收盘收益率曲线历史数据
    https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1
    :return: 收盘收益率曲线历史数据
    :rtype: pandas.DataFrame
    """
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "0",
        "Host": "www.chinamoney.com.cn",
        "Origin": "https://www.chinamoney.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/ClsYldCurvCurvGO"
    try:
        r = requests.get(url, headers=headers)
        data_json = r.json()
    except:  # noqa: E722
        session = __bond_register_service()
        r = session.get(url, headers=headers)
        data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    return temp_df


def bond_china_close_return(
    symbol: str = "国债",
    period: str = "1",
    start_date: str = "20231101",
    end_date: str = "20231101",
) -> pd.DataFrame:
    """
    收盘收益率曲线历史数据
    https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC000&reference=1
    :param symbol: 需要获取的指标
    :type period: choice of {'0.1', '0.5', '1'}
    :param period: 期限间隔
    :type symbol: str
    :param start_date: 开始日期, 结束日期和开始日期不要超过 1 个月
    :type start_date: str
    :param end_date: 结束日期, 结束日期和开始日期不要超过 1 个月
    :type end_date: str
    :return: 收盘收益率曲线历史数据
    :rtype: pandas.DataFrame
    """
    name_code_df = bond_china_close_return_map()
    symbol_code = name_code_df[name_code_df["cnLabel"] == symbol]["value"].values[0]
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/ClsYldCurvHis"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
    }
    params = {
        "lang": "CN",
        "reference": "1,2,3",
        "bondType": symbol_code,
        "startDate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "endDate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "termId": period,
        "pageNum": "1",
        "pageSize": "50",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    del temp_df["newDateValue"]
    temp_df.columns = [
        "日期",
        "期限",
        "到期收益率",
        "即期收益率",
        "远期收益率",
    ]
    temp_df = temp_df[
        [
            "日期",
            "期限",
            "到期收益率",
            "即期收益率",
            "远期收益率",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["期限"] = pd.to_numeric(temp_df["期限"], errors="coerce")
    temp_df["到期收益率"] = pd.to_numeric(temp_df["到期收益率"], errors="coerce")
    temp_df["即期收益率"] = pd.to_numeric(temp_df["即期收益率"], errors="coerce")
    temp_df["远期收益率"] = pd.to_numeric(temp_df["远期收益率"], errors="coerce")
    return temp_df


def macro_china_swap_rate(
    start_date: str = "20231101", end_date: str = "20231204"
) -> pd.DataFrame:
    """
    FR007 利率互换曲线历史数据; 只能获取近一年的数据
    https://www.chinamoney.com.cn/chinese/bkcurvfxhis/?cfgItemType=72&curveType=FR007
    :param start_date: 开始日期, 开始和结束日期不得超过一个月
    :type start_date: str
    :param end_date: 结束日期, 开始和结束日期不得超过一个月
    :type end_date: str
    :return: FR007利率互换曲线历史数据
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/IfccHis"
    params = {
        "cfgItemType": "72",
        "interestRateType": "0",
        "startDate": start_date,
        "endDate": end_date,
        "bidAskType": "",
        "lang": "CN",
        "quoteTime": "全部",
        "pageSize": "5000",
        "pageNum": "1",
    }
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "0",
        "Host": "www.chinamoney.com.cn",
        "Origin": "https://www.chinamoney.com.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.chinamoney.com.cn/chinese/bkcurvfxhis/?cfgItemType=72&curveType=FR007",
        "sec-ch-ua": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, data=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "日期",
        "_",
        "_",
        "时刻",
        "_",
        "_",
        "_",
        "_",
        "_",
        "价格类型",
        "_",
        "曲线名称",
        "_",
        "_",
        "_",
        "_",
        "data",
    ]
    price_df = pd.DataFrame([item for item in temp_df["data"]])
    price_df.columns = [
        "1M",
        "3M",
        "6M",
        "9M",
        "1Y",
        "2Y",
        "3Y",
        "4Y",
        "5Y",
        "7Y",
        "10Y",
    ]
    big_df = pd.concat(objs=[temp_df, price_df], axis=1)
    big_df = big_df[
        [
            "日期",
            "曲线名称",
            "时刻",
            "价格类型",
            "1M",
            "3M",
            "6M",
            "9M",
            "1Y",
            "2Y",
            "3Y",
            "4Y",
            "5Y",
            "7Y",
            "10Y",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["1M"] = pd.to_numeric(big_df["1M"], errors="coerce")
    big_df["3M"] = pd.to_numeric(big_df["3M"], errors="coerce")
    big_df["6M"] = pd.to_numeric(big_df["6M"], errors="coerce")
    big_df["9M"] = pd.to_numeric(big_df["9M"], errors="coerce")
    big_df["1Y"] = pd.to_numeric(big_df["1Y"], errors="coerce")
    big_df["2Y"] = pd.to_numeric(big_df["2Y"], errors="coerce")
    big_df["3Y"] = pd.to_numeric(big_df["3Y"], errors="coerce")
    big_df["4Y"] = pd.to_numeric(big_df["4Y"], errors="coerce")
    big_df["5Y"] = pd.to_numeric(big_df["5Y"], errors="coerce")
    big_df["7Y"] = pd.to_numeric(big_df["7Y"], errors="coerce")
    big_df["10Y"] = pd.to_numeric(big_df["10Y"], errors="coerce")
    big_df.sort_values(["日期"], inplace=True, ignore_index=True)
    return big_df


def macro_china_bond_public() -> pd.DataFrame:
    """
    中国-债券信息披露-债券发行
    https://www.chinamoney.com.cn/chinese/xzjfx/
    :return: 债券发行
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bond-an/bnBondEmit"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
    }
    payload = {
        "enty": "",
        "bondType": "",
        "bondNameCode": "",
        "leadUnderwriter": "",
        "pageNo": "1",
        "pageSize": "10",
        "limit": "1",
    }
    r = requests.post(url, data=payload, headers=headers)
    data_json = r.json()
    total_page = int(data_json["data"]["pageTotalSize"]) + 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page), leave=False):
        payload.update({"pageNo": page})
        r = requests.post(url, data=payload, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["records"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "债券全称",
        "债券类型",
        "-",
        "发行日期",
        "-",
        "计息方式",
        "-",
        "债券期限",
        "-",
        "债券评级",
        "-",
        "价格",
        "计划发行量",
    ]
    big_df = big_df[
        [
            "债券全称",
            "债券类型",
            "发行日期",
            "计息方式",
            "价格",
            "债券期限",
            "计划发行量",
            "债券评级",
        ]
    ]
    big_df["价格"] = pd.to_numeric(big_df["价格"], errors="coerce")
    big_df["计划发行量"] = pd.to_numeric(big_df["计划发行量"], errors="coerce")
    return big_df


if __name__ == "__main__":
    bond_china_close_return_df = bond_china_close_return(
        symbol="同业存单(AAA)", period="1", start_date="20240607", end_date="20240607"
    )
    print(bond_china_close_return_df)

    macro_china_swap_rate_df = macro_china_swap_rate(
        start_date="20240501", end_date="20240531"
    )
    print(macro_china_swap_rate_df)

    macro_china_bond_public_df = macro_china_bond_public()
    print(macro_china_bond_public_df)
