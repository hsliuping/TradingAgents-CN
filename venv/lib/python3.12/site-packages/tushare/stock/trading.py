# -*- coding:utf-8 -*- 
"""
交易数据接口 
Created on 2014/07/31
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
from __future__ import division

import time
import json
import lxml.html
from lxml import etree
import pandas as pd
import numpy as np
import datetime
from tushare.stock import cons as ct
import re
from tushare.util import dateu as du
from tushare.util.formula import MA
import os
from tushare.util.conns import get_apis, close_apis
from tushare.stock.fundamental import get_stock_basics
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request
v = pd.__version__ 
if int(v.split('.')[1])>=25 or int(v.split('.')[0])>0:
    from io import StringIO
else:    
    from pandas.compat import StringIO

def get_hist_data(code=None, start=None, end=None,
                  ktype='D', retry_count=3,
                  pause=0.001):
    """
        获取个股历史交易记录
    Parameters
    ------
      code:string
                  股票代码 e.g. 600848
      start:string
                  开始日期 format：YYYY-MM-DD 为空时取到API所提供的最早日期数据
      end:string
                  结束日期 format：YYYY-MM-DD 为空时取到最近一个交易日数据
      ktype：string
                  数据类型，D=日k线 W=周 M=月 5=5分钟 15=15分钟 30=30分钟 60=60分钟，默认为D
      retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
      pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    return
    -------
      DataFrame
          属性:日期 ，开盘价， 最高价， 收盘价， 最低价， 成交量， 价格变动 ，涨跌幅，5日均价，10日均价，20日均价，5日均量，10日均量，20日均量，换手率
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    symbol = ct._code_to_symbol(code)
    url = ''
    if ktype.upper() in ct.K_LABELS:
        url = ct.DAY_PRICE_URL%(ct.P_TYPE['http'], ct.DOMAINS['ifeng'],
                                ct.K_TYPE[ktype.upper()], symbol)
    elif ktype in ct.K_MIN_LABELS:
        url = ct.DAY_PRICE_MIN_URL%(ct.P_TYPE['http'], ct.DOMAINS['ifeng'],
                                    symbol, ktype)
    else:
        raise TypeError('ktype input error.')
    
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(url)
            lines = urlopen(request, timeout = 10).read()
            if len(lines) < 15: #no data
                return None
        except Exception as e:
            print(e)
        else:
            js = json.loads(lines.decode('utf-8') if ct.PY3 else lines)
            cols = []
            if (code in ct.INDEX_LABELS) & (ktype.upper() in ct.K_LABELS):
                cols = ct.INX_DAY_PRICE_COLUMNS
            else:
                cols = ct.DAY_PRICE_COLUMNS
            if len(js['record'][0]) == 14:
                cols = ct.INX_DAY_PRICE_COLUMNS
            df = pd.DataFrame(js['record'], columns=cols)
            if ktype.upper() in ['D', 'W', 'M']:
                df = df.applymap(lambda x: x.replace(u',', u''))
                df[df==''] = 0
            for col in cols[1:]:
                df[col] = df[col].astype(float)
            if start is not None:
                df = df[df.date >= start]
            if end is not None:
                df = df[df.date <= end]
            if (code in ct.INDEX_LABELS) & (ktype in ct.K_MIN_LABELS):
                df = df.drop('turnover', axis=1)
            df = df.set_index('date')
            df = df.sort_index(ascending = False)
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def _parsing_dayprice_json(types=None, page=1):
    """
           处理当日行情分页数据，格式为json
     Parameters
     ------
        pageNum:页码
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
    """
    ct._write_console()
    request = Request(ct.SINA_DAY_PRICE_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                 ct.PAGES['jv'], types, page))
    text = urlopen(request, timeout=10).read()
    if text == 'null':
        return None
    reg = re.compile(r'\,(.*?)\:') 
    text = reg.sub(r',"\1":', text.decode('gbk') if ct.PY3 else text) 
    text = text.replace('"{symbol', '{"symbol')
    text = text.replace('{symbol', '{"symbol"')
    text = text.replace('""', '"')
    text = text.replace('"{"', '{"')
    if ct.PY3:
#         text = text.decode('GBK')
        js = json.dumps(text)
    else:
        js = json.dumps(text, encoding='GBK')
    js = json.loads(js)
    df = pd.DataFrame(pd.read_json(js, dtype={'code':object}),
                      columns=ct.DAY_TRADING_COLUMNS)
    df = df.drop('symbol', axis=1)
#     df = df.ix[df.volume > 0]
    return df


