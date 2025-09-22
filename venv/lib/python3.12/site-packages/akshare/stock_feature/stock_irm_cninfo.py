#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/20 16:00
Desc: 互动易-提问与回答
https://irm.cninfo.com.cn/
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def _fetch_org_id(symbol: str = "000001") -> str:
    """
    股票-互动易-组织代码
    https://irm.cninfo.com.cn/
    :return: 组织代码
    :rtype: str
    """
    url = "https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo"
    params = {"_t": "1691144074"}
    data = {"keyWord": symbol}
    r = requests.post(url, params=params, data=data)
    data_json = r.json()
    org_id = data_json["data"][0]["secid"]
    return org_id


def stock_irm_cninfo(symbol: str = "002594") -> pd.DataFrame:
    """
    互动易-提问
    https://irm.cninfo.com.cn/ircs/question/questionDetail?questionId=1515236357817618432
    :param symbol: 股票代码
    :type symbol: str
    :return: 提问
    :rtype: str
    """
    url = "https://irm.cninfo.com.cn/newircs/company/question"
    params = {
        "_t": "1691142650",
        "stockcode": symbol,
        "orgId": _fetch_org_id(symbol),
        "pageSize": "1000",
        "pageNum": "1",
        "keyWord": "",
        "startDay": "",
        "endDay": "",
    }
    r = requests.post(url, params=params)
    data_json = r.json()
    total_page = int(data_json["totalPage"])
    total_page = 10 if total_page > 10 else total_page
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, 1 + total_page), leave=False):
        params.update({"pageNum": page})
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["rows"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.rename(
        columns={
            "indexId": "问题编号",
            "contentType": "-",
            "trade": "行业",
            "mainContent": "问题",
            "attachmentUrl": "-",
            "boardType": "行业代码",
            "filetype": "-",
            "pubDate": "提问时间",
            "stockCode": "股票代码",
            "companyShortName": "公司简称",
            "author": "提问者编号",
            "authorName": "提问者",
            "authorLogo": "-",
            "pubClient": "来源",
            "attachedId": "回答ID",
            "attachedContent": "回答内容",
            "attachedAuthor": "回答者",
            "attachedPubDate": "-",
            "updateDate": "更新时间",
            "isPraise": "-",
            "isFavorite": "-",
            "isForward": "-",
            "praiseCount": "-",
            "qaStatus": "-",
            "rights": "-",
            "topStatus": "-",
            "companyLogo": "-",
            "favoriteCount": "-",
            "forwardCount": "-",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "公司简称",
            "行业",
            "行业代码",
            "问题",
            "提问者",
            "来源",
            "提问时间",
            "更新时间",
            "提问者编号",
            "问题编号",
            "回答ID",
            "回答内容",
            "回答者",
        ]
    ]
    big_df["行业"] = [item[0] for item in big_df["行业"]]
    big_df["行业代码"] = [item[0] for item in big_df["行业代码"]]
    big_df["提问时间"] = (
        pd.to_datetime(big_df["提问时间"], unit="ms", errors="coerce")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Shanghai")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    big_df["更新时间"] = (
        pd.to_datetime(big_df["更新时间"], unit="ms", errors="coerce")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Shanghai")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    big_df["来源"] = big_df["来源"].map(
        {
            "2": "APP",
            "5": "公众号",
            "4": "网站",
        }
    )
    big_df["来源"] = big_df["来源"].fillna("网站")
    return big_df


def stock_irm_ans_cninfo(symbol: str = "1513586704097333248") -> pd.DataFrame:
    """
    互动易-回答
    https://irm.cninfo.com.cn/ircs/question/questionDetail?questionId=1515236357817618432
    :param symbol: 提问者编号; 通过 ak.stock_irm_cninfo() 来获取具体的提问者编号
    :type symbol: str
    :return: 回答
    :rtype: str
    """
    url = "https://irm.cninfo.com.cn/newircs/question/getQuestionDetail"
    params = {"questionId": symbol, "_t": "1691146921"}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["data"], orient="index").T
    if "replyDate" not in temp_df.columns:
        return pd.DataFrame()
    temp_df.rename(
        columns={
            "questionContent": "问题",
            "questioner": "提问者",
            "questionDate": "提问时间",
            "replyDate": "回答时间",
            "replyContent": "回答内容",
            "stockCode": "股票代码",
            "shortName": "公司简称",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "股票代码",
            "公司简称",
            "问题",
            "回答内容",
            "提问者",
            "提问时间",
            "回答时间",
        ]
    ]
    temp_df["提问时间"] = (
        pd.to_datetime(temp_df["提问时间"], unit="ms", errors="coerce")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Shanghai")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    temp_df["回答时间"] = (
        pd.to_datetime(temp_df["回答时间"], unit="ms", errors="coerce")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Shanghai")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    return temp_df


if __name__ == "__main__":
    stock_irm_cninfo_df = stock_irm_cninfo(symbol="002594")
    print(stock_irm_cninfo_df)

    stock_irm_ans_cninfo_df = stock_irm_ans_cninfo(symbol="1495108801386602496")
    print(stock_irm_ans_cninfo_df)
