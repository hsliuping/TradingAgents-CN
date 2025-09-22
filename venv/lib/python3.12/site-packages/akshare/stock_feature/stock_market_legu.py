#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/25 20:22
Desc: 乐咕乐股网-赚钱效应分析
https://www.legulegu.com/stockdata/market-activity
"""

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.cons import headers


def stock_market_activity_legu() -> pd.DataFrame:
    """
    乐咕乐股网-赚钱效应分析
    https://www.legulegu.com/stockdata/market-activity
    :return: 乐咕乐股网-赚钱效应分析
    :rtype: pandas.DataFrame
    """
    url = "https://legulegu.com/stockdata/market-activity"
    r = requests.get(url, headers=headers)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df_one = temp_df.iloc[:, :2]
    temp_df_one.columns = ["item", "value"]
    temp_df_two = temp_df.iloc[:, 2:4]
    temp_df_two.columns = ["item", "value"]
    temp_df_three = temp_df.iloc[:, 4:6]
    temp_df_three.columns = ["item", "value"]
    temp_df = pd.concat(
        objs=[temp_df_one, temp_df_two, temp_df_three], ignore_index=True
    )
    temp_df.dropna(how="all", axis=0, inplace=True)
    soup = BeautifulSoup(r.text, features="lxml")
    item_str = soup.find(name="div", attrs={"class": "current-index"}).text
    inner_temp_df = pd.DataFrame([item.strip() for item in item_str.split("：")]).T
    inner_temp_df.columns = ["item", "value"]
    temp_df = pd.concat(objs=[temp_df, inner_temp_df], ignore_index=True)
    item_str = soup.find(name="div", attrs={"class": "current-data"}).text.strip()
    inner_temp_df = pd.DataFrame(["统计日期", item_str]).T
    inner_temp_df.columns = ["item", "value"]
    temp_df = pd.concat(objs=[temp_df, inner_temp_df], ignore_index=True)
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


if __name__ == "__main__":
    stock_market_activity_legu_df = stock_market_activity_legu()
    print(stock_market_activity_legu_df)
