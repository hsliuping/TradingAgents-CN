# -*- coding:utf-8 -*- 
"""
财新网新闻数据检索下载
Created on 2017/06/09
@author: Yuan Yifan
@group : ~
@contact: tsingjyujing@163.com
"""

"""
    # 测试脚本
    from caixinnews import *
    urls = query_news(start_date='2017-05-09',end_date='2017-05-09')
    title,text = read_page(urls[0])
    print(title)
    print(text)
"""

import re
import datetime
from bs4 import BeautifulSoup
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

caixin_search_url = "http://search.caixin.com/search/search.jsp?startDate=%s&endDate=%s&keyword=%s&x=0&y=0"

default_parser = "html.parser"
#default_parser = "lxml"

UA    =    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "+\
        "AppleWebKit/537.36 (KHTML, like Gecko) "+\
        "Chrome/42.0.2311.135 "+\
        "Safari/537.36 "+\
        "Edge/12.10240"
        
req_header = {\
        'User-Agent': UA,\
        'Accept': '"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"',\
        'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3'}
        
req_timeout = 10

def read_url(url):
    """
    读取URL对应的内容（模拟浏览器）
    Parameters
    ------
        url string 需要读取的链接
    Return
    ------
        string 读取的内容
    """
    req_header_this = req_header
    req_header_this['Host'] = re.findall('://.*?/',url,re.DOTALL)[0][3:-1]
    return urlopen(Request(url,None,req_header),None,req_timeout).read()
    
def get_soup(url):
    """
    读取URL对应的内容，并解析为Soup
    Parameters
        url string 需要读取的链接
    Return
        string 读取的内容
    """
    return BeautifulSoup(read_url(url), default_parser)
    
def query_news(keywords='*',start_date=None,end_date=None):
    """
    读取某一时间段对应的新闻链接列表
    Parameters
    ------
        keywords string 关键词
        start_date string 开始日期，格式yyyy-mm-dd
        end_date string 结束日期，格式yyyy-mm-dd
    Return
    ------
        List<string> 读取的内容
    """
    if start_date is None or end_date is None:
        now_time = datetime.datetime.now()
        last_day = datetime.datetime(now_time.year,now_time.month,now_time.day,12,0) - datetime.timedelta(seconds = 3600*24)
        start_date = last_day.strftime("%Y-%m-%d")
        end_date = start_date
    url = caixin_search_url % (start_date,end_date,keywords)
    soup = get_soup(url)
    info_urls = []
    while(True):
        next_info = soup.find_all(name='a',attrs={'class','pageNavBtn2'})[0]
        all_res = soup.find_all(name='div',attrs={'class','searchxt'})
        for res in all_res:
            info_urls.append(res.a.attrs['href'])
        next_info = next_info.attrs['href']    

        if next_info=="javascript:void();":
            break;
        else:
            soup = get_soup(caixin_search_url+next_info)
    return info_urls
    
def is_blog(url):
    """
    判断某一链接是否博客
    Parameters
    ------
        url string 需要判断的链接
    Return
    ------
        bool 该url是否是博客URL
    """
    return len(re.findall('blog\.caixin\.com',url))>0
    
def read_page(url):
    """
    读取链接的内容
    Parameters
    ------
        url string 需要判断的链接
    Return
    ------
        title string 文章标题
        text string 文章内容
    """
    if is_blog(url):
        return read_blog(url)
    else:
        return read_normal_artical(url)
        
def read_normal_artical(url):
    soup = get_soup(url)
    title = soup.title.get_text()
    ps = soup.find_all('p')
    text = ''
    for p in ps:
        text += p.get_text() + "\n"
    return title,text

def read_blog(url):
    soup = get_soup(url)
    title = soup.title.get_text()
    bcontent = soup.find_all(name='div',attrs={'class','blog_content'})
    ps = bcontent[0].find_all('p')
    text = ''
    for p in ps:
        text += p.get_text() + "\n"
    return title,text
    