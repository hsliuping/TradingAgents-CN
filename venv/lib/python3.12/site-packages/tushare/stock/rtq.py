#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
所有 A 股的实时行情数据
Created on 2023/12/06
@author: Monday
@group : waditu
@contact:
"""
import time
import pandas as pd
import requests
from tqdm import tqdm
from typing import Optional
import re
from tushare.util.format_stock_code import symbol_verify
from tushare.util.format_stock_code import format_stock_code, verify_stock_or_index
from tushare.util.form_date import timestemp_to_time
from tushare.stock import rtq_vars as rtqv
from tushare.util.verify_token import require_permission
from tushare.stock import cons as ct
from tushare.stock.rtq_vars import (
    zh_sina_a_stock_payload,
    zh_sina_a_stock_url,
    zh_sina_a_stock_count_url,
    zh_sina_a_stock_headers,
    zh_sina_a_stock_cookies,

)


def _random(n=13):
    from random import randint
    start = 10 ** (n - 1)
    end = (10 ** n) - 1
    return str(randint(start, end))


def _get_current_timestamp():
    return str(int(time.time() * 1000))


@require_permission(event_name="realtime_quote", event_detail="个股实时交易数据")
def realtime_quote(ts_code="688553.SH", src="sina", ):
    """
        获取实时交易数据 getting real time quotes data
       用于跟踪交易情况（本次执行的结果-上一次执行的数据）
    Parameters
    ------
        ts_code : string
        src : sina ，dc

    return
    -------
        DataFrame 实时交易数据
              属性:0：name，股票名字
            1：open，今日开盘价
            2：pre_close，昨日收盘价
            3：price，当前价格
            4：high，今日最高价
            5：low，今日最低价
            6：bid，竞买价，即“买一”报价
            7：ask，竞卖价，即“卖一”报价
            8：volumn，成交量 maybe you need do volumn/100
            9：amount，成交金额（元 CNY）
            10：b1_v，委买一（笔数 bid volume）
            11：b1_p，委买一（价格 bid price）
            12：b2_v，“买二”
            13：b2_p，“买二”
            14：b3_v，“买三”
            15：b3_p，“买三”
            16：b4_v，“买四”
            17：b4_p，“买四”
            18：b5_v，“买五”
            19：b5_p，“买五”
            20：a1_v，委卖一（笔数 ask volume）
            21：a1_p，委卖一（价格 ask price）
            ...
            30：date，日期；
            31：time，时间；
        """
    symbols = symbol_verify(ts_code)
    if src == "sina":
        return get_realtime_quotes_sina(symbols)
    else:
        return get_realtime_quotes_dc(symbols)


sina_stock_code = {}


def get_realtime_quotes_sina(symbol="688553"):  # "688553"
    global sina_stock_code
    symbols = []
    syms = []
    for i in [j for j in symbol.split(",")]:
        s = i.split(".")
        sina_stock_code[s[0]] = s[1].upper()
        symbols.append(s[1].lower() + s[0])
        syms.append(s[0])
    # symbols = re.search(r"(\d+)", str(symbols), re.S | re.M).group(1)
    symbols_list = ''
    if isinstance(symbols, list) or isinstance(symbols, set) or \
            isinstance(symbols, tuple) or isinstance(symbols, pd.Series):
        for code in symbols:
            symbols_list += code + ','
    else:
        symbols_list = symbols
    symbols_list = symbols_list[:-1] if len(symbols_list) > 8 else symbols_list
    root_url = ct.LIVE_DATA_URL % (ct.P_TYPE['http'], ct.DOMAINS['sinahq'], _get_current_timestamp(), symbols_list)
    response = requests.get(root_url,
                            headers={
                                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
                                'host': 'hq.sinajs.cn',
                                'referer': 'https://finance.sina.com.cn/'
                            })
    text = response.content.decode('GBK')
    reg = re.compile(r'\="(.*?)\";')
    data = reg.findall(text)
    data_list = []
    syms_list = []
    for index, row in enumerate(data):
        if len(row) > 1:
            data_list.append([astr for astr in row.split(',')[:33]])
            syms_list.append(syms[index])
    if len(syms_list) == 0:
        return None
    df = pd.DataFrame(data_list, columns=ct.LIVE_DATA_COLS)
    df = df.drop('s', axis=1)
    df['code'] = syms_list
    ls = [cls for cls in df.columns if '_v' in cls]
    for txt in ls:
        df[txt] = df[txt].map(lambda x: x[:-2])
    df.columns = rtqv.LIVE_DATA_COLS
    df["TS_CODE"] = df["TS_CODE"].apply(format_sina_stock_code)
    df["DATE"] = df["DATE"].apply(format_date_str)
    new_order = rtqv.LIVE_DATA_COLS_REINDEX
    df = df[new_order]
    # 指定要转换为 float 类型的列
    cols_to_convert = ['OPEN', 'PRE_CLOSE', 'PRICE', 'HIGH', 'LOW', 'BID', 'ASK',
                       'VOLUME', 'AMOUNT', 'B1_V', 'B1_P',
                       'B2_V', 'B2_P', 'B3_V', 'B3_P', 'B4_V', 'B4_P', 'B5_V', 'B5_P', 'A1_V', 'A1_P', 'A2_V',
                       'A2_P',
                       'A3_V', 'A3_P', 'A4_V', 'A4_P', 'A5_V', 'A5_P']
    # 使用 to_numeric() 方法将指定的列转换为 float 类型，并将非数值类型的数据转换为 NaN
    df[cols_to_convert] = df[cols_to_convert].apply(pd.to_numeric, errors='coerce')
    # 使用 fillna() 方法将 NaN 值替换为 0
    df_filled = df.fillna(0)
    return df_filled


def format_sina_stock_code(x):
    ts_code = f"{x}.{sina_stock_code[x]}"
    return ts_code


def format_date_str(date_str):
    return date_str.replace("-", "")


@require_permission(event_name="realtime_list", event_detail="A股所有实时交易数据")
def realtime_list(src: Optional[str] = None, interval: Optional[int] = 3,
                  page_count: Optional[int] = None, proxies: Optional[dict] = {}) -> pd.DataFrame:
    """
    沪深京 A 股 all -实时行情
    @param src:  数据源 新浪sina |东方财富 dc
    @param interval:  分页采集时间间隔（默认3秒翻译一夜）
    @param page_count:  限制抓取的页数（仅对新浪有效）
    @param proxies:  设置代理 防止被封禁
    @return: 按涨跌幅 倒序排序
    -------
        DataFrame 实时交易数据
        东方财富：
            2、代码:TS_CODE
            3、名称:NAME
            4、最新价:CLOSE
            5、涨跌幅:PCT_CHANGE
            6、涨跌额:CHANGE
            7、成交量:VOLUME
            8、成交额:AMOUNT
            9、振幅:SWING
            10、最高:HIGH
            11、最低:LOW
            12、今开:OPEN
            13、昨收:PRICE
            14、量比:VOL_RATIO
            15、换手率:TURNOVER_RATE
            16、市盈率-动态:PE
            17、市净率:PB
            18、总市值:TOTAL_MV
            19、流通市值:FLOAT_MV
            20、涨速:RISE
            21、5分钟涨跌:5MIN
            22、60日涨跌幅:60DAY
            23、年初至今涨跌幅:1YEAR
        新浪财经：
            1、代码:TS_CODE
            2、名称:NAME
            3、最新价:CLOSE
            4、涨跌额:CHANGE
            5、涨跌幅:PCT_CHANGE
            6、买入:BUY
            7、卖出:SALE
            8、昨收:CLOSE
            9、今开:OPEN
            10、最高:HIGH
            11、最低:LOW
            12、成交量:VOLUME
            13、成交额:AMOUNT
            14、时间戳:TIME

    """
    if src == "dc":
        return get_stock_all_a_dc(page_count, proxies)
    elif src == "sina":
        return get_stock_all_a_sina(interval, page_count, proxies)
    else:
        return get_stock_all_a_dc(page_count, proxies)


def get_stock_all_a_dc(page_count: Optional[int] = None,
                       proxies: Optional[dict] = {}) -> pd.DataFrame:
    """
    东方财富网-沪深京 A 股-实时行情
    https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    :return: 实时行情
    :rtype: pandas.DataFrame
        1、序号:RANK
        2、代码:TS_CODE
        3、名称:NAME
        4、最新价:PRICE
        5、涨跌幅:PCT_CHANGE
        6、涨跌额:CHANGE
        7、成交量:VOLUME
        8、成交额:AMOUNT
        9、振幅:SWING
        10、最高:HIGH
        11、最低:LOW
        12、今开:OPEN
        13、昨收:CLOSE
        14、量比:VOL_RATIO
        15、换手率:TURNOVER_RATE
        16、市盈率-动态:PE
        17、市净率:PB
        18、总市值:TOTAL_MV
        19、流通市值:FLOAT_MV
        20、涨速:RISE
        21、5分钟涨跌:5MIN
        22、60日涨跌幅:60DAY
        23、年初至今涨跌幅:1YEAR
    """
    dfs = []
    for page in range(1,500):
        url = "http://82.push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": page,
            "pz": "200",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
            "_": "1623833739532",
        }
        if page_count:
            params["pz"] = 20
        r = requests.get(url, params=params, proxies=proxies)
        data_json = r.json()
        if not data_json["data"]:
            break
            # return pd.DataFrame()
        temp_df = pd.DataFrame(data_json["data"]["diff"])
        temp_df.columns = [
            "_",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "换手率",
            "市盈率-动态",
            "量比",
            "5分钟涨跌",
            "代码",
            "_",
            "名称",
            "最高",
            "最低",
            "今开",
            "昨收",
            "总市值",
            "流通市值",
            "涨速",
            "市净率",
            "60日涨跌幅",
            "年初至今涨跌幅",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        ]
        temp_df.reset_index(inplace=True)
        # temp_df["index"] = temp_df.index + 1
        # temp_df.rename(columns={"index": "序号"}, inplace=True)
        temp_df = temp_df[
            [
                # "序号",
                "代码",
                "名称",
                "最新价",
                "涨跌幅",
                "涨跌额",
                "成交量",
                "成交额",
                "振幅",
                "最高",
                "最低",
                "今开",
                "昨收",
                "量比",
                "换手率",
                "市盈率-动态",
                "市净率",
                "总市值",
                "流通市值",
                "涨速",
                "5分钟涨跌",
                "60日涨跌幅",
                "年初至今涨跌幅",
            ]
        ]

        temp_df["代码"] = temp_df["代码"].apply(format_stock_code)
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
        temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
        temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["市盈率-动态"] = pd.to_numeric(temp_df["市盈率-动态"], errors="coerce")
        temp_df["市净率"] = pd.to_numeric(temp_df["市净率"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["涨速"] = pd.to_numeric(temp_df["涨速"], errors="coerce")
        temp_df["5分钟涨跌"] = pd.to_numeric(temp_df["5分钟涨跌"], errors="coerce")
        temp_df["60日涨跌幅"] = pd.to_numeric(temp_df["60日涨跌幅"], errors="coerce")
        temp_df["年初至今涨跌幅"] = pd.to_numeric(temp_df["年初至今涨跌幅"], errors="coerce")
        temp_df.columns = [
            # "RANK",
            "TS_CODE",
            "NAME",
            "PRICE",
            "PCT_CHANGE",
            "CHANGE",
            "VOLUME",
            "AMOUNT",
            "SWING",
            "HIGH",
            "LOW",
            "OPEN",
            "CLOSE",
            "VOL_RATIO",
            "TURNOVER_RATE",
            "PE",
            "PB",
            "TOTAL_MV",
            "FLOAT_MV",
            "RISE",
            "5MIN",
            "60DAY",
            "1YEAR",
        ]
        # 指定要转换为 float 类型的列
        cols_to_convert = ['PRICE', 'PCT_CHANGE', 'CHANGE', "VOLUME", "AMOUNT", "SWING",
                           'HIGH', "LOW", "OPEN", "CLOSE", "VOL_RATIO", "TURNOVER_RATE", "PE", "PB", "TOTAL_MV", "FLOAT_MV",
                           "RISE", "5MIN", "60DAY", "1YEAR"
                           ]
        # 使用 to_numeric() 方法将指定的列转换为 float 类型，并将非数值类型的数据转换为 NaN
        temp_df[cols_to_convert] = temp_df[cols_to_convert].apply(pd.to_numeric, errors='coerce')
        dfs.append(
            temp_df
        )
        if page_count:
            break
    result_df = pd.concat(dfs, ignore_index=True)
    # 使用 fillna() 方法将 NaN 值替换为 0
    df_filled = result_df.fillna(0)
    df_sorted = df_filled.sort_values(by='PCT_CHANGE', ascending=False).reset_index(drop=True)
    return df_sorted


def _get_zh_a_page_count() -> int:
    """
    所有股票的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 需要采集的股票总页数
    :rtype: int
    """
    res = requests.get(zh_sina_a_stock_count_url)
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def get_stock_all_a_sina(interval: Optional[int] = 3, page_count: Optional[int] = None,
                         proxies: Optional[dict] = {}) -> pd.DataFrame:
    """
    新浪财经-所有 A 股的实时行情数据; 重复运行本函数会被新浪暂时封 IP
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :param interval:请求间隔时间
    :param page_count:限制抓取页数
    :param proxies: 代理ip {}
    :return: 所有股票的实时行情数据
    :rtype: pandas.DataFrame
        1、代码:TS_CODE
        2、名称:NAME
        3、最新价:PRICE
        4、涨跌额:CHANGE
        5、涨跌幅:PCT_CHANGE
        6、买入:BUY
        7、卖出:SALE
        8、昨收:CLOSE
        9、今开:OPEN
        10、最高:HIGH
        11、最低:LOW
        12、成交量:VOLUME
        13、成交额:AMOUNT
        14、时间戳:TIME

    """
    big_df = pd.DataFrame()
    if not page_count:
        page_count = _get_zh_a_page_count()
    zh_sina_stock_payload_copy = zh_sina_a_stock_payload.copy()
    for page in tqdm(
            range(1, page_count + 1), leave=False, desc="Please wait for a moment"
    ):
        zh_sina_stock_payload_copy.update({"page": page})
        r = requests.get(
            zh_sina_a_stock_url, headers=zh_sina_a_stock_headers,
            cookies=zh_sina_a_stock_cookies,
            params=zh_sina_stock_payload_copy,
            proxies=proxies,
        )
        data_json = r.json()
        big_df = pd.concat(
            [big_df, pd.DataFrame(data_json)], ignore_index=True
        )

        time.sleep(interval)

    big_df = big_df.astype(
        {
            "trade": "float",
            "pricechange": "float",
            "changepercent": "float",
            "buy": "float",
            "sell": "float",
            "settlement": "float",
            "open": "float",
            "high": "float",
            "low": "float",
            "volume": "float",
            "amount": "float",
            "per": "float",
            "pb": "float",
            "mktcap": "float",
            "nmc": "float",
            "turnoverratio": "float",
        }
    )
    big_df.columns = [
        "代码",
        "_",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "买入",
        "卖出",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "时间戳",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "时间戳",
        ]
    ]
    big_df["代码"] = big_df["代码"].apply(format_stock_code)
    big_df.columns = [
        "TS_CODE",
        "NAME",
        "PRICE",
        "CHANGE",
        "PCT_CHANGE",
        "BUY",
        "SALE",
        "CLOSE",
        "OPEN",
        "HIGH",
        "LOW",
        "VOLUME",
        "AMOUNT",
        "TIME",

    ]
    df_sorted = big_df.sort_values(by='PCT_CHANGE', ascending=False).reset_index(drop=True)
    return df_sorted


def get_realtime_quotes_dc(symbols="688553"):
    """
    https://quote.eastmoney.com/sh601096.html
    """
    symbols = str(symbols).split(",")[0]
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    symbol = re.search(r"(\d+)", symbols, re.S | re.M).group(1)
    # print(symbol)
    params = {
        "invt": "2",
        "fltt": "1",
        # "cb": "jQuery35108939078769986013_1701853424476",
        "fields": "f58,f734,f107,f57,f43,f59,f169,f301,f60,f170,f152,f177,f111,f46,f44,f45,f47,f260,f48,f261,f279,f277,f278,f288,f19,f17,f531,f15,f13,f11,f20,f18,f16,f14,f12,f39,f37,f35,f33,f31,f40,f38,f36,f34,f32,f211,f212,f213,f214,f215,f210,f209,f208,f207,f206,f161,f49,f171,f50,f86,f84,f85,f168,f108,f116,f167,f164,f162,f163,f92,f71,f117,f292,f51,f52,f191,f192,f262,f294,f295,f748,f747",
        "secid": f"0.{symbol}",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "wbp2u": "|0|0|0|web",
        "_": _get_current_timestamp()
    }
    if not verify_stock_or_index(symbols):
        params["secid"] = f"1.{symbol}"
    # print(params["secid"])
    response = requests.get(url, headers=rtqv.dc_cookies, cookies=rtqv.dc_headers, params=params)
    data_info = response.json()["data"]
    if not data_info:
        return pd.DataFrame()
    name = data_info["f58"]
    open = data_info["f46"]  # / 100
    high = data_info["f44"]  # / 100
    pre_close = data_info["f60"]  # / 100
    low =  data_info["f45"] # / 100
    price = data_info["f43"]  # / 100 if data_info["f43"] != "-" else ""
    b5_v = format_str_to_float(data_info["f12"])
    b5_p = data_info["f11"]  # / 100 if data_info["f11"] != "-" else ""
    b4_v = format_str_to_float(data_info["f14"])
    b4_p = data_info["f13"]  # / 100 if data_info["f13"] != "-" else ""
    b3_v = format_str_to_float(data_info["f16"])
    b3_p = data_info["f15"]  # / 100 if data_info["f15"] != "-" else ""
    b2_v = format_str_to_float(data_info["f18"])
    b2_p = data_info["f17"]  # / 100 if data_info["f17"] != "-" else ""
    b1_v = format_str_to_float(data_info["f20"])
    b1_p = data_info["f19"]  # / 100 if data_info["f19"] != "-" else ""
    a5_v = format_str_to_float(data_info["f32"])
    a5_p = data_info["f31"]  # / 100 if data_info["f31"] != "-" else ""
    a4_v = format_str_to_float(data_info["f34"])
    a4_p = data_info["f33"]  # / 100 if data_info["f33"] != "-" else ""
    a3_v = format_str_to_float(data_info["f36"])
    a3_p = data_info["f35"]  # / 100 if data_info["f35"] != "-" else ""
    a2_v = format_str_to_float(data_info["f38"])
    a2_p = data_info["f37"]  # / 100 if data_info["f38"] != "-" else ""
    a1_v = format_str_to_float(data_info["f40"])
    a1_p = data_info["f39"]  # / 100 if data_info["f39"] != "-" else ""
    date_time = timestemp_to_time(data_info["f86"])
    date = date_time[0:10]
    times = date_time[10:]
    volume = format_str_to_float(data_info["f47"])
    amount = format_str_to_float(data_info["f48"])
    bid = format_str_to_float(data_info["f19"])
    ask = format_str_to_float(data_info["f39"])
    code = symbols
    data_list = [[name, open, pre_close, price, high, low, bid, ask, volume, amount,
                  b1_v, b1_p, b2_v, b2_p, b3_v, b3_p, b4_v, b4_p, b5_v, b5_p,
                  a1_v, a1_p, a2_v, a2_p, a3_v, a3_p, a4_v, a4_p, a5_v, a5_p, date, times, code]]
    df = pd.DataFrame(data_list, columns=rtqv.LIVE_DATA_COLS)
    df["DATE"] = df["DATE"].apply(format_date_str)
    df["ASK"] = df["ASK"].apply(format_dc_str)
    df["OPEN"] = df["OPEN"].apply(format_dc_str)
    df["HIGH"] = df["HIGH"].apply(format_dc_str)
    df["LOW"] = df["LOW"].apply(format_dc_str)
    df["PRE_CLOSE"] = df["PRE_CLOSE"].apply(format_dc_str)
    df["BID"] = df["BID"].apply(format_dc_str)
    df["A1_P"] = df["A1_P"].apply(format_dc_str)
    df["A2_P"] = df["A2_P"].apply(format_dc_str)
    df["A3_P"] = df["A3_P"].apply(format_dc_str)
    df["A4_P"] = df["A4_P"].apply(format_dc_str)
    df["A5_P"] = df["A5_P"].apply(format_dc_str)
    df["PRICE"] = df["PRICE"].apply(format_dc_str)
    df["B1_P"] = df["B1_P"].apply(format_dc_str)
    df["B2_P"] = df["B2_P"].apply(format_dc_str)
    df["B3_P"] = df["B3_P"].apply(format_dc_str)
    df["B4_P"] = df["B4_P"].apply(format_dc_str)
    df["B5_P"] = df["B5_P"].apply(format_dc_str)
    new_order = rtqv.LIVE_DATA_COLS_REINDEX
    df = df[new_order]
    return df


def format_dc_str(x):
    return float(x / 100) if x != "-" else 0


def format_str_to_float(x):
    try:
        return float(x) if x != "" else 0
    except:
        return 0


if __name__ == '__main__':
    # df = realtime_quote(ts_code="000688.SH,000010.SH,000012.SH,399005.SZ", src="sina")
    # df = realtime_list(src="dc", page_count=1)
    df = realtime_list(src="sina")
    print(df)
    # ts_code = '399005.SZ'
    # ts_code = '000001.SZ'
    # # ts_code = '836149.BJ'
    # # ts_code = '600000.SH'
    # # ts_code = '000001.SH'
    # # ts_code = '000010.SH'
    # ts_code = '600148.SH'
    # df = realtime_quote(src="dc", ts_code=ts_code)
    # print(df)


