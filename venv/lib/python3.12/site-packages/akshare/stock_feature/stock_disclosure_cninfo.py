#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/1 20:00
Desc: 巨潮资讯-首页-公告查询-信息披露
http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search
"""

import math
from functools import lru_cache

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


@lru_cache()
def __get_category_dict() -> dict:
    """
    获取巨潮资讯-首页-公告查询-信息披露-类别字典
    http://www.cninfo.com.cn/new/js/app/disclosure/notice/history-notice.js?v=20231124083101
    :return: dict
    :rtype: dict
    """
    big_dict = {
        "年报": "category_ndbg_szsh",
        "半年报": "category_bndbg_szsh",
        "一季报": "category_yjdbg_szsh",
        "三季报": "category_sjdbg_szsh",
        "业绩预告": "category_yjygjxz_szsh",
        "权益分派": "category_qyfpxzcs_szsh",
        "董事会": "category_dshgg_szsh",
        "监事会": "category_jshgg_szsh",
        "股东大会": "category_gddh_szsh",
        "日常经营": "category_rcjy_szsh",
        "公司治理": "category_gszl_szsh",
        "中介报告": "category_zj_szsh",
        "首发": "category_sf_szsh",
        "增发": "category_zf_szsh",
        "股权激励": "category_gqjl_szsh",
        "配股": "category_pg_szsh",
        "解禁": "category_jj_szsh",
        "公司债": "category_gszq_szsh",
        "可转债": "category_kzzq_szsh",
        "其他融资": "category_qtrz_szsh",
        "股权变动": "category_gqbd_szsh",
        "补充更正": "category_bcgz_szsh",
        "澄清致歉": "category_cqdq_szsh",
        "风险提示": "category_fxts_szsh",
        "特别处理和退市": "category_tbclts_szsh",
        "退市整理期": "category_tszlq_szsh",
    }
    return big_dict


@lru_cache()
def __get_stock_json(symbol: str = "沪深京") -> dict:
    """
    获取巨潮资讯-首页-公告查询-信息披露-股票代码字典
    :param symbol: choice of {"沪深京", "港股", "三板", "基金", "债券"}
    :type symbol: str
    :return: 股票代码字典
    :rtype: dict
    """
    url = "http://www.cninfo.com.cn/new/data/szse_stock.json"
    if symbol == "沪深京":
        url = "http://www.cninfo.com.cn/new/data/szse_stock.json"
    elif symbol == "港股":
        url = "http://www.cninfo.com.cn/new/data/hke_stock.json"
    elif symbol == "三板":
        url = "http://www.cninfo.com.cn/new/data/gfzr_stock.json"
    elif symbol == "基金":
        url = "http://www.cninfo.com.cn/new/data/fund_stock.json"
    elif symbol == "债券":
        url = "http://www.cninfo.com.cn/new/data/bond_stock.json"
    r = requests.get(url)
    text_json = r.json()
    temp_df = pd.DataFrame([item for item in text_json["stockList"]])
    return dict(zip(temp_df["code"], temp_df["orgId"]))


def stock_zh_a_disclosure_report_cninfo(
    symbol: str = "000001",
    market: str = "沪深京",
    keyword: str = "",
    category: str = "",
    start_date: str = "20230618",
    end_date: str = "20231219",
) -> pd.DataFrame:
    """
    巨潮资讯-首页-公告查询-信息披露公告
    http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search
    :param symbol: 股票代码
    :type symbol: str
    :param market: choice of {"沪深京", "港股", "三板", "基金", "债券", "监管", "预披露"}
    :type market: str
    :param keyword: 关键词
    :type keyword: str
    :param category: choice of {'年报', '半年报', '一季报', '三季报', '业绩预告', '权益分派',
    '董事会', '监事会', '股东大会', '日常经营', '公司治理', '中介报告',
     '首发', '增发', '股权激励', '配股', '解禁', '公司债', '可转债', '其他融资',
     '股权变动', '补充更正', '澄清致歉', '风险提示', '特别处理和退市', '退市整理期'}
    :type category: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 开始时间
    :type end_date: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    column_map = {
        "沪深京": "szse",
        "港股": "hke",
        "三板": "third",
        "基金": "fund",
        "债券": "bond",
        "监管": "regulator",
        "预披露": "pre_disclosure",
    }
    stock_id_map = ""
    if market == "沪深京" or "基金":
        stock_id_map = __get_stock_json(market)
    category_dict = __get_category_dict()
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    stock_item = "" if symbol == "" else f"{symbol},{stock_id_map[symbol]}"
    category_item = "" if category == "" else f"{category_dict[category]}"
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": column_map[market],
        "tabName": "fulltext",
        "plate": "",
        "stock": stock_item,
        "searchkey": keyword,
        "secid": "",
        "category": category_item,
        "trade": "",
        "seDate": f'{"-".join([start_date[:4], start_date[4:6], start_date[6:]])}~'
        f'{"-".join([end_date[:4], end_date[4:6], end_date[6:]])}',
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    r = requests.post(url, params=payload)
    text_json = r.json()
    page_num = math.ceil(int(text_json["totalAnnouncement"]) / 30)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        payload.update({"pageNum": page})
        r = requests.post(url, data=payload)
        text_json = r.json()
        temp_df = pd.DataFrame(text_json["announcements"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "secCode": "代码",
            "secName": "简称",
            "announcementTitle": "公告标题",
            "announcementTime": "公告时间",
        },
        inplace=True,
    )
    big_df = big_df[["代码", "简称", "公告标题", "公告时间", "announcementId", "orgId"]]
    big_df["公告时间"] = pd.to_datetime(
        big_df["公告时间"], unit="ms", utc=True, errors="coerce"
    )
    big_df["公告时间"] = (
        big_df["公告时间"]
        .dt.tz_convert("Asia/Shanghai")
        .dt.tz_localize(None)
        .astype(str)
    )
    url_list = []
    for item in zip(
        big_df["代码"], big_df["announcementId"], big_df["orgId"], big_df["公告时间"]
    ):
        url_format = (
            f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode={item[0]}&"
            f"announcementId={item[1]}&orgId={item[2]}&announcementTime={item[3]}"
        )
        url_list.append(url_format)
    big_df["公告链接"] = url_list
    big_df = big_df[["代码", "简称", "公告标题", "公告时间", "公告链接"]]
    return big_df


