# -*- coding:utf-8 -*- 
"""
基本面数据接口 
Created on 2015/01/18
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
import pandas as pd
from tushare.stock import cons as ct
import lxml.html
from lxml import etree
import re
import time
v = pd.__version__ 
if int(v.split('.')[1])>=25 or int(v.split('.')[0])>0:
    from io import StringIO
else:    
    from pandas.compat import StringIO
from tushare.util import dateu as du
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

def get_stock_basics(date=None):
    """
        获取沪深上市公司基本情况
    Parameters
    date:日期YYYY-MM-DD，默认为上一个交易日，目前只能提供2016-08-09之后的历史数据

    Return
    --------
    DataFrame
               code,代码
               name,名称
               industry,细分行业
               area,地区
               pe,市盈率
               outstanding,流通股本
               totals,总股本(万)
               totalAssets,总资产(万)
               liquidAssets,流动资产
               fixedAssets,固定资产
               reserved,公积金
               reservedPerShare,每股公积金
               eps,每股收益
               bvps,每股净资
               pb,市净率
               timeToMarket,上市日期
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    wdate = du.last_tddate() if date is None else date
    wdate = wdate.replace('-', '')
    if wdate < '20160809':
        return None
    datepre = '' if date is None else wdate[0:4] + wdate[4:6] + '/'
    request = Request(ct.ALL_STOCK_BASICS_FILE%(datepre, '' if date is None else wdate))
    text = urlopen(request, timeout=10).read()
    text = text.decode('GBK')
    text = text.replace('--', '')
    df = pd.read_csv(StringIO(text), dtype={'code':'object'})
    df = df.set_index('code')
    return df


def get_report_data(year, quarter):
    """
        获取业绩报表数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        eps,每股收益
        eps_yoy,每股收益同比(%)
        bvps,每股净资产
        roe,净资产收益率(%)
        epcf,每股现金流量(元)
        net_profits,净利润(万元)
        profits_yoy,净利润同比(%)
        distrib,分配方案
        report_date,发布日期
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year,quarter) is True:
        ct._write_head()
        df =  _get_report_data(year, quarter, 1, pd.DataFrame())
        if df is not None:
#             df = df.drop_duplicates('code')
            df['code'] = df['code'].map(lambda x:str(x).zfill(6))
        return df


def _get_report_data(year, quarter, pageNo, dataArr,
                     retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.REPORT_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], ct.PAGES['fd'],
                             year, quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.replace('--', '')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df = df.drop(11, axis=1)
            df.columns = ct.REPORT_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_report_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except Exception as e:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_profit_data(year, quarter):
    """
        获取盈利能力数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        roe,净资产收益率(%)
        net_profit_ratio,净利率(%)
        gross_profit_rate,毛利率(%)
        net_profits,净利润(万元)
        eps,每股收益
        business_income,营业收入(百万元)
        bips,每股主营业务收入(元)
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year, quarter) is True:
        ct._write_head()
        data =  _get_profit_data(year, quarter, 1, pd.DataFrame())
        if data is not None:
#             data = data.drop_duplicates('code')
            data['code'] = data['code'].map(lambda x:str(x).zfill(6))
        return data


def _get_profit_data(year, quarter, pageNo, dataArr,
                     retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.PROFIT_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                  ct.PAGES['fd'], year,
                                                  quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.replace('--', '')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns=ct.PROFIT_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_profit_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_operation_data(year, quarter):
    """
        获取营运能力数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        arturnover,应收账款周转率(次)
        arturndays,应收账款周转天数(天)
        inventory_turnover,存货周转率(次)
        inventory_days,存货周转天数(天)
        currentasset_turnover,流动资产周转率(次)
        currentasset_days,流动资产周转天数(天)
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year, quarter) is True:
        ct._write_head()
        data =  _get_operation_data(year, quarter, 1, pd.DataFrame())
        if data is not None:
#             data = data.drop_duplicates('code')
            data['code'] = data['code'].map(lambda x:str(x).zfill(6))
        return data


def _get_operation_data(year, quarter, pageNo, dataArr,
                        retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.OPERATION_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                     ct.PAGES['fd'], year,
                                                     quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.replace('--', '')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns=ct.OPERATION_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_operation_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except Exception as e:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_growth_data(year, quarter):
    """
        获取成长能力数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        mbrg,主营业务收入增长率(%)
        nprg,净利润增长率(%)
        nav,净资产增长率
        targ,总资产增长率
        epsg,每股收益增长率
        seg,股东权益增长率
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year, quarter) is True:
        ct._write_head()
        data =  _get_growth_data(year, quarter, 1, pd.DataFrame())
        if data is not None:
#             data = data.drop_duplicates('code')
            data['code'] = data['code'].map(lambda x:str(x).zfill(6))
        return data