def get_tick_data(code=None, date=None, retry_count=3, pause=0.001,
                  src='sn'):
    """
        获取分笔数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
        date:string
                  日期 format: YYYY-MM-DD
        retry_count : int, 默认 3
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
        src : 数据源选择，可输入sn(新浪)、tt(腾讯)、nt(网易)，默认sn
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
    """
    if (src.strip() not in ct.TICK_SRCS):
        print(ct.TICK_SRC_ERROR)
        return None
    symbol = ct._code_to_symbol(code)
    symbol_dgt = ct._code_to_symbol_dgt(code)
    datestr = date.replace('-', '')
    url = {
            ct.TICK_SRCS[0] : ct.TICK_PRICE_URL % (ct.P_TYPE['http'], ct.DOMAINS['sf'], ct.PAGES['dl'],
                                date, symbol),
            ct.TICK_SRCS[1] : ct.TICK_PRICE_URL_TT % (ct.P_TYPE['http'], ct.DOMAINS['tt'], ct.PAGES['idx'],
                                           symbol, datestr),
            ct.TICK_SRCS[2] : ct.TICK_PRICE_URL_NT % (ct.P_TYPE['http'], ct.DOMAINS['163'], date[0:4], 
                                         datestr, symbol_dgt)
             }
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            if src == ct.TICK_SRCS[2]:
                df = pd.read_excel(url[src])
                df.columns = ct.TICK_COLUMNS
            else:
                re = Request(url[src])
                lines = urlopen(re, timeout=10).read()
                lines = lines.decode('GBK') 
                if len(lines) < 20:
                    return None
                df = pd.read_table(StringIO(lines), names=ct.TICK_COLUMNS,
                                   skiprows=[0])      
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_sina_dd(code=None, date=None, vol=400, retry_count=3, pause=0.001):
    """
        获取sina大单数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
        date:string
                  日期 format：YYYY-MM-DD
        retry_count : int, 默认 3
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:股票代码    股票名称    交易时间    价格    成交量    前一笔价格    类型（买、卖、中性盘）
    """
    if code is None or len(code)!=6 or date is None:
        return None
    symbol = ct._code_to_symbol(code)
    vol = vol*100
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            re = Request(ct.SINA_DD % (ct.P_TYPE['http'], ct.DOMAINS['vsf'], ct.PAGES['sinadd'],
                                symbol, vol, date))
            lines = urlopen(re, timeout=10).read()
            lines = lines.decode('GBK') 
            if len(lines) < 100:
                return None
            df = pd.read_csv(StringIO(lines), names=ct.SINA_DD_COLS,
                               skiprows=[0])    
            if df is not None:
                df['code'] = df['code'].map(lambda x: x[2:])
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_today_tickss(code=None, retry_count=3, pause=0.001):
    """
        获取当日分笔明细数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
        retry_count : int, 默认 3
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
    """
    if code is None or len(code)!=6 :
        return None
    symbol = ct._code_to_symbol(code)
    date = du.today()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.TODAY_TICKS_PAGE_URL % (ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                       ct.PAGES['jv'], date,
                                                       symbol))
            data_str = urlopen(request, timeout=10).read()
            data_str = data_str.decode('GBK')
            data_str = data_str[1:-1]
            data_str = eval(data_str, type('Dummy', (dict,), 
                                           dict(__getitem__ = lambda s, n:n))())
            data_str = json.dumps(data_str)
            data_str = json.loads(data_str)
            pages = len(data_str['detailPages'])
            data = pd.DataFrame()
            ct._write_head()
            for pNo in range(1, pages+1):
                data = data.append(_today_ticks(symbol, date, pNo,
                                                retry_count, pause), ignore_index=True)
        except Exception as er:
            print(str(er))
        else:
            return data
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def _today_ticks(symbol, tdate, pageNo, retry_count, pause):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            html = lxml.html.parse(ct.TODAY_TICKS_URL % (ct.P_TYPE['http'],
                                                         ct.DOMAINS['vsf'], ct.PAGES['t_ticks'],
                                                         symbol, tdate, pageNo
                                ))  
            res = html.xpath('//table[@id=\"datatbl\"]/tbody/tr')
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            sarr = sarr.replace('--', '0')
            df = pd.read_html(StringIO(sarr), parse_dates=False)[0]
            df.columns = ct.TODAY_TICK_COLUMNS
            df['pchange'] = df['pchange'].map(lambda x : x.replace('%', ''))
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)
        
    
def get_today_all():
    """
        一次性获取最近一个日交易日所有股票的交易数据
    return
    -------
      DataFrame
           属性：代码，名称，涨跌幅，现价，开盘价，最高价，最低价，最日收盘价，成交量，换手率，成交额，市盈率，市净率，总市值，流通市值
    """
    ct._write_head()
    df = _parsing_dayprice_json('hs_a', 1)
    if df is not None:
        for i in range(2, ct.PAGE_NUM[1]):
            newdf = _parsing_dayprice_json('hs_a', i)
            if newdf.shape[0] > 0:
                df = df.append(newdf, ignore_index=True)
            else:
                break
    df = df.append(_parsing_dayprice_json('shfxjs', 1),
                                               ignore_index=True)
    return df


