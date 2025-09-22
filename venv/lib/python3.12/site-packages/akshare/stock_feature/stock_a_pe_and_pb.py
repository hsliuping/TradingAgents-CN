#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/20 20:00
Desc: 乐咕乐股-A 股市盈率和市净率
https://legulegu.com/stockdata/shanghaiPE
"""

from datetime import datetime

import pandas as pd
import py_mini_racer
import requests

from akshare.stock_feature.stock_a_indicator import get_cookie_csrf

hash_code = """
function e(n) {
    var e, t, r = "", o = -1, f;
    if (n && n.length) {
        f = n.length;
        while ((o += 1) < f) {
            e = n.charCodeAt(o);
            t = o + 1 < f ? n.charCodeAt(o + 1) : 0;
            if (55296 <= e && e <= 56319 && 56320 <= t && t <= 57343) {
                e = 65536 + ((e & 1023) << 10) + (t & 1023);
                o += 1
            }
            if (e <= 127) {
                r += String.fromCharCode(e)
            } else if (e <= 2047) {
                r += String.fromCharCode(192 | e >>> 6 & 31, 128 | e & 63)
            } else if (e <= 65535) {
                r += String.fromCharCode(224 | e >>> 12 & 15, 128 | e >>> 6 & 63, 128 | e & 63)
            } else if (e <= 2097151) {
                r += String.fromCharCode(240 | e >>> 18 & 7, 128 | e >>> 12 & 63, 128 | e >>> 6 & 63, 128 | e & 63)
            }
        }
    }
    return r
}

function t(n) {
    var e, t, r, o, f, i = [], h;
    e = t = r = o = f = 0;
    if (n && n.length) {
        h = n.length;
        n += "";
        while (e < h) {
            r = n.charCodeAt(e);
            t += 1;
            if (r < 128) {
                i[t] = String.fromCharCode(r);
                e += 1
            } else if (r > 191 && r < 224) {
                o = n.charCodeAt(e + 1);
                i[t] = String.fromCharCode((r & 31) << 6 | o & 63);
                e += 2
            } else {
                o = n.charCodeAt(e + 1);
                f = n.charCodeAt(e + 2);
                i[t] = String.fromCharCode(
                    (r & 15) << 12 | (o & 63) << 6 | f & 63);
                e += 3
            }
        }
    }
    return i.join("")
}

function r(n, e) {
    var t = (n & 65535) + (e & 65535)
        , r = (n >> 16) + (e >> 16) + (t >> 16);
    return r << 16 | t & 65535
}

function o(n, e) {
    return n << e | n >>> 32 - e
}

function f(n, e) {
    var t = e ? "0123456789ABCDEF" : "0123456789abcdef", r = "", o, f = 0, i = n.length;
    for (; f < i; f += 1) {
        o = n.charCodeAt(f);
        r += t.charAt(o >>> 4 & 15) + t.charAt(o & 15)
    }
    return r
}

function i(n) {
    var e, t = n.length, r = "";
    for (e = 0; e < t; e += 1) {
        r += String.fromCharCode(n.charCodeAt(e) & 255, n.charCodeAt(e) >>> 8 & 255)
    }
    return r
}

function h(n) {
    var e, t = n.length, r = "";
    for (e = 0; e < t; e += 1) {
        r += String.fromCharCode(n.charCodeAt(e) >>> 8 & 255, n.charCodeAt(e) & 255)
    }
    return r
}

function u(n) {
    var e, t = n.length * 32, r = "";
    for (e = 0; e < t; e += 8) {
        r += String.fromCharCode(n[e >> 5] >>> 24 - e % 32 & 255)
    }
    return r
}

function a(n) {
    var e, t = n.length * 32, r = "";
    for (e = 0; e < t; e += 8) {
        r += String.fromCharCode(n[e >> 5] >>> e % 32 & 255)
    }
    return r
}

function c(n) {
    var e, t = n.length * 8, r = Array(n.length >> 2), o = r.length;
    for (e = 0; e < o; e += 1) {
        r[e] = 0
    }
    for (e = 0; e < t; e += 8) {
        r[e >> 5] |= (n.charCodeAt(e / 8) & 255) << e % 32
    }
    return r
}

