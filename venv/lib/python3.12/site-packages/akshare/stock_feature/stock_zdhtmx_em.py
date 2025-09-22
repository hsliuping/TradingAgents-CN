#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/11 20:32
Desc: 东方财富网-数据中心-重大合同-重大合同明细
https://data.eastmoney.com/zdht/mx.html
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def stock_zdhtmx_em(
    start_date: str = "20200819", end_date: str = "20230819"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-重大合同-重大合同明细
    https://data.eastmoney.com/zdht/mx.html
    :return: 股东大会
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "DIM_RDATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "columns": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "reportName": "RPTA_WEB_ZDHT_LIST",
        "filter": f"""(DIM_RDATE>='{"-".join([start_date[:4], start_date[4:6], start_date[6:]])}')
        (DIM_RDATE<='{"-".join([end_date[:4], end_date[4:6], end_date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.rename(
        columns={
            "index": "序号",
            "DIM_SCODE": "-",
            "CONTENTS": "-",
            "CONTRACTNAME": "合同名称",
            "CONTRACTTYPE": "-",
            "COUNTERPARTY": "其他签署方",
            "COUNTERPARTYREL": "-",
            "ISABOLISHED": "-",
            "DIM_RDATE": "公告日期",
            "REMARK": "-",
            "SIGNATORY": "签署主体",
            "SIGNATORYREL": "与上市公司关系",
            "SIGNDATE": "签署日期",
            "SIGNEFFECT": "-",
            "UPDATEDATE": "-",
            "YEAR": "-",
            "AMOUNTS": "合同金额",
            "SECURITYCODE": "股票代码",
            "SECURITYSHORTNAME": "股票简称",
            "CONTRACTTYPENAME": "合同类型",
            "SIGNATORYRELNAME": "签署主体-与上市公司关系",
            "COUNTERPARTYRELNAME": "其他签署方-与上市公司关系",
            "SNDYYSR": "上年度营业收入",
            "OPERATEREVE": "最新财务报表的营业收入",
            "RCHANGE1DC": "-",
            "RCHANGE20DC": "-",
            "ZSNDYYSRBL": "占上年度营业收入比例",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "签署主体",
            "签署主体-与上市公司关系",
            "其他签署方",
            "其他签署方-与上市公司关系",
            "合同类型",
            "合同名称",
            "合同金额",
            "上年度营业收入",
            "占上年度营业收入比例",
            "最新财务报表的营业收入",
            "签署日期",
            "公告日期",
        ]
    ]
    big_df["签署日期"] = pd.to_datetime(big_df["签署日期"], errors="coerce").dt.date
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["合同金额"] = pd.to_numeric(big_df["合同金额"], errors="coerce")
    big_df["上年度营业收入"] = pd.to_numeric(big_df["上年度营业收入"], errors="coerce")
    big_df["占上年度营业收入比例"] = pd.to_numeric(
        big_df["占上年度营业收入比例"], errors="coerce"
    )
    big_df["最新财务报表的营业收入"] = pd.to_numeric(
        big_df["最新财务报表的营业收入"], errors="coerce"
    )
    return big_df


if __name__ == "__main__":
    stock_zdhtmx_em_df = stock_zdhtmx_em(start_date="20220819", end_date="20230819")
    print(stock_zdhtmx_em_df)
