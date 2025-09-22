# -*- coding:utf-8 -*-
"""
Created on 2016/04/03
@author: Leo
@group : lazytech
@contact: lazytech@sina.cn
"""

VERSION = '0.0.1'
P_TYPE = {'http': 'http://', 'ftp': 'ftp://'}
FORMAT = lambda x: '%.2f' % x
FORMAT4 = lambda x: '%.4f' % x
DOMAINS = {'sina': 'sina.com.cn', 'sinahq': 'sinajs.cn',
           'ifeng': 'ifeng.com', 'sf': 'finance.sina.com.cn',
           'ssf': 'stock.finance.sina.com.cn',
           'vsf': 'vip.stock.finance.sina.com.cn',
           'idx': 'www.csindex.com.cn', '163': 'money.163.com',
           'em': 'eastmoney.com', 'sseq': 'query.sse.com.cn',
           'sse': 'www.sse.com.cn', 'szse': 'www.szse.cn',
           'oss': '218.244.146.57',
           'shibor': 'www.shibor.org'}

NAV_OPEN_API = {'all': 'getNetValueOpen', 'equity': 'getNetValueOpen',
                'mix': 'getNetValueOpen', 'bond': 'getNetValueOpen',
                'monetary': 'getNetValueMoney', 'qdii': 'getNetValueOpen'}

NAV_OPEN_KEY = {'all': '6XxbX6h4CED0ATvW', 'equity': 'Gb3sH5uawH5WCUZ9',
                'mix': '6XxbX6h4CED0ATvW', 'bond': 'Gb3sH5uawH5WCUZ9',
                'monetary': 'uGo5qniFnmT5eQjp', 'qdii': 'pTYExKwRmqrSaP0P'}
NAV_OPEN_T2 = {'all': '0', 'equity': '2', 'mix': '1',
               'bond': '3', 'monetary': '0', 'qdii': '6'}
NAV_OPEN_T3 = ''


NAV_CLOSE_API = 'getNetValueClose'
NAV_CLOSE_KEY = ''
NAV_CLOSE_T2 = {'all': '0', 'fbqy': '4', 'fbzq': '9'}
NAV_CLOSE_T3 = {'all': '0', 'ct': '10',
                'cx': '11', 'wj': '3', 'jj': '5', 'cz': '12'}


NAV_GRADING_API = 'getNetValueCX'
NAV_GRADING_KEY = ''
NAV_GRADING_T2 = {'all': '0', 'fjgs': '7', 'fjgg': '8'}
NAV_GRADING_T3 = {'all': '0', 'wjzq': '13',
                  'gp': '14', 'zs': '15', 'czzq': '16', 'jjzq': '17'}


NAV_DEFAULT_PAGE = 1

##########################################################################
# 基金数据列名

NAV_OPEN_COLUMNS = ['symbol', 'sname', 'per_nav', 'total_nav', 'yesterday_nav',
                    'nav_rate', 'nav_a', 'nav_date', 'fund_manager',
                    'jjlx', 'jjzfe']

NAV_HIS_JJJZ = ['fbrq', 'jjjz', 'ljjz']
NAV_HIS_NHSY = ['fbrq', 'nhsyl', 'dwsy']

FUND_INFO_COLS = ['symbol', 'jjqc', 'jjjc', 'clrq', 'ssrq', 'xcr', 'ssdd',
                  'Type1Name', 'Type2Name', 'Type3Name', 'jjgm', 'jjfe',
                  'jjltfe', 'jjferq', 'quarter', 'glr', 'tgr']


NAV_CLOSE_COLUMNS = ['symbol', 'sname', 'per_nav', 'total_nav', 'nav_rate',
                     'discount_rate', 'nav_date', 'start_date', 'end_date',
                     'fund_manager', 'jjlx', 'jjzfe']


NAV_GRADING_COLUMNS = ['symbol', 'sname', 'per_nav', 'total_nav', 'nav_rate',
                       'discount_rate', 'nav_date', 'start_date', 'end_date',
                       'fund_manager', 'jjlx', 'jjzfe']