function l(n) {
    var e, t = n.length * 8, r = Array(n.length >> 2), o = r.length;
    for (e = 0; e < o; e += 1) {
        r[e] = 0
    }
    for (e = 0; e < t; e += 8) {
        r[e >> 5] |= (n.charCodeAt(e / 8) & 255) << 24 - e % 32
    }
    return r
}

function D(n, e) {
    var t = e.length, r = Array(), o, f, i, h, u, a, c, l;
    a = Array(Math.ceil(n.length / 2));
    h = a.length;
    for (o = 0; o < h; o += 1) {
        a[o] = n.charCodeAt(o * 2) << 8 | n.charCodeAt(o * 2 + 1)
    }
    while (a.length > 0) {
        u = Array();
        i = 0;
        for (o = 0; o < a.length; o += 1) {
            i = (i << 16) + a[o];
            f = Math.floor(i / t);
            i -= f * t;
            if (u.length > 0 || f > 0) {
                u[u.length] = f
            }
        }
        r[r.length] = i;
        a = u
    }
    c = "";
    for (o = r.length - 1; o >= 0; o--) {
        c += e.charAt(r[o])
    }
    l = Math.ceil(n.length * 8 / (Math.log(e.length) / Math.log(2)));
    for (o = c.length; o < l; o += 1) {
        c = e[0] + c
    }
    return c
}

function B(n, e) {
    var t = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", r = "", o = n.length, f, i, h;
    e = e || "=";
    for (f = 0; f < o; f += 3) {
        h = n.charCodeAt(f) << 16 | (f + 1 < o ? n.charCodeAt(f + 1) << 8 : 0) | (f + 2 < o ? n.charCodeAt(f + 2) : 0);
        for (i = 0; i < 4; i += 1) {
            if (f * 8 + i * 6 > n.length * 8) {
                r += e
            } else {
                r += t.charAt(h >>> 6 * (3 - i) & 63)
            }
        }
    }
    return r
}

function hex(n) {
    return f(u(n, h), t)
}

function u(n) {
    n = h ? e(n) : n;
    return a(C(c(n), n.length * 8))
}

function l(n, t) {
    var r, o, f, i, u;
    n = h ? e(n) : n;
    t = h ? e(t) : t;
    r = c(n);
    if (r.length > 16) {
        r = C(r, n.length * 8)
    }
    o = Array(16),
        f = Array(16);
    for (u = 0; u < 16; u += 1) {
        o[u] = r[u] ^ 909522486;
        f[u] = r[u] ^ 1549556828
    }
    i = C(o.concat(c(t)), 512 + t.length * 8);
    return a(C(f.concat(i), 512 + 128))
}

