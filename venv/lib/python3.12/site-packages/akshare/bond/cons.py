#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2019/10/20 10:21
Desc: 债券配置文件
"""

# bond-cov-sina
zh_sina_bond_hs_cov_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
zh_sina_bond_hs_cov_count_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCountSimple"
zh_sina_bond_hs_cov_hist_url = (
    "https://finance.sina.com.cn/realstock/company/{}/hisdata/klc_kl.js?d={}"
)
zh_sina_bond_hs_cov_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "hskzz_z",
    "_s_r_a": "page",
}

# bond-sina
zh_sina_bond_hs_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
zh_sina_bond_hs_count_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCountSimple"
zh_sina_bond_hs_hist_url = (
    "https://finance.sina.com.cn/realstock/company/{}/hisdata/klc_kl.js?d={}"
)
zh_sina_bond_hs_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "hs_z",
    "_s_r_a": "page",
}

# headers
SHORT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.91 Safari/537.36"
}

# quote
MARKET_QUOTE_URL = "http://www.chinamoney.com.cn/ags/ms/cm-u-md-bond/CbMktMakQuot?flag=1&lang=cn&abdAssetEncdShrtDesc=&emaEntyEncdShrtDesc="
MARKET_QUOTE_PAYLOAD = {
    "flag": "1",
    "lang": "cn",
    "abdAssetEncdShrtDesc": "",
    "emaEntyEncdShrtDesc": "",
}

# trade
MARKET_TRADE_URL = (
    "http://www.chinamoney.com.cn/ags/ms/cm-u-md-bond/CbtPri?lang=cn&flag=1&bondName="
)
MARKET_TRADE_PAYLOAD = {"lang": "cn", "flag": "1", "bondName": ""}