def get_realtime_quotes(symbols=None):
    """
        获取实时交易数据 getting real time quotes data
       用于跟踪交易情况（本次执行的结果-上一次执行的数据）
    Parameters
    ------
        symbols : string, array-like object (list, tuple, Series).
        
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
    symbols_list = ''
    if isinstance(symbols, list) or isinstance(symbols, set) or isinstance(symbols, tuple) or isinstance(symbols, pd.Series):
        for code in symbols:
            symbols_list += ct._code_to_symbol(code) + ','
    else:
        symbols_list = ct._code_to_symbol(symbols)
    symbols_list = symbols_list[:-1] if len(symbols_list) > 8 else symbols_list 
    request = Request(ct.LIVE_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['sinahq'], _random(), symbols_list), headers={
        'host': 'hq.sinajs.cn',
        'referer': 'https://finance.sina.com.cn/'
    })
    text = urlopen(request,timeout=10).read()
    text = text.decode('GBK')
    reg = re.compile(r'\="(.*?)\";')
    data = reg.findall(text)
    regSym = re.compile(r'(?:sh|sz)(.*?)\=')
    syms = regSym.findall(text)
    data_list = []
    syms_list = []
    for index, row in enumerate(data):
        if len(row)>1:
            data_list.append([astr for astr in row.split(',')[:33]])
            syms_list.append(syms[index])
    if len(syms_list) == 0:
        return None
    df = pd.DataFrame(data_list, columns=ct.LIVE_DATA_COLS)
    df = df.drop('s', axis=1)
    df['code'] = syms_list
    ls = [cls for cls in df.columns if '_v' in cls]
    for txt in ls:
        df[txt] = df[txt].map(lambda x : x[:-2])
    return df


def get_h_data(code, start=None, end=None, autype='qfq',
               index=False, retry_count=3, pause=0.001, drop_factor=True):
    '''
    获取历史复权数据
    Parameters
    ------
      code:string
                  股票代码 e.g. 600848
      start:string
                  开始日期 format：YYYY-MM-DD 为空时取当前日期
      end:string
                  结束日期 format：YYYY-MM-DD 为空时取去年今日
      autype:string
                  复权类型，qfq-前复权 hfq-后复权 None-不复权，默认为qfq
      retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
      pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
      drop_factor : bool, 默认 True
                是否移除复权因子，在分析过程中可能复权因子意义不大，但是如需要先储存到数据库之后再分析的话，有该项目会更加灵活
    return
    -------
      DataFrame
          date 交易日期 (index)
          open 开盘价
          high  最高价
          close 收盘价
          low 最低价
          volume 成交量
          amount 成交金额
    '''
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    start = du.today_last_year() if start is None else start
    end = du.today() if end is None else end
    qs = du.get_quarts(start, end)
    qt = qs[0]
    ct._write_head()
    data = _parse_fq_data(_get_index_url(index, code, qt), index,
                          retry_count, pause)
    if data is None:
        data = pd.DataFrame()
    if len(qs)>1:
        for d in range(1, len(qs)):
            qt = qs[d]
            ct._write_console()
            df = _parse_fq_data(_get_index_url(index, code, qt), index,
                                retry_count, pause)
            if df is None:  # 可能df为空，退出循环
                break
            else:
                data = data.append(df, ignore_index = True)
    if len(data) == 0 or len(data[(data.date >= start) & (data.date <= end)]) == 0:
        return pd.DataFrame()
    data = data.drop_duplicates('date')
    if index:
        data = data[(data.date >= start) & (data.date <= end)]
        data = data.set_index('date')
        data = data.sort_index(ascending = False)
        return data
    if autype == 'hfq':
        if drop_factor:
            data = data.drop('factor', axis=1)
        data = data[(data.date >= start) & (data.date <= end)]
        for label in ['open', 'high', 'close', 'low']:
            data[label] = data[label].map(ct.FORMAT)
            data[label] = data[label].astype(float)
        data = data.set_index('date')
        data = data.sort_index(ascending = False)
        return data
    else:
        if autype == 'qfq':
            if drop_factor:
                data = data.drop('factor', axis = 1)
            df = _parase_fq_factor(code, start, end)
            df = df.drop_duplicates('date')
            df = df.sort_values('date', ascending = False)
            firstDate = data.head(1)['date']
            frow = df[df.date == firstDate[0]]
            rt = get_realtime_quotes(code)
            if rt is None:
                return pd.DataFrame()
            if ((float(rt['high']) == 0) & (float(rt['low']) == 0)):
                preClose = float(rt['pre_close'])
            else:
                if du.is_holiday(du.today()):
                    preClose = float(rt['price'])
                else:
                    if (du.get_hour() > 9) & (du.get_hour() < 18):
                        preClose = float(rt['pre_close'])
                    else:
                        preClose = float(rt['price'])
            
            rate = float(frow['factor']) / preClose
            data = data[(data.date >= start) & (data.date <= end)]
            for label in ['open', 'high', 'low', 'close']:
                data[label] = data[label] / rate
                data[label] = data[label].map(ct.FORMAT)
                data[label] = data[label].astype(float)
            data = data.set_index('date')
            data = data.sort_index(ascending = False)
            return data
        else:
            for label in ['open', 'high', 'close', 'low']:
                data[label] = data[label] / data['factor']
            if drop_factor:
                data = data.drop('factor', axis=1)
            data = data[(data.date >= start) & (data.date <= end)]
            for label in ['open', 'high', 'close', 'low']:
                data[label] = data[label].map(ct.FORMAT)
            data = data.set_index('date')
            data = data.sort_index(ascending = False)
            data = data.astype(float)
            return data


def _parase_fq_factor(code, start, end):
    symbol = ct._code_to_symbol(code)
    request = Request(ct.HIST_FQ_FACTOR_URL%(ct.P_TYPE['http'],
                                             ct.DOMAINS['vsf'], symbol))
    text = urlopen(request, timeout=10).read()
    text = text[1:len(text)-1]
    text = text.decode('utf-8') if ct.PY3 else text
    text = text.replace('{_', '{"')
    text = text.replace('total', '"total"')
    text = text.replace('data', '"data"')
    text = text.replace(':"', '":"')
    text = text.replace('",_', '","')
    text = text.replace('_', '-')
    text = json.loads(text)
    df = pd.DataFrame({'date':list(text['data'].keys()), 'factor':list(text['data'].values())})
    df['date'] = df['date'].map(_fun_except) # for null case
    if df['date'].dtypes == np.object:
        df['date'] = pd.to_datetime(df['date'])
    df = df.drop_duplicates('date')
    df['factor'] = df['factor'].astype(float)
    return df


def _fun_except(x):
    if len(x) > 10:
        return x[-10:]
    else:
        return x


def _parse_fq_data(url, index, retry_count, pause):
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(url)
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath('//table[@id=\"FundHoldSharesTable\"]')
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            if sarr == '':
                return None
            df = pd.read_html(sarr, skiprows = [0, 1])[0]
            if len(df) == 0:
                return pd.DataFrame()
            if index:
                df.columns = ct.HIST_FQ_COLS[0:7]
            else:
                df.columns = ct.HIST_FQ_COLS
            if df['date'].dtypes == np.object:
                df['date'] = pd.to_datetime(df['date'])
            df = df.drop_duplicates('date')
        except ValueError as e:
            # 时间较早，已经读不到数据
            return None
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_index():
    """
    获取大盘指数行情
    return
    -------
      DataFrame
          code:指数代码
          name:指数名称
          change:涨跌幅
          open:开盘价
          preclose:昨日收盘价
          close:收盘价
          high:最高价
          low:最低价
          volume:成交量(手)
          amount:成交金额（亿元）
    """
    request = Request(ct.INDEX_HQ_URL%(ct.P_TYPE['http'],
                                             ct.DOMAINS['sinahq']))
    text = urlopen(request, timeout=10).read()
    text = text.decode('GBK')
    text = text.replace('var hq_str_sh', '').replace('var hq_str_sz', '')
    text = text.replace('";', '').replace('"', '').replace('=', ',')
    text = '%s%s'%(ct.INDEX_HEADER, text)
    df = pd.read_csv(StringIO(text), sep=',', thousands=',')
    df['change'] = (df['close'] / df['preclose'] - 1 ) * 100
    df['amount'] = df['amount'] / 100000000
    df['change'] = df['change'].map(ct.FORMAT)
    df['amount'] = df['amount'].map(ct.FORMAT4)
    df = df[ct.INDEX_COLS]
    df['code'] = df['code'].map(lambda x:str(x).zfill(6))
    df['change'] = df['change'].astype(float)
    df['amount'] = df['amount'].astype(float)
    return df
 

def _get_index_url(index, code, qt):
    if index:
        url = ct.HIST_INDEX_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                              code, qt[0], qt[1])
    else:
        url = ct.HIST_FQ_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                              code, qt[0], qt[1])
    return url


def get_k_data(code=None, start='', end='',
                  ktype='D', autype='qfq', 
                  index=False,
                  retry_count=3,
                  pause=0.001):
    """
    获取k线数据
    ---------
    Parameters:
      code:string
                  股票代码 e.g. 600848
      start:string
                  开始日期 format：YYYY-MM-DD 为空时取上市首日
      end:string
                  结束日期 format：YYYY-MM-DD 为空时取最近一个交易日
      autype:string
                  复权类型，qfq-前复权 hfq-后复权 None-不复权，默认为qfq
      ktype：string
                  数据类型，D=日k线 W=周 M=月 5=5分钟 15=15分钟 30=30分钟 60=60分钟，默认为D
      retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
      pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    return
    -------
      DataFrame
          date 交易日期 (index)
          open 开盘价
          high  最高价
          close 收盘价
          low 最低价
          volume 成交量
          amount 成交额
          turnoverratio 换手率
          code 股票代码
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    symbol = ct.INDEX_SYMBOL[code] if index else ct._code_to_symbol(code)
    url = ''
    dataflag = ''
    autype = '' if autype is None else autype
    if (start is not None) & (start != ''):
        end = du.today() if end is None or end == '' else end
    if ktype.upper() in ct.K_LABELS:
        fq = autype if autype is not None else ''
        if code[:1] in ('1', '5') or index:
            fq = ''
        kline = '' if autype is None else 'fq'
        if (start is None or start == '') & (end is None or end == ''):
            urls = [ct.KLINE_TT_URL%(ct.P_TYPE['http'], ct.DOMAINS['tt'],
                                    kline, fq, symbol, 
                                    ct.TT_K_TYPE[ktype.upper()], start, end,
                                    fq, _random(17))]
        else:
            years = du.tt_dates(start, end)
            urls = []
            for year in years:
                startdate = str(year) + '-01-01'
                enddate = str(year+1) + '-12-31'
                url = ct.KLINE_TT_URL%(ct.P_TYPE['http'], ct.DOMAINS['tt'],
                                    kline, fq+str(year), symbol, 
                                    ct.TT_K_TYPE[ktype.upper()], startdate, enddate,
                                    fq, _random(17))
                urls.append(url)
        dataflag = '%s%s'%(fq, ct.TT_K_TYPE[ktype.upper()])
    elif ktype in ct.K_MIN_LABELS:
        urls = [ct.KLINE_TT_MIN_URL%(ct.P_TYPE['http'], ct.DOMAINS['tt'],
                                    symbol, ktype, ktype,
                                    _random(16))]
        dataflag = 'm%s'%ktype
    else:
        raise TypeError('ktype input error.')
    data = pd.DataFrame()
    for url in urls:
        data = data.append(_get_k_data(url, dataflag, 
                                       symbol, code,
                                       index, ktype,
                                       retry_count, pause), 
                           ignore_index=True)
    if ktype not in ct.K_MIN_LABELS:
        if ((start is not None) & (start != '')) & ((end is not None) & (end != '')):
            if data.empty==False:       
                data = data[(data.date >= start) & (data.date <= end)]
    return data
    raise IOError(ct.NETWORK_URL_ERROR_MSG)
    

