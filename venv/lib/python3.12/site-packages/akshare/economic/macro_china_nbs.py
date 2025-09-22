#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/30 22:00
Desc: 中国-国家统计局-宏观数据
https://data.stats.gov.cn/easyquery.htm
"""

import time
from functools import lru_cache
from typing import Union, Literal, List, Dict

import jsonpath as jp
import numpy as np
import pandas as pd
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# 忽略InsecureRequestWarning警告
urllib3.disable_warnings(InsecureRequestWarning)


@lru_cache
def _get_nbs_tree(idcode: str, dbcode: str) -> List[Dict]:
    """
    获取指标目录树
    :param idcode: 指标编码
    :param dbcode: 库编码
    :return:  json数据
    """
    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {"id": idcode, "dbcode": dbcode, "wdcode": "zb", "m": "getTree"}
    r = requests.post(url, params=params, verify=False, allow_redirects=True)
    data_json = r.json()
    return data_json


@lru_cache
def _get_nbs_wds_tree(idcode: str, dbcode: str, rowcode: str) -> List[Dict]:
    """
    获取地区数据的可选指标目录树
    :param idcode: 指标编码
    :param dbcode: 库编码
    :param rowcode: 值为zb是返回地区的编码，值为reg时返回可选指标的编码
    :return:  json数据
    """
    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {
        "m": "getOtherWds",
        "dbcode": dbcode,
        "rowcode": rowcode,
        "colcode": "sj",
        "wds": '[{"wdcode":"zb","valuecode":"%s"}]' % idcode,
        "k1": str(time.time_ns())[:13],
    }
    r = requests.post(url, params=params, verify=False, allow_redirects=True)
    data_json = r.json()
    data_json = data_json["returndata"][0]["nodes"]
    return data_json


def _get_code_from_nbs_tree(tree: List[Dict], name: str, target: str = "id") -> str:
    """
    根据指标名称从目录树中获取target编码
    :param tree: 目录树
    :param name: 指标名称
    :param target: 指标编码属性名
    :return: 指标编码
    """
    expr = f'$[?(@.name == "{name}")].{target}'
    ret = jp.jsonpath(tree, expr)
    if ret is False:
        raise ValueError("Please check if the data path or indicator is correct.")
    return ret[0]


def macro_china_nbs_nation(
    kind: Literal["月度数据", "季度数据", "年度数据"], path: str, period: str = "LAST10"
) -> pd.DataFrame:
    """
    国家统计局全国数据通用接口
    https://data.stats.gov.cn/easyquery.htm
    :param kind: 数据类别
    :param path: 数据路径
    :param period: 时间区间，例如'LAST10', '2016-2023', '2016-'等
    :return: 国家统计局统计数据
    :rtype: pandas.DataFrame
    """
    # 获取dbcode
    kind_code = {"月度数据": "hgyd", "季度数据": "hgjd", "年度数据": "hgnd"}
    dbcode = kind_code[kind]

    # 获取最终id
    parent_tree = _get_nbs_tree("zb", dbcode)
    path_split = path.replace(" ", "").split(">")
    indicator_id = _get_code_from_nbs_tree(parent_tree, path_split[0])
    path_split.pop(0)
    while path_split:
        temp_tree = _get_nbs_tree(indicator_id, dbcode)
        indicator_id = _get_code_from_nbs_tree(temp_tree, path_split[0])
        path_split.pop(0)

    # 请求数据
    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {
        "m": "QueryData",
        "dbcode": dbcode,
        "rowcode": "zb",
        "colcode": "sj",
        "wds": "[]",
        "dfwds": '[{"wdcode":"zb","valuecode":"%s"}, '
        '{"wdcode":"sj","valuecode":"%s"}]' % (indicator_id, period),
        "k1": str(time.time_ns())[:13],
    }
    r = requests.get(url, params=params, verify=False, allow_redirects=True)
    data_json = r.json()

    # 整理为dataframe
    temp_df = pd.DataFrame(data_json["returndata"]["datanodes"])
    temp_df["data"] = temp_df["data"].apply(
        lambda x: x["data"] if x["hasdata"] else None
    )

    wdnodes = data_json["returndata"]["wdnodes"]
    wn_df_list = []
    for wn in wdnodes:
        wn_df_list.append(
            pd.DataFrame(wn["nodes"])
            .assign(
                funit=lambda df: df["unit"].apply(lambda x: "(" + x + ")" if x else x)
            )
            .assign(fname=lambda df: df["cname"] + df["funit"]),
        )

    row_name, column_name = (
        wn_df_list[0]["fname"],
        wn_df_list[1]["fname"],
    )

    data_ndarray = np.reshape(temp_df["data"], (len(row_name), len(column_name)))
    data_df = pd.DataFrame(data=data_ndarray, columns=column_name, index=row_name)
    data_df.index.name = None
    data_df.columns.name = None

    return data_df


def macro_china_nbs_region(
    kind: Literal[
        "分省月度数据",
        "分省季度数据",
        "分省年度数据",
        "主要城市月度价格",
        "主要城市年度数据",
        "港澳台月度数据",
        "港澳台年度数据",
    ],
    path: str,
    indicator: Union[str, None],
    region: Union[str, None] = None,
    period: str = "LAST10",
) -> pd.DataFrame:
    """
    国家统计局地区数据通用接口
    https://data.stats.gov.cn/easyquery.htm
    :param kind: 数据类别
    :param path: 数据路径
    :param indicator: 指定指标
    :param region:  指定地区 当指定region时，将symbol设为None可以同时获得所有可选指标的值
    :param period: 时间区间，例如'LAST10', '2016-2023', '2016-'等
    :return: 国家统计局统计数据
    :rtype: pandas.DataFrame
    """
    if indicator is None and region is None:
        raise AssertionError("The indicator and region parameters cannot both be None.")

    # 获取dbcode
    kind_dict = {
        "分省月度数据": "fsyd",
        "分省季度数据": "fsjd",
        "分省年度数据": "fsnd",
        "主要城市月度价格": "csyd",
        "主要城市年度数据": "csnd",
        "港澳台月度数据": "gatyd",
        "港澳台年度数据": "gatnd",
    }
    dbcode = kind_dict[kind]

    # 获取最终id
    parent_tree = _get_nbs_tree("zb", dbcode)
    path_split = path.replace(" ", "").split(">")
    indicator_id = _get_code_from_nbs_tree(parent_tree, path_split[0])
    path_split.pop(0)
    while path_split:
        temp_tree = _get_nbs_tree(indicator_id, dbcode)
        indicator_id = _get_code_from_nbs_tree(temp_tree, path_split[0])
        path_split.pop(0)

    # 参数设定
    if region is None:
        indicator_tree = _get_nbs_wds_tree(indicator_id, dbcode, "reg")
        indicator_id = _get_code_from_nbs_tree(indicator_tree, indicator, target="code")
        rowcode = "reg"
        colcode = "sj"
        wds = '[{"wdcode":"zb","valuecode":"%s"}]' % indicator_id
        dfwds = '[{"wdcode":"sj","valuecode":"%s"}]' % period
    else:
        if indicator is not None:
            indicator_tree = _get_nbs_wds_tree(indicator_id, dbcode, "reg")
            indicator_id = _get_code_from_nbs_tree(
                indicator_tree, indicator, target="code"
            )
        region_tree = _get_nbs_wds_tree(indicator_id, dbcode, "zb")
        region_id = _get_code_from_nbs_tree(region_tree, region, target="code")
        rowcode = "zb"
        colcode = "sj"
        wds = '[{"wdcode":"reg","valuecode":"%s"}]' % region_id
        dfwds = (
            '[{"wdcode":"zb","valuecode":"%s"}, '
            '{"wdcode":"sj","valuecode":"%s"}]' % (indicator_id, period)
        )

    # 请求数据
    url = "https://data.stats.gov.cn/easyquery.htm"
    params = {
        "m": "QueryData",
        "dbcode": dbcode,
        "rowcode": rowcode,
        "colcode": colcode,
        "wds": wds,
        "dfwds": dfwds,
        "k1": str(time.time_ns())[:13],
    }
    r = requests.get(url, params=params, verify=False, allow_redirects=True)
    data_json = r.json()

    # 整理为dataframe
    temp_df = pd.DataFrame(data_json["returndata"]["datanodes"])
    temp_df["data"] = temp_df["data"].apply(
        lambda x: x["data"] if x["hasdata"] else None
    )

    wdnodes = data_json["returndata"]["wdnodes"]
    wn_df_list = []
    for wn in wdnodes:
        wn_df_list.append(
            pd.DataFrame(wn["nodes"])
            .assign(
                funit=lambda df: df["unit"].apply(lambda x: "(" + x + ")" if x else x)
            )
            .assign(fname=lambda df: df["cname"] + df["funit"]),
        )

    if region is None:
        row_name, column_name = wn_df_list[1]["fname"], wn_df_list[2]["fname"]
        title_name = wn_df_list[0]["fname"][0]
    else:
        row_name, column_name = wn_df_list[0]["fname"], wn_df_list[2]["fname"]
        title_name = wn_df_list[1]["fname"][0]

    data_ndarray = np.reshape(temp_df["data"], (len(row_name), len(column_name)))
    data_df = pd.DataFrame(data=data_ndarray, columns=column_name, index=row_name)
    data_df.index.name = None
    data_df.columns.name = title_name

    return data_df


if __name__ == "__main__":
    macro_china_nbs_nation_df = macro_china_nbs_nation(
        kind="月度数据",
        path="工业 > 工业分大类行业出口交货值(2018-至今) > 废弃资源综合利用业",
        period="LAST5",
    )
    print(macro_china_nbs_nation_df)

    macro_china_nbs_region_df = macro_china_nbs_region(
        kind="分省季度数据",
        path="人民生活 > 居民人均可支配收入",
        period="2018-2022",
        indicator=None,
        region="北京市",
    )
    print(macro_china_nbs_region_df)

    macro_china_nbs_region_df = macro_china_nbs_region(
        kind="分省季度数据",
        path="国民经济核算 > 地区生产总值",
        period="2018-",
        indicator="地区生产总值_累计值(亿元)",
    )
    print(macro_china_nbs_region_df)
