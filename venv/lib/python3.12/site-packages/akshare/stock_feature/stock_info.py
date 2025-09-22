#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/25 17:00
Desc: 东方财富-财经早餐
https://stock.eastmoney.com/a/czpnc.html
"""

from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.request import make_request_with_retry_json
from akshare.utils.cons import headers


def stock_info_cjzc_em() -> pd.DataFrame:
    """
    东方财富-财经早餐
    https://stock.eastmoney.com/a/czpnc.html
    :return: 财经早餐
    :rtype: pandas.DataFrame
    """
    url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
    params = {
        "client": "web",
        "biz": "web_news_col",
        "column": "1207",
        "order": "1",
        "needInteractData": "0",
        "page_index": "1",
        "page_size": "200",
        "req_trace": "1710314682980",
        "fields": "code,showTime,title,mediaName,summary,image,url,uniqueUrl,Np_dst",
    }
    big_df = pd.DataFrame()
    for page in range(1, 3):
        params.update({"page_index": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["list"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df = big_df[["title", "summary", "showTime", "uniqueUrl"]]
    big_df.rename(
        columns={
            "title": "标题",
            "summary": "摘要",
            "showTime": "发布时间",
            "uniqueUrl": "链接",
        },
        inplace=True,
    )
    return big_df


def stock_info_global_em() -> pd.DataFrame:
    """
    东方财富-全球财经快讯
    https://kuaixun.eastmoney.com/7_24.html
    :return: 全球财经快讯
    :rtype: pandas.DataFrame
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web",
        "biz": "web_724",
        "fastColumn": "102",
        "sortEnd": "",
        "pageSize": "200",
        "req_trace": "1710315450384",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["fastNewsList"])
    temp_df = temp_df[["title", "summary", "showTime", "code"]]
    temp_df["code"] = [
        f"https://finance.eastmoney.com/a/{item}.html" for item in temp_df["code"]
    ]
    temp_df.rename(
        columns={
            "title": "标题",
            "summary": "摘要",
            "showTime": "发布时间",
            "code": "链接",
        },
        inplace=True,
    )
    return temp_df