def _get_k_data(url, dataflag='',
                symbol='',
                code = '',
                index = False,
                ktype = '',
                retry_count=3,
                pause=0.001):
    for _ in range(retry_count):
            time.sleep(pause)
            try:
                request = Request(url)
                lines = urlopen(request, timeout = 10).read()
                if len(lines) < 100: #no data
                    return None
            except Exception as e:
                print(e)
            else:
                lines = lines.decode('utf-8') if ct.PY3 else lines
                lines = lines.split('=')[1]
                reg = re.compile(r',{"nd.*?}') 
                lines = re.subn(reg, '', lines) 
                js = json.loads(lines[0])
                dataflag = dataflag if dataflag in list(js['data'][symbol].keys()) else ct.TT_K_TYPE[ktype.upper()]
                if len(js['data'][symbol][dataflag]) == 0:
                    return None
                if len(js['data'][symbol][dataflag][0]) == 6:
                    df = pd.DataFrame(js['data'][symbol][dataflag], 
                                  columns = ct.KLINE_TT_COLS_MINS)
                else:
                    df = pd.DataFrame(js['data'][symbol][dataflag], 
                                  columns = ct.KLINE_TT_COLS)
                df['code'] = symbol if index else code
                if ktype in ct.K_MIN_LABELS:
                    df['date'] = df['date'].map(lambda x: '%s-%s-%s %s:%s'%(x[0:4], x[4:6], 
                                                                            x[6:8], x[8:10], 
                                                                            x[10:12]))
                for col in df.columns[1:6]:
                    df[col] = df[col].astype(float)
                return df

