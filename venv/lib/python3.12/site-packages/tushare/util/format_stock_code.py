# -*- coding: utf-8 -*-
"""
Created on 2021-12-13 16:29:25
---------
@summary: 股票代码 code 格式化
---------
@author: yangyx01
"""
import re


def format_stock_code(x, special=""):
    """
    股票代码 code 格式化
    @param x:
    @param special:
    @return:
    """
    x = str(x)
    x = "".join(filter(str.isdigit, x))

    stock_len = 6
    hk_stock_len = 5
    if special:
        x = str(x)
        if "行业" in special or "概念" in special:
            x = x.zfill(stock_len) if len(x) < stock_len else x
            return '%s.TI' % x
        elif special == "港股":
            r = re.search(r"(\d+)", str(x), re.S | re.M)
            if not r:
                return x
            else:
                x = r.group(1)
                x = x.zfill(hk_stock_len) if len(x) < hk_stock_len else x
            return '%s.HK' % x
        elif special == "场外基金" or special == "热基":
            x = x.zfill(stock_len) if len(x) < stock_len else x
            return '%s.OF' % x
        elif special == "可转债":
            if str(x).startswith('11'):
                x = x.zfill(stock_len) if len(x) < stock_len else x
                return '%s.SH' % x
            elif str(x).startswith('12'):
                x = x.zfill(stock_len) if len(x) < stock_len else x
                return '%s.SZ' % x
    if not x[0].isdigit():
        return x.upper()
    if str(x[0:3]) in ['920'] or str(x[0]) in ['8', '4']:
        x = x.zfill(stock_len) if len(x) < stock_len else x
        return '%s.BJ' % x
    if str(x[0]) in ['5', '6'] or str(x[0:3]) in ['900']:
        x = x.zfill(stock_len) if len(x) < stock_len else x
        return '%s.SH' % x
    else:
        x = x.zfill(stock_len) if len(x) < stock_len else x
        return '%s.SZ' % x

def a_symbol_verify(x):
    l = str(x).upper().split(".")
    if not x[-1].isdigit():
        return True
    elif len(l) == 2:
        return True
    else:
        return False


def symbol_verify(x):
    ss = x.split(",")
    if len(ss) > 1:
        if a_symbol_verify(ss[0]):
            return x
        else:
            raise '请按照 "000001.SZ,000001.SZ,000001.SZ" 格式传入symbol'
    else:
        if a_symbol_verify(x):
            return x
        else:
            raise '请按照 "000001.SZ" 格式传入symbol'


def verify_stock_or_index(x):
    """
    判断代码是否是 股票 True  指数 False
    @param x:
    @return:
    """
    x = str(x).upper()
    if x.startswith('39') and x.endswith('SZ'):
        return True
    elif x.startswith('30') and x.endswith('SZ'):
        return True
    elif x.startswith('0') and x.endswith('SH'):
        return False
    elif x.startswith('0') and x.endswith('SZ'):
        return True
    elif x.endswith("SH"):
        return False
    # elif x.startswith('6') and x.endswith('SH'):
    #     return True
    elif x.startswith('8') and x.endswith('BJ'):
        return True
    elif x.startswith('4') and x.endswith('BJ'):
        return True
    elif x.startswith('920') and x.endswith('BJ'):
        return True
    elif x.startswith('9') and x.endswith('CSI'):
        return False
    else:
        return True


if __name__ == '__main__':
    # s = symbol_verify("13.SH")
    # # s = symbol_verify("sh13")
    # s = symbol_verify("sz000001")
    # s = symbol_verify("000001.SZ")
    # s = symbols_f("000001", special="港股")
    # s = verify_stock_or_index(x="399005.SZ")
    s = format_stock_code(x="sz92052")
    print(s)
