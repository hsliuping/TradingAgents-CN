# -*- coding:utf-8 -*-
"""
上海银行间同业拆放利率（Shibor）数据接口
Created on 2014/07/31
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
import pandas as pd
import numpy as np
from tushare.stock import cons as ct
from tushare.util import dateu as du
from tushare.util.netbase import Client
v = pd.__version__ 
if int(v.split('.')[1])>=25 or int(v.split('.')[0])>0:
    from io import StringIO
else:    
    from pandas.compat import StringIO

def shibor_data(year=None):
    """
    获取上海银行间同业拆放利率（Shibor）
    Parameters
    ------
      year:年份(int)
      
    Return
    ------
    date:日期
    ON:隔夜拆放利率
    1W:1周拆放利率
    2W:2周拆放利率
    1M:1个月拆放利率
    3M:3个月拆放利率
    6M:6个月拆放利率
    9M:9个月拆放利率
    1Y:1年拆放利率
    """
    year = du.get_year() if year is None else year
    lab = ct.SHIBOR_TYPE['Shibor']
    lab = lab.encode('utf-8') if ct.PY3 else lab
    try:
        clt = Client(url=ct.SHIBOR_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['shibor'],
                                               ct.PAGES['dw'], 'Shibor',
                                               year, lab,
                                               year))
        content = clt.gvalue()
        df = pd.read_excel(StringIO(content))
        df.columns = ct.SHIBOR_COLS
        df['date'] = df['date'].map(lambda x: x.date())
        if pd.__version__ < '0.21':
            df['date'] = df['date'].astype(np.datetime64)
        else:
            df['date'] = df['date'].astype('datetime64[D]')
        return df
    except:
        return None

def shibor_quote_data(year=None):
    """
    获取Shibor银行报价数据
    Parameters
    ------
      year:年份(int)
      
    Return
    ------
    date:日期
    bank:报价银行名称
    ON:隔夜拆放利率
    ON_B:隔夜拆放买入价
    ON_A:隔夜拆放卖出价
    1W_B:1周买入
    1W_A:1周卖出
    2W_B:买入
    2W_A:卖出
    1M_B:买入
    1M_A:卖出
    3M_B:买入
    3M_A:卖出
    6M_B:买入
    6M_A:卖出
    9M_B:买入
    9M_A:卖出
    1Y_B:买入
    1Y_A:卖出
    """
    year = du.get_year() if year is None else year
    lab = ct.SHIBOR_TYPE['Quote']
    lab = lab.encode('utf-8') if ct.PY3 else lab
    try:
        clt = Client(url=ct.SHIBOR_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['shibor'],
                                               ct.PAGES['dw'], 'Quote',
                                               year, lab,
                                               year))
        content = clt.gvalue()
        df = pd.read_excel(StringIO(content), skiprows=[0])
#         df.columns = ct.QUOTE_COLS
        df.columns = ct.SHIBOR_Q_COLS
        df['date'] = df['date'].map(lambda x: x.date())
        if pd.__version__ < '0.21':
            df['date'] = df['date'].astype(np.datetime64)
        else:
            df['date'] = df['date'].astype('datetime64[D]')
        return df
    except:
        return None

def shibor_ma_data(year=None):
    """
    获取Shibor均值数据
    Parameters
    ------
      year:年份(int)
      
    Return
    ------
    date:日期
       其它分别为各周期5、10、20均价
    """
    year = du.get_year() if year is None else year
    lab = ct.SHIBOR_TYPE['Tendency']
    lab = lab.encode('utf-8') if ct.PY3 else lab
    try:
        clt = Client(url=ct.SHIBOR_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['shibor'],
                                               ct.PAGES['dw'], 'Shibor_Tendency',
                                               year, lab,
                                               year))
        content = clt.gvalue()
        df = pd.read_excel(StringIO(content), skiprows=[0])
        df.columns = ct.SHIBOR_MA_COLS
        df['date'] = df['date'].map(lambda x: x.date())
        if pd.__version__ < '0.21':
            df['date'] = df['date'].astype(np.datetime64)
        else:
            df['date'] = df['date'].astype('datetime64[D]')
        return df
    except:
        return None


def lpr_data(year=None):
    """
    获取贷款基础利率（LPR）
    Parameters
    ------
      year:年份(int)
      
    Return
    ------
    date:日期
    1Y:1年贷款基础利率
    """
    year = du.get_year() if year is None else year
    lab = ct.SHIBOR_TYPE['LPR']
    lab = lab.encode('utf-8') if ct.PY3 else lab
    try:
        clt = Client(url=ct.SHIBOR_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['shibor'],
                                               ct.PAGES['dw'], 'LPR',
                                               year, lab,
                                               year))
        content = clt.gvalue()
        df = pd.read_excel(StringIO(content), skiprows=[0])
        df.columns = ct.LPR_COLS
        df['date'] = df['date'].map(lambda x: x.date())
        if pd.__version__ < '0.21':
            df['date'] = df['date'].astype(np.datetime64)
        else:
            df['date'] = df['date'].astype('datetime64[D]')
        return df
    except:
        return None
    

def lpr_ma_data(year=None):
    """
    获取贷款基础利率均值数据
    Parameters
    ------
      year:年份(int)
      
    Return
    ------
    date:日期
    1Y_5:5日均值
    1Y_10:10日均值
    1Y_20:20日均值
    """
    year = du.get_year() if year is None else year
    lab = ct.SHIBOR_TYPE['LPR_Tendency']
    lab = lab.encode('utf-8') if ct.PY3 else lab
    try:
        clt = Client(url=ct.SHIBOR_DATA_URL%(ct.P_TYPE['http'], ct.DOMAINS['shibor'],
                                               ct.PAGES['dw'], 'LPR_Tendency',
                                               year, lab,
                                               year))
        content = clt.gvalue()
        df = pd.read_excel(StringIO(content), skiprows=[0])
        df.columns = ct.LPR_MA_COLS
        df['date'] = df['date'].map(lambda x: x.date())
        if pd.__version__ < '0.21':
            df['date'] = df['date'].astype(np.datetime64)
        else:
            df['date'] = df['date'].astype('datetime64[D]')
        return df
    except:
        return None
    
    