def get_hists(symbols, start=None, end=None,
                  ktype='D', retry_count=3,
                  pause=0.001):
    """
    批量获取历史行情数据，具体参数和返回数据类型请参考get_hist_data接口
    """
    df = pd.DataFrame()
    if isinstance(symbols, list) or isinstance(symbols, set) or isinstance(symbols, tuple) or isinstance(symbols, pd.Series):
        for symbol in symbols:
            data = get_hist_data(symbol, start=start, end=end,
                                 ktype=ktype, retry_count=retry_count,
                                 pause=pause)
            data['code'] = symbol
            df = df.append(data, ignore_index=True)
        return df
    else:
        return None
  
  
def get_day_all(date=None):
    """
    获取每日收盘行情
    Parameters:
    -------------
    date:交易日期，格式:YYYY-MM-DD
    
    Return:
    -------------
    DataFrame
    code 代码, name 名称, p_change 涨幅%,
    price 现价, change 涨跌, open 今开, high 最高,
    low 最低, preprice 昨收, pe 市盈(动),
    volratio 量比, turnover 换手%, range 振幅%%,
    volume 总量, selling 内盘, buying 外盘,
    amount 总金额, totals 总股本(万), industry 细分行业,
    area 地区, floats 流通股本(万), fvalues 流通市值,
    abvalues AB股总市值, avgprice 均价, strength 强弱度%,
    activity 活跃度, avgturnover 笔换手, attack 攻击波%,
    interval3 近3月涨幅 ，interval 近6月涨幅
    """
    wdate = du.last_tddate() if date is None else date
    wdate = wdate.replace('-', '')
    if wdate < '20170614':
        return None
    datepre = '' if date is None else wdate[0:4] + wdate[4:6] + '/'
    df = pd.read_csv(ct.ALL_DAY_FILE%(datepre, \
                                      'hq' if date is None else wdate), \
                                      dtype={'code':'object'})
    return df


def get_dt_time(t):
    tstr = str(t)[:-2]
    tstr = tstr.replace('-', '').replace(':', '')
    return tstr


def bar2h5(market='', date='', freq='D', asset='E', filepath=''):
    cons = get_apis()
    stks = get_stock_basics()
    fname = "%s%s%sbar%s.h5"%(filepath, market, date, freq)
    store = pd.HDFStore(fname, "a")
    if market in ['SH', 'SZ']:
        if market == 'SH':
            stks = stks.loc[stks.index.str[0]=='6', :]
        elif market == 'SZ':
            stks = stks.loc[stks.index.str[0]!='6', :]
        else:
            stks = ''
        market = 1 if market == 'SH' else 0
        for stk in stks.index:
            symbol = '%s.SH'%stk
            if 'min' in freq:
                df = bar(stk, conn=cons, start_date=date, end_date=date, freq=freq, 
                             market=market, asset=asset)
                df['Time'] = df.index
                df['Time'] = df['Time'].apply(get_dt_time) 
                df.index = df['Time']
                df.drop(['code','Time'], axis = 1, inplace=True)    
                df.rename(columns={'open':'OPEN'}, inplace=True) 
                df.rename(columns={'close':'CLOSE'}, inplace=True)
                df.rename(columns={'low':'LOW'}, inplace=True)
                df.rename(columns={'high':'HIGH'}, inplace=True)
                df.rename(columns={'vol':'VOLUME'}, inplace=True) 
                df.rename(columns={'amount':'TURNOVER'}, inplace=True) 
                df.loc[:,'HIGH'] =  df.loc[:,'HIGH'].astype("int64")
                df.loc[:,'LOW'] =  df.loc[:,'LOW'].astype("int64")
                df.loc[:,'OPEN'] =  df.loc[:,'OPEN'].astype("int64")
                df.loc[:,'CLOSE'] =  df.loc[:,'CLOSE'].astype("int64")
                df.loc[:,'VOLUME'] =  df.loc[:,'VOLUME'].astype("int64")
                df.loc[:,'TURNOVER'] =  df.loc[:,'TURNOVER'].astype("int64")    
                df.loc[:,'OPEN'] *= 10000   
                df.loc[:,'CLOSE'] *= 10000    
                df.loc[:,'HIGH'] *= 10000    
                df.loc[:,'LOW'] *= 10000
                df.loc[:,'ASKPRICE1']  = 0
                df.loc[:,'ASKPRICE2']  = 0
                df.loc[:,'ASKPRICE3']  = 0
                df.loc[:,'ASKPRICE4']  = 0
                df.loc[:,'ASKPRICE5']  = 0
                df.loc[:,'ASKPRICE6']  = 0
                df.loc[:,'ASKPRICE7']  = 0
                df.loc[:,'ASKPRICE8']  = 0
                df.loc[:,'ASKPRICE9']  = 0
                df.loc[:,'ASKPRICE10'] = 0    
                df.loc[:,'BIDPRICE1']  = 0
                df.loc[:,'BIDPRICE2']  = 0
                df.loc[:,'BIDPRICE3']  = 0
                df.loc[:,'BIDPRICE4']  = 0
                df.loc[:,'BIDPRICE5']  = 0
                df.loc[:,'BIDPRICE6']  = 0
                df.loc[:,'BIDPRICE7']  = 0
                df.loc[:,'BIDPRICE8']  = 0
                df.loc[:,'BIDPRICE9']  = 0
                df.loc[:,'BIDPRICE10'] = 0    
                df.loc[:,'ASKVOL1']  = 0
                df.loc[:,'ASKVOL2']  = 0
                df.loc[:,'ASKVOL3']  = 0
                df.loc[:,'ASKVOL4']  = 0
                df.loc[:,'ASKVOL5']  = 0
                df.loc[:,'ASKVOL6']  = 0
                df.loc[:,'ASKVOL7']  = 0
                df.loc[:,'ASKVOL8']  = 0
                df.loc[:,'ASKVOL9']  = 0
                df.loc[:,'ASKVOL10'] = 0    
                df.loc[:,'BIDVOL1']  = 0
                df.loc[:,'BIDVOL2']  = 0
                df.loc[:,'BIDVOL3']  = 0
                df.loc[:,'BIDVOL4']  = 0
                df.loc[:,'BIDVOL5']  = 0
                df.loc[:,'BIDVOL6']  = 0
                df.loc[:,'BIDVOL7']  = 0
                df.loc[:,'BIDVOL8']  = 0
                df.loc[:,'BIDVOL9']  = 0
                df.loc[:,'BIDVOL10'] = 0    
                df.loc[:,'VWAP'] = 0.0
                df.loc[:,'VOL30']=0.0
                df.loc[:,'TOTAL_VOLUME']=0.0
                df.loc[:,'TOTAL_TURNOVER']=0.0
                df.loc[:,'INTEREST']=0.0
                print(df)
