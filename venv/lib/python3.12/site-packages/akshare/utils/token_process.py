#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2020/2/13 21:22
Desc: 存储和读取 Token 文件
"""

import os

import pandas as pd

from akshare.pro import cons


def set_token(token):
    df = pd.DataFrame([token], columns=["token"])
    user_home = os.path.expanduser("~")
    fp = os.path.join(user_home, cons.TOKEN_F_P)
    df.to_csv(fp, index=False)


def get_token():
    user_home = os.path.expanduser("~")
    fp = os.path.join(user_home, cons.TOKEN_F_P)
    if os.path.exists(fp):
        df = pd.read_csv(fp)
        return str(df.iloc[0]["token"])
    else:
        print(cons.TOKEN_ERR_MSG)
        return


if __name__ == "__main__":
    pass
