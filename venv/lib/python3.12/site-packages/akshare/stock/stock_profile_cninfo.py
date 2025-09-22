#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/10/14 22:00
Desc: 巨潮资讯-个股-公司概况
https://webapi.cninfo.com.cn/#/company
"""

import pandas as pd
import py_mini_racer
import requests

from akshare.datasets import get_ths_js


def _get_file_content_ths(file: str = "cninfo.js") -> str:
    """
    获取 JS 文件的内容
    :param file:  JS 文件名
    :type file: str
    :return: 文件内容
    :rtype: str
    """
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


def stock_profile_cninfo(symbol: str = "600030") -> pd.DataFrame:
    """
    巨潮资讯-个股-公司概况
    https://webapi.cninfo.com.cn/#/company
    :param symbol: 股票代码
    :type symbol: str
    :return: 公司概况
    :rtype: pandas.DataFrame
    :raise: Exception，如果服务器返回的数据无法被解析
    """
    url = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1133"
    params = {
        "scode": symbol,
    }
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Accept-Enckey": mcode,
        "Origin": "https://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "https://webapi.cninfo.com.cn/",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, params=params, headers=headers)
    data_json = r.json()
    columns = [
        "公司名称",
        "英文名称",
        "曾用简称",
        "A股代码",
        "A股简称",
        "B股代码",
        "B股简称",
        "H股代码",
        "H股简称",
        "入选指数",
        "所属市场",
        "所属行业",
        "法人代表",
        "注册资金",
        "成立日期",
        "上市日期",
        "官方网站",
        "电子邮箱",
        "联系电话",
        "传真",
        "注册地址",
        "办公地址",
        "邮政编码",
        "主营业务",
        "经营范围",
        "机构简介",
    ]
    count = data_json["count"]
    if count == 1:
        # 有公司概况的
        redundant_json = data_json["records"][0]
        records_json = {}
        i = 0
        for k, v in redundant_json.items():
            if i == (len(redundant_json) - 4):
                break
            records_json[k] = v
            i += 1
        del i
        temp_df = pd.Series(records_json).to_frame().T
        temp_df.columns = columns
    elif count == 0:
        # 没公司概况的
        temp_df = pd.DataFrame(columns=columns)
    else:
        raise Exception("数据错误！")
    return temp_df


if __name__ == "__main__":
    stock_profile_cninfo_df = stock_profile_cninfo(symbol="600030")
    print(stock_profile_cninfo_df)