def stock_zh_a_disclosure_relation_cninfo(
    symbol: str = "000001",
    market: str = "沪深京",
    start_date: str = "20230618",
    end_date: str = "20231219",
) -> pd.DataFrame:
    """
    巨潮资讯-首页-数据-预约披露调研
    http://www.cninfo.com.cn/new/commonUrl?url=data/yypl
    :param symbol: 股票代码
    :type symbol: str
    :param market: choice of {"沪深京", "港股", "三板", "基金", "债券", "监管", "预披露"}
    :type market: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 开始时间
    :type end_date: str
    :return: 指定 symbol 的数据
    :rtype: pandas.DataFrame
    """
    column_map = {
        "沪深京": "szse",
        "港股": "hke",
        "三板": "third",
        "基金": "fund",
        "债券": "bond",
        "监管": "regulator",
        "预披露": "pre_disclosure",
    }
    stock_id_map = ""
    if market == "沪深京":
        stock_id_map = __get_stock_json(symbol)
    stock_item = "" if symbol == "" else f"{symbol},{stock_id_map[symbol]}"
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": column_map[market],
        "tabName": "relation",
        "plate": "",
        "stock": stock_item,
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f'{"-".join([start_date[:4], start_date[4:6], start_date[6:]])}~'
        f'{"-".join([end_date[:4], end_date[4:6], end_date[6:]])}',
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    r = requests.post(url, data=payload)
    text_json = r.json()
    page_num = math.ceil(int(text_json["totalAnnouncement"]) / 30)
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_num + 1), leave=False):
        payload.update({"pageNum": page})
        r = requests.post(url, data=payload)
        text_json = r.json()
        temp_df = pd.DataFrame(text_json["announcements"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "secCode": "代码",
            "secName": "简称",
            "announcementTitle": "公告标题",
            "announcementTime": "公告时间",
        },
        inplace=True,
    )
    big_df = big_df[["代码", "简称", "公告标题", "公告时间", "announcementId", "orgId"]]
    big_df["公告时间"] = pd.to_datetime(
        big_df["公告时间"], unit="ms", utc=True, errors="coerce"
    )
    big_df["公告时间"] = (
        big_df["公告时间"]
        .dt.tz_convert("Asia/Shanghai")
        .dt.tz_convert(None)
        .astype(str)
    )
    url_list = []
    for item in zip(
        big_df["代码"], big_df["announcementId"], big_df["orgId"], big_df["公告时间"]
    ):
        url_format = (
            f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode={item[0]}"
            f"&announcementId={item[1]}&orgId={item[2]}&announcementTime={item[3]}"
        )
        url_list.append(url_format)
    big_df["公告链接"] = url_list
    big_df = big_df[["代码", "简称", "公告标题", "公告时间", "公告链接"]]
    return big_df


if __name__ == "__main__":
    stock_zh_a_disclosure_report_cninfo_df = stock_zh_a_disclosure_report_cninfo(
        symbol="164701",
        market="基金",
        keyword="大模型",
        category="",
        start_date="20240422",
        end_date="20250422",
    )
    print(stock_zh_a_disclosure_report_cninfo_df)

    stock_zh_a_disclosure_relation_cninfo_df = stock_zh_a_disclosure_relation_cninfo(
        symbol="000001", market="沪深京", start_date="20230619", end_date="20231220"
    )
    print(stock_zh_a_disclosure_relation_cninfo_df)