NAV_COLUMNS = {'open': NAV_OPEN_COLUMNS,
               'close': NAV_CLOSE_COLUMNS, 'grading': NAV_GRADING_COLUMNS}

##########################################################################
# 数据源URL
SINA_NAV_COUNT_URL = '%s%s/fund_center/data/jsonp.php/IO.XSRV2.CallbackList[\'%s\']/NetValue_Service.%s?ccode=&type2=%s&type3=%s'
SINA_NAV_DATA_URL = '%s%s/fund_center/data/jsonp.php/IO.XSRV2.CallbackList[\'%s\']/NetValue_Service.%s?page=%s&num=%s&ccode=&type2=%s&type3=%s'

SINA_NAV_HISTROY_COUNT_URL = '%s%s/fundInfo/api/openapi.php/CaihuiFundInfoService.getNav?symbol=%s&datefrom=%s&dateto=%s'
SINA_NAV_HISTROY_DATA_URL = '%s%s/fundInfo/api/openapi.php/CaihuiFundInfoService.getNav?symbol=%s&datefrom=%s&dateto=%s&num=%s'

SINA_NAV_HISTROY_COUNT_CUR_URL = '%s%s/fundInfo/api/openapi.php/CaihuiFundInfoService.getNavcur?symbol=%s&datefrom=%s&dateto=%s'
SINA_NAV_HISTROY_DATA_CUR_URL = '%s%s/fundInfo/api/openapi.php/CaihuiFundInfoService.getNavcur?symbol=%s&datefrom=%s&dateto=%s&num=%s'

SINA_DATA_DETAIL_URL = '%s%s/quotes_service/api/%s/Market_Center.getHQNodeData?page=1&num=400&sort=symbol&asc=1&node=%s&symbol=&_s_r_a=page'

SINA_FUND_INFO_URL = '%s%s/fundInfo/api/openapi.php/FundPageInfoService.tabjjgk?symbol=%s&format=json'

##########################################################################
DATA_GETTING_TIPS = '[Getting data:]'
DATA_GETTING_FLAG = '#'
DATA_ROWS_TIPS = '%s rows data found.Please wait for a moment.'
DATA_INPUT_ERROR_MSG = 'date input error.'
NETWORK_URL_ERROR_MSG = '获取失败，请检查网络和URL'
DATE_CHK_MSG = '年度输入错误：请输入1989年以后的年份数字，格式：YYYY'
DATE_CHK_Q_MSG = '季度输入错误：请输入1、2、3或4数字'
TOP_PARAS_MSG = 'top有误，请输入整数或all.'
LHB_MSG = '周期输入有误，请输入数字5、10、30或60'

OFT_MSG = u'开放型基金类型输入有误，请输入all、equity、mix、bond、monetary、qdii'

DICT_NAV_EQUITY = {
    'fbrq': 'date',
    'jjjz': 'value',
    'ljjz': 'total',
    'change': 'change'
}

DICT_NAV_MONETARY = {
    'fbrq': 'date',
    'nhsyl': 'value',
    'dwsy': 'total',
    'change': 'change'
}

import sys
PY3 = (sys.version_info[0] >= 3)


def _write_head():
    sys.stdout.write(DATA_GETTING_TIPS)
    sys.stdout.flush()


def _write_console():
    sys.stdout.write(DATA_GETTING_FLAG)
    sys.stdout.flush()


def _write_tips(tip):
    sys.stdout.write(DATA_ROWS_TIPS % tip)
    sys.stdout.flush()


def _write_msg(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()


def _check_nav_oft_input(found_type):
    if found_type not in NAV_OPEN_KEY.keys():
        raise TypeError(OFT_MSG)
    else:
        return True


def _check_input(year, quarter):
    if isinstance(year, str) or year < 1989:
        raise TypeError(DATE_CHK_MSG)
    elif quarter is None or isinstance(quarter, str) or quarter not in [1, 2, 3, 4]:
        raise TypeError(DATE_CHK_Q_MSG)
    else:
        return True
