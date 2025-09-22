#!/usr/bin/env python
# -*- coding:utf-8 -*-
'''
Created on 2017年06月04日
@author: debugo
@contact: me@debugo.com
'''
import re
import datetime


CFFEX_DAILY_URL = 'http://www.cffex.com.cn/fzjy/mrhq/%s/%s/%s_1.csv'
SHFE_DAILY_URL = 'http://www.shfe.com.cn/data/dailydata/kx/kx%s.dat'
SHFE_VWAP_URL = 'http://www.shfe.com.cn/data/dailydata/ck/%sdailyTimePrice.dat'
DCE_DAILY_URL = 'http://www.dce.com.cn//publicweb/quotesdata/dayQuotesCh.html'
CZCE_DAILY_URL = 'http://www.czce.com.cn/portal/DFSStaticFiles/Future/%s/%s/FutureDataDaily.txt'
CZCE_OPTION_URL = 'http://www.czce.com.cn/portal/DFSStaticFiles/Option/%s/%s/OptionDataDaily.txt'
CFFEX_COLUMNS = ['open','high','low','volume','turnover','open_interest','close','settle','change1','change2']
CZCE_COLUMNS = ['pre_settle','open','high','low','close','settle','change1','change2','volume','open_interest','oi_chg','turnover','final_settle']
CZCE_OPTION_COLUMNS =  ['pre_settle', 'open', 'high', 'low', 'close', 'settle', 'change1', 'change2', 'volume', 'open_interest', 'oi_chg', 'turnover', 'delta', 'implied_volatility', 'exercise_volume']
SHFE_COLUMNS =  {'CLOSEPRICE': 'close',  'HIGHESTPRICE': 'high', 'LOWESTPRICE': 'low', 'OPENINTEREST': 'open_interest', 'OPENPRICE': 'open',  'PRESETTLEMENTPRICE': 'pre_settle', 'SETTLEMENTPRICE': 'settle',  'VOLUME': 'volume'}
SHFE_VWAP_COLUMNS = {':B1': 'date', 'INSTRUMENTID': 'symbol', 'TIME': 'time_range', 'REFSETTLEMENTPRICE': 'vwap'}
DCE_COLUMNS = ['open', 'high', 'low', 'close', 'pre_settle', 'settle', 'change1','change2','volume','open_interest','oi_chg','turnover']
DCE_OPTION_COLUMNS = ['open', 'high', 'low', 'close', 'pre_settle', 'settle', 'change1', 'change2', 'delta', 'volume', 'open_interest', 'oi_chg', 'turnover', 'exercise_volume']
OUTPUT_COLUMNS = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'turnover', 'settle', 'pre_settle', 'variety']
OPTION_OUTPUT_COLUMNS = ['symbol', 'date', 'open', 'high', 'low', 'close', 'pre_settle', 'settle', 'delta', 'volume', 'open_interest', 'oi_chg', 'turnover', 'implied_volatility', 'exercise_volume', 'variety']
CLOSE_LOC = 5
PRE_SETTLE_LOC = 11

FUTURE_SYMBOL_PATTERN = re.compile(r'(^[A-Za-z]{1,2})[0-9]+')
DATE_PATTERN = re.compile(r'^([0-9]{4})[-/]?([0-9]{2})[-/]?([0-9]{2})')
SIM_HAEDERS = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
DCE_HEADERS = {
    'cache-control': "no-cache",
    'postman-token': "153f42ca-148a-8f03-3302-8172cc4a5185"
}
def convert_date(date):
    """
    transform a date string to datetime.date object.
    :param day, string, e.g. 2016-01-01, 20160101 or 2016/01/01
    :return: object of datetime.date(such as 2016-01-01) or None
    """
    if isinstance(date, datetime.date):
        return date
    elif isinstance(date, str):
        match = DATE_PATTERN.match(date)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return datetime.date(year=int(groups[0]), month=int(groups[1]), day=int(groups[2]))
    return None

DCE_MAP =  {
    '豆一': 'A',
    '豆二': 'B',
    '豆粕': 'M',
    '豆油': 'Y',
    '棕榈油': 'P',
    '玉米': 'C',
    '玉米淀粉': 'CS',
    '鸡蛋': 'JD',
    '纤维板': 'FB',
    '胶合板': 'BB',
    '聚乙烯': 'L',
    '聚氯乙烯': 'V',
    '聚丙烯': 'PP',
    '焦炭': 'J',
    '焦煤': 'JM',
    '铁矿石': 'I'
}

FUTURE_CODE={ 
    'IH': ('CFFEX', '上证50指数', 300), 
    'IF': ('CFFEX', '沪深300指数', 300), 
    'IC': ('CFFEX', '中证500指数', 200), 
    'T': ('CFFEX', '10年期国债期货', 10000), 
    'TF': ('CFFEX', '5年期国债期货', 10000), 
    'CU': ('SHFE', '沪铜' ,5), 
    'AL': ('SHFE', '沪铝', 5), 
    'ZN': ('SHFE', '沪锌', 5), 
    'PB': ('SHFE', '沪铅', 5), 
    'NI': ('SHFE', '沪镍', 1), 
    'SN': ('SHFE', '沪锡', 1), 
    'AU': ('SHFE', '沪金', 1000), 
    'AG': ('SHFE', '沪银', 15), 
    'RB': ('SHFE', '螺纹钢', 10), 
    'WR': ('SHFE', '线材', 10), 
    'HC': ('SHFE', '热轧卷板', 10), 
    'FU': ('SHFE', '燃油', 50), 
    'BU': ('SHFE', '沥青', 10), 
    'RU': ('SHFE', '橡胶', 10), 
    'A': ('DCE', '豆一', 10), 
    'B': ('DCE', '豆二', 10), 
    'M': ('DCE', '豆粕', 10), 
    'Y': ('DCE', '豆油', 10), 
    'P': ('DCE', '棕榈油', 10), 
    'C': ('DCE', '玉米', 10), 
    'CS': ('DCE', '玉米淀粉', 10), 
    'JD': ('DCE', '鸡蛋', 5), 
    'FB': ('DCE', '纤维板', 500), 
    'BB': ('DCE', '胶合板', 500), 
    'L': ('DCE', '聚乙烯', 5), 
    'V': ('DCE', '聚氯乙烯', 5), 
    'PP': ('DCE', '聚丙烯', 5), 
    'J': ('DCE', '焦炭', 100), 
    'JM': ('DCE', '焦煤', 60), 
    'I': ('DCE', '铁矿石', 100), 
    'SR': ('CZCE', '白糖', 10), 
    'CF': ('CZCE', '棉花',5), 
    'PM': ('CZCE', '普麦',50), 
    'WH': ('CZCE', '强麦',20), 
    'OI': ('CZCE', '菜籽油',10), 
    'PTA': ('CZCE', 'PTA', 0), 
    'RI': ('CZCE', '早籼稻',20), 
    'LR': ('CZCE', '晚籼稻',20), 
    'MA': ('CZCE', '甲醇', 10), 
    'FG': ('CZCE', '玻璃', 20), 
    'RS': ('CZCE', '油菜籽', 10), 
    'RM': ('CZCE', '籽粕', 10), 
    'TC': ('CZCE', '动力煤', 200), 
    'ZC': ('CZCE', '动力煤', 100), 
    'JR': ('CZCE', '粳稻', 20), 
    'SF': ('CZCE', '硅铁', 5), 
    'SM': ('CZCE', '锰硅', 5) 
}