function C(n, e) {
    var t, o, f, i, h, u = 1732584193, a = -271733879, c = -1732584194, l = 271733878;
    n[e >> 5] |= 128 << e % 32;
    n[(e + 64 >>> 9 << 4) + 14] = e;
    for (t = 0; t < n.length; t += 16) {
        o = u;
        f = a;
        i = c;
        h = l;
        u = s(u, a, c, l, n[t + 0], 7, -680876936);
        l = s(l, u, a, c, n[t + 1], 12, -389564586);
        c = s(c, l, u, a, n[t + 2], 17, 606105819);
        a = s(a, c, l, u, n[t + 3], 22, -1044525330);
        u = s(u, a, c, l, n[t + 4], 7, -176418897);
        l = s(l, u, a, c, n[t + 5], 12, 1200080426);
        c = s(c, l, u, a, n[t + 6], 17, -1473231341);
        a = s(a, c, l, u, n[t + 7], 22, -45705983);
        u = s(u, a, c, l, n[t + 8], 7, 1770035416);
        l = s(l, u, a, c, n[t + 9], 12, -1958414417);
        c = s(c, l, u, a, n[t + 10], 17, -42063);
        a = s(a, c, l, u, n[t + 11], 22, -1990404162);
        u = s(u, a, c, l, n[t + 12], 7, 1804603682);
        l = s(l, u, a, c, n[t + 13], 12, -40341101);
        c = s(c, l, u, a, n[t + 14], 17, -1502002290);
        a = s(a, c, l, u, n[t + 15], 22, 1236535329);
        u = w(u, a, c, l, n[t + 1], 5, -165796510);
        l = w(l, u, a, c, n[t + 6], 9, -1069501632);
        c = w(c, l, u, a, n[t + 11], 14, 643717713);
        a = w(a, c, l, u, n[t + 0], 20, -373897302);
        u = w(u, a, c, l, n[t + 5], 5, -701558691);
        l = w(l, u, a, c, n[t + 10], 9, 38016083);
        c = w(c, l, u, a, n[t + 15], 14, -660478335);
        a = w(a, c, l, u, n[t + 4], 20, -405537848);
        u = w(u, a, c, l, n[t + 9], 5, 568446438);
        l = w(l, u, a, c, n[t + 14], 9, -1019803690);
        c = w(c, l, u, a, n[t + 3], 14, -187363961);
        a = w(a, c, l, u, n[t + 8], 20, 1163531501);
        u = w(u, a, c, l, n[t + 13], 5, -1444681467);
        l = w(l, u, a, c, n[t + 2], 9, -51403784);
        c = w(c, l, u, a, n[t + 7], 14, 1735328473);
        a = w(a, c, l, u, n[t + 12], 20, -1926607734);
        u = F(u, a, c, l, n[t + 5], 4, -378558);
        l = F(l, u, a, c, n[t + 8], 11, -2022574463);
        c = F(c, l, u, a, n[t + 11], 16, 1839030562);
        a = F(a, c, l, u, n[t + 14], 23, -35309556);
        u = F(u, a, c, l, n[t + 1], 4, -1530992060);
        l = F(l, u, a, c, n[t + 4], 11, 1272893353);
        c = F(c, l, u, a, n[t + 7], 16, -155497632);
        a = F(a, c, l, u, n[t + 10], 23, -1094730640);
        u = F(u, a, c, l, n[t + 13], 4, 681279174);
        l = F(l, u, a, c, n[t + 0], 11, -358537222);
        c = F(c, l, u, a, n[t + 3], 16, -722521979);
        a = F(a, c, l, u, n[t + 6], 23, 76029189);
        u = F(u, a, c, l, n[t + 9], 4, -640364487);
        l = F(l, u, a, c, n[t + 12], 11, -421815835);
        c = F(c, l, u, a, n[t + 15], 16, 530742520);
        a = F(a, c, l, u, n[t + 2], 23, -995338651);
        u = E(u, a, c, l, n[t + 0], 6, -198630844);
        l = E(l, u, a, c, n[t + 7], 10, 1126891415);
        c = E(c, l, u, a, n[t + 14], 15, -1416354905);
        a = E(a, c, l, u, n[t + 5], 21, -57434055);
        u = E(u, a, c, l, n[t + 12], 6, 1700485571);
        l = E(l, u, a, c, n[t + 3], 10, -1894986606);
        c = E(c, l, u, a, n[t + 10], 15, -1051523);
        a = E(a, c, l, u, n[t + 1], 21, -2054922799);
        u = E(u, a, c, l, n[t + 8], 6, 1873313359);
        l = E(l, u, a, c, n[t + 15], 10, -30611744);
        c = E(c, l, u, a, n[t + 6], 15, -1560198380);
        a = E(a, c, l, u, n[t + 13], 21, 1309151649);
        u = E(u, a, c, l, n[t + 4], 6, -145523070);
        l = E(l, u, a, c, n[t + 11], 10, -1120210379);
        c = E(c, l, u, a, n[t + 2], 15, 718787259);
        a = E(a, c, l, u, n[t + 9], 21, -343485551);
        u = r(u, o);
        a = r(a, f);
        c = r(c, i);
        l = r(l, h)
    }
    return Array(u, a, c, l)
}

function A(n, e, t, f, i, h) {
    return r(o(r(r(e, n), r(f, h)), i), t)
}

function s(n, e, t, r, o, f, i) {
    return A(e & t | ~e & r, n, e, o, f, i)
}

function w(n, e, t, r, o, f, i) {
    return A(e & r | t & ~r, n, e, o, f, i)
}

function F(n, e, t, r, o, f, i) {
    return A(e ^ t ^ r, n, e, o, f, i)
}

