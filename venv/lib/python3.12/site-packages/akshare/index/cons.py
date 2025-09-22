#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2021/5/27 20:19
Desc: 指数配置文件
"""

# weibo-user-agent
index_weibo_headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) "
    "AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1",
    "Referer": "http://data.weibo.com/index/newindex",
    "Accept": "application/json",
    "Origin": "https://data.weibo.com",
}

# sw-cons
sw_cons_headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Content-Length": "34",
    "Content-Type": "text/plain; charset=UTF-8",
    # "Cookie": "ASP.NET_SessionId=i55eaz55142xdxfx0bkqp145",
    "Host": "www.swsindex.com",
    "Origin": "http://www.swsindex.com",
    "Referer": "http://www.swsindex.com/idx0210.aspx?swindexcode=801010",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/78.0.3904.108 Safari/537.36",
    "X-AjaxPro-Method": "ReturnContent",
}

# sw-url
sw_url = "http://www.swsindex.com/handler.aspx"

# sw-payload
sw_payload = {
    "tablename": "swzs",
    "key": "L1",
    "p": "1",
    "where": "L1 in('801010','801020','801030','801040','801050','801080','801110','801120','801130',"
    "'801140','801150','801160','801170','801180','801200','801210','801230','801710','801720',"
    "'801730','801740','801750','801760','801770','801780','801790','801880','801890','801950',"
    "'801960','801970','801980')",
    "orderby": "",
    "fieldlist": "L1,L2,L3,L4,L5,L6,L7,L8,L11",
    "pagecount": "28",
    "timed": "",
}

# sw-headers
sw_headers = {
    "Accept": "application/json, text/javascript, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Content-Type": "application/x-www-form-urlencoded",
    "DNT": "1",
    "Host": "www.swsindex.com",
    "Origin": "http://www.swsindex.com",
    "Pragma": "no-cache",
    "Referer": "http://www.swsindex.com/idx0120.aspx?columnid=8832",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/74.0.3729.169 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# zh-sina-a
zh_sina_index_stock_url = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeDataSimple"
)
zh_sina_index_stock_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "hs_s",
    "_s_r_a": "page",
}
zh_sina_index_stock_count_url = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCountSimple?node=hs_s"
)
zh_sina_index_stock_hist_url = (
    "https://finance.sina.com.cn/realstock/company/{}/hisdata/klc_kl.js"
)

# investing
short_headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/61.0.3163.91 Safari/537.36"
}

long_headers = {
    "accept": "text/plain, */*; q=0.01",
    # 'accept-encoding': 'gzip, deflate, br',
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    # 'cache-control': 'no-cache',
    "content-length": "267",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://cn.investing.com",
    "referer": "https://cn.investing.com/commodities/brent-oil-historical-data",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/61.0.3163.91 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}

index_global_sina_symbol_map = {
    # 欧洲股市
    "英国富时100指数": "UKX",
    "德国DAX 30种股价指数": "DAX",
    "俄罗斯MICEX指数": "INDEXCF",
    "法CAC40指数": "CAC",
    "瑞士股票指数": "SWI20",
    "富时意大利MIB指数": "FTSEMIB",
    "荷兰AEX综合指数": "AEX",
    "西班牙IBEX指数": "IBEX",
    "欧洲Stoxx50指数": "SX5E",
    # 美洲股市
    "加拿大S&P/TSX综合指数": "GSPTSE",
    "墨西哥BOLSA指数": "MXX",
    "巴西BOVESPA股票指数": "IBOV",
    # 亚洲股市
    "中国台湾加权指数": "TWJQ",
    "日经225指数": "NKY",
    "首尔综合指数": "KOSPI",
    "印度尼西亚雅加达综合指数": "JCI",
    "印度孟买SENSEX指数": "SENSEX",
    # 澳洲股市
    "澳大利亚标准普尔200指数": "AS51",
    "新西兰NZSE 50指数": "NZ250",
    # 非洲股市
    "埃及CASE 30指数": "CASE",
}

index_global_em_symbol_map = {
    "波罗的海BDI指数": {"code": "BDI", "market": "100"},
    "葡萄牙PSI20": {"code": "PSI20", "market": "100"},
    "菲律宾马尼拉": {"code": "PSI", "market": "100"},
    "泰国SET": {"code": "SET", "market": "100"},
    "俄罗斯RTS": {"code": "RTS", "market": "100"},
    "巴基斯坦卡拉奇": {"code": "KSE100", "market": "100"},
    "越南胡志明": {"code": "VNINDEX", "market": "100"},
    "红筹指数": {"code": "HSCCI", "market": "124"},
    "印尼雅加达综合": {"code": "JKSE", "market": "100"},
    "希腊雅典ASE": {"code": "ASE", "market": "100"},
    "墨西哥BOLSA": {"code": "MXX", "market": "100"},
    "挪威OSEBX": {"code": "OSEBX", "market": "100"},
    "巴西BOVESPA": {"code": "BVSP", "market": "100"},
    "波兰WIG": {"code": "WIG", "market": "100"},
    "印度孟买SENSEX": {"code": "SENSEX", "market": "100"},
    "布拉格指数": {"code": "PX", "market": "100"},
    "荷兰AEX": {"code": "AEX", "market": "100"},
    "冰岛ICEX": {"code": "ICEXI", "market": "100"},
    "斯里兰卡科伦坡": {"code": "CSEALL", "market": "100"},
    "富时新加坡海峡时报": {"code": "STI", "market": "100"},
    "富时意大利MIB": {"code": "MIB", "market": "100"},
    "路透CRB商品指数": {"code": "CRB", "market": "100"},
    "比利时BFX": {"code": "BFX", "market": "100"},
    "富时AIM全股": {"code": "AXX", "market": "100"},
    "新西兰50": {"code": "NZ50", "market": "100"},
    "上证指数": {"code": "000001", "market": "1"},
    "国企指数": {"code": "HSCEI", "market": "100"},
    "沪深300": {"code": "000300", "market": "1"},
    "英国富时100": {"code": "FTSE", "market": "100"},
    "中小100": {"code": "399005", "market": "0"},
    "瑞士SMI": {"code": "SSMI", "market": "100"},
    "西班牙IBEX35": {"code": "IBEX", "market": "100"},
    "瑞典OMXSPI": {"code": "OMXSPI", "market": "100"},
    "爱尔兰综合": {"code": "ISEQ", "market": "100"},
    "韩国KOSPI": {"code": "KS11", "market": "100"},
    "深证成指": {"code": "399001", "market": "0"},
    "韩国KOSPI200": {"code": "KOSPI200", "market": "100"},
    "芬兰赫尔辛基": {"code": "HEX", "market": "100"},
    "恒生指数": {"code": "HSI", "market": "100"},
    "欧洲斯托克50": {"code": "SX5E", "market": "100"},
    "美元指数": {"code": "UDI", "market": "100"},
    "法国CAC40": {"code": "FCHI", "market": "100"},
    "台湾加权": {"code": "TWII", "market": "100"},
    "英国富时250": {"code": "MCX", "market": "100"},
    "富时马来西亚KLCI": {"code": "KLSE", "market": "100"},
    "OMX哥本哈根20": {"code": "OMXC20", "market": "100"},
    "道琼斯": {"code": "DJIA", "market": "100"},
    "奥地利ATX": {"code": "ATX", "market": "100"},
    "加拿大S&P/TSX": {"code": "TSX", "market": "100"},
    "德国DAX30": {"code": "GDAXI", "market": "100"},
    "创业板指": {"code": "399006", "market": "0"},
    "澳大利亚普通股": {"code": "AORD", "market": "100"},
    "标普500": {"code": "SPX", "market": "100"},
    "澳大利亚标普200": {"code": "AS51", "market": "100"},
    "日经225": {"code": "N225", "market": "100"},
    "纳斯达克": {"code": "NDX", "market": "100"},
}
