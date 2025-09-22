#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/16 9:00
Desc:中国银行间市场交易商协会(https://www.nafmii.org.cn/)
孔雀开屏(http://zhuce.nafmii.org.cn/fans/publicQuery/manager)的债券基本信息数据
"""

import pandas as pd
import requests


def bond_debt_nafmii(page: str = "1") -> pd.DataFrame:
    """
    中国银行间市场交易商协会-非金融企业债务融资工具注册信息系统
    http://zhuce.nafmii.org.cn/fans/publicQuery/manager
    :param page: 输入数字页码
    :type page: int
    :return: 指定 sector 和 indicator 的数据
    :rtype: pandas.DataFrame
    """
    url = "http://zhuce.nafmii.org.cn/fans/publicQuery/releFileProjDataGrid"
    payload = {
        "regFileName": "",
        "itemType": "",
        "startTime": "",
        "endTime": "",
        "entityName": "",
        "leadManager": "",
        "regPrdtType": "",
        "page": page,
        "rows": 50,
    }
    payload.update({"page": page})
    r = requests.post(url, data=payload)
    data_json = r.json()  # 数据类型为 json 格式
    temp_df = pd.DataFrame(data_json["rows"])
    temp_df.rename(
        columns={
            "firstIssueAmount": "金额",
            "isReg": "注册或备案",
            "regFileName": "债券名称",
            "regNoticeNo": "注册通知书文号",
            "regPrdtType": "品种",
            "releaseTime": "更新日期",
            "projPhase": "项目状态",
        },
        inplace=True,
    )
    if "注册通知书文号" not in temp_df.columns:
        temp_df["注册通知书文号"] = pd.NA
    temp_df = temp_df[
        [
            "债券名称",
            "品种",
            "注册或备案",
            "金额",
            "注册通知书文号",
            "更新日期",
            "项目状态",
        ]
    ]
    temp_df["金额"] = pd.to_numeric(temp_df["金额"], errors="coerce")
    temp_df["更新日期"] = pd.to_datetime(temp_df["更新日期"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    bond_debt_nafmii_df = bond_debt_nafmii(page="1")
    print(bond_debt_nafmii_df)
