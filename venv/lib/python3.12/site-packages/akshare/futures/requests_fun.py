#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/9/15 19:00
Desc: 请求网站内容的函数: 在链接失败后可重复 20 次
"""

from io import StringIO
import time
from typing import Dict

import pandas as pd
import requests


def requests_link(
    url: str,
    encoding: str = "utf-8",
    method: str = "get",
    data: Dict = None,
    headers: Dict = None,
):
    """
    利用 requests 请求网站, 爬取网站内容, 如网站链接失败, 可重复爬取 20 次
    :param url: string 网站地址
    :param encoding: string 编码类型: "utf-8", "gbk", "gb2312"
    :param method: string 访问方法: "get", "post"
    :param data: dict 上传数据: 键值对
    :param headers: dict 游览器请求头: 键值对
    :return: requests.response 爬取返回内容: response
    """
    i = 0
    while True:
        try:
            if method == "get":
                r = requests.get(url, timeout=20, headers=headers)
                r.encoding = encoding
                return r
            elif method == "post":
                r = requests.post(url, timeout=20, data=data, headers=headers)
                r.encoding = encoding
                return r
            else:
                raise ValueError("请提供正确的请求方式")
        except:  # noqa: E722
            i += 1
            print(f"第{str(i)}次链接失败, 最多尝试 20 次")
            time.sleep(5)
            if i > 20:
                return None


def pandas_read_html_link(
    url: str,
    encoding: str = "utf-8",
    method: str = "get",
    data: Dict = None,
    headers: Dict = None,
):
    """
    利用 pandas 提供的 read_html 函数来直接提取网页中的表格内容, 如网站链接失败, 可重复爬取 20 次
    :param url: string 网站地址
    :param encoding: string 编码类型: "utf-8", "gbk", "gb2312"
    :param method: string 访问方法: "get", "post"
    :param data: dict 上传数据: 键值对
    :param headers: dict 游览器请求头: 键值对
    :return: requests.response 爬取返回内容: response
    """
    i = 0
    while True:
        try:
            if method == "get":
                r = requests.get(url, timeout=20)
                r.encoding = encoding
                r = pd.read_html(StringIO(r.text), encoding=encoding)
                return r
            elif method == "post":
                r = requests.post(url, timeout=20, data=data, headers=headers)
                r.encoding = encoding
                r = pd.read_html(StringIO(r.text), encoding=encoding)
                return r
            else:
                raise ValueError("请提供正确的请求方式")
        except requests.exceptions.Timeout as e:
            i += 1
            print(f"第{str(i)}次链接失败, 最多尝试20次", e)
            time.sleep(5)
            if i > 20:
                return None