#             if market == 1 and stk[0] == '6':
#                 df = bar(stk, conn=cons, start_date=date, end_date=date, freq=freq, market=market, asset=asset)
                
            store[symbol] = df
    
    store.close()
    close_apis(cons)
 

def bar(code, conn=None, start_date=None, end_date=None, freq='D', asset='E', 
           market='',
           adj = None,
           ma = [],
           factors = [],
           retry_count = 3):
    """
    BAR数据
    Parameters:
    ------------
    code:证券代码，支持股票,ETF/LOF,期货/期权,港股
    con:服务器连接 ，通过ts.api()或者ts.xpi()获得
    start_date:开始日期  YYYY-MM-DD/YYYYMMDD
    end_date:结束日期 YYYY-MM-DD/YYYYMMDD
    freq:支持1/5/15/30/60分钟,周/月/季/年
    asset:证券类型 E:股票和交易所基金，INDEX:沪深指数,X:期货/期权/港股/中概美国/中证指数/国际指数
    market:市场代码，通过ts.get_markets()获取
    adj:复权类型,None不复权,qfq:前复权,hfq:后复权
    ma:均线,支持自定义均线频度，如：ma5/ma10/ma20/ma60/maN
    factors因子数据，目前支持以下两种：
        vr:量比,默认不返回，返回需指定：factor=['vr']
        tor:换手率，默认不返回，返回需指定：factor=['tor']
                    以上两种都需要：factor=['vr', 'tor']
    retry_count:网络重试次数
    
    Return
    ----------
    DataFrame
    code:代码
    open：开盘close/high/low/vol成交量/amount成交额/maN均价/vr量比/tor换手率
    
         期货(asset='X')
    code/open/close/high/low/avg_price：均价  position：持仓量  vol：成交总量
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    code = code.strip().upper()
    for _ in range(retry_count):
        try:
            if conn is None:
                print(ct.MSG_NOT_CONNECTED)
                return None
            api, xapi = conn
            ktype = freq.strip().upper()
            asset = asset.strip().upper()
            mkcode = _get_mkcode(code, asset=asset, xapi=xapi) if market == '' else market
            if asset in['E', 'INDEX']:
                func = getattr(api, ct.ASSET[asset])
            else:
                ktype = 'XD' if ktype == 'D' else ktype
                func = getattr(xapi, ct.ASSET['X'])
            if ktype in ct.KTYPE_LOW_COLS:
                data = pd.DataFrame()
                for i in range(100): 
                    ds = func(ct.KTYPE[ktype], mkcode, code, i * 800, 800)
                    df =  api.to_df(ds)
                    data = data.append(df) if i == 0 else df.append(data,  ignore_index=True)
                    if len(ds) < 800:
                        break
                data['datetime'] = data['datetime'].apply(lambda x: str(x[0:10]))
            if ktype in ct.KTYPE_ARR:
                data = pd.DataFrame()
                for i in range(100): 
                    ds = func(ct.KTYPE[ktype], mkcode, code, i * 800, 800)
                    df =  api.to_df(ds)
                    data = data.append(df) if i == 0 else df.append(data,  ignore_index=True)
                    if len(ds) < 800:
                        break
            data['datetime'] = pd.to_datetime(data['datetime'])
            data = data.assign(code=str(code)) \
                .set_index('datetime', drop=True, inplace=False) \
                .drop(ct.T_DROP_COLS, axis=1)[ None if start_date == '' else start_date : 
                                              None if end_date == '' else end_date]
            data = data.sort_index(ascending=False)
            if asset in['E', 'INDEX']:
                data = data[ct.BAR_E_COLS]
                if ktype in ct.KTYPE_ARR:
                    data['vol'] = data['vol'] / 100
            else:
                data = data[ct.BAR_X_COLS]
                if mkcode in [28, 29, 30, 47, 60]:
                    data.columns = ct.BAR_X_FUTURE_COLS
                    data = data[ct.BAR_X_FUTURE_RL_COLS]
                else:
                    data = data.drop(['price', 'position'], axis=1)
                    data.columns = ct.BAR_X_OTHER_COLS
            if asset == 'E':
                if adj is not None:
                    df = factor_adj(code)
                    if ktype in ct.KTYPE_LOW_COLS: 
                        data = data.merge(df, left_index=True, right_index=True)
                        data['adj_factor'] = data['adj_factor'].fillna(method='bfill')
                    else:
                        def get_val(day):
                            return df.loc[day]['adj_factor']
                        data['adj_factor'] = data.index.map(lambda x: get_val(str(x)[0:10]))
                    for col in ct.BAR_E_COLS[1:5]:
                        if adj == 'hfq':
                            data[col] = data[col] * data['adj_factor']
                        else:
                            data[col] = data[col] * data['adj_factor'] / float(df['adj_factor'][0])
                        data[col] = data[col].map(ct.FORMAT)
                    data = data.drop('adj_factor', axis=1)
                if factors is not None and len(factors) >0 :
                    if 'tor' in factors:
                        df = factor_shares(code)
                        if ktype in ct.KTYPE_LOW_COLS: 
                            data = data.merge(df, left_index=True, right_index=True)
                            data['floats'] = data['floats'].fillna(method='bfill')
                        else:
                            def get_val(day):
                                return df.loc[day]['floats']
                            data['floats'] = data.index.map(lambda x: get_val(str(x)[0:10]))
                        data['tor'] = data['vol'] / data['floats'] 
                        data['tor'] = data['tor'].map(ct.FORMAT)
                        data['tor'] = data['tor'].astype(float)
                        data = data.drop('floats', axis=1)
                    if 'vr' in factors:
                        data['vol5'] = MA(data['vol'], 5)
                        data['mean'] = data['vol5'].shift(-5)
                        data['vr'] = (data['vol'] / data['mean']).map(ct.FORMAT)
                        data['vr'] = data['vr'].astype(float)
                        data = data.drop(['vol5', 'mean'], axis=1)
            if ma is not None and len(ma) > 0:
                for a in ma:
                    if isinstance(a, int):
                        data['ma%s'%a] = MA(data['close'], a).map(ct.FORMAT).shift(-(a-1))
                        data['ma%s'%a] = data['ma%s'%a].astype(float)
            for col in ['open', 'high', 'low', 'close']:
                data[col] = data[col].astype(float)
            data['p_change'] = data['close'].pct_change(-1) * 100
            data['p_change'] = data['p_change'].map(ct.FORMAT).astype(float)
            return data
        except:
            return None
        else:
            data['p_change'] = data['close'].pct_change(-1) * 100
            data['p_change'] = data['p_change'].map(ct.FORMAT).astype(float)
            return data
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def _get_mkcode(code='', asset='E', xapi=None):
    mkcode = ''
    if asset == 'E':
        mkcode = ct._market_code(code)
    elif asset == 'INDEX':
        mkcode = ct._idx_market_code(code)
    else:
        if os.path.exists(ct.INST_PLK_F):
            mks = pd.read_pickle(ct.INST_PLK_F)
        else:
            mks = get_instrument(xapi)
            mks.to_pickle(ct.INST_PLK_F)
        mkcode = mks[mks.code == code]['market'].values[0]
    return mkcode


def tick(code, conn=None, date='', asset='E', market='', retry_count = 3):
    """
    tick数据
    Parameters:
    ------------
    code:证券代码，支持股票,ETF/LOF,期货/期权,港股
    conn:服务器连接 ，通过ts.api()或者ts.xpi()获得
    date:日期
    asset:证券品种，E:沪深交易所股票和基金, INDEX:沪深交易所指数， X:其他证券品种，大致如下：
                     支持的扩展行情包括(asset='X')：
                            郑州商品期权         OZ 大连商品期权         OD 上海商品期权         OS
                            上海个股期权         QQ 香港指数         FH 郑州商品         QZ 大连商品         QD 上海期货         QS
                            香港主板         KH 香港权证         KR 开放式基金         FU 货币型基金         FB
                            招商理财产品         LC 招商货币产品         LB 国际指数         FW 国内宏观指标         HG 中国概念股         CH
                            美股知名公司         MG B股转H股         HB 股份转让         SB 股指期货         CZ 香港创业板         KG 香港信托基金         KT
                             国债预发行         GY 主力期货合约         MA
                              中证指数         ZZ 港股通         GH
    market:市场代码，通过ts.get_markets()获取
                  
    Return
    ----------
    DataFrame
    date:日期
    time:时间
    price:成交价
    vol:成交量
    type:买卖方向，0-买入 1-卖出 2-集合竞价成交
            期货  0:开仓  1:多开   -1:空开
         期货多一列数据oi_change:增仓数据

    """
    code = code.strip().upper()
    date = int(date.replace('-', ''))
    today = int(str(du.today()).replace('-', ''))
    for _ in range(retry_count):
        try:
            if conn is None:
                print(ct.MSG_NOT_CONNECTED)
                return None
            api, xapi = conn
            data = pd.DataFrame()
            mkcode = _get_mkcode(code, asset=asset, xapi=xapi) if market == '' else market
            con = api if asset in['E', 'INDEX'] else xapi
            for i in range(200):
                if date == today:
                    ds = con.get_transaction_data(market=mkcode, code=code, start=i * 300, count=300)
                else:
                    ds = con.get_history_transaction_data(market=mkcode, code=code, date=date, start=i * 300, count=300)
                df =  api.to_df(ds)
                data = data.append(df) if i == 0 else df.append(data,  ignore_index=True)
                if len(ds) < 300:
                    break
            if asset in['E', 'INDEX']:
                data['date'] = date
                data['date'] = data['date'].map(lambda x: '%s-%s-%s '%(str(x)[0:4], str(x)[4:6], str(x)[6:8]))
                data['datetime'] = data['date'] + data['time']
                data = data[['datetime', 'price', 'vol', 'buyorsell']]
                data.columns = ['datetime', 'price', 'vol', 'type']
            else:
                if mkcode in [31, 71]:
                    if date == today:
                        data = data.drop(['hour', 'minute', 'nature_name', 'zengcang', 'direction', 
                                        'second', 'nature_mark', 'nature_value'], axis=1)
                    else:
                        data = data.drop(['hour', 'minute', 'nature_name', 'zengcang', 'direction'], axis=1)
                    data.loc[data.nature== 512, 'nature' ] = 2
                    data.loc[data.nature== 256, 'nature' ] = 1
                    data = data.sort_values('date')
                    data.columns = ['date', 'price', 'vol', 'type']
                elif mkcode in [28, 29, 30, 47, 60]:
                    if date == today:
                        data = data.drop(['hour', 'minute', 'nature', 'direction', 
                                            'second', 'nature_mark', 'nature_value'], axis=1)
                    else:
                        data = data.drop(['hour', 'minute', 'nature', 'direction'], axis=1)
                    data.columns = ['date', 'price', 'vol', 'oi_change', 'type']
                else:
                    data = data.drop(['hour', 'minute', 'nature_name', 'zengcang', 'direction', 'nature'], axis=1)
            
        except Exception as e:
            print(e)
        else:
            return data



def quotes(symbols, conn=None, asset='E', market=[], retry_count = 3):
    """
        获取实时快照
    Parameters
    ------
        symbols : string, array-like object (list, tuple, Series).
        
    return
    -------
        DataFrame 实时快照，5档行情
    """
    for _ in range(retry_count):
        try:
            if conn is None:
                print(ct.MSG_NOT_CONNECTED)
                return None
            api, xapi = conn
            data = pd.DataFrame()
            if isinstance(symbols, list) or isinstance(symbols, set) or isinstance(symbols, tuple) or isinstance(symbols, pd.Series):
                for code in symbols:
                    mkcode = _get_mkcode(code, asset=asset, xapi=xapi)
                    if asset == 'E':
                        df = api.to_df(api.get_security_quotes([(mkcode, code)]))
                    elif asset == 'INDEX':
                        df = api.to_df(api.get_security_quotes([(mkcode, code)]))
                    else:
                        df = xapi.to_df(xapi.get_instrument_quote(mkcode, code))
                    data = data.append(df)
            else:
                mkcode = _get_mkcode(symbols, asset=asset, xapi=xapi)
                if asset == 'E':
                    data = api.to_df(api.get_security_quotes([(mkcode, symbols)]))
                elif asset == 'INDEX':
                    data = api.to_df(api.get_security_quotes([(mkcode, symbols)]))
                else:
                    data = xapi.to_df(xapi.get_instrument_quote(mkcode, symbols))
            if asset in ['E', 'INDEX']:
                data = data.drop(['market', 'active1', 'active2', 'reversed_bytes0', 'reversed_bytes1', 'reversed_bytes2',
                                  'reversed_bytes3',
                                  'reversed_bytes4',
                                  'reversed_bytes5',
                                  'reversed_bytes6',
                                  'reversed_bytes7',
                                  'reversed_bytes8',
                                  'reversed_bytes9'], axis=1)
            else:
                data = data.drop(['market'], axis=1)
        except Exception as e:
            print(e)
        else:
            return data
    raise IOError(ct.NETWORK_URL_ERROR_MSG)



def get_security(api):
    """
            获取股票列表
    """
    data = []
    for p in range(100):
        ds = api.get_security_list(0, p*1000)
        data += ds
        if len(ds) < 1000:
            break
    data = api.to_df(data)
    return data


def reset_instrument(xapi=None):
    """
            重新设置本地证券列表
    """
    import tushare.util.conns as cs 
    xapi = cs.xapi_x() if xapi is None else xapi
    data=[]
    for i in range(200): 
        ds = xapi.get_instrument_info(i * 300, 300)
        data += ds
        if len(ds) < 300:
            break
    data = xapi.to_df(data)
    data.to_pickle(ct.INST_PLK_F)
    return data



def get_instrument(xapi=None):
    """
            获取证券列表
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    import tushare.util.conns as cs 
    xapi = cs.xapi_x() if xapi is None else xapi
    if xapi is None:
        print(ct.MSG_NOT_CONNECTED)
        return None
    data=[]
    for i in range(200): # range for python2/3
        ds = xapi.get_instrument_info(i * 300, 300)
        data += ds
        if len(ds) < 300:
            break
    data = xapi.to_df(data)
    return data


