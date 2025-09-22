# -*- coding:utf-8 -*- 
"""
pro init 
Created on 2018/07/01
@author: Jimmy Liu
@group : https://tushare.pro
@contact: jimmysoa@sina.cn
"""
from __future__  import division
import datetime
from tushare.pro import client
from tushare.util import upass
from tushare.util.formula import MA

PRICE_COLS = ['open', 'close', 'high', 'low', 'pre_close']
FORMAT = lambda x: '%.2f' % x
FREQS = {'D': '1DAY',
         'W': '1WEEK',
         'Y': '1YEAR',
         }
FACT_LIST = {
           'tor': 'turnover_rate',
           'turnover_rate': 'turnover_rate',
           'vr': 'volume_ratio',
           'volume_ratio': 'volume_ratio',
           'pe': 'pe',
           'pe_ttm': 'pe_ttm',
        }
def pro_api(token='', timeout=30):
    """
    初始化pro API,第一次可以通过ts.set_token('your token')来记录自己的token凭证，临时token可以通过本参数传入
    """
    if token == '' or token is None:
        token = upass.get_token()
    if token is not None and token != '':
        pro = client.DataApi(token=token, timeout=timeout)
        return pro
    else:
        raise Exception('api init error.')


def pro_bar(ts_code='', api=None, start_date='', end_date='', freq='D', asset='E',
           exchange='',
           adj = None,
           ma = [],
           factors = None,
           adjfactor = False,
           offset = None,
           limit = None,
           fields = '',
           contract_type = '',
           retry_count = 3):
    """
    BAR数据
    Parameters:
    ------------
    ts_code:证券代码，支持股票,ETF/LOF,期货/期权,港股,数字货币
    start_date:开始日期  YYYYMMDD
    end_date:结束日期 YYYYMMDD
    freq:支持1/5/15/30/60分钟,周/月/季/年
    asset:证券类型 E:股票和交易所基金，I:沪深指数,C:数字货币,FT:期货 FD:基金/O期权/H港股/CB可转债
    exchange:市场代码，用户数字货币行情
    adj:复权类型,None不复权,qfq:前复权,hfq:后复权
    ma:均线,支持自定义均线频度，如：ma5/ma10/ma20/ma60/maN
    offset:开始行数（分页功能，从第几行开始取数据）
    limit: 本次提取数据行数
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

         期货(asset='FT')
    code/open/close/high/low/avg_price：均价  position：持仓量  vol：成交总量
    """
    if (ts_code=='' or ts_code is None) and (adj is not None):
        print('提取复权行情必须输入ts_code参数')
        return
    if len(freq.strip())>=3:
        freq = freq.strip().lower()
    else:
        freq = freq.strip().upper() if asset != 'C' else freq.strip().lower()

    if 'min' not in freq:
        today= datetime.datetime.today().date()
        today = str(today)[0:10]
        start_date = '' if start_date is None else start_date
        end_date = today if end_date == '' or end_date is None else end_date
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
    ts_code = ts_code.strip().upper() if asset != 'C' else ts_code.strip().lower()
    asset = asset.strip().upper()
    api = api if api is not None else pro_api()
    for _ in range(retry_count):
        try:
            if asset == 'E':
                if freq == 'D':
                    data = api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                    if factors is not None and len(factors) >0 :
                        ds = api.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)[['trade_date', 'turnover_rate', 'volume_ratio']]
                        ds = ds.set_index('trade_date')
                        data = data.set_index('trade_date')
                        data = data.merge(ds, left_index=True, right_index=True)
                        data = data.reset_index()
                        if ('tor' in factors) and ('vr' not in factors):
                            data = data.drop('volume_ratio', axis=1)
                        if ('vr' in factors) and ('tor' not in factors):
                            data = data.drop('turnover_rate', axis=1)
                if freq == 'W':
                    data = api.weekly(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'M':
                    data = api.monthly(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
                    data['trade_date'] = data['trade_time'].map(lambda x: x.replace('-', '')[0:8])
                    data['pre_close'] = data['close'].shift(-1)
                if adj is not None:
                    fcts = api.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)[['trade_date', 'adj_factor']]
                    if fcts.shape[0] == 0:
                        return None
                    data = data.set_index('trade_date', drop=False).merge(fcts.set_index('trade_date'), left_index=True, right_index=True, how='left')
                    if 'min' in freq:
                        data = data.sort_values('trade_time', ascending=False)
                    data['adj_factor'] = data['adj_factor'].fillna(method='bfill')
                    for col in PRICE_COLS:
                        if adj == 'hfq':
                            data[col] = data[col] * data['adj_factor']
                        if adj == 'qfq':
                            data[col] = data[col] * data['adj_factor'] / float(fcts['adj_factor'][0])
                        data[col] = data[col].map(FORMAT)
                        data[col] = data[col].astype(float)
                    if adjfactor is False:
                        data = data.drop('adj_factor', axis=1)
                    if 'min' not in freq:
                        data['change'] = data['close'] - data['pre_close']
                        data['pct_chg'] = data['change'] / data['pre_close'] * 100
                        data['pct_chg'] = data['pct_chg'].map(lambda x: FORMAT(x)).astype(float)
                    else:
                        data = data.drop(['trade_date', 'pre_close'], axis=1)
                else:
                    data['pre_close'] = data['close'].shift(-1)
                    data['change'] = data['close'] - data['pre_close']
                    data['pct_chg'] = data['change'] / data['pre_close'] * 100
                    data['pct_chg'] = data['pct_chg'].map(lambda x: FORMAT(x)).astype(float)
            elif asset == 'I':
                if freq == 'D':
                    data = api.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'W':
                    data = api.index_weekly(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'M':
                    data = api.index_monthly(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'FT':
                if freq == 'D':
                    data = api.fut_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, exchange=exchange, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.ft_mins(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'O':
                if freq == 'D':
                    data = api.opt_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, exchange=exchange, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.opt_mins(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'CB':
                if freq == 'D':
                    data = api.cb_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
            elif asset == 'FD':
                if freq == 'D':
                    data = api.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            if asset == 'C':
                if freq == 'd':
                    freq = 'daily'
                elif freq == 'w':
                    freq = 'week'
                data = api.coinbar(exchange=exchange, symbol=ts_code, freq=freq, start_dae=start_date, end_date=end_date,
                                   contract_type=contract_type)
            if ma is not None and len(ma) > 0:
                for a in ma:
                    if isinstance(a, int):
                        data['ma%s'%a] = MA(data['close'], a).map(FORMAT).shift(-(a-1))
                        data['ma%s'%a] = data['ma%s'%a].astype(float)
                        data['ma_v_%s'%a] = MA(data['vol'], a).map(FORMAT).shift(-(a-1))
                        data['ma_v_%s'%a] = data['ma_v_%s'%a].astype(float)
            data = data.reset_index(drop=True)
        except Exception as e:
            print(e)
        else:
            if fields is not None and fields != '':
                f_list = [col.strip() for col in fields.split(',')]
                data = data[f_list]
            return data
    raise IOError('ERROR.')

def pro_api(token='', timeout=30):
    """
    初始化pro API,第一次可以通过ts.set_token('your token')来记录自己的token凭证，临时token可以通过本参数传入
    """
    if token == '' or token is None:
        token = upass.get_token()
    if token is not None and token != '':
        pro = client.DataApi(token=token, timeout=timeout)
        return pro
    else:
        raise Exception('api init error.') 
        

def pro_bar_vip(ts_code='', api=None, start_date='', end_date='', freq='D', asset='E',
           exchange='',
           adj = None,
           ma = [],
           factors = None,
           adjfactor = False,
           offset = None,
           limit = None,
           fields = '',
           contract_type = '',
           retry_count = 3):
    """
    BAR数据
    Parameters:
    ------------
    ts_code:证券代码，支持股票,ETF/LOF,期货/期权,港股,数字货币
    start_date:开始日期  YYYYMMDD
    end_date:结束日期 YYYYMMDD
    freq:支持1/5/15/30/60分钟,周/月/季/年
    asset:证券类型 E:股票和交易所基金，I:沪深指数,C:数字货币,FT:期货 FD:基金/O期权/H港股/CB可转债
    exchange:市场代码，用户数字货币行情
    adj:复权类型,None不复权,qfq:前复权,hfq:后复权
    ma:均线,支持自定义均线频度，如：ma5/ma10/ma20/ma60/maN
    offset:开始行数（分页功能，从第几行开始取数据）
    limit: 本次提取数据行数
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
    
         期货(asset='FT')
    code/open/close/high/low/avg_price：均价  position：持仓量  vol：成交总量
    """
    if (ts_code=='' or ts_code is None) and (adj is not None):
        print('提取复权行情必须输入ts_code参数')
        return
    if len(freq.strip())>=3:
        freq = freq.strip().lower()
    else:
        freq = freq.strip().upper() if asset != 'C' else freq.strip().lower()
        
    if 'min' not in freq:
        today= datetime.datetime.today().date()
        today = str(today)[0:10]
        start_date = '' if start_date is None else start_date
        end_date = today if end_date == '' or end_date is None else end_date
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
    ts_code = ts_code.strip().upper() if asset != 'C' else ts_code.strip().lower()
    asset = asset.strip().upper()
    api = api if api is not None else pro_api()
    for _ in range(retry_count):
        try:
            if asset == 'E':
                if freq == 'D':
                    data = api.daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                    if factors is not None and len(factors) >0 :
                        ds = api.daily_basic_vip(ts_code=ts_code, start_date=start_date, end_date=end_date)[['trade_date', 'turnover_rate', 'volume_ratio']]
                        ds = ds.set_index('trade_date')
                        data = data.set_index('trade_date')
                        data = data.merge(ds, left_index=True, right_index=True)
                        data = data.reset_index()
                        if ('tor' in factors) and ('vr' not in factors):
                            data = data.drop('volume_ratio', axis=1)
                        if ('vr' in factors) and ('tor' not in factors):
                            data = data.drop('turnover_rate', axis=1)
                if freq == 'W':
                    data = api.weekly_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'M':
                    data = api.monthly_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
                    data['trade_date'] = data['trade_time'].map(lambda x: x.replace('-', '')[0:8])
                    data['pre_close'] = data['close'].shift(-1)
                if adj is not None:
                    fcts = api.adj_factor_vip(ts_code=ts_code, start_date=start_date, end_date=end_date)[['trade_date', 'adj_factor']]
                    if fcts.shape[0] == 0:
                        return None
                    data = data.set_index('trade_date', drop=False).merge(fcts.set_index('trade_date'), left_index=True, right_index=True, how='left')
                    if 'min' in freq:
                        data = data.sort_values('trade_time', ascending=False)
                    data['adj_factor'] = data['adj_factor'].fillna(method='bfill')
                    for col in PRICE_COLS:
                        if adj == 'hfq':
                            data[col] = data[col] * data['adj_factor']
                        if adj == 'qfq':
                            data[col] = data[col] * data['adj_factor'] / float(fcts['adj_factor'][0])
                        data[col] = data[col].map(FORMAT)
                        data[col] = data[col].astype(float)
                    if adjfactor is False:
                        data = data.drop('adj_factor', axis=1)
                    if 'min' not in freq:
                        data['change'] = data['close'] - data['pre_close']
                        data['pct_chg'] = data['change'] / data['pre_close'] * 100
                        data['pct_chg'] = data['pct_chg'].map(lambda x: FORMAT(x)).astype(float)
                    else:
                        data = data.drop(['trade_date', 'pre_close'], axis=1)
                else:
                    data['pre_close'] = data['close'].shift(-1)
                    data['change'] = data['close'] - data['pre_close']
                    data['pct_chg'] = data['change'] / data['pre_close'] * 100
                    data['pct_chg'] = data['pct_chg'].map(lambda x: FORMAT(x)).astype(float)
            elif asset == 'I':
                if freq == 'D':
                    data = api.index_daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'W':
                    data = api.index_weekly_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if freq == 'M':
                    data = api.index_monthly_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'FT':
                if freq == 'D':
                    data = api.fut_daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, exchange=exchange, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.ft_mins_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'O':
                if freq == 'D':
                    data = api.opt_daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, exchange=exchange, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.opt_mins_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            elif asset == 'CB':
                if freq == 'D':
                    data = api.cb_daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
            elif asset == 'FD':
                if freq == 'D':
                    data = api.fund_daily_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
                if 'min' in freq:
                    data = api.stk_mins_vip(ts_code=ts_code, start_date=start_date, end_date=end_date, freq=freq, offset=offset, limit=limit)
            if asset == 'C':
                if freq == 'd':
                    freq = 'daily'
                elif freq == 'w':
                    freq = 'week'
                data = api.coinbar(exchange=exchange, symbol=ts_code, freq=freq, start_dae=start_date, end_date=end_date,
                                   contract_type=contract_type)
            if ma is not None and len(ma) > 0:
                for a in ma:
                    if isinstance(a, int):
                        data['ma%s'%a] = MA(data['close'], a).map(FORMAT).shift(-(a-1))
                        data['ma%s'%a] = data['ma%s'%a].astype(float)
                        data['ma_v_%s'%a] = MA(data['vol'], a).map(FORMAT).shift(-(a-1))
                        data['ma_v_%s'%a] = data['ma_v_%s'%a].astype(float)
            data = data.reset_index(drop=True)
        except Exception as e:
            print(e)
        else:
            if fields is not None and fields != '':
                f_list = [col.strip() for col in fields.split(',')]
                data = data[f_list]
            return data
    raise IOError('ERROR.')


def subs(token=''):
    if token == '' or token is None:
        token = upass.get_token()

    from tushare.subs.ts_subs.subscribe import TsSubscribe
    app = TsSubscribe(token=token)
    return app


def ht_subs(username, password):
    from tushare.subs.ht_subs.subscribe import InsightSubscribe
    app = InsightSubscribe(username, password)
    return app


if __name__ == '__main__':
#     upass.set_token('')
    pro = pro_api()
    df = pro_bar(ts_code='688539.SH', adj='qfq')
    print(df)
