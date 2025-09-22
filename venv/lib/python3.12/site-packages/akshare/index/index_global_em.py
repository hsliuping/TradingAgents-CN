#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/7 17:00
Desc: 东方财富网-行情中心-全球指数
https://quote.eastmoney.com/center/gridlist.html#global_qtzs
"""

import pandas as pd
import requests

from akshare.index.cons import index_global_em_symbol_map


def index_global_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-全球指数-实时行情数据
    https://quote.eastmoney.com/center/gridlist.html#global_qtzs
    :return: 实时行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "2",
        "fltt": "1",
        "invt": "2",
        "fs": "i:1.000001,i:0.399001,i:0.399005,i:0.399006,i:1.000300,i:100.HSI,i:100.HSCEI,i:124.HSCCI,"
        "i:100.TWII,i:100.N225,i:100.KOSPI200,i:100.KS11,i:100.STI,i:100.SENSEX,i:100.KLSE,i:100.SET,"
        "i:100.PSI,i:100.KSE100,i:100.VNINDEX,i:100.JKSE,i:100.CSEALL,i:100.SX5E,i:100.FTSE,i:100.MCX,"
        "i:100.AXX,i:100.FCHI,i:100.GDAXI,i:100.RTS,i:100.IBEX,i:100.PSI20,i:100.OMXC20,i:100.BFX,"
        "i:100.AEX,i:100.WIG,i:100.OMXSPI,i:100.SSMI,i:100.HEX,i:100.OSEBX,i:100.ATX,i:100.MIB,"
        "i:100.ASE,i:100.ICEXI,i:100.PX,i:100.ISEQ,i:100.DJIA,i:100.SPX,i:100.NDX,i:100.TSX,"
        "i:100.BVSP,i:100.MXX,i:100.AS51,i:100.AORD,i:100.NZ50,i:100.UDI,i:100.BDI,i:100.CRB",
        "fields": "f12,f13,f14,f292,f1,f2,f4,f3,f152,f17,f18,f15,f16,f7,f124",
        "fid": "f3",
        "pn": "1",
        "pz": "200",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"]).T
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "f12": "代码",
            "f14": "名称",
            "f17": "开盘价",
            "f4": "涨跌额",
            "f3": "涨跌幅",
            "f2": "最新价",
            "f15": "最高价",
            "f16": "最低价",
            "f18": "昨收价",
            "f7": "振幅",
            "f124": "最新行情时间",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "开盘价",
            "最高价",
            "最低价",
            "昨收价",
            "振幅",
            "最新行情时间",
        ]
    ]
    temp_df["最新行情时间"] = pd.to_datetime(
        temp_df["最新行情时间"], unit="s", utc=True, errors="coerce"
    ).dt.tz_convert("Asia/Shanghai")
    temp_df["最新行情时间"] = temp_df["最新行情时间"].dt.strftime("%Y-%m-%d %H:%M:%S")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce") / 100
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce") / 100
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce") / 100
    temp_df["开盘价"] = pd.to_numeric(temp_df["开盘价"], errors="coerce") / 100
    temp_df["最高价"] = pd.to_numeric(temp_df["最高价"], errors="coerce") / 100
    temp_df["最低价"] = pd.to_numeric(temp_df["最低价"], errors="coerce") / 100
    temp_df["昨收价"] = pd.to_numeric(temp_df["昨收价"], errors="coerce") / 100
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce") / 100
    return temp_df


def index_global_hist_em(symbol: str = "美元指数") -> pd.DataFrame:
    """
    东方财富网-行情中心-全球指数-历史行情数据
    https://quote.eastmoney.com/gb/zsUDI.html
    :param symbol: 指数名称；可以通过 ak.index_global_spot_em() 获取
    :type symbol: str
    :return: 历史行情数据
    :rtype: pandas.DataFrame
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": f"{index_global_em_symbol_map[symbol]['market']}.{index_global_em_symbol_map[symbol]['code']}",
        "klt": "101",
        "fqt": "1",
        "lmt": "50000",
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()

    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df["code"] = data_json["data"]["code"]
    temp_df["name"] = data_json["data"]["name"]
    temp_df.columns = [
        "日期",
        "今开",
        "最新价",
        "最高",
        "最低",
        "-",
        "-",
        "振幅",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "代码",
        "名称",
    ]
    temp_df = temp_df[
        [
            "日期",
            "代码",
            "名称",
            "今开",
            "最新价",
            "最高",
            "最低",
            "振幅",
        ]
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_global_spot_em_df = index_global_spot_em()
    print(index_global_spot_em_df)

    index_global_hist_em_df = index_global_hist_em(symbol="美元指数")
    print(index_global_hist_em_df)