def get_today_ticks(code=None, retry_count=3, pause=0.001):
    """
        获取分笔数据
    Parameters
    ------
        code:string
                  股票代码 e.g. 600848
                  如遇网络等问题重复执行的次数
        pause : int, 默认 0
                 重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
        src : 数据源选择，可输入sn(新浪)、tt(腾讯)、nt(网易)，默认sn
     return
     -------
        DataFrame 当日所有股票交易数据(DataFrame)
              属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
    """
    url = 'http://push2ex.eastmoney.com/getStockFenShi?pagesize=6644&ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wzfscj&pageindex=0&id=%s&sort=1&ft=1&code=%s&market=1&_=%s'
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            re = Request(url%(code, code, _random()))
            lines = urlopen(re, timeout=10).read()
#             if ct.PY3:
#                 lines = lines.decode('GBK') 
            lines = json.loads(lines)
            lines = lines['data']['data']
            df = pd.DataFrame(lines)   
            df = df.rename(columns={'t': 'time', 'p': 'price', 'v': 'vol', 'bs': 'type'})
            df = df[['time', 'price', 'vol', 'type']]
            df['price'] = df['price'].map(lambda x: x/1000)
            df['type'] = df['type'].map(lambda x: bs_type[str(x)])
            df['time'] = df['time'].map(lambda x: str(x).zfill(6))
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)

