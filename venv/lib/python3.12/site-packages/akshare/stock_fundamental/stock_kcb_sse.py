# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2022/4/7 17:36
Desc: http://kcb.sse.com.cn/renewal/#
"""

import requests
import pandas as pd

# TODO


def stock_kcb_renewal():
    url = "http://query.sse.com.cn/statusAction.do"
    params = {
        "isPagination": "true",
        "sqlId": "SH_XM_LB",
        "pageHelp.pageSize": "20",
        "offerType": "",
        "commitiResult": "",
        "registeResult": "",
        "province": "",
        "csrcCode": "",
        "currStatus": "",
        "order": "updateDate|desc,stockAuditNum|desc",
        "keyword": "",
        "auditApplyDateBegin": "",
        "auditApplyDateEnd": "",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.endPage": "1",
        "_": "1649322742207",
    }
    headers = {
        "Host": "query.sse.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://kcb.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36",
    }

    for page in range(1, 37):
        print(page)
        params.update(
            {
                "pageHelp.pageNo": page,
                "pageHelp.beginPage": page,
                "pageHelp.endPage": page,
            }
        )
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"])
        # 处理下 temp_df 里面的字段就可以了
        print(temp_df)
        break
