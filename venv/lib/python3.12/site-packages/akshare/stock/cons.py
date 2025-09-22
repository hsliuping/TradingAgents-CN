#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/15 18:00
Desc: 股票配置文件
"""

xq_a_token = "78591293b0e2907176f7f507563a6b9ac189af0b"

# zh-sina-kcb
zh_sina_kcb_stock_url = ("http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                         "Market_Center.getHQNodeData")
zh_sina_kcb_stock_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "kcb",
    "symbol": "",
    "_s_r_a": "auto",
}
zh_sina_kcb_stock_count_url = ("http://vip.stock.finance.sina.com.cn/quotes_service/api/"
                               "json_v2.php/Market_Center.getHQNodeStockCount?node=kcb")
zh_sina_kcb_stock_hist_url = ("https://quotes.sina.cn/cn/api/jsonp.php/var%20_{}{}=/"
                              "KC_MarketDataService.getKLineData?symbol={}")
zh_sina_kcb_stock_amount_url = ("https://stock.finance.sina.com.cn/stock/api/jsonp.php/"
                                "var%20KKE_ShareAmount_{}=/StockService.getAmountBySymbol?_=20&symbol={}")
zh_sina_kcb_stock_hfq_url = "https://finance.sina.com.cn/realstock/company/{}/hfq.js"
zh_sina_kcb_stock_qfq_url = "https://finance.sina.com.cn/realstock/company/{}/qfq.js"

# zh-sina-a
zh_sina_a_stock_url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
zh_sina_a_stock_payload = {
    "page": "1",
    "num": "80",
    "sort": "symbol",
    "asc": "1",
    "node": "hs_a",
    "symbol": "",
    "_s_r_a": "page",
}
zh_sina_a_stock_count_url = ("http://vip.stock.finance.sina.com.cn/quotes_service/api/"
                             "json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a")
zh_sina_a_stock_hist_url = (
    "https://finance.sina.com.cn/realstock/company/{}/hisdata_klc2/klc_kl.js"
)
zh_sina_a_stock_amount_url = ("https://stock.finance.sina.com.cn/stock/api/jsonp.php/"
                              "var%20KKE_ShareAmount_{}=/StockService.getAmountBySymbol?_=20&symbol={}")
zh_sina_a_stock_hfq_url = "https://finance.sina.com.cn/realstock/company/{}/hfq.js"
zh_sina_a_stock_qfq_url = "https://finance.sina.com.cn/realstock/company/{}/qfq.js"

# us-sina
us_sina_stock_hist_qfq_url = (
    "https://finance.sina.com.cn/us_stock/company/reinstatement/{}_qfq.js"
)
us_sina_stock_hist_url = (
    "https://finance.sina.com.cn/us_stock/company/hisdata/klc_kl_{}.js"
)
us_sina_stock_list_url = ("http://stock.finance.sina.com.cn/usstock/api/jsonp.php"
                          "/IO.XSRV2.CallbackList[{}]/US_CategoryService.getList")
us_sina_stock_dict_payload = {
    "page": "2",
    "num": "20",
    "sort": "",
    "asc": "0",
    "market": "",
    "id": "",
}
js_hash_text = """
    function d(s){
		var a, i, j, c, c0, c1, c2, r;
		var _s = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$';
		var _r64 = function(s, b)
		{
			return ((s | (s << 6)) >>> (b % 6)) & 63;
		};
		a = [];
		c = [];
		for (i = 0; i < s.length; i++)
		{
			c0 = s.charCodeAt(i);
			if (c0 & ~255)
			{
				c0 = (c0 >> 8) ^ c0;
			}
			c.push(c0);
			if (c.length == 3 || i == s.length - 1)
			{
				while(c.length < 3)
				{
					c.push(0);
				}
				a.push((c[0] >> 2) & 63);
				a.push(((c[1] >> 4) | (c[0] << 6)) & 63);
				a.push(((c[1] << 4) | (c[2] >> 2)) & 63);
				a.push(c[2] & 63);
				c = [];
			}
		}
		while (a.length < 16)
		{
			a.push(0);
		}
		r = 0;
		for (i = 0; i < a.length; i++)
		{
			r ^= (_r64(a[i] ^ (r | i), i) ^ _r64(i, r)) & 63;
		}
		for (i = 0; i < a.length; i++)
		{
			a[i] = (_r64((r | i & a[i]), r) ^ a[i]) & 63;
			r += a[i];
		}
		for (i = 16; i < a.length; i++)
		{
			a[i % 16] ^= (a[i] + (i >>> 4)) & 63;
		}
		for (i = 0; i < 16; i++)
		{
			a[i] = _s.substr(a[i], 1);
		}
		a = a.slice(0, 16).join('');
		return a;
	}
