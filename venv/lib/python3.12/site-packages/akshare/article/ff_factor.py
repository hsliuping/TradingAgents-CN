#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/20 22:30
Desc: FF-data-library
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
"""

from io import StringIO

import pandas as pd
import requests

from akshare.article.cons import ff_home_url


def article_ff_crr() -> pd.DataFrame:
    """
    FF多因子模型
    https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
    :return: FF多因子模型单一表格
    :rtype: pandas.DataFrame
    """
    res = requests.get(ff_home_url)
    # first table
    list_index = (
        pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[2, :]
        .index.tolist()
    )
    list_0 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[0, :]
        .iloc[0]
        .split(" ")
        if item != ""
    ]
    list_1 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[0, :]
        .iloc[1]
        .split(" ")
        if item != ""
    ]
    list_2 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[0, :]
        .iloc[2]
        .split(" ")
        if item != ""
    ]
    list_0.insert(0, "-")
    list_1.insert(0, "-")
    list_2.insert(0, "-")
    temp_columns = (
        pd.read_html(StringIO(res.text), header=0)[4]
        .iloc[:, 0]
        .str.split("  ", expand=True)
        .T[0]
        .dropna()
        .tolist()
    )
    table_one = pd.DataFrame(
        [list_0, list_1, list_2], index=list_index, columns=temp_columns
    ).T

    # second table
    list_index = (
        pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[1, :]
        .index.tolist()
    )
    list_0 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[1, :]
        .iloc[0]
        .split(" ")
        if item != ""
    ]
    list_1 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[1, :]
        .iloc[1]
        .split(" ")
        if item != ""
    ]
    list_2 = [
        item
        for item in pd.read_html(StringIO(res.text), header=0, index_col=0)[4]
        .iloc[1, :]
        .iloc[2]
        .split(" ")
        if item != ""
    ]
    list_0.insert(0, "-")
    list_1.insert(0, "-")
    list_2.insert(0, "-")
    temp_columns = (
        pd.read_html(StringIO(res.text), header=0)[4]
        .iloc[:, 0]
        .str.split("  ", expand=True)
        .T[1]
        .dropna()
        .tolist()
    )
    table_two = pd.DataFrame(
        [list_0, list_1, list_2], index=list_index, columns=temp_columns
    ).T

    # third table
    df = pd.read_html(StringIO(res.text), header=0, index_col=0)[4].iloc[2, :]
    name_list = (
        pd.read_html(StringIO(res.text), header=0)[4]
        .iloc[:, 0]
        .str.split(r"  ", expand=True)
        .iloc[2, :]
        .tolist()
    )
    value_list_0 = df.iloc[0].split("  ")
    value_list_0.insert(0, "-")
    value_list_0.insert(1, "-")
    value_list_0.insert(8, "-")
    value_list_0.insert(15, "-")

    value_list_1 = df.iloc[1].split("  ")
    value_list_1.insert(0, "-")
    value_list_1.insert(1, "-")
    value_list_1.insert(8, "-")
    value_list_1.insert(15, "-")

    value_list_2 = df.iloc[2].split("  ")
    value_list_2.insert(0, "-")
    value_list_2.insert(1, "-")
    value_list_2.insert(8, "-")
    value_list_2.insert(15, "-")

    name_list.remove("Small Growth Big Value")
    name_list.insert(5, "Small Growth")
    name_list.insert(6, "Big Value")
    temp_list = [item for item in name_list if "Portfolios" not in item]
    temp_list.insert(0, "Fama/French Research Portfolios")
    temp_list.insert(1, "Size and Book-to-Market Portfolios")
    temp_list.insert(8, "Size and Operating Profitability Portfolios")
    temp_list.insert(15, "Size and Investment Portfolios")
    temp_df = pd.DataFrame([temp_list, value_list_0, value_list_1, value_list_2]).T
    temp_df.index = temp_df.iloc[:, 0]
    temp_df = temp_df.iloc[:, 1:]
    # concat
    all_df = pd.DataFrame()
    all_df = pd.concat([all_df, table_one])
    all_df = pd.concat([all_df, table_two])
    temp_df.columns = table_two.columns
    all_df = pd.concat([all_df, temp_df])
    all_df.reset_index(inplace=True)
    all_df.rename(columns={"index": "item"}, inplace=True)
    return all_df


if __name__ == "__main__":
    article_ff_crr_df = article_ff_crr()
    print(article_ff_crr_df)
