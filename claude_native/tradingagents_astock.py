"""a-stock-data 实时数据访问:研报/资金/财务快照等。

数据访问函数从 a-stock-data 的 SKILL.md 逐字 lift(已实测验证),再加薄封装与容错。
本流水线只处理个股,无指数代码歧义问题。
"""
import urllib.request
import requests
import datetime
from mootdx.quotes import Quotes

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_API = "https://reportapi.eastmoney.com/report/list"

_MOOTDX = None


def _client():
    global _MOOTDX
    if _MOOTDX is None:
        _MOOTDX = Quotes.factory(market="std")
    return _MOOTDX


# ============ 共用 helper(lift §东财数据中心统一查询) ============
def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> list:
    """东财数据中心统一查询 — 龙虎榜/融资融券/股东户数 共用。"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = requests.get(DATACENTER_URL, params=params, headers={"User-Agent": UA}, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


# ============ §1.2 腾讯财经报价(PE/PB/市值/换手率) ============
def tencent_quote(codes: list) -> dict:
    """批量拉取腾讯财经实时行情。返回: {code: {name, price, pe_ttm, pb, mcap_yi, ...}}。"""
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


# ============ §6.1 mootdx 财务快照 ============
def _finance_row(code: str) -> dict:
    fin = _client().finance(symbol=code)
    if fin is None:
        return {}
    try:
        return fin.iloc[0].to_dict() if hasattr(fin, "iloc") else dict(fin)
    except Exception:  # noqa: BLE001
        return dict(fin) if isinstance(fin, dict) else {}


def finance_snapshot(code: str) -> dict:
    """mootdx 季报财务快照:净资产收益率(ROE,比率单位无关可靠)、每股净资产、净利润、主营收入、股东人数。

    注:ROE=净利润/净资产(单位自抵消,可靠);eps_approx=净利润/总股本(单位依赖,仅供参考)。
    """
    row = _finance_row(code)
    if not row:
        return {}

    def g(k):
        v = row.get(k)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    income = g("zhuyingshouru")      # 主营收入
    profit = g("jinglirun")          # 净利润
    net_assets = g("jingzichan")     # 净资产
    total_shares = g("zongguben")    # 总股本(股)
    bvps = g("meigujingzichan")      # 每股净资产
    roe = round(profit / net_assets * 100, 2) if profit and net_assets else None
    eps_approx = round(profit / total_shares, 4) if profit and total_shares else None
    return {
        "roe": roe,
        "bvps": bvps,
        "eps_approx": eps_approx,
        "profit": profit,
        "income": income,
        "net_assets": net_assets,
        "holder_num": g("gudongrenshu"),
    }


# ============ 个股基本面(行业/上市日期/市值)— 绕开不可达的 push2,用 mootdx+腾讯 ============
def stock_info(code: str) -> dict:
    """行业/上市日期来自 mootdx finance,名称/总市值来自腾讯报价。"""
    row = _finance_row(code)
    q = tencent_quote([code]).get(code, {})
    return {
        "code": code,
        "name": q.get("name", ""),
        "industry": row.get("industry", ""),
        "list_date": str(row.get("ipo_date", "")),
        "mcap_yi": q.get("mcap_yi", 0),
        "float_mcap_yi": q.get("float_mcap_yi", 0),
    }


# ============ §2.1 东财研报列表 ============
def eastmoney_reports(code: str, max_pages: int = 2) -> list:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        r = session.get(REPORT_API, params=params, timeout=30)
        d = r.json()
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break
    return all_records


def research_list(code: str, n: int = 10) -> list:
    """近 n 篇研报精简:日期/机构/评级/标题。"""
    recs = eastmoney_reports(code)
    out = []
    for r in recs[:n]:
        out.append({
            "date": (r.get("publishDate") or "")[:10],
            "org": r.get("orgSName", ""),
            "rating": r.get("emRatingName", ""),
            "title": (r.get("title", "") or "")[:60],
        })
    return out


# ============ §3.1 同花顺热点题材归因 ============
def hotspot_reasons(code: str) -> list:
    """该股若在当日强势股池,返回其题材归因 tags;否则返回 []。"""
    code = code.strip().split(".")[0]
    date = datetime.date.today().strftime("%Y-%m-%d")
    url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{date}/orderby/date/orderway/desc/charset/GBK/")
    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "Chrome/117.0.0.0 Safari/537.36")}
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    for row in (data.get("data") or []):
        if str(row.get("code", "")) == code:
            reason = row.get("reason", "")
            return [t for t in reason.replace("+", "|").split("|") if t] if reason else []
    return []


# ============ §3.5 龙虎榜 ============
def dragon_tiger_board(code: str, trade_date: str, look_back: int = 60) -> dict:
    start = datetime.datetime.strptime(trade_date, "%Y-%m-%d") - datetime.timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")
    records = []
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=50, sort_columns="TRADE_DATE", sort_types="-1")
    for row in data:
        records.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"records": records}


def lhb(code: str) -> dict:
    """近 60 日龙虎榜上榜记录。"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    return dragon_tiger_board(code, today)


# ============ §4.1 融资融券 ============
def margin(code: str, page_size: int = 10) -> list:
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX", filter_str=f'(SCODE="{code}")',
        page_size=page_size, sort_columns="DATE", sort_types="-1")
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("DATE", ""))[:10],
            "rzye_yi": round((row.get("RZYE") or 0) / 1e8, 3),   # 融资余额(亿)
            "rqye_yi": round((row.get("RQYE") or 0) / 1e8, 3),   # 融券余额(亿)
        })
    return rows


# ============ §4.3 股东户数 ============
def holders(code: str, page_size: int = 6) -> list:
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST", filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size, sort_columns="END_DATE", sort_types="-1")
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("END_DATE", ""))[:10],
            "holder_num": row.get("HOLDER_NUM", 0),
            "change_ratio": row.get("HOLDER_NUM_RATIO", 0),   # 环比%
        })
    return rows


# ============ §4.5 个股资金流 ============
def stock_fund_flow_120d(code: str) -> list:
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
    d = r.json()
    klines = d.get("data", {}).get("klines", [])
    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "date": parts[0],
                "main_net": float(parts[1]) if parts[1] != "-" else 0,
                "super_net": float(parts[5]) if parts[5] != "-" else 0,
            })
    return rows


def moneyflow(code: str) -> dict:
    """近 20 日主力净流入汇总(亿)+ 最近一日。"""
    data = stock_fund_flow_120d(code)
    if not data:
        return {}
    recent = data[-20:]
    total_main_yi = round(sum(d["main_net"] for d in recent) / 1e8, 2)
    last = data[-1]
    return {
        "main_net_20d_yi": total_main_yi,
        "last_date": last["date"],
        "last_main_net_wan": round(last["main_net"] / 1e4, 0),
    }


# ============ 统一容错包装 ============
def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}


def _valuation_realtime(code: str) -> dict:
    return tencent_quote([code]).get(code, {})


def collect(code: str) -> dict:
    """汇总该股全部 a-stock-data 实时板块;每块失败独立降级为 {_error:...}。"""
    return {
        "valuation_realtime": _safe(_valuation_realtime, code),
        "snapshot": _safe(finance_snapshot, code),
        "stock_info": _safe(stock_info, code),
        "research": _safe(research_list, code, 10),
        "hotspot_reason": _safe(hotspot_reasons, code),
        "moneyflow": _safe(moneyflow, code),
        "lhb": _safe(lhb, code),
        "margin": _safe(margin, code),
        "holders": _safe(holders, code),
    }