"""
# hk-sina
hk_sina_stock_hist_hfq_url = "https://finance.sina.com.cn/stock/hkstock/{}/hfq.js"
hk_sina_stock_hist_qfq_url = "https://finance.sina.com.cn/stock/hkstock/{}/qfq.js"
hk_sina_stock_hist_url = "https://finance.sina.com.cn/stock/hkstock/{}/klc_kl.js"
hk_sina_stock_list_url = ("http://vip.stock.finance.sina.com.cn/quotes_service/api/"
                          "json_v2.php/Market_Center.getHKStockData")

hk_sina_stock_dict_payload = {
    "page": "1",
    "num": "3000",
    "sort": "symbol",
    "asc": "1",
    "node": "qbgg_hk",
    "_s_r_a": "page",
}

# hk-tx
hk_url = "http://stock.gtimg.cn/data/hk_rank.php"
hk_headers = {
    "Referer": "http://stockapp.finance.qq.com/mstats/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
}
hk_payload = {
    "board": "A_H",
    "metric": "price",
    "pageSize": "20",
    "reqPage": "1",
    "order": "decs",
    "var_name": "list_data",
}

hk_stock_url = "http://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get"
hk_stock_headers = {
    # "Referer": "http://gu.qq.com/hk00168/gp",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36"
}
hk_stock_payload = {
    "_var": "kline_dayhfq{}",
    "param": "hk{},day,{}-01-01,{}-12-31,640,hfq",
    "r": "",
}

# usa
url_usa_daily = "http://webusstock.hermes.hexun.com/usa/kline"
payload_usa_daily = {
    "code": "NASDAQNTES",
    "start": "20191026213000",
    "number": "-1000",
    "type": "5",
}

# china
hx_url = "http://stockdata.stock.hexun.com/zrbg/data/zrbList.aspx"

hx_headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Cookie": "ADVC=371c0a2afd9a7b; UM_distinctid=16a24d29c4f142-0f969e46eea4c7-e323069-1fa400-16a24d29c50aa5; "
              "HexunTrack=SID=20190416142542146f54a3710276640a88fea687ad6a7bcb0&CITY=51&TOWN=510100; "
              "vjuids=11fcc219b5.16a820267e4.0.cc0391a93be56; vjlast=1556959357.1556959357.30; "
              "__utma=194262068.1423418741.1558975446.1558975446.1558975446.1; "
              "__utmz=194262068.1558975446.1.1.utmcsr=baidu|utmccn=(organic)|utmcmd=organic; "
              "ASL=18179,anzqo,7ca108c3ded485387ca108c27ca108b97ca108ef; "
              "cn_1263247791_dplus=%7B%22distinct_id%22%3A%20%2216a24d29c4f142-0f969e46eea4c7-e323069-1fa400-"
              "16a24d29c50aa5%22%2C%22userFirstDate%22%3A%20%2220190504%22%2C%22userID%22%3A%20%22%22%2C%22us"
              "erName%22%3A%20%22%22%2C%22userType%22%3A%20%22nologinuser%22%2C%22userLoginDate%22%3A%20%2"
              "220191010%22%2C%22%24_sessionid%22%3A%200%2C%22%24_sessionTime%22%3A%201570727325%2C%22%2"
              "4dp%22%3A%200%2C%22%24_sessionPVTime%22%3A%201570727325%2C%22initial_view_time%22%3A%20%"
              "221556958609%22%2C%22initial_referrer%22%3A%20%22https%3A%2F%2Fwww.baidu.com%2Flink%3F"
              "url%3DJmHPP1QGABcJs0kzrvZREqHK_nobidR7d7YPCQF75loa5N33Au5q_xFu8y9VPlvl8O6I7b1LmRuhIicc"
              "TnFW-_%26wd%3D%26eqid%3Db55837ee0001a310000000025ccd4f55%22%2C%22initial_referrer_doma"
              "in%22%3A%20%22www.baidu.com%22%2C%22%24recent_outside_referrer%22%3A%20%22www.baidu.co"
              "m%22%7D; hxck_webdev1_general=bondjlvcookie_list=019124_11%e5%9b%bd%e5%80%ba24_1&npF"
              "utjlvcookie_list=czcers1409|WT1009; appToken=pc%2Cother%2Cchrome%2ChxAppSignId9625376"
              "0252191461570688954189%2CHXGG20190415; __jsluid_h=08f65cba22ad34dc3fd095b5b986c8a4",
    "Host": "stockdata.stock.hexun.com",
    "Pragma": "no-cache",
    "Referer": "http://stockdata.stock.hexun.com/zrbg/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/77.0.3865.120 Safari/537.36",
}

hx_params = {
    "date": "2018-12-31",
    "count": "20",
    "pname": "20",
    "titType": "null",
    "page": "8",
    "callback": "hxbase_json11571989979887",
}

hk_js_decode = """
function d(t) {
            var e, i, n, r, a, o, s, l = (arguments,
            864e5), u = 7657, c = [], d = [], h = ~(3 << 30), f = 1 << 30, m = [0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 20, 23, 24, 27, 29, 30], p = Math, g = function() {
                var l, u;
                for (l = 0; 64 > l; l++)
                    d[l] = p.pow(2, l),
                    26 > l && (c[l] = v(l + 65),
                    c[l + 26] = v(l + 97),
                    10 > l && (c[l + 52] = v(l + 48)));
                for (c.push("+", "/"),
                c = c.join(""),
                i = t.split(""),
                n = i.length,
                l = 0; n > l; l++)
                    i[l] = c.indexOf(i[l]);
                return r = {},
                e = o = 0,
                a = {},
                u = w([12, 6]),
                s = 63 ^ u[1],
                {
                    _1479: D,
                    _136: _,
                    _200: C,
                    _139: R,
                    _197: A,
                    _3466: O
                }["_" + u[0]] || function() {
                    return []
                }
            }, v = String.fromCharCode, b = function(t) {
                return t === {}._
            }, N = function() {
                var t, e;
                for (t = y(),
                e = 1; ; ) {
                    if (!y())
                        return e * (2 * t - 1);
                    e++
                }
            }, y = function() {
                var t;
                return e >= n ? 0 : (t = i[e] & 1 << o,
                o++,
                o >= 6 && (o -= 6,
                e++),
                !!t)
            }, w = function(t, r, a) {
                var s, l, u, c, h;
                for (l = [],
                u = 0,
                r || (r = []),
                a || (a = []),
                s = 0; s < t.length; s++)
                    if (c = t[s],
                    u = 0,
                    c) {
                        if (e >= n)
                            return l;
                        if (t[s] <= 0)
                            u = 0;
                        else if (t[s] <= 30) {
                            for (; h = 6 - o,
                            h = c > h ? h : c,
                            u |= (i[e] >> o & (1 << h) - 1) << t[s] - c,
                            o += h,
                            o >= 6 && (o -= 6,
                            e++),
                            c -= h,
                            !(0 >= c); )
                                ;
                            r[s] && u >= d[t[s] - 1] && (u -= d[t[s]])
                        } else
                            u = w([30, t[s] - 30], [0, r[s]]),
                            a[s] || (u = u[0] + u[1] * d[30]);
                        l[s] = u
                    } else
                        l[s] = 0;
                return l
            }, x = function() {
                var t;
                return t = w([3])[0],
                1 == t ? (r.d = w([18], [1])[0],
                t = 0) : t || (t = w([6])[0]),
                t
            }, S = function(t) {
                var e, i, n;
                for (t > 1 && (e = 0),
                e = 0; t > e; e++)
                    r.d++,
                    n = r.d % 7,
                    (3 == n || 4 == n) && (r.d += 5 - n);
                return i = new Date,
                i.setTime((u + r.d) * l),
                i
            }, k = function(t) {
                var e, i, n;
                for (n = r.wd || 62,
                e = 0; t > e; e++)
                    do
                        r.d++;
                    while (!(n & 1 << (r.d % 7 + 10) % 7));
                return i = new Date,
                i.setTime((u + r.d) * l),
                i
            }, T = function(t) {
                var e, i, n;
                return t ? 0 > t ? (e = T(-t),
                [-e[0], -e[1]]) : (e = t % 3,
                i = (t - e) / 3,
                n = [i, i],
                e && n[e - 1]++,
                n) : [0, 0]
            }, P = function(t, e, i) {
                var n, r, a;
                for (r = "number" == typeof e ? T(e) : e,
                a = T(i),
                n = [a[0] - r[0], a[1] - r[1]],
                r = 1; n[0] < n[1]; )
                    r *= 5,
                    n[1]--;
                for (; n[1] < n[0]; )
                    r *= 2,
                    n[0]--;
                if (r > 1 && (t *= r),
                n = n[0],
                t = E(t),
                0 > n) {
                    for (; t.length + n <= 0; )
                        t = "0" + t;
                    return n += t.length,
                    r = t.substr(0, n) - 0,
                    void 0 === i ? r + "." + t.substr(n) - 0 : (a = t.charAt(n) - 0,
                    a > 5 ? r++ : 5 == a && (t.substr(n + 1) - 0 > 0 ? r++ : r += 1 & r),
                    r)
                }
                for (; n > 0; n--)
                    t += "0";
                return t - 0
            }, C = function() {
                var t, i, a, o, l;
                if (s >= 1)
                    return [];
                for (r.d = w([18], [1])[0] - 1,
                a = w([3, 3, 30, 6]),
                r.p = a[0],
                r.ld = a[1],
                r.cd = a[2],
                r.c = a[3],
                r.m = p.pow(10, r.p),
                r.pc = r.cd / r.m,
                i = [],
                t = 0; o = {
                    d: 1
                },
                y() && (a = w([3])[0],
                0 == a ? o.d = w([6])[0] : 1 == a ? (r.d = w([18])[0],
                o.d = 0) : o.d = a),
                l = {
                    date: S(o.d)
                },
                y() && (r.ld += N()),
                a = w([3 * r.ld], [1]),
                r.cd += a[0],
                l.close = r.cd / r.m,
                i.push(l),
                !(e >= n) && (e != n - 1 || 63 & (r.c ^ t + 1)); t++)
                    ;
                return i[0].prevclose = r.pc,
                i
            }, _ = function() {
                var t, i, a, o, l, u, c, d, h, f, m;
                if (s > 2)
                    return [];
                for (c = [],
                h = {
                    v: "volume",
                    p: "price",
                    a: "avg_price"
                },
                r.d = w([18], [1])[0] - 1,
                d = {
                    date: S(1)
                },
                a = w(1 > s ? [3, 3, 4, 1, 1, 1, 5] : [4, 4, 4, 1, 1, 1, 3]),
                t = 0; 7 > t; t++)
                    r[["la", "lp", "lv", "tv", "rv", "zv", "pp"][t]] = a[t];
                for (r.m = p.pow(10, r.pp),
                s >= 1 ? (a = w([3, 3]),
                r.c = a[0],
                a = a[1]) : (a = 5,
                r.c = 2),
                r.pc = w([6 * a])[0],
                d.pc = r.pc / r.m,
                r.cp = r.pc,
                r.da = 0,
                r.sa = r.sv = 0,
                t = 0; !(e >= n) && (e != n - 1 || 7 & (r.c ^ t)); t++) {
                    for (l = {},
                    o = {},
                    f = r.tv ? y() : 1,
                    i = 0; 3 > i; i++)
                        if (m = ["v", "p", "a"][i],
                        (f ? y() : 0) && (a = N(),
                        r["l" + m] += a),
                        u = "v" == m && r.rv ? y() : 1,
                        a = w([3 * r["l" + m] + ("v" == m ? 7 * u : 0)], [!!i])[0] * (u ? 1 : 100),
                        o[m] = a,
                        "v" == m) {
                            if (!(l[h[m]] = a) && (s > 1 || 241 > t) && (r.zv ? !y() : 1)) {
                                o.p = 0;
                                break
                            }
                        } else
                            "a" == m && (r.da = (1 > s ? 0 : r.da) + o.a);
                    r.sv += o.v,
                    l[h.p] = (r.cp += o.p) / r.m,
                    r.sa += o.v * r.cp,
                    l[h.a] = b(o.a) ? t ? c[t - 1][h.a] : l[h.p] : r.sv ? ((p.floor((r.sa * (2e3 / r.m) + r.sv) / r.sv) >> 1) + r.da) / 1e3 : l[h.p] + r.da / 1e3,
                    c.push(l)
                }
                return c[0].date = d.date,
                c[0].prevclose = d.pc,
                c
            }, D = function() {
                var t, e, i, n, a, o, l;
                if (s >= 1)
                    return [];
                for (r.lv = 0,
                r.ld = 0,
                r.cd = 0,
                r.cv = [0, 0],
                r.p = w([6])[0],
                r.d = w([18], [1])[0] - 1,
                r.m = p.pow(10, r.p),
                a = w([3, 3]),
                r.md = a[0],
                r.mv = a[1],
                t = []; a = w([6]),
                a.length; ) {
                    if (i = {
                        c: a[0]
                    },
                    n = {},
                    i.d = 1,
                    32 & i.c)
                        for (; ; ) {
                            if (a = w([6])[0],
                            63 == (16 | a)) {
                                l = 16 & a ? "x" : "u",
                                a = w([3, 3]),
                                i[l + "_d"] = a[0] + r.md,
                                i[l + "_v"] = a[1] + r.mv;
                                break
                            }
                            if (32 & a) {
                                o = 8 & a ? "d" : "v",
                                l = 16 & a ? "x" : "u",
                                i[l + "_" + o] = (7 & a) + r["m" + o];
                                break
                            }
                            if (o = 15 & a,
                            0 == o ? i.d = w([6])[0] : 1 == o ? (r.d = o = w([18])[0],
                            i.d = 0) : i.d = o,
                            !(16 & a))
                                break
                        }
                    n.date = S(i.d);
                    for (o in {
                        v: 0,
                        d: 0
                    })
                        b(i["x_" + o]) || (r["l" + o] = i["x_" + o]),
                        b(i["u_" + o]) && (i["u_" + o] = r["l" + o]);
                    for (i.l_l = [i.u_d, i.u_d, i.u_d, i.u_d, i.u_v],
                    l = m[15 & i.c],
                    1 & i.u_v && (l = 31 - l),
                    16 & i.c && (i.l_l[4] += 2),
                    e = 0; 5 > e; e++)
                        l & 1 << 4 - e && i.l_l[e]++,
                        i.l_l[e] *= 3;
                    i.d_v = w(i.l_l, [1, 0, 0, 1, 1], [0, 0, 0, 0, 1]),
                    o = r.cd + i.d_v[0],
                    n.open = o / r.m,
                    n.high = (o + i.d_v[1]) / r.m,
                    n.low = (o - i.d_v[2]) / r.m,
                    n.close = (o + i.d_v[3]) / r.m,
                    a = i.d_v[4],
                    "number" == typeof a && (a = [a, a >= 0 ? 0 : -1]),
                    r.cd = o + i.d_v[3],
                    l = r.cv[0] + a[0],
                    r.cv = [l & h, r.cv[1] + a[1] + !!((r.cv[0] & h) + (a[0] & h) & f)],
                    n.volume = (r.cv[0] & f - 1) + r.cv[1] * f,
                    t.push(n)
                }
                return t
            }, R = function() {
                var t, e, i, n;
                if (s > 1)
                    return [];
                for (r.l = 0,
                n = -1,
                r.d = w([18])[0] - 1,
                i = w([18])[0]; r.d < i; )
                    e = S(1),
                    0 >= n ? (y() && (r.l += N()),
                    n = w([3 * r.l], [0])[0] + 1,
                    t || (t = [e],
                    n--)) : t.push(e),
                    n--;
                return t
            }, A = function() {
                var t, i, a, o;
                if (s >= 1)
                    return [];
                for (r.f = w([6])[0],
                r.c = w([6])[0],
                a = [],
                r.dv = [],
                r.dl = [],
                t = 0; t < r.f; t++)
                    r.dv[t] = 0,
                    r.dl[t] = 0;
                for (t = 0; !(e >= n) && (e != n - 1 || 7 & (r.c ^ t)); t++) {
                    for (o = [],
                    i = 0; i < r.f; i++)
                        y() && (r.dl[i] += N()),
                        r.dv[i] += w([3 * r.dl[i]], [1])[0],
                        o[i] = r.dv[i];
                    a.push(o)
                }
                return a
            }, O = function() {
                if (r = {
                    b_avp: 1,
                    b_ph: 0,
                    b_phx: 0,
                    b_sep: 0,
                    p_p: 6,
                    p_v: 0,
                    p_a: 0,
                    p_e: 0,
                    p_t: 0,
                    l_o: 3,
                    l_h: 3,
                    l_l: 3,
                    l_c: 3,
                    l_v: 5,
                    l_a: 5,
                    l_e: 3,
                    l_t: 0,
                    u_p: 0,
                    u_v: 0,
                    u_a: 0,
                    wd: 62,
                    d: 0
                },
                s > 0)
                    return [];
                var t, i, a, o, l, u, c;
                for (t = []; ; ) {
                    if (e >= n)
                        return void 0;
                    if (a = {
                        d: 1,
                        c: 0
                    },
                    y())
                        if (y()) {
                            if (y()) {
                                for (a.c++,
                                a.a = r.b_avp,
                                y() && (r.b_avp ^= y(),
                                r.b_ph ^= y(),
                                r.b_phx ^= y(),
                                a.s = r.b_sep,
                                r.b_sep ^= y(),
                                y() && (r.wd = w([7])[0]),
                                a.s ^ r.b_sep && (a.s ? r.u_p = r.u_c : r.u_o = r.u_h = r.u_l = r.u_c = r.u_p)),
                                u = 0; u < 3 + 2 * r.b_ph; u++)
                                    if (y() && (l = "pvaet".charAt(u),
                                    o = r["p_" + l],
                                    r["p_" + l] += N(),
                                    r["u_" + l] = P(r["u_" + l], o, r["p_" + l]) - 0,
                                    r.b_sep && !u))
                                        for (c = 0; 4 > c; c++)
                                            l = "ohlc".charAt(c),
                                            r["u_" + l] = P(r["u_" + l], o, r.p_p) - 0;
                                !r.b_avp && a.a && (r.u_a = P(i && i.amount || 0, 0, r.p_a))
                            }
                            if (y())
                                for (a.c++,
                                u = 0; u < 7 + r.b_ph + r.b_phx; u++)
                                    y() && (6 == u ? a.d = x() : r["l_" + "ohlcva*et".charAt(u)] += N());
                            if (y() && (a.c++,
                            l = r.l_o + (y() && N()),
                            o = w([3 * l], [1])[0],
                            a.p = r.b_sep ? r.u_c + o : r.u_p += o),
                            !a.c)
                                break
                        } else
                            y() ? y() ? y() ? a.d = x() : r.l_v += N() : r.b_ph && y() ? r["l_" + "et".charAt(r.b_phx && y())] += N() : r.l_a += N() : r["l_" + "ohlc".charAt(w([2])[0])] += N();
                    for (u = 0; u < 6 + r.b_ph + r.b_phx; u++)
                        c = "ohlcvaet".charAt(u),
                        o = (r.b_sep ? 191 : 185) >> u & 1,
                        a["v_" + c] = w([3 * r["l_" + c]], [o])[0];
                    i = {
                        date: k(a.d)
                    },
                    a.p && (i.prevclose = P(a.p, r.p_p)),
                    r.b_sep ? (i.open = P(r.u_o += a.v_o, r.p_p),
                    i.high = P(r.u_h += a.v_h, r.p_p),
                    i.low = P(r.u_l += a.v_l, r.p_p),
                    i.close = P(r.u_c += a.v_c, r.p_p)) : (a.o = r.u_p + a.v_o,
                    i.open = P(a.o, r.p_p),
                    i.high = P(a.o + a.v_h, r.p_p),
                    i.low = P(a.o - a.v_l, r.p_p),
                    i.close = P(r.u_p = a.o + a.v_c, r.p_p)),
                    i.volume = P(r.u_v += a.v_v, r.p_v),
                    r.b_avp ? (o = T(r.p_p),
                    l = T(r.p_v),
                    i.amount = P(P(Math.floor((r.b_sep ? (r.u_o + r.u_h + r.u_l + r.u_c) / 4 : a.o + (a.v_h - a.v_l + a.v_c) / 4) * r.u_v + .5), [o[0] + l[0], o[1] + l[1]], r.p_a) + a.v_a, r.p_a)) : (r.u_a += a.v_a,
                    i.amount = P(r.u_a, r.p_a)),
                    r.b_ph && (i.postVol = P(a.v_e, r.p_e),
                    i.postAmt = P(Math.floor(i.postVol * i.close + (r.b_phx ? P(a.v_t, r.p_t) : 0) + .5), 0)),
                    t.push(i)
                }
                return t
            }, E = function(t) {
                var e, i, n;
                if (t = (t || 0).toString(),
                n = [],
                i = t.toLowerCase().indexOf("e"),
                i > 0) {
                    for (e = t.substr(i + 1) - 0; e >= 0; e--)
                        n.push(Math.floor(e * Math.pow(10, -e) + .5) - 0);
                    return n.join("")
                }
                return t
            };
            return g()()
        }
        ;