def _get_growth_data(year, quarter, pageNo, dataArr, 
                     retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.GROWTH_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                  ct.PAGES['fd'], year,
                                                  quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=50).read()
            text = text.decode('GBK')
            text = text.replace('--', '')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns=ct.GROWTH_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_growth_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except Exception as e:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_debtpaying_data(year, quarter):
    """
        获取偿债能力数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        currentratio,流动比率
        quickratio,速动比率
        cashratio,现金比率
        icratio,利息支付倍数
        sheqratio,股东权益比率
        adratio,股东权益增长率
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year, quarter) is True:
        ct._write_head()
        df =  _get_debtpaying_data(year, quarter, 1, pd.DataFrame())
        if df is not None:
#             df = df.drop_duplicates('code')
            df['code'] = df['code'].map(lambda x:str(x).zfill(6))
        return df


def _get_debtpaying_data(year, quarter, pageNo, dataArr,
                         retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.DEBTPAYING_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                      ct.PAGES['fd'], year,
                                                      quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = ct.DEBTPAYING_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_debtpaying_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except Exception as e:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)
 
 
def get_cashflow_data(year, quarter):
    """
        获取现金流量数据
    Parameters
    --------
    year:int 年度 e.g:2014
    quarter:int 季度 :1、2、3、4，只能输入这4个季度
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
       
    Return
    --------
    DataFrame
        code,代码
        name,名称
        cf_sales,经营现金净流量对销售收入比率
        rateofreturn,资产的经营现金流量回报率
        cf_nm,经营现金净流量与净利润的比率
        cf_liabilities,经营现金净流量对负债比率
        cashflowratio,现金流量比率
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if ct._check_input(year, quarter) is True:
        ct._write_head()
        df =  _get_cashflow_data(year, quarter, 1, pd.DataFrame())
        if df is not None:
#             df = df.drop_duplicates('code')
            df['code'] = df['code'].map(lambda x:str(x).zfill(6))
        return df


def _get_cashflow_data(year, quarter, pageNo, dataArr,
                       retry_count=3, pause=0.001):
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.CASHFLOW_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'],
                                                    ct.PAGES['fd'], year,
                                                    quarter, pageNo, ct.PAGE_NUM[1]))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.replace('--', '')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@class=\"list_table\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = ct.CASHFLOW_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _get_cashflow_data(year, quarter, pageNo, dataArr)
            else:
                return dataArr
        except Exception as e:
            pass
    raise IOError(ct.NETWORK_URL_ERROR_MSG)
       
       
def _data_path():
    import os
    import inspect
    caller_file = inspect.stack()[1][1]  
    pardir = os.path.abspath(os.path.join(os.path.dirname(caller_file), os.path.pardir))
    return os.path.abspath(os.path.join(pardir, os.path.pardir))
  

def get_balance_sheet(code):
    """
        获取某股票的历史所有时期资产负债表
    Parameters
    --------
    code:str 股票代码 e.g:600518
       
    Return
    --------
    DataFrame
        行列名称为中文且数目较多，建议获取数据后保存到本地查看
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if code.isdigit():
        request = Request(ct.SINA_BALANCESHEET_URL%(code))
        text = urlopen(request, timeout=10).read()
        text = text.decode('GBK')
        text = text.replace('\t\n', '\r\n')
        text = text.replace('\t', ',')
        df = pd.read_csv(StringIO(text), dtype={'code':'object'})
        return df

def get_profit_statement(code):
    """
        获取某股票的历史所有时期利润表
    Parameters
    --------
    code:str 股票代码 e.g:600518
       
    Return
    --------
    DataFrame
        行列名称为中文且数目较多，建议获取数据后保存到本地查看
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if code.isdigit():
        request = Request(ct.SINA_PROFITSTATEMENT_URL%(code))
        text = urlopen(request, timeout=10).read()
        text = text.decode('GBK')
        text = text.replace('\t\n', '\r\n')
        text = text.replace('\t', ',')
        df = pd.read_csv(StringIO(text), dtype={'code':'object'})
        return df

      
def get_cash_flow(code):
    """
        获取某股票的历史所有时期现金流表
    Parameters
    --------
    code:str 股票代码 e.g:600518
       
    Return
    --------
    DataFrame
        行列名称为中文且数目较多，建议获取数据后保存到本地查看
    """
    print("本接口即将停止更新，请尽快使用Pro版接口：https://tushare.pro/document/2")
    if code.isdigit():
        request = Request(ct.SINA_CASHFLOW_URL%(code))
        text = urlopen(request, timeout=10).read()
        text = text.decode('GBK')
        text = text.replace('\t\n', '\r\n')
        text = text.replace('\t', ',')
        df = pd.read_csv(StringIO(text), dtype={'code':'object'})
        return df