def stock_info_global_sina() -> pd.DataFrame:
    """
    新浪财经-全球财经快讯
    https://finance.sina.com.cn/7x24
    :return: 全球财经快讯
    :rtype: pandas.DataFrame
    """
    url = "https://zhibo.sina.com.cn/api/zhibo/feed"
    params = {
        "page": "1",
        "page_size": "20",
        "zhibo_id": "152",
        "tag_id": "0",
        "dire": "f",
        "dpc": "1",
        "pagesize": "20",
        "type": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    time_list = [
        item["create_time"] for item in data_json["result"]["data"]["feed"]["list"]
    ]
    text_list = [
        item["rich_text"] for item in data_json["result"]["data"]["feed"]["list"]
    ]
    temp_df = pd.DataFrame([time_list, text_list]).T
    temp_df.columns = ["时间", "内容"]
    return temp_df


def stock_info_global_futu() -> pd.DataFrame:
    """
    富途牛牛-快讯
    https://news.futunn.com/main/live
    :return: 快讯
    :rtype: pandas.DataFrame
    """
    url = "https://news.futunn.com/news-site-api/main/get-flash-list"
    params = {
        "pageSize": "50",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/111.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()

    temp_df = pd.DataFrame(data_json["data"]["data"]["news"])
    temp_df = temp_df[["title", "content", "time", "detailUrl"]]
    temp_df["time"] = [
        datetime.fromtimestamp(int(item)).strftime("%Y-%m-%d %H:%M:%S")
        for item in temp_df["time"]
    ]
    temp_df.rename(
        columns={
            "title": "标题",
            "content": "内容",
            "time": "发布时间",
            "detailUrl": "链接",
        },
        inplace=True,
    )
    return temp_df


def stock_info_global_ths() -> pd.DataFrame:
    """
    同花顺财经-全球财经直播
    https://news.10jqka.com.cn/realtimenews.html
    :return: 全球财经直播
    :rtype: pandas.DataFrame
    """
    url = "https://news.10jqka.com.cn/tapp/news/push/stock"
    params = {
        "page": "1",
        "tag": "",
        "track": "website",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df = temp_df[["title", "digest", "rtime", "url"]]
    temp_df["rtime"] = [
        datetime.fromtimestamp(int(item)).strftime("%Y-%m-%d %H:%M:%S")
        for item in temp_df["rtime"]
    ]
    temp_df.rename(
        columns={
            "title": "标题",
            "digest": "内容",
            "rtime": "发布时间",
            "url": "链接",
        },
        inplace=True,
    )
    return temp_df


def stock_info_global_cls(symbol: str = "全部") -> pd.DataFrame:
    """
    财联社-电报
    https://www.cls.cn/telegraph
    :param symbol: choice of {"全部", "重点"}
    :type symbol: str
    :return: 财联社-电报
    :rtype: pandas.DataFrame
    """
    url = "https://www.cls.cn/nodeapi/telegraphList"
    data_json = make_request_with_retry_json(url, max_retries=10, headers=headers)
    temp_df = pd.DataFrame(data_json["data"]["roll_data"])
    big_df = temp_df.copy()
    big_df = big_df[["title", "content", "ctime", "level"]]
    big_df["ctime"] = pd.to_datetime(big_df["ctime"], unit="s", utc=True).dt.tz_convert(
        "Asia/Shanghai"
    )
    big_df.columns = ["标题", "内容", "发布时间", "等级"]
    big_df.sort_values(["发布时间"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    big_df["发布日期"] = big_df["发布时间"].dt.date
    big_df["发布时间"] = big_df["发布时间"].dt.time
    if symbol == "重点":
        big_df = big_df[(big_df["等级"] == "B") | (big_df["等级"] == "A")]
        big_df.reset_index(inplace=True, drop=True)
        big_df = big_df[["标题", "内容", "发布日期", "发布时间"]]
        return big_df
    else:
        big_df = big_df[["标题", "内容", "发布日期", "发布时间"]]
        return big_df


def stock_info_broker_sina(page: str = "1") -> pd.DataFrame:
    """
    新浪财经-证券-证券原创
    https://finance.sina.com.cn/roll/index.d.html?cid=221431
    :param page: 页面号
    :type page: str
    :return: 证券原创文章
    :rtype: pandas.DataFrame
    """
    url = "https://finance.sina.com.cn/roll/index.d.html?cid=221431"
    params = {"page": page}
    r = requests.get(url, params=params)
    r.encoding = "utf-8"
    data_text = r.text
    soup = BeautifulSoup(data_text, features="lxml")
    data = []
    current_year = datetime.now().year
    for ul_index in range(0, 11):
        for li_index in range(0, 6):
            a_selector = f"#Main > div:nth-of-type(3) > ul:nth-of-type({ul_index}) > li:nth-of-type({li_index}) > a"
            span_selector = f"#Main > div:nth-of-type(3) > ul:nth-of-type({ul_index}) > li:nth-of-type({li_index}) > span"
            # 获取<a>标签和<span>标签内的文本内容
            a_element = soup.select_one(a_selector)
            span_element = soup.select_one(span_selector)
            if a_element and span_element:
                href = a_element.get("href")
                target = a_element.get("target")
                date = str(current_year) + "年" + span_element.text[1:-1]
                text = a_element.text
                data.append(
                    {"href": href, "target": target, "date": date, "text": text}
                )

    temp_df = pd.DataFrame(data)
    temp_df = temp_df[["date", "text", "href"]]
    temp_df.columns = ["时间", "内容", "链接"]
    temp_df.sort_values(["时间"], ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    stock_info_cjzc_em_df = stock_info_cjzc_em()
    print(stock_info_cjzc_em_df)

    stock_info_global_em_df = stock_info_global_em()
    print(stock_info_global_em_df)

    stock_info_global_sina_df = stock_info_global_sina()
    print(stock_info_global_sina_df)

    stock_info_global_futu_df = stock_info_global_futu()
    print(stock_info_global_futu_df)

    stock_info_global_ths_df = stock_info_global_ths()
    print(stock_info_global_ths_df)

    stock_info_global_cls_df = stock_info_global_cls(symbol="全部")
    print(stock_info_global_cls_df)

    stock_info_broker_sina_df = stock_info_broker_sina(page="1")
    print(stock_info_broker_sina_df)
