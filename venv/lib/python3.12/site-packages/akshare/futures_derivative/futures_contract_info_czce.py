#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/11 16:30
Desc: 郑州商品交易所-交易数据-参考数据
http://www.czce.com.cn/cn/jysj/cksj/H770322index_1.htm
"""

import xml.etree.ElementTree as ET

import pandas as pd
import requests


def futures_contract_info_czce(date: str = "20240228") -> pd.DataFrame:
    """
    郑州商品交易所-交易数据-参考数据
    http://www.czce.com.cn/cn/jysj/cksj/H770322index_1.htm
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/84.0.4147.89 Safari/537.36",
        "Host": "www.czce.com.cn",
    }
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date[:4]}/{date}/FutureDataReferenceData.xml"
    r = requests.get(url, headers=headers)
    xml_data = r.text
    # 解析 XML
    tree = ET.ElementTree(ET.fromstring(xml_data))
    root = tree.getroot()
    # 获取所有的记录
    records = root.findall(".//Contract")
    # 解析数据并填充到列表中
    data = []
    for record in records:
        # 对于每个记录，创建一个字典
        row_data = {}
        for field in record:
            row_data[field.tag] = field.text
        # 将字典添加到数据列表中
        data.append(row_data)

    temp_df = pd.DataFrame(data)
    temp_df.rename(
        columns={
            "Name": "产品名称",
            "CtrCd": "合约代码",
            "PrdCd": "产品代码",
            "PrdTp": "产品类型",
            "ExchCd": "交易所MIC编码",
            "SegTp": "交易场所",
            "TrdHrs": "交易时间节假日除外",
            "TrdCtyCd": "交易国家ISO编码",
            "TrdCcyCd": "交易币种ISO编码",
            "ClrngCcyCd": "结算币种ISO编码",
            "ExpiryTime": "到期时间待国家公布2025年节假日安排后进行调整",
            "SettleTp": "结算方式",
            "Duration": "挂牌频率",
            "TckSz": "最小变动价位",
            "TckVal": "最小变动价值",
            "CtrSz": "交易单位",
            "MsrmntUnt": "计量单位",
            "MaxOrdSz": "最大下单量",
            "MnthPosLmt": "日持仓限额期货公司会员不限仓",
            "MinBlckTrdSz": "大宗交易最小规模",
            "CesrEaaFl": "是否受CESR监管",
            "FlexElgblFl": "是否为灵活合约",
            "ListCy": "上市周期该产品的所有合约月份",
            "DlvryNtcDt": "交割通知日",
            "FrstTrdDt": "第一交易日",
            "LstTrdDt": "最后交易日待国家公布2025年节假日安排后进行调整",
            "DlvrySettleDt": "交割结算日",
            "MnthCd": "月份代码",
            "YrCd": "年份代码",
            "LstDlvryDt": "最后交割日",
            "LstDlvryDtBoard": "车（船）板最后交割日",
            "DlvryMnth": "合约交割月份本合约交割月份",
            "Margin": "交易保证金率",
            "PxLim": "涨跌停板",
            "FeeCcy": "费用币种ISO编码",
            "TrdFee": "交易手续费",
            "FeeCollectionType": "手续费收取方式",
            "DlvryFee": "交割手续费",
            "IntraDayTrdFee": "平今仓手续费",
            "TradingLimit": "交易限额",
        },
        inplace=True,
    )

    temp_df["交易手续费"] = pd.to_numeric(temp_df["交易手续费"], errors="coerce")
    temp_df["交割手续费"] = pd.to_numeric(temp_df["交割手续费"], errors="coerce")
    temp_df["平今仓手续费"] = pd.to_numeric(temp_df["平今仓手续费"], errors="coerce")
    temp_df["交易限额"] = pd.to_numeric(temp_df["交易限额"], errors="coerce")
    temp_df["车（船）板最后交割日"] = pd.to_datetime(
        temp_df["车（船）板最后交割日"], errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    futures_contract_info_czce_df = futures_contract_info_czce(date="20240228")
    print(futures_contract_info_czce_df)
