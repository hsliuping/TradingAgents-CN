#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/21 15:00
Desc: 期货配置文件
"""

import datetime
import json
import os
import pickle
import re


futures_inventory_em_symbol_dict = {
    "a": "A",  # 豆一
    "ag": "AG",  # 沪银
    "al": "AL",  # 沪铝
    "ao": "AO",  # 氧化铝
    "AP": "AP",  # 苹果
    "au": "AU",  # 沪金
    "b": "B",  # 豆二
    "bb": None,  # 胶合板 (new中没有对应)
    "bc": None,  # 国际铜 (new中没有对应)
    "br": "BR",  # BR橡胶
    "bu": "BU",  # 沥青
    "c": "C",  # 玉米
    "CF": "CF",  # 棉花/郑棉
    "CJ": "CJ",  # 红枣
    "cs": "CS",  # 淀粉/玉米淀粉
    "cu": "CU",  # 沪铜
    "CY": "CY",  # 棉纱
    "eb": "EB",  # 苯乙烯
    "ec": "ec",  # 集运欧线/集运指数(欧线)
    "eg": "EG",  # 乙二醇
    "fb": None,  # 纤维板 (new中没有对应)
    "FG": "FG",  # 玻璃
    "fu": "FU",  # 燃料油/燃油
    "hc": "HC",  # 热卷
    "i": "I",  # 铁矿石
    "IC": "IC",  # 中证500
    "IF": "IF",  # 沪深300
    "IH": "IH",  # 上证50
    "IM": "IM",  # 中证1000
    "j": "J",  # 焦炭
    "jd": "JD",  # 鸡蛋
    "jm": "JM",  # 焦煤
    "JR": None,  # 粳稻 (new中没有对应)
    "l": "L",  # 塑料
    "lc": "lc",  # 碳酸锂
    "lh": "LH",  # 生猪
    "LR": None,  # 晚籼稻 (new中没有对应)
    "lu": "lu",  # LU燃油/低硫燃料油
    "m": "M",  # 豆粕
    "MA": "MA",  # 甲醇
    "ni": "NI",  # 沪镍/镍
    "nr": "nr",  # 20号胶
    "OI": "OI",  # 菜籽油/菜油
    "p": "P",  # 棕榈油/棕榈
    "pb": "PB",  # 沪铅
    "PF": "PF",  # 短纤
    "pg": "PG",  # 液化气/液化石油气
    "PK": "PK",  # 花生
    "PM": None,  # 普麦 (new中没有对应)
    "pp": "PP",  # 聚丙烯
    "PX": "PX",  # 对二甲苯
    "rb": "RB",  # 螺纹钢
    "RI": None,  # 早籼稻 (new中没有对应)
    "RM": "RM",  # 菜籽粕/菜粕
    "rr": None,  # 粳米 (new中没有对应)
    "RS": "RS",  # 油菜籽/菜籽
    "ru": "RU",  # 橡胶
    "SA": "SA",  # 纯碱
    "sc": None,  # 原油 (new中没有对应)
    "SF": "SF",  # 硅铁
    "SH": "SH",  # 烧碱
    "si": "si",  # 工业硅
    "SM": "SM",  # 锰硅
    "sn": "SN",  # 沪锡/锡
    "sp": "SP",  # 纸浆
    "SR": "SR",  # 白糖
    "ss": "SS",  # 不锈钢
    "T": "T",  # 十年国债/10年期国债
    "TA": "TA",  # PTA
    "TF": "TF",  # 五年国债/5年期国债
    "TL": "TL",  # 三十年国债/30年期国债期货
    "TS": "TS",  # 二年国债/2年期国债
    "UR": "UR",  # 尿素
    "v": "V",  # PVC
    "WH": None,  # 强麦 (new中没有对应)
    "wr": None,  # 线材 (new中没有对应)
    "y": "Y",  # 豆油
    "ZC": None,  # 动力煤 (new中没有对应)
    "zn": "ZN",  # 沪锌
}

hq_sina_spot_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "finance.sina.com.cn",
    "Pragma": "no-cache",
    "Referer": "https://finance.sina.com.cn/futuremarket/",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36",
}

# zh_sina_spot
zh_subscribe_exchange_symbol_url = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/view/js/qihuohangqing.js"
)
zh_match_main_contract_url = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/"
    "api/json_v2.php/Market_Center.getHQFuturesData"
)
zh_match_main_contract_payload = {
    "page": "1",
    "num": "5",
    "sort": "position",
    "asc": "0",
    "node": "001",
    "base": "futures",
}
zh_sina_spot_headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "hq.sinajs.cn",
    "Pragma": "no-cache",
    "Referer": "https://finance.sina.com.cn/futuremarket/",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/78.0.3904.97 Safari/537.36",
}

# 99 期货
inventory_temp_headers = {
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Cookie": "UM_distinctid=16c378978de5cc-02cfeac5f7869b-c343162-1fa400-16c378978df8d7; "
    "__utmz=181566328.1570520149.3.2.utmcsr=baidu|utmccn=(organic)|utmcmd=organic; "
    "ASP.NET_SessionId=wj5gxuzl3fvvr25503tquq55; __utmc=181566328; _fxaid=1D9A634AB9F5D026585"
    "6F7E85E7BC196%1D%2BOOl1inxPE7181fmKs5HCs%2BdLO%2Fq%2FbSvf46UVjo%2BE7w%3D%1DPYphpUa9OlzW"
    "UzatrOQTXLPOVillbwMhTIJas%2ByfkyVL2Hd5XA1GOSslksqDkMTccXvQ2duLNsc0CHT4789JrYNbakJrpzrxL"
    "nwtBC5GCTssKHGEpor6EwAZfWJgBUlCs4JYFcGUnh3jIO69A4LsOlRMOGf4c9cd%2FbohSjTx3VA%3D; __utma"
    "=181566328.1348268634.1564299852.1571066568.1571068391.7; tgw_l7_route=eb1311426274fc07"
    "631b2135a6431f7d; __utmt=1; __utmb=181566328.7.10.1571068391",
    "Host": "service.99qh.com",
    "Referer": "http://service.99qh.com/Storage/Storage.aspx?page=99qh",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
}

# 奇货可查
QHKC_INDEX_URL = "https://www.qhkch.com/ajax/index_show.php"
QHKC_INDEX_TREND_URL = "https://qhkch.com/ajax/indexes_trend.php"
QHKC_INDEX_PROFIT_LOSS_URL = "https://qhkch.com/ajax/indexes_profit_loss.php"
QHKC_FUND_BS_URL = "https://qhkch.com/ajax/fund_bs_pie.php"
QHKC_FUND_POSITION_URL = "https://qhkch.com/ajax/fund_position_pie.php"
QHKC_FUND_POSITION_CHANGE_URL = "https://qhkch.com/ajax/fund_position_chge_pie.php"
QHKC_FUND_DEAL_URL = "https://qhkch.com/ajax/fund_deal_pie.php"
QHKC_FUND_BIG_CHANGE_URL = "https://qhkch.com/ajax/fund_big_chge.php"
QHKC_TOOL_FOREIGN_URL = "https://qhkch.com/ajax/toolbox_foreign.php"
QHKC_TOOL_GDP_URL = "https://qhkch.com/dist/views/toolbox/gdp.html?v=1.10.7.1"

# 键值对: 键为交易所代码, 值为具体合约代码
market_exchange_symbols = {
    "cffex": ["IF", "IC", "IM", "IH", "T", "TF", "TS", "TL"],
    "dce": [
        "C",
        "CS",
        "A",
        "B",
        "M",
        "Y",
        "P",
        "FB",
        "BB",
        "JD",
        "L",
        "V",
        "PP",
        "J",
        "JM",
        "I",
        "EG",
        "RR",
        "EB",  # 20191009
        "PG",
        "LH",  # 20210108 生猪期货
        "LG",  # 20241118 原木期货
        "BZ",  # 20250708 纯苯期货
    ],
    "czce": [
        "WH",
        "PM",
        "CF",
        "SR",
        "TA",
        "OI",
        "RI",
        "MA",
        "ME",
        "FG",
        "RS",
        "RM",
        "ZC",
        "JR",
        "LR",
        "SF",
        "SM",
        "WT",
        "TC",
        "GN",
        "RO",
        "ER",
        "SRX",
        "SRY",
        "WSX",
        "WSY",
        "CY",
        "AP",
        "UR",
        "CJ",  # 红枣期货
        "SA",  # 纯碱期货
        "PK",  # 20210201 花生期货
        "PF",  # 短纤
        "PX",  # 对二甲苯
        "SH",  # 烧碱
        "PR",  # 瓶片
    ],
    "shfe": [
        "CU",
        "AL",
        "ZN",
        "PB",
        "NI",
        "SN",
        "AU",
        "AG",
        "RB",
        "WR",
        "HC",
        "FU",
        "BU",
        "RU",
        "SC",
        "NR",
        "SP",
        "SS",
        "LU",
        "BC",
        "AO",
        "BR",
        "EC",  # 集运指数
        "AD",  # 铸造铝合金期货
    ],
    "gfex": ["SI", "LC", "PS"],
}

contract_symbols = []
[contract_symbols.extend(i) for i in market_exchange_symbols.values()]

headers = {
    "Host": "www.czce.com.cn",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/56.0.2924.87 Safari/537.36",
    "DNT": "1",
    "Referer": "http://www.super-ping.com/?ping=www.google.com&locale=sc",
    "Accept-Encoding": "gzip, deflate, sdch",
    "Accept-Language": "zh-CN,zh;q=0.8,ja;q=0.6",
}

shfe_headers = {"User-Agent": "Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)"}

dce_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,"
    "*/*;q=0.8,application/signed-exchange;v=b3",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Content-Length": "71",
    "Content-Type": "application/x-www-form-urlencoded",
    "Host": "www.dce.com.cn",
    "Origin": "http://www.dce.com.cn",
    "Proxy-Connection": "keep-alive",
    "Referer": "http://www.dce.com.cn/publicweb/quotesdata/weekQuotesCh.html",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/77.0.3865.90 Safari/537.36",
}

SYS_SPOT_PRICE_URL = "http://www.100ppi.com/sf/day-{}.html"
SYS_SPOT_PRICE_LATEST_URL = "http://www.100ppi.com/sf/"

SHFE_VOL_RANK_URL = "https://tsite.shfe.com.cn/data/dailydata/kx/pm%s.dat"
SHFE_VOL_RANK_URL_20250701 = "https://www.shfe.com.cn/data/tradedata/future/dailydata/pm%s.dat"
CFFEX_VOL_RANK_URL = "http://www.cffex.com.cn/sj/ccpm/%s/%s/%s_1.csv"
DCE_VOL_RANK_URL_1 = (
    "http://www.dce.com.cn/publicweb/quotesdata/exportMemberDealPosiQuotesData.html?"
    "memberDealPosiQuotes.variety=%s&memberDealPosiQuotes.trade_type=0&contract.cont"
    "ract_id=%s&contract.variety_id=%s&year=%s&month=%s&day=%s&exportFlag=txt"
)
DCE_VOL_RANK_URL_2 = (
    "http://www.dce.com.cn/publicweb/quotesdata/memberDealPosiQuotes.html?memberDeal"
    "PosiQuotes.variety=%s&memberDealPosiQuotes.trade_type=0&contract.contract_id="
    "all&contract.variety_id=%s&year=%s&month=%s&day=%s"
)
CZCE_VOL_RANK_URL_1 = "http://www.czce.com.cn/cn/exchange/jyxx/pm/pm%s.html"
CZCE_VOL_RANK_URL_2 = "http://www.czce.com.cn/cn/exchange/%s/datatradeholding/%s.htm"
CZCE_VOL_RANK_URL_3 = (
    "http://www.czce.com.cn/cn/DFSStaticFiles/Future/%s/%s/FutureDataHolding.htm"
)

DCE_RECEIPT_URL = "http://www.dce.com.cn/publicweb/quotesdata/wbillWeeklyQuotes.html"

SHFE_RECEIPT_URL_1 = "http://tsite.shfe.com.cn/data/dailydata/%sdailystock.html"
SHFE_RECEIPT_URL_2 = "http://tsite.shfe.com.cn/data/dailydata/%sdailystock.dat"
SHFE_RECEIPT_URL_20250701 = "https://www.shfe.com.cn/data/tradedata/future/dailydata/%sdailystock.dat"
CZCE_RECEIPT_URL_1 = "http://www.czce.com.cn/cn/exchange/jyxx/sheet/sheet%s.html"
CZCE_RECEIPT_URL_2 = "http://www.czce.com.cn/cn/exchange/%s/datawhsheet/%s.htm"
CZCE_RECEIPT_URL_3 = (
    "http://www.czce.com.cn/cn/DFSStaticFiles/Future/%s/%s/FutureDataWhsheet.htm"
)

CFFEX_DAILY_URL = "http://www.cffex.com.cn/fzjy/mrhq/{}/{}/{}_1.csv"
SHFE_DAILY_URL = "http://tsite.shfe.com.cn/data/dailydata/kx/kx%s.dat"
SHFE_DAILY_URL_20250630 = "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx%s.dat"
SHFE_V_WAP_URL = "http://tsite.shfe.com.cn/data/dailydata/ck/%sdailyTimePrice.dat"
DCE_DAILY_URL = "http://www.dce.com.cn//publicweb/quotesdata/dayQuotesCh.html"
CZCE_DAILY_URL_1 = "http://www.czce.com.cn/cn/exchange/jyxx/hq/hq%s.html"
CZCE_DAILY_URL_2 = "http://www.czce.com.cn/cn/exchange/%s/datadaily/%s.txt"
CZCE_DAILY_URL_3 = (
    "http://www.czce.com.cn/cn/DFSStaticFiles/Future/%s/%s/FutureDataDaily.txt"
)

DATE_PATTERN = re.compile(r"^([0-9]{4})[-/]?([0-9]{2})[-/]?([0-9]{2})")
FUTURES_SYMBOL_PATTERN = re.compile(r"(^[A-Za-z]{1,2})[0-9]+")

CFFEX_COLUMNS = [
    "open",
    "high",
    "low",
    "volume",
    "turnover",
    "open_interest",
    "close",
    "settle",
    "change1",
    "change2",
]

CZCE_COLUMNS = [
    "pre_settle",
    "open",
    "high",
    "low",
    "close",
    "settle",
    "change1",
    "change2",
    "volume",
    "open_interest",
    "oi_chg",
    "turnover",
    "final_settle",
]

CZCE_COLUMNS_2 = [
    "pre_settle",
    "open",
    "high",
    "low",
    "close",
    "settle",
    "change1",
    "volume",
    "open_interest",
    "oi_chg",
    "turnover",
    "final_settle",
]

SHFE_COLUMNS = {
    "CLOSEPRICE": "close",
    "HIGHESTPRICE": "high",
    "LOWESTPRICE": "low",
    "OPENINTEREST": "open_interest",
    "OPENPRICE": "open",
    "PRESETTLEMENTPRICE": "pre_settle",
    "SETTLEMENTPRICE": "settle",
    "VOLUME": "volume",
}

SHFE_V_WAP_COLUMNS = {
    ":B1": "date",
    "INSTRUMENT_ID": "symbol",
    "TIME": "time_range",
    "REF_SETTLEMENT_PRICE": "v_wap",
}

DCE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "pre_settle",
    "settle",
    "change1",
    "change2",
    "volume",
    "open_interest",
    "oi_chg",
    "turnover",
]

DCE_OPTION_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "pre_settle",
    "settle",
    "change1",
    "change2",
    "delta",
    "volume",
    "open_interest",
    "oi_chg",
    "turnover",
    "exercise_volume",
]

OUTPUT_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "turnover",
    "settle",
    "pre_settle",
    "variety",
]

OPTION_OUTPUT_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "pre_settle",
    "settle",
    "delta",
    "volume",
    "open_interest",
    "oi_chg",
    "turnover",
    "implied_volatility",
    "exercise_volume",
    "variety",
]

DCE_MAP = {
    "大豆": "A",
    "豆一": "A",
    "豆二": "B",
    "豆粕": "M",
    "豆油": "Y",
    "棕榈油": "P",
    "玉米": "C",
    "玉米淀粉": "CS",
    "鸡蛋": "JD",
    "纤维板": "FB",
    "胶合板": "BB",
    "聚乙烯": "L",
    "聚氯乙烯": "V",
    "聚丙烯": "PP",
    "焦炭": "J",
    "焦煤": "JM",
    "铁矿石": "I",
    "乙二醇": "EG",
    "粳米": "RR",
    "苯乙烯": "EB",
    "液化石油气": "PG",
    "生猪": "LH",
    "原木": "LG",
    "纯苯": "BZ",
}


def convert_date(date):
    """
    transform a date string to datetime.date object
    :param date, string, e.g. 2016-01-01, 20160101 or 2016/01/01
    :return: object of datetime.date(such as 2016-01-01) or None
    """
    if isinstance(date, datetime.date):
        return date
    elif isinstance(date, str):
        match = DATE_PATTERN.match(date)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return datetime.date(
                    year=int(groups[0]),
                    month=int(groups[1]),
                    day=int(groups[2]),
                )
    return None


def get_json_path(name, module_file):
    """
    获取 JSON 配置文件的路径(从模块所在目录查找)
    :param name: 文件名
    :param module_file: filename
    :return: str json_file_path
    """
    module_folder = os.path.abspath(os.path.dirname(os.path.dirname(module_file)))
    module_json_path = os.path.join(module_folder, "file_fold", name)
    return module_json_path


def get_pk_path(name, module_file):
    """
    获取 pickle 配置文件的路径(从模块所在目录查找)
    :param name: 文件名
    :param module_file: filename
    :return: str json_file_path
    """
    module_folder = os.path.abspath(os.path.dirname(os.path.dirname(module_file)))
    module_json_path = os.path.join(module_folder, "file_fold", name)
    return module_json_path


def get_pk_data(file_name):
    """
    获取交易日历至 2019 年结束, 这里的交易日历需要按年更新
    :return: json
    """
    setting_file_name = file_name
    setting_file_path = get_pk_path(setting_file_name, __file__)
    return pickle.load(open(setting_file_path, "rb"))


def get_calendar():
    """
    获取交易日历, 这里的交易日历需要按年更新, 主要是从新浪获取的
    :return: 交易日历
    :rtype: json
    """
    setting_file_name = "calendar.json"
    setting_file_path = get_json_path(setting_file_name, __file__)
    with open(setting_file_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    return data_json


def last_trading_day(day):
    """
    获取前一个交易日
    :param day: "%Y%m%d" or  datetime.date()
    :return last_day: "%Y%m%d" or  datetime.date()
    """
    calendar = get_calendar()

    if isinstance(day, str):
        if day not in calendar:
            print("Today is not trading day：" + day)
            return False
        pos = calendar.index(day)
        last_day = calendar[pos - 1]
        return last_day

    elif isinstance(day, datetime.date):
        d_str = day.strftime("%Y%m%d")
        if d_str not in calendar:
            print("Today is not working day：" + d_str)
            return False
        pos = calendar.index(d_str)
        last_day = calendar[pos - 1]
        last_day = datetime.datetime.strptime(last_day, "%Y%m%d").date()
        return last_day


def get_latest_data_date(day):
    """
    获取最新的有数据的交易日
    :param day: datetime.datetime
    :return string YYYYMMDD
    """
    calendar = get_calendar()
    if day.strftime("%Y%m%d") in calendar:
        if day.time() > datetime.time(17, 0, 0):
            return day.strftime("%Y%m%d")
        else:
            return last_trading_day(day.strftime("%Y%m%d"))
    else:
        while day.strftime("%Y%m%d") not in calendar:
            day = day - datetime.timedelta(days=1)
        return day.strftime("%Y%m%d")


if __name__ == "__main__":
    d = datetime.datetime(2018, 10, 5, 17, 1, 0)
    print(get_latest_data_date(d))
