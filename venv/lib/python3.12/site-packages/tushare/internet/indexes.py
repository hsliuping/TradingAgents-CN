#!/usr/bin/env python
# -*- coding:utf-8 -*- 
"""
龙虎榜数据
Created on 2017年8月13日
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""

import pandas as pd
v = pd.__version__ 
if int(v.split('.')[1])>=25 or int(v.split('.')[0])>0:
    from io import StringIO
else:    
    from pandas.compat import StringIO
from tushare.stock import cons as ct
import time
import re
import lxml.html
from lxml import etree
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

def bdi(itype='D', retry_count=3,
                pause=0.001):
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(ct.BDI_URL%(ct.P_TYPE['http'], ct.DOMAINS['v500']))
            lines = urlopen(request, timeout = 10).read()
            if len(lines) < 100: #no data
                return None
        except Exception as e:
                print(e)
        else:
            linestr = lines.decode('utf-8') if ct.PY3 else lines
            if itype == 'D': # Daily
                reg = re.compile(r'\"chart_data\",\"(.*?)\"\);') 
                lines = reg.findall(linestr)
                lines = lines[0]
                lines = lines.replace('chart', 'table').\
                        replace('</series><graphs>', '').\
                        replace('</graphs>', '').\
                        replace('series', 'tr').\
                        replace('value', 'td').\
                        replace('graph', 'tr').\
                        replace('graphs', 'td')
                df = pd.read_html(lines, encoding='utf8')[0]
                df = df.T
                df.columns = ['date', 'index']
                df['date'] = df['date'].map(lambda x: x.replace(u'年', '-')).\
                    map(lambda x: x.replace(u'月', '-')).\
                    map(lambda x: x.replace(u'日', ''))
                df['date'] = pd.to_datetime(df['date'])
                df['index'] = df['index'].astype(float)
                df = df.sort_values('date', ascending=False).reset_index(drop = True)
                df['change'] = df['index'].pct_change(-1)
                df['change'] = df['change'] * 100
                df['change'] = df['change'].map(lambda x: '%.2f' % x)
                df['change'] = df['change'].astype(float)
                return df
            else: #Weekly
                html = lxml.html.parse(StringIO(linestr))
                res = html.xpath("//table[@class=\"style33\"]/tr/td/table[last()]")
                if ct.PY3:
                    sarr = [etree.tostring(node).decode('utf-8') for node in res]
                else:
                    sarr = [etree.tostring(node) for node in res]
                sarr = ''.join(sarr)
                sarr = '<table>%s</table>'%sarr
                df = pd.read_html(sarr)[0][1:]
                df.columns = ['month', 'index']
                df['month'] = df['month'].map(lambda x: x.replace(u'年', '-')).\
                    map(lambda x: x.replace(u'月', ''))
                df['month'] = pd.to_datetime(df['month'])
                df['month'] = df['month'].map(lambda x: str(x).replace('-', '')).\
                              map(lambda x: x[:6])
                df['index'] = df['index'].astype(float)
                df['change'] = df['index'].pct_change(-1)
                df['change'] = df['change'].map(lambda x: '%.2f' % x)
                df['change'] = df['change'].astype(float)
                return df