"""

zh_js_decode = """
function d(t) {
            var e, n, i, o, r, a, s, l = (arguments,
            864e5), c = 7657, u = [], h = [], d = ~(3 << 30), f = 1 << 30, p = [0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 20, 23, 24, 27, 29, 30], g = Math, v = function() {
                var l, c;
                for (l = 0; 64 > l; l++)
                    h[l] = g.pow(2, l),
                    26 > l && (u[l] = m(l + 65),
                    u[l + 26] = m(l + 97),
                    10 > l && (u[l + 52] = m(l + 48)));
                for (u.push("+", "/"),
                u = u.join(""),
                n = t.split(""),
                i = n.length,
                l = 0; i > l; l++)
                    n[l] = u.indexOf(n[l]);
                return o = {},
                e = a = 0,
                r = {},
                c = N([12, 6]),
                s = 63 ^ c[1],
                {
                    _1479: M,
                    _136: A,
                    _200: k,
                    _139: O,
                    _197: _mi_run,
                    _3466: _k2_run
                }["_" + c[0]] || function() {
                    return []
                }
            }, m = String.fromCharCode, b = function(t) {
                return t === {}._
            }, y = function() {
                var t, e;
                for (t = _(),
                e = 1; ; ) {
                    if (!_())
                        return e * (2 * t - 1);
                    e++
                }
            }, _ = function() {
                var t;
                return e >= i ? 0 : (t = n[e] & 1 << a,
                a++,
                a >= 6 && (a -= 6,
                e++),
                !!t)
            }, N = function(t, o, r) {
                var s, l, c, u, d;
                for (l = [],
                c = 0,
                o || (o = []),
                r || (r = []),
                s = 0; s < t.length; s++)
                    if (u = t[s],
                    c = 0,
                    u) {
                        if (e >= i)
                            return l;
                        if (t[s] <= 0)
                            c = 0;
                        else if (t[s] <= 30) {
                            for (; d = 6 - a,
                            d = u > d ? d : u,
                            c |= (n[e] >> a & (1 << d) - 1) << t[s] - u,
                            a += d,
                            a >= 6 && (a -= 6,
                            e++),
                            u -= d,
                            !(0 >= u); )
                                ;
                            o[s] && c >= h[t[s] - 1] && (c -= h[t[s]])
                        } else
                            c = N([30, t[s] - 30], [0, o[s]]),
                            r[s] || (c = c[0] + c[1] * h[30]);
                        l[s] = c
                    } else
                        l[s] = 0;
                return l
            }, x = function() {
                var t;
                return t = N([3])[0],
                1 == t ? (o.d = N([18], [1])[0],
                t = 0) : t || (t = N([6])[0]),
                t
            }, w = function(t) {
                var e, n, i;
                for (t > 1 && (e = 0),
                e = 0; t > e; e++)
                    o.d++,
                    i = o.d % 7,
                    (3 == i || 4 == i) && (o.d += 5 - i);
                return n = new Date,
                n.setTime((c + o.d) * l),
                n
            }, S = function(t) {
                var e, n, i;
                for (i = o.wd || 62,
                e = 0; t > e; e++)
                    do
                        o.d++;
                    while (!(i & 1 << (o.d % 7 + 10) % 7));
                return n = new Date,
                n.setTime((c + o.d) * l),
                n
            }, T = function(t) {
                var e, n, i;
                return t ? 0 > t ? (e = T(-t),
                [-e[0], -e[1]]) : (e = t % 3,
                n = (t - e) / 3,
                i = [n, n],
                e && i[e - 1]++,
                i) : [0, 0]
            }, C = function(t, e, n) {
                var i, o, r;
                for (o = "number" == typeof e ? T(e) : e,
                r = T(n),
                i = [r[0] - o[0], r[1] - o[1]],
                o = 1; i[0] < i[1]; )
                    o *= 5,
                    i[1]--;
                for (; i[1] < i[0]; )
                    o *= 2,
                    i[0]--;
                if (o > 1 && (t *= o),
                i = i[0],
                t = _decnum(t),
                0 > i) {
                    for (; t.length + i <= 0; )
                        t = "0" + t;
                    return i += t.length,
                    o = t.substr(0, i) - 0,
                    void 0 === n ? o + "." + t.substr(i) - 0 : (r = t.charAt(i) - 0,
                    r > 5 ? o++ : 5 == r && (t.substr(i + 1) - 0 > 0 ? o++ : o += 1 & o),
                    o)
                }
                for (; i > 0; i--)
                    t += "0";
                return t - 0
            }, k = function() {
                var t, n, r, a, l;
                if (s >= 1)
                    return [];
                for (o.d = N([18], [1])[0] - 1,
                r = N([3, 3, 30, 6]),
                o.p = r[0],
                o.ld = r[1],
                o.cd = r[2],
                o.c = r[3],
                o.m = g.pow(10, o.p),
                o.pc = o.cd / o.m,
                n = [],
                t = 0; a = {
                    d: 1
                },
                _() && (r = N([3])[0],
                0 == r ? a.d = N([6])[0] : 1 == r ? (o.d = N([18])[0],
                a.d = 0) : a.d = r),
                l = {
                    date: w(a.d)
                },
                _() && (o.ld += y()),
                r = N([3 * o.ld], [1]),
                o.cd += r[0],
                l.close = o.cd / o.m,
                n.push(l),
                !(e >= i) && (e != i - 1 || 63 & (o.c ^ t + 1)); t++)
                    ;
                return n[0].prevclose = o.pc,
                n
            }, A = function() {
                var t, n, r, a, l, c, u, h, d, f, p;
                if (s > 2)
                    return [];
                for (u = [],
                d = {
                    v: "volume",
                    p: "price",
                    a: "avg_price"
                },
                o.d = N([18], [1])[0] - 1,
                h = {
                    date: w(1)
                },
                r = N(1 > s ? [3, 3, 4, 1, 1, 1, 5] : [4, 4, 4, 1, 1, 1, 3]),
                t = 0; 7 > t; t++)
                    o[["la", "lp", "lv", "tv", "rv", "zv", "pp"][t]] = r[t];
                for (o.m = g.pow(10, o.pp),
                s >= 1 ? (r = N([3, 3]),
                o.c = r[0],
                r = r[1]) : (r = 5,
                o.c = 2),
                o.pc = N([6 * r])[0],
                h.pc = o.pc / o.m,
                o.cp = o.pc,
                o.da = 0,
                o.sa = o.sv = 0,
                t = 0; !(e >= i) && (e != i - 1 || 7 & (o.c ^ t)); t++) {
                    for (l = {},
                    a = {},
                    f = o.tv ? _() : 1,
                    n = 0; 3 > n; n++)
                        if (p = ["v", "p", "a"][n],
                        (f ? _() : 0) && (r = y(),
                        o["l" + p] += r),
                        c = "v" == p && o.rv ? _() : 1,
                        r = N([3 * o["l" + p] + ("v" == p ? 7 * c : 0)], [!!n])[0] * (c ? 1 : 100),
                        a[p] = r,
                        "v" == p) {
                            if (!(l[d[p]] = r) && (s > 1 || 241 > t) && (o.zv ? !_() : 1)) {
                                a.p = 0;
                                break
                            }
                        } else
                            "a" == p && (o.da = (1 > s ? 0 : o.da) + a.a);
                    o.sv += a.v,
                    l[d.p] = (o.cp += a.p) / o.m,
                    o.sa += a.v * o.cp,
                    l[d.a] = b(a.a) ? t ? u[t - 1][d.a] : l[d.p] : o.sv ? ((g.floor((o.sa * (2e3 / o.m) + o.sv) / o.sv) >> 1) + o.da) / 1e3 : l[d.p] + o.da / 1e3,
                    u.push(l)
                }
                return u[0].date = h.date,
                u[0].prevclose = h.pc,
                u
            }, M = function() {
                var t, e, n, i, r, a, l;
                if (s >= 1)
                    return [];
                for (o.lv = 0,
                o.ld = 0,
                o.cd = 0,
                o.cv = [0, 0],
                o.p = N([6])[0],
                o.d = N([18], [1])[0] - 1,
                o.m = g.pow(10, o.p),
                r = N([3, 3]),
                o.md = r[0],
                o.mv = r[1],
                t = []; r = N([6]),
                r.length; ) {
                    if (n = {
                        c: r[0]
                    },
                    i = {},
                    n.d = 1,
                    32 & n.c)
                        for (; ; ) {
                            if (r = N([6])[0],
                            63 == (16 | r)) {
                                l = 16 & r ? "x" : "u",
                                r = N([3, 3]),
                                n[l + "_d"] = r[0] + o.md,
                                n[l + "_v"] = r[1] + o.mv;
                                break
                            }
                            if (32 & r) {
                                a = 8 & r ? "d" : "v",
                                l = 16 & r ? "x" : "u",
                                n[l + "_" + a] = (7 & r) + o["m" + a];
                                break
                            }
                            if (a = 15 & r,
                            0 == a ? n.d = N([6])[0] : 1 == a ? (o.d = a = N([18])[0],
                            n.d = 0) : n.d = a,
                            !(16 & r))
                                break
                        }
                    i.date = w(n.d);
                    for (a in {
                        v: 0,
                        d: 0
                    })
                        b(n["x_" + a]) || (o["l" + a] = n["x_" + a]),
                        b(n["u_" + a]) && (n["u_" + a] = o["l" + a]);
                    for (n.l_l = [n.u_d, n.u_d, n.u_d, n.u_d, n.u_v],
                    l = p[15 & n.c],
                    1 & n.u_v && (l = 31 - l),
                    16 & n.c && (n.l_l[4] += 2),
                    e = 0; 5 > e; e++)
                        l & 1 << 4 - e && n.l_l[e]++,
                        n.l_l[e] *= 3;
                    n.d_v = N(n.l_l, [1, 0, 0, 1, 1], [0, 0, 0, 0, 1]),
                    a = o.cd + n.d_v[0],
                    i.open = a / o.m,
                    i.high = (a + n.d_v[1]) / o.m,
                    i.low = (a - n.d_v[2]) / o.m,
                    i.close = (a + n.d_v[3]) / o.m,
                    r = n.d_v[4],
                    "number" == typeof r && (r = [r, r >= 0 ? 0 : -1]),
                    o.cd = a + n.d_v[3],
                    l = o.cv[0] + r[0],
                    o.cv = [l & d, o.cv[1] + r[1] + !!((o.cv[0] & d) + (r[0] & d) & f)],
                    i.volume = (o.cv[0] & f - 1) + o.cv[1] * f,
                    t.push(i)
                }
                return t
            }, O = function() {
                var t, e, n, i;
                if (s > 1)
                    return [];
                for (o.l = 0,
                i = -1,
                o.d = N([18])[0] - 1,
                n = N([18])[0]; o.d < n; )
                    e = w(1),
                    0 >= i ? (_() && (o.l += y()),
                    i = N([3 * o.l], [0])[0] + 1,
                    t || (t = [e],
                    i--)) : t.push(e),
                    i--;
                return t
            };
            return _mi_run = function() {
                var t, n, r, a;
                if (s >= 1)
                    return [];
                for (o.f = N([6])[0],
                o.c = N([6])[0],
                r = [],
                o.dv = [],
                o.dl = [],
                t = 0; t < o.f; t++)
                    o.dv[t] = 0,
                    o.dl[t] = 0;
                for (t = 0; !(e >= i) && (e != i - 1 || 7 & (o.c ^ t)); t++) {
                    for (a = [],
                    n = 0; n < o.f; n++)
                        _() && (o.dl[n] += y()),
                        o.dv[n] += N([3 * o.dl[n]], [1])[0],
                        a[n] = o.dv[n];
                    r.push(a)
                }
                return r
            }
            ,
            _k2_run = function() {
                if (o = {
                    b_avp: 1,
                    b_ph: 0,
                    b_phx: 0,
                    b_sep: 0,
                    p_p: 6,
                    p_v: 0,
                    p_a: 0,
                    p_e: 0,
                    p_t: 0,
                    l_o: 3,
                    l_h: 3,
                    l_l: 3,
                    l_c: 3,
                    l_v: 5,
                    l_a: 5,
                    l_e: 3,
                    l_t: 0,
                    u_p: 0,
                    u_v: 0,
                    u_a: 0,
                    wd: 62,
                    d: 0
                },
                s > 0)
                    return [];
                var t, n, r, a, l, c, u;
                for (t = []; ; ) {
                    if (e >= i)
                        return void 0;
                    if (r = {
                        d: 1,
                        c: 0
                    },
                    _())
                        if (_()) {
                            if (_()) {
                                for (r.c++,
                                r.a = o.b_avp,
                                _() && (o.b_avp ^= _(),
                                o.b_ph ^= _(),
                                o.b_phx ^= _(),
                                r.s = o.b_sep,
                                o.b_sep ^= _(),
                                _() && (o.wd = N([7])[0]),
                                r.s ^ o.b_sep && (r.s ? o.u_p = o.u_c : o.u_o = o.u_h = o.u_l = o.u_c = o.u_p)),
                                c = 0; c < 3 + 2 * o.b_ph; c++)
                                    if (_() && (l = "pvaet".charAt(c),
                                    a = o["p_" + l],
                                    o["p_" + l] += y(),
                                    o["u_" + l] = C(o["u_" + l], a, o["p_" + l]) - 0,
                                    o.b_sep && !c))
                                        for (u = 0; 4 > u; u++)
                                            l = "ohlc".charAt(u),
                                            o["u_" + l] = C(o["u_" + l], a, o.p_p) - 0;
                                !o.b_avp && r.a && (o.u_a = C(n && n.amount || 0, 0, o.p_a))
                            }
                            if (_())
                                for (r.c++,
                                c = 0; c < 7 + o.b_ph + o.b_phx; c++)
                                    _() && (6 == c ? r.d = x() : o["l_" + "ohlcva*et".charAt(c)] += y());
                            if (_() && (r.c++,
                            l = o.l_o + (_() && y()),
                            a = N([3 * l], [1])[0],
                            r.p = o.b_sep ? o.u_c + a : o.u_p += a),
                            !r.c)
                                break
                        } else
                            _() ? _() ? _() ? r.d = x() : o.l_v += y() : o.b_ph && _() ? o["l_" + "et".charAt(o.b_phx && _())] += y() : o.l_a += y() : o["l_" + "ohlc".charAt(N([2])[0])] += y();
                    for (c = 0; c < 6 + o.b_ph + o.b_phx; c++)
                        u = "ohlcvaet".charAt(c),
                        a = (o.b_sep ? 191 : 185) >> c & 1,
                        r["v_" + u] = N([3 * o["l_" + u]], [a])[0];
                    n = {
                        date: S(r.d)
                    },
                    r.p && (n.prevclose = C(r.p, o.p_p)),
                    o.b_sep ? (n.open = C(o.u_o += r.v_o, o.p_p),
                    n.high = C(o.u_h += r.v_h, o.p_p),
                    n.low = C(o.u_l += r.v_l, o.p_p),
                    n.close = C(o.u_c += r.v_c, o.p_p)) : (r.o = o.u_p + r.v_o,
                    n.open = C(r.o, o.p_p),
                    n.high = C(r.o + r.v_h, o.p_p),
                    n.low = C(r.o - r.v_l, o.p_p),
                    n.close = C(o.u_p = r.o + r.v_c, o.p_p)),
                    n.volume = C(o.u_v += r.v_v, o.p_v),
                    o.b_avp ? (a = T(o.p_p),
                    l = T(o.p_v),
                    n.amount = C(C(Math.floor((o.b_sep ? (o.u_o + o.u_h + o.u_l + o.u_c) / 4 : r.o + (r.v_h - r.v_l + r.v_c) / 4) * o.u_v + .5), [a[0] + l[0], a[1] + l[1]], o.p_a) + r.v_a, o.p_a)) : (o.u_a += r.v_a,
                    n.amount = C(o.u_a, o.p_a)),
                    o.b_ph && (n.postVol = C(r.v_e, o.p_e),
                    n.postAmt = C(Math.floor(n.postVol * n.close + (o.b_phx ? C(r.v_t, o.p_t) : 0) + .5), 0)),
                    t.push(n)
                }
                return t
            }
            ,
            _decnum = function(t) {
                var e, n, i;
                if (t = (t || 0).toString(),
                i = [],
                n = t.toLowerCase().indexOf("e"),
                n > 0) {
                    for (e = t.substr(n + 1) - 0; e >= 0; e--)
                        i.push(Math.floor(e * Math.pow(10, -e) + .5) - 0);
                    return i.join("")
                }
                return t
            }
            ,
            v()()
        }
        ;
"""