bs_type = {'1':u'买入', 
           '2': u'卖出', 
           '4': u'-'}

def get_markets(xapi=None):
    """
            获取市场代码
    """
    if xapi is None:
        print(ct.MSG_NOT_CONNECTED)
        return None
    data = xapi.get_markets()
    data = xapi.to_df(data)
    return data
    
    
def factor_adj(code):
    df = pd.read_csv(ct.ADJ_FAC_URL%(ct.P_TYPE['http'],
                                             ct.DOMAINS['oss'], code))
    df = df.set_index('datetime')
    return df


def factor_shares(code):
    df = pd.read_csv(ct.SHS_FAC_URL%(ct.P_TYPE['http'],
                                             ct.DOMAINS['oss'], code))[['datetime', 'floats']]
    df = df.set_index('datetime')
    return df



def _random(n=13):
    from random import randint
    start = 10**(n-1)
    end = (10**n)-1
    return str(randint(start, end))


if __name__ == '__main__':
#     from tushare.util.conns import get_apis, close_apis
#     cons = get_apis()
#     df = bar('rb2001', conn=cons, asset='X', freq='1min')
#     print(df)
#     close_apis(cons)
#     df = get_tick_data('600848', src='sn', date='2020-04-10')
#     df = get_today_ticks(code='000001')
#     print(df)
#     df = get_today_ticks(code='600000')
#     print(df)
    
    df = get_realtime_quotes('600000')
    print(df)
    
