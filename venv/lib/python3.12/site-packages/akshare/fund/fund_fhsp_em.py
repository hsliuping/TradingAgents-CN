# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2022/12/13 14:18
Desc: 天天基金网-基金数据-分红送配
https://fund.eastmoney.com/data/fundfenhong.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def fund_fh_em() -> pd.DataFrame:
    """
    天天基金网-基金数据-分红送配-基金分红
    https://fund.eastmoney.com/data/fundfenhong.html#DJR,desc,1,,,
    :return: 基金分红
    :rtype: pandas.DataFrame
    """
    url = "http://fund.eastmoney.com/Data/funddataIndex_Interface.aspx"
    params = {
        "dt": "8",
        "page": "1",
        "rank": "BZDM",
        "sort": "asc",
        "gs": "",
        "ftype": "",
        "year": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    total_page = eval(data_text[data_text.find("=") + 1 : data_text.find(";")])[0]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params)
        data_text = r.text
        temp_list = eval(
            data_text[data_text.find("[[") : data_text.find(";var jjfh_jjgs")]
        )
        temp_df = pd.DataFrame(temp_list)
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "权益登记日",
        "除息日期",
        "分红",
        "分红发放日",
        "-",
    ]
    big_df = big_df[
        ["序号", "基金代码", "基金简称", "权益登记日", "除息日期", "分红", "分红发放日"]
    ]
    big_df["权益登记日"] = pd.to_datetime(big_df["权益登记日"]).dt.date
    big_df["除息日期"] = pd.to_datetime(big_df["除息日期"]).dt.date
    big_df["分红发放日"] = pd.to_datetime(big_df["分红发放日"]).dt.date
    big_df["分红"] = pd.to_numeric(big_df["分红"])
    return big_df


def fund_cf_em() -> pd.DataFrame:
    """
    天天基金网-基金数据-分红送配-基金拆分
    https://fund.eastmoney.com/data/fundchaifen.html#FSRQ,desc,1,,,
    :return: 基金拆分
    :rtype: pandas.DataFrame
    """
    url = "http://fund.eastmoney.com/Data/funddataIndex_Interface.aspx"
    params = {
        "dt": "9",
        "page": "1",
        "rank": "FSRQ",
        "sort": "desc",
        "gs": "",
        "ftype": "",
        "year": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    total_page = eval(data_text[data_text.find("=") + 1 : data_text.find(";")])[0]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params)
        data_text = r.text
        temp_str = data_text[data_text.find("[[") : data_text.find(";var jjcf_jjgs")]
        if temp_str:
            temp_list = eval(temp_str)
            temp_df = pd.DataFrame(temp_list)
            big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df.loc[:, "index"] = big_df["index"] + 1
    big_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "拆分折算日",
        "拆分类型",
        "拆分折算",
        "-",
    ]
    big_df = big_df[
        ["序号", "基金代码", "基金简称", "拆分折算日", "拆分类型", "拆分折算"]
    ]
    big_df["拆分折算日"] = pd.to_datetime(big_df["拆分折算日"]).dt.date
    big_df["拆分折算"] = pd.to_numeric(big_df["拆分折算"], errors="coerce")
    return big_df


def fund_fh_rank_em() -> pd.DataFrame:
    """
    天天基金网-基金数据-分红送配-基金分红排行
    https://fund.eastmoney.com/data/fundleijifenhong.html
    :return: 基金分红排行
    :rtype: pandas.DataFrame
    """
    url = "http://fund.eastmoney.com/Data/funddataIndex_Interface.aspx"
    params = {
        "dt": "10",
        "page": "1",
        "rank": "FHFCZ",
        "sort": "desc",
        "gs": "",
        "ftype": "",
        "year": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    total_page = eval(data_text[data_text.find("=") + 1 : data_text.find(";")])[0]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params)
        data_text = r.text
        temp_list = eval(
            data_text[data_text.find("[[") : data_text.find(";var fhph_jjgs")]
        )
        temp_df = pd.DataFrame(temp_list)
        big_df = pd.concat([big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df.loc[:, "index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "基金代码",
        "基金简称",
        "累计分红",
        "累计次数",
        "成立日期",
        "-",
    ]
    big_df = big_df[
        ["序号", "基金代码", "基金简称", "累计分红", "累计次数", "成立日期"]
    ]
    big_df["成立日期"] = pd.to_datetime(big_df["成立日期"]).dt.date
    big_df["累计分红"] = pd.to_numeric(big_df["累计分红"], errors="coerce")
    big_df["累计次数"] = pd.to_numeric(big_df["累计次数"], errors="coerce")
    return big_df


if __name__ == "__main__":
    fund_fh_em_df = fund_fh_em()
    print(fund_fh_em_df)

    fund_cf_em_df = fund_cf_em()
    print(fund_cf_em_df)

    fund_fh_rank_em_df = fund_fh_rank_em()
    print(fund_fh_rank_em_df)
