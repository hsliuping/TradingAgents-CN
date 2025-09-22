#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2021/9/29 16:19
Desc: 巨潮资讯-数据中心-专题统计-公司治理-公司诉讼
http://webapi.cninfo.com.cn/#/thematicStatistics
"""

import time

import pandas as pd
import requests
import py_mini_racer

js_str = """
    function mcode(input) {
                var keyStr = "ABCDEFGHIJKLMNOP" + "QRSTUVWXYZabcdef" + "ghijklmnopqrstuv"   + "wxyz0123456789+/" + "=";
                var output = "";
                var chr1, chr2, chr3 = "";
                var enc1, enc2, enc3, enc4 = "";
                var i = 0;
                do {
                    chr1 = input.charCodeAt(i++);
                    chr2 = input.charCodeAt(i++);
                    chr3 = input.charCodeAt(i++);
                    enc1 = chr1 >> 2;
                    enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
                    enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
                    enc4 = chr3 & 63;
                    if (isNaN(chr2)) {
                        enc3 = enc4 = 64;
                    } else if (isNaN(chr3)) {
                        enc4 = 64;
                    }
                    output = output + keyStr.charAt(enc1) + keyStr.charAt(enc2)
                            + keyStr.charAt(enc3) + keyStr.charAt(enc4);
                    chr1 = chr2 = chr3 = "";
                    enc1 = enc2 = enc3 = enc4 = "";
                } while (i < input.length);

                return output;
            }
"""


def stock_cg_lawsuit_cninfo(
    symbol: str = "全部", start_date: str = "20180630", end_date: str = "20210927"
) -> pd.DataFrame:
    """
    巨潮资讯-数据中心-专题统计-公司治理-公司诉讼
    http://webapi.cninfo.com.cn/#/thematicStatistics
    :param symbol: choice of {"全部", "深市主板", "沪市", "创业板", "科创板"}
    :type symbol: str
    :param start_date: 开始统计时间
    :type start_date: str
    :param end_date: 结束统计时间
    :type end_date: str
    :return: 对外担保
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部": "",
        "深市主板": "012002",
        "沪市": "012001",
        "创业板": "012015",
        "科创板": "012029",
    }
    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1055"
    random_time_str = str(int(time.time()))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(js_str)
    mcode = js_code.call("mcode", random_time_str)
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "mcode": mcode,
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "sdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "edate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "market": symbol_map[symbol],
    }
    r = requests.post(url, headers=headers, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "公告统计区间",
        "诉讼金额",
        "诉讼次数",
        "证券简称",
        "证券代码",
    ]
    temp_df = temp_df[
        [
            "证券代码",
            "证券简称",
            "公告统计区间",
            "诉讼次数",
            "诉讼金额",
        ]
    ]
    temp_df["诉讼次数"] = pd.to_numeric(temp_df["诉讼次数"])
    temp_df["诉讼金额"] = pd.to_numeric(temp_df["诉讼金额"])
    return temp_df


if __name__ == "__main__":
    stock_cg_lawsuit_cninfo_df = stock_cg_lawsuit_cninfo(
        symbol="全部", start_date="20180928", end_date="20210927"
    )
    print(stock_cg_lawsuit_cninfo_df)