function E(n, e, t, r, o, f, i) {
    return A(t ^ (e | ~r), n, e, o, f, i)
}
"""


def stock_market_pe_lg(symbol: str = "深证") -> pd.DataFrame:
    """
    乐咕乐股-主板市盈率
    https://legulegu.com/stockdata/shanghaiPE
    :param symbol: choice of {"上证", "深证", "创业板", "科创版"}
    :type symbol: str
    :return: 指定市场的市盈率数据
    :rtype: pandas.DataFrame
    """
    js_functions = py_mini_racer.MiniRacer()
    js_functions.eval(hash_code)
    token = js_functions.call("hex", datetime.now().date().isoformat()).lower()
    if symbol in {"上证", "深证", "创业板"}:
        url = "https://legulegu.com/api/stock-data/market-pe"
        symbol_map = {
            "上证": "1",
            "深证": "2",
            "创业板": "4",
        }
        url_map = {
            "上证": "https://legulegu.com/stockdata/shanghaiPE",
            "深证": "https://legulegu.com/stockdata/shenzhenPE",
            "创业板": "https://legulegu.com/stockdata/cybPE",
        }
        params = {"token": token, "marketId": symbol_map[symbol]}
        r = requests.get(url, params=params, **get_cookie_csrf(url=url_map[symbol]))
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df["date"] = (
            pd.to_datetime(temp_df["date"], unit="ms", utc=True)
            .dt.tz_convert("Asia/Shanghai")
            .dt.date
        )
        temp_df = temp_df[
            [
                "date",
                "close",
                "pe",
            ]
        ]
        temp_df.columns = [
            "日期",
            "指数",
            "平均市盈率",
        ]
        return temp_df
    else:
        url = "https://legulegu.com/api/stockdata/get-ke-chuang-ban-pe"
        params = {"token": token}
        r = requests.get(
            url,
            params=params,
            **get_cookie_csrf(url="https://legulegu.com/stockdata/ke-chuang-ban-pe"),
        )
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df["date"] = (
            pd.to_datetime(temp_df["date"], unit="ms", utc=True)
            .dt.tz_convert("Asia/Shanghai")
            .dt.date
        )
        temp_df = temp_df[
            [
                "date",
                "close",
                "pe",
            ]
        ]
        temp_df.columns = [
            "日期",
            "总市值",
            "市盈率",
        ]
        return temp_df


def stock_index_pe_lg(symbol: str = "沪深300") -> pd.DataFrame:
    """
    乐咕乐股-指数市盈率
    https://legulegu.com/stockdata/sz50-ttm-lyr
    :param symbol: choice of {"上证50", "沪深300", "上证380", "创业板50", "中证500", "上证180", "深证红利", "深证100", "中证1000", "上证红利", "中证100", "中证800"}
    :type symbol: str
    :return: 指定指数的市盈率数据
    :rtype: pandas.DataFrame
    """
    js_functions = py_mini_racer.MiniRacer()
    js_functions.eval(hash_code)
    token = js_functions.call("hex", datetime.now().date().isoformat()).lower()
    symbol_map = {
        "上证50": "000016.SH",
        "沪深300": "000300.SH",
        "上证380": "000009.SH",
        "创业板50": "399673.SZ",
        "中证500": "000905.SH",
        "上证180": "000010.SH",
        "深证红利": "399324.SZ",
        "深证100": "399330.SZ",
        "中证1000": "000852.SH",
        "上证红利": "000015.SH",
        "中证100": "000903.SH",
        "中证800": "000906.SH",
    }
    url = "https://legulegu.com/api/stockdata/index-basic-pe"
    params = {"token": token, "indexCode": symbol_map[symbol]}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/sz50-ttm-lyr"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    temp_df = temp_df[
        [
            "date",
            "close",
            "lyrPe",
            "addLyrPe",
            "middleLyrPe",
            "ttmPe",
            "addTtmPe",
            "middleTtmPe",
        ]
    ]
    temp_df.columns = [
        "日期",
        "指数",
        "等权静态市盈率",
        "静态市盈率",
        "静态市盈率中位数",
        "等权滚动市盈率",
        "滚动市盈率",
        "滚动市盈率中位数",
    ]
    return temp_df


def stock_market_pb_lg(symbol: str = "上证") -> pd.DataFrame:
    """
    乐咕乐股-主板市净率
    https://legulegu.com/stockdata/shanghaiPB
    :param symbol: choice of {"上证", "深证", "创业板", "科创版"}
    :type symbol: str
    :return: 指定市场的市净率数据
    :rtype: pandas.DataFrame
    """
    js_functions = py_mini_racer.MiniRacer()
    js_functions.eval(hash_code)
    token = js_functions.call("hex", datetime.now().date().isoformat()).lower()
    url = "https://legulegu.com/api/stockdata/index-basic-pb"
    symbol_map = {"上证": "1", "深证": "2", "创业板": "4", "科创版": "7"}
    url_map = {
        "上证": "https://legulegu.com/stockdata/shanghaiPB",
        "深证": "https://legulegu.com/stockdata/shenzhenPB",
        "创业板": "https://legulegu.com/stockdata/cybPB",
        "科创版": "https://legulegu.com/stockdata/ke-chuang-ban-pb",
    }
    params = {"token": token, "indexCode": symbol_map[symbol]}
    r = requests.get(url, params=params, **get_cookie_csrf(url=url_map[symbol]))
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    temp_df = temp_df[
        [
            "date",
            "close",
            "addPb",
            "pb",
            "middlePb",
        ]
    ]
    temp_df.columns = [
        "日期",
        "指数",
        "市净率",
        "等权市净率",
        "市净率中位数",
    ]
    return temp_df


def stock_index_pb_lg(symbol: str = "上证50") -> pd.DataFrame:
    """
    乐咕乐股-指数市净率
    https://legulegu.com/stockdata/sz50-pb
    :param symbol: choice of {"上证50", "沪深300", "上证380", "创业板50", "中证500", "上证180", "深证红利", "深证100", "中证1000", "上证红利", "中证100", "中证800"}
    :type symbol: str
    :return: 指定指数的市净率数据
    :rtype: pandas.DataFrame
    """
    js_functions = py_mini_racer.MiniRacer()
    js_functions.eval(hash_code)
    token = js_functions.call("hex", datetime.now().date().isoformat()).lower()
    symbol_map = {
        "上证50": "000016.SH",
        "沪深300": "000300.SH",
        "上证380": "000009.SH",
        "创业板50": "399673.SZ",
        "中证500": "000905.SH",
        "上证180": "000010.SH",
        "深证红利": "399324.SZ",
        "深证100": "399330.SZ",
        "中证1000": "000852.SH",
        "上证红利": "000015.SH",
        "中证100": "000903.SH",
        "中证800": "000906.SH",
    }
    url = "https://legulegu.com/api/stockdata/index-basic-pb"
    params = {"token": token, "indexCode": symbol_map[symbol]}
    r = requests.get(
        url,
        params=params,
        **get_cookie_csrf(url="https://legulegu.com/stockdata/zz500-ttm-lyr"),
    )
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df["date"] = (
        pd.to_datetime(temp_df["date"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    temp_df = temp_df[
        [
            "date",
            "close",
            "addPb",
            "pb",
            "middlePb",
        ]
    ]
    temp_df.columns = [
        "日期",
        "指数",
        "市净率",
        "等权市净率",
        "市净率中位数",
    ]
    return temp_df


if __name__ == "__main__":
    stock_market_pe_lg_df = stock_market_pe_lg(symbol="上证")
    print(stock_market_pe_lg_df)

    stock_market_pe_lg_df = stock_market_pe_lg(symbol="科创版")
    print(stock_market_pe_lg_df)

    for item in {"上证", "深证", "创业板", "科创版"}:
        stock_market_pe_lg_df = stock_market_pe_lg(symbol=item)
        print(stock_market_pe_lg_df)

    stock_index_pe_lg_df = stock_index_pe_lg(symbol="上证50")
    print(stock_index_pe_lg_df)

    for item in [
        "上证50",
        "沪深300",
        "上证380",
        "创业板50",
        "中证500",
        "上证180",
        "深证红利",
        "深证100",
        "中证1000",
        "上证红利",
        "中证100",
        "中证800",
    ]:
        stock_index_pe_lg_df = stock_index_pe_lg(symbol=item)
        print(stock_index_pe_lg_df)

    for item in {"上证", "深证", "创业板", "科创版"}:
        stock_market_pb_lg_df = stock_market_pb_lg(symbol=item)
        print(stock_market_pb_lg_df)

    for item in [
        "上证50",
        "沪深300",
        "上证380",
        "创业板50",
        "中证500",
        "上证180",
        "深证红利",
        "深证100",
        "中证1000",
        "上证红利",
        "中证100",
        "中证800",
    ]:
        stock_index_pe_lg_df = stock_index_pb_lg(symbol=item)
        print(stock_index_pe_lg_df)
