#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Created on 2023/12/06
@author: Monday
@group : waditu
@contact:
Desc: 实时行情配置文件
"""
TICK_COLUMNS = ['TIME', 'PRICE', 'CHANGE', 'VOLUME', 'AMOUNT', 'TYPE']
TODAY_TICK_COLUMNS = ['TIME', 'PRICE', 'PCHANGE', 'CHANGE', 'VOLUME', 'AMOUNT', 'TYPE']

# zh-sina-a
zh_sina_a_stock_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
zh_sina_a_stock_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "hs_a",
    "symbol": "",
    "_s_r_a": "page"
}
zh_sina_a_stock_count_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a"
zh_sina_a_stock_headers = {
    "authority": "vip.stock.finance.sina.com.cn",
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "content-type": "application/x-www-form-urlencoded",
    # "referer": "https://vip.stock.finance.sina.com.cn/mkt/",
    # "sec-ch-ua": "\"Microsoft Edge\";v=\"119\", \"Chromium\";v=\"119\", \"Not?A_Brand\";v=\"24\"",
    # "sec-ch-ua-mobile": "?0",
    # "sec-ch-ua-platform": "\"Windows\"",
    # "sec-fetch-dest": "empty",
    # "sec-fetch-mode": "cors",
    # "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
}
zh_sina_a_stock_cookies = {
    "SINAGLOBAL": "119.253.37.47_1644226852.508455",
    "__bid_n": "18450c0cd85e35c7a94207",
    "SGUID": "1667802124734_57135459",
    "UOR": ",,",
    "U_TRS1": "000000b2.9f5130ad.644b86b5.59248297",
    "FPTOKEN": "uUvE76pfAI7Jn5FFqInwSdRtqTyLuL6pdbfc+x7roC/Cpq02sGKHOVBuDqX/cKmBhQoZsBDCVIcATeySQAv+5tBq6PrNHaCYc4QsF52US/Wr3r8Cm59WbQrDmdDS3PqZpDuWkrt1rqVmi4llaINOSWOnBHROpQon1cDv67tj7ExYL8WNCE/lwJRwHmNWMVwYhNbTV4YIcPF7rNuvdqoBpEmosmMgOcH5xtUi6odo51pnKjBC5YkARH+vWoDLsR4NTSu6WSR5KbZ04ia/4UQWZ8I/EWvyqhqtCnIlrWUiSbsuPPdIKtb2WSuIYW2HwR8Phqeasf3vqLukS+0yHphVhJkUFWI1auczbXZQvVs8Yyaxnxytn1BeuY0QSMaQtZ7WpHpDw/OciAwlxsnTC3D6qg==|5cED1wgbzTZjJ/dqIVeem7K6xn6k7piH0T+g7xbaU7I=|10|5a3963e2a78e2a5d10021960ecf84860",
    "SUB": "_2AkMT-zNof8NxqwFRmP0SzWLjaYRzwgnEieKlp8KzJRMyHRl-yD9kqkEytRB6OHsdh6VxEajRUyiJp4p33F_Ga6PI0ilQ",
    "Hm_lvt_b82ffdf7cbc70caaacee097b04128ac1": "1688714348",
    "ULV": "1699583417865:11:2:2::1698999895443",
    "Hm_lvt_fcf72dc8287d20a78b3dfd301a50cbf8": "1698373541,1699583419",
    "Apache": "220.231.47.169_1701671587.570418"
}

dc_headers = {
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Dest": "script",
    "Referer": "https://quote.eastmoney.com/kcb/688720.html",
    "Accept-Language": "zh-CN,zh;q=0.9"
}
dc_cookies = {
    "qgqp_b_id": "cf8b058a05d005ca7fb2afc14957f250",
    "st_si": "72907886672492",
    "st_asi": "delete",
    "HAList": "ty-1-688720-N%u827E%u68EE%2Cty-0-873122-%u4E2D%u7EBA%u6807",
    "st_pvi": "02194384728897",
    "st_sp": "2023-12-06%2016%3A05%3A53",
    "st_inirUrl": "https%3A%2F%2Fquote.eastmoney.com%2Fcenter%2Fgridlist.html",
    "st_sn": "11",
    "st_psi": "20231206170058129-113200313000-8845421016"
}

LIVE_DATA_COLS = ['NAME', 'OPEN', 'PRE_CLOSE', 'PRICE', 'HIGH', 'LOW', 'BID', 'ASK', 'VOLUME', 'AMOUNT', 'B1_V', 'B1_P',
                  'B2_V', 'B2_P', 'B3_V', 'B3_P', 'B4_V', 'B4_P', 'B5_V', 'B5_P', 'A1_V', 'A1_P', 'A2_V', 'A2_P',
                  'A3_V', 'A3_P', 'A4_V', 'A4_P', 'A5_V', 'A5_P', 'DATE', 'TIME', 'TS_CODE']

LIVE_DATA_COLS_REINDEX = ['NAME', 'TS_CODE', 'DATE', 'TIME', 'OPEN', 'PRE_CLOSE', 'PRICE', 'HIGH', 'LOW', 'BID', 'ASK',
                          'VOLUME', 'AMOUNT', 'B1_V', 'B1_P',
                          'B2_V', 'B2_P', 'B3_V', 'B3_P', 'B4_V', 'B4_P', 'B5_V', 'B5_P', 'A1_V', 'A1_P', 'A2_V',
                          'A2_P',
                          'A3_V', 'A3_P', 'A4_V', 'A4_P', 'A5_V', 'A5_P']
