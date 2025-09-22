#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/22 20:30
Desc: 期货-期转现-交割
"""

from io import StringIO, BytesIO

import pandas as pd
import requests


def futures_to_spot_shfe(date: str = "202312") -> pd.DataFrame:
    """
    上海期货交易所-期转现
    https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx
    1、铜、铜(BC)、铝、锌、铅、镍、锡、螺纹钢、线材、热轧卷板、天然橡胶、20号胶、低硫燃料油、燃料油、石油沥青、纸浆、不锈钢的数量单位为：吨；黄金的数量单位为：克；白银的数量单位为：千克；原油的数量单位为：桶。
    2、交割量、期转现量为单向计算。
    :param date: 年月
    :type date: str
    :return: 上海期货交易所期转现
    :rtype: pandas.DataFrame
    """
    url = f"https://tsite.shfe.com.cn/data/instrument/ExchangeDelivery{date}.dat"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.4896.127 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["ExchangeDelivery"])
    temp_df.columns = [
        "_",
        "日期",
        "交割量",
        "_",
        "期转现量",
        "合约",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "日期",
            "合约",
            "交割量",
            "期转现量",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["交割量"] = pd.to_numeric(temp_df["交割量"], errors="coerce")
    temp_df["期转现量"] = pd.to_numeric(temp_df["期转现量"], errors="coerce")
    return temp_df


def futures_delivery_dce(date: str = "202312") -> pd.DataFrame:
    """
    大连商品交易所-交割统计
    http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/jgtj/jgsj/index.html
    :param date: 交割日期
    :type date: str
    :return: 大连商品交易所-交割统计
    :rtype: pandas.DataFrame
    """
    url = "http://www.dce.com.cn/publicweb/quotesdata/delivery.html"
    params = {
        "deliveryQuotes.variety": "all",
        "year": "",
        "month": "",
        "deliveryQuotes.begin_month": date,
        "deliveryQuotes.end_month": str(int(date) + 1),
    }
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    }
    r = requests.post(url, params=params, headers=headers)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["交割日期"] = (
        temp_df["交割日期"].astype(str).str.split(".", expand=True).iloc[:, 0]
    )
    temp_df = temp_df[~temp_df["品种"].str.contains("小计|总计")]
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["交割日期"] = pd.to_datetime(temp_df["交割日期"], errors="coerce").dt.date
    temp_df["交割量"] = pd.to_numeric(temp_df["交割量"], errors="coerce")
    temp_df["交割金额"] = pd.to_numeric(temp_df["交割金额"], errors="coerce")
    return temp_df


def futures_to_spot_dce(date: str = "202312") -> pd.DataFrame:
    """
    大连商品交易所-期转现
    http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/jgtj/qzxcx/index.html
    :param date: 期转现日期
    :type date: str
    :return: 大连商品交易所-期转现
    :rtype: pandas.DataFrame
    """
    url = "http://www.dce.com.cn/publicweb/quotesdata/ftsDeal.html"
    params = {
        "ftsDealQuotes.variety": "all",
        "year": "",
        "month": "",
        "ftsDealQuotes.begin_month": date,
        "ftsDealQuotes.end_month": date,
    }
    r = requests.post(url, params=params)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["期转现发生日期"] = (
        temp_df["期转现发生日期"].astype(str).str.split(".", expand=True).iloc[:, 0]
    )
    temp_df = temp_df[~temp_df["合约代码"].str.contains("小计|总计")]
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["期转现发生日期"] = pd.to_datetime(
        temp_df["期转现发生日期"], errors="coerce"
    ).dt.date
    temp_df["期转现数量"] = pd.to_numeric(temp_df["期转现数量"], errors="coerce")
    return temp_df


def futures_delivery_match_dce(symbol: str = "a") -> pd.DataFrame:
    """
    大连商品交易所-交割配对表
    http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/jgtj/jgsj/index.html
    :param symbol: 交割品种
    :type symbol: str
    :return: 大连商品交易所-交割配对表
    :rtype: pandas.DataFrame
    """
    url = "http://www.dce.com.cn/publicweb/quotesdata/deliveryMatch.html"
    params = {
        "deliveryMatchQuotes.variety": symbol,
        "contract.contract_id": "all",
        "contract.variety_id": symbol,
    }
    r = requests.post(url, params=params)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["配对日期"] = (
        temp_df["配对日期"].astype(str).str.split(".", expand=True).iloc[:, 0]
    )
    temp_df = temp_df.iloc[:-1, :]
    temp_df["配对日期"] = pd.to_datetime(temp_df["配对日期"], errors="coerce").dt.date
    temp_df["配对手数"] = pd.to_numeric(temp_df["配对手数"], errors="coerce")
    temp_df["交割结算价"] = pd.to_numeric(temp_df["交割结算价"], errors="coerce")
    return temp_df


def futures_to_spot_czce(date: str = "20231228") -> pd.DataFrame:
    """
    郑州商品交易所-期转现统计
    http://www.czce.com.cn/cn/jysj/qzxtj/H770311index_1.htm
    :param date: 年月日
    :type date: str
    :return: 郑州商品交易所-期转现统计
    :rtype: pandas.DataFrame
    """
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataTrdtrades.xls"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "www.czce.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://www.czce.com.cn/",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    r.encoding = "utf-8"
    temp_df = pd.read_excel(BytesIO(r.content), skiprows=1)

    temp_df.columns = [
        "合约代码",
        "合约数量",
    ]
    temp_df = temp_df[
        [
            "合约代码",
            "合约数量",
        ]
    ]
    temp_df["合约数量"] = temp_df["合约数量"].astype(str).str.replace(",", "")
    temp_df["合约数量"] = pd.to_numeric(temp_df["合约数量"], errors="coerce")
    temp_df = temp_df[~temp_df["合约代码"].str.contains("小计|合计")]
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def futures_delivery_match_czce(date: str = "20210106") -> pd.DataFrame:
    """
    郑州商品交易所-交割配对
    http://www.czce.com.cn/cn/jysj/jgpd/H770308index_1.htm
    :param date: 年月日
    :type date: str
    :return: 郑州商品交易所-交割配对
    :rtype: pandas.DataFrame
    """
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataDelsettle.xls"
    r = requests.get(url)
    r.encoding = "utf-8"
    temp_df = pd.read_excel(BytesIO(r.content), skiprows=0)
    index_flag = temp_df[temp_df.iloc[:, 0].str.contains("配对日期")].index.values
    big_df = pd.DataFrame()
    for i, item in enumerate(index_flag):
        try:
            temp_inner_df = temp_df[index_flag[i] + 1 : index_flag[i + 1]]
        except:  # noqa: E722
            temp_inner_df = temp_df[index_flag[i] + 1 :]
        temp_inner_df.columns = temp_inner_df.iloc[0, :]
        temp_inner_df = temp_inner_df.iloc[1:-1, :]
        temp_inner_df.reset_index(drop=True, inplace=True)
        date_contract_str = (
            temp_df[temp_df.iloc[:, 0].str.contains("配对日期")].iloc[:, 0].values[i]
        )
        inner_date = date_contract_str.split("：")[1].split(" ")[0]
        symbol = date_contract_str.split("：")[-1]
        temp_inner_df["配对日期"] = inner_date
        temp_inner_df["合约代码"] = symbol
        big_df = pd.concat([big_df, temp_inner_df], ignore_index=True)

    big_df.columns = [
        "卖方会员",
        "卖方会员-会员简称",
        "买方会员",
        "买方会员-会员简称",
        "交割量",
        "配对日期",
        "合约代码",
    ]
    big_df["交割量"] = big_df["交割量"].str.replace(",", "")
    big_df["交割量"] = pd.to_numeric(big_df["交割量"])
    return big_df


def futures_delivery_czce(date: str = "20210112") -> pd.DataFrame:
    """
    郑州商品交易所-月度交割查询
    http://www.czce.com.cn/cn/jysj/ydjgcx/H770316index_1.htm
    :param date: 年月日
    :type date: str
    :return: 郑州商品交易所-月度交割查询
    :rtype: pandas.DataFrame
    """
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataSettlematched.xls"
    r = requests.get(url)
    r.encoding = "utf-8"
    temp_df = pd.read_excel(BytesIO(r.content), skiprows=1)
    temp_df.columns = [
        "品种",
        "交割数量",
        "交割额",
    ]
    temp_df["交割数量"] = temp_df["交割数量"].str.replace(",", "")
    temp_df["交割额"] = temp_df["交割额"].str.replace(",", "")

    temp_df["交割数量"] = pd.to_numeric(temp_df["交割数量"])
    temp_df["交割额"] = pd.to_numeric(temp_df["交割额"])
    return temp_df


def futures_delivery_shfe(date: str = "202312") -> pd.DataFrame:
    """
    上海期货交易所-交割情况表
    https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx
    注意: 日期 -> 月度统计 -> 下拉到交割情况表
    :param date: 年月日
    :type date: str
    :return: 上海期货交易所-交割情况表
    :rtype: pandas.DataFrame
    """
    url = f"https://tsite.shfe.com.cn/data/dailydata/{date}monthvarietystatistics.dat"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.4896.127 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    r.encoding = "utf-8"
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["o_curdelivery"])
    temp_df.columns = [
        "品种",
        "品种代码",
        "_",
        "交割量-本月",
        "交割量-比重",
        "交割量-本年累计",
        "交割量-累计同比",
    ]
    temp_df = temp_df[
        [
            "品种",
            "交割量-本月",
            "交割量-比重",
            "交割量-本年累计",
            "交割量-累计同比",
        ]
    ]
    temp_df["交割量-本月"] = pd.to_numeric(temp_df["交割量-本月"], errors="coerce")
    temp_df["交割量-比重"] = pd.to_numeric(temp_df["交割量-比重"], errors="coerce")
    temp_df["交割量-本年累计"] = pd.to_numeric(
        temp_df["交割量-本年累计"], errors="coerce"
    )
    temp_df["交割量-累计同比"] = pd.to_numeric(
        temp_df["交割量-累计同比"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    futures_to_spot_dce_df = futures_to_spot_dce(date="202312")
    print(futures_to_spot_dce_df)

    futures_to_spot_shfe_df = futures_to_spot_shfe(date="202312")
    print(futures_to_spot_shfe_df)

    futures_to_spot_czce_df = futures_to_spot_czce(date="20210112")
    print(futures_to_spot_czce_df)

    futures_delivery_dce_df = futures_delivery_dce(date="202101")
    print(futures_delivery_dce_df)

    futures_delivery_monthly_czce_df = futures_delivery_czce(date="20210112")
    print(futures_delivery_monthly_czce_df)

    futures_delivery_shfe_df = futures_delivery_shfe(date="202312")
    print(futures_delivery_shfe_df)

    futures_delivery_match_dce_df = futures_delivery_match_dce(symbol="a")
    print(futures_delivery_match_dce_df)

    futures_delivery_match_czce_df = futures_delivery_match_czce(date="20210106")
    print(futures_delivery_match_czce_df)
