# -*- coding: utf-8 -*-

import tushare as ts
from token_manager import get_valid_token


token = get_valid_token()
ts.set_token(token)

df = ts.pro_api().index_daily(
    ts_code="000001.SH", start_date="20250620", end_date="20250628"  # 上证指数
)
print(df.head())
