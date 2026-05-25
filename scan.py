import time
import json
import requests
import pandas as pd
import akshare as ak
from datetime import datetime
from zoneinfo import ZoneInfo

# ===== 参数 =====
PERIOD = "30min"
PERIOD_NAME = "30分钟"

WATCHLIST = [
    {"code": "002463", "name": "沪电股份"},
    {"code": "300750", "name": "宁德时代"},
    {"code": "688981", "name": "中芯国际"},
    {"code": "600006", "name": "东风股份"},
]

# ===== K线获取 =====
def market_symbol(code):
    code = str(code).zfill(6)
    return "sh" + code if code.startswith(("600","601","603","605","688")) else "sz" + code

def get_30m_kline_sina(code):
    symbol = market_symbol(code)
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
        "var%20KLC_ML=/CN_MinlineService.getMinlineData"
    )
    params = {"symbol": symbol, "scale": "30", "ma":"no", "datalen":"120"}
    headers = {"User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn/","Accept":"*/*"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    text = r.text
    start = text.find("["); end = text.rfind("]")
    if start==-1 or end==-1: raise RuntimeError("新浪接口返回格式异常")
    data = json.loads(text[start:end+1])
    if not data: raise RuntimeError("新浪接口返回空K线")
    rows = [{"时间":x.get("day"),"开盘":x.get("open"),"最高":x.get("high"),
             "最低":x.get("low"),"收盘":x.get("close"),"成交额":x.get("volume",0)} for x in data]
    df = pd.DataFrame(rows)[["时间","开盘","收盘","最高","最低","成交额"]].copy()
    for col in ["开盘","收盘","最高","最低","成交额"]:
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df=df.dropna(subset=["收盘","最高","最低"]).tail(90).reset_index(drop=True)
    if len(df)<60: raise RuntimeError(f"{PERIOD_NAME}K线不足60根，当前{len(df)}根")
    return df

def get_30m_kline_akshare(code):
    df = ak.stock_zh_a_hist_min_em(symbol=str(code).zfill(6), period=PERIOD, adjust="qfq")
    if df is None or df.empty: raise RuntimeError("akshare返回空数据")
    df = df[["时间","开盘","收盘","最高","最低","成交额"]].copy()
    for col in ["开盘","收盘","最高","最低","成交额"]:
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df = df.dropna(subset=["收盘","最高","最低"]).tail(90).reset_index(drop=True)
    if len(df)<60: raise RuntimeError(f"{PERIOD_NAME}K线不足60根，当前{len(df)}根")
    return df

def get_30m_kline(code):
    errors=[]
    for i in range(3):
        try: time.sleep(2+i); return get_30m_kline_sina(code)
        except Exception as e: errors.append(f"新浪第{i+1}次失败:{type(e).__name__}:{e}"); time.sleep(3+i*2)
    for i in range(3):
        try: time.sleep(2+i); return get_30m_kline_akshare(code)
        except Exception as e: errors.append(f"akshare第{i+1}次失败:{type(e).__name__}:{e}"); time.sleep(3+i*2)
    raise RuntimeError("30分钟K线获取失败："+"；".join(errors[-4:]))

# ===== 帮助函数 =====
def near(a,b,tol=0.01): return a>0 and b>0 and abs(a-b)/max(a,b)<=tol
def is_main_board(code): return code.startswith(("600","601","603","605","000","001","002","003","300","301","688"))

def analyze(code,name):
    if not is_main_board(code):
        return {"code":code,"name":name,"status":"过滤","reason":"不在扫描范围"}
    df = get_30m_kline(code)
    current = float(df["收盘"].iloc[-1])
    h5,h20,h60 = float(df["最高"].tail(5).max()),float(df["最高"].tail(20).max()),float(df["最高"].tail(60).max())
    l2,l5 = float(df["最低"].tail(2).min()),float(df["最低"].tail(5).min())
    amount = float(df["成交额"].iloc[-1]) if "成交额" in df.columns else 0
    A,B,D = near(h5,h20) and near(h20,h60), near(l2,l5), current>h60*1.003
    F = current<l5*0.99
    if F: status="证伪"; reason=f"{PERIOD_NAME}收盘价 {current:.2f} 跌破 {l5:.2f}"
    elif A and B and D: status="突破"; reason=f"{PERIOD_NAME}收盘价 {current:.2f} 突破 {h60:.2f}"
    elif A and B: status="等待"; reason=f"{PERIOD_NAME}结构有效，等待突破 {h60:.2f}"
    elif A: status="观察"; reason="高点压缩存在，但低点承接不足"
    else: status="未成型"; reason=f"不满足{PERIOD_NAME}5/20/60高点重合"
    return {"code":code,"name":name,"status":status,"reason":reason,"price":current,"last_time":str(df["时间"].iloc[-1]),
            "amount":amount/1e8 if amount else 0,"A":A,"B":B,"D":D,"F":F,"h5":h5,"h20":h20,"h60":h60,"l2":l2,"l5":l5}

# ===== 主逻辑 =====
results=[]
for item in WATCHLIST:
    try: results.append(analyze(item["code"],item["name"]))
    except Exception as e: results.append({"code":item["code"],"name":item["name"],"status":"ERROR","reason":f"{type(e).__name__}: {e}"})

now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
lines=["A股等突破自动扫描",f"模型周期：{PERIOD_NAME}K",f"时间：{now}",""]
lines+=["突破："+str(sum(r["status"]=="突破" for r in results)),
        "等待："+str(sum(r["status"]=="等待" for r in results)),
        "证伪："+str(sum(r["status"]=="证伪" for r in results)),
        "观察："+str(sum(r["status"]=="观察" for r in results)),
        "未成型："+str(sum(r["status"]=="未成型" for r in results)),
        "错误："+str(sum(r["status"]=="ERROR" for r in results)),""]
for r in results:
    lines.append(f"{r['code']} {r['name']}｜{r['status']}")
    lines.append(f"原因：{r['reason']}")
    if "price" in r:
        lines.append(f"K线时间：{r['last_time']}")
        lines.append(f"价格：{r['price']:.2f}｜成交额：{r['amount']:.2f}亿")
        lines.append(f"A高点重合：{r['A']}｜B低点承接：{r['B']}｜D突破：{r['D']}｜证伪：{r['F']}")
        lines.append(f"5高：{r['h5']:.2f}｜20高：{r['h20']:.2f}｜60高：{r['h60']:.2f}")
        lines.append(f"2低：{r['l2']:.2f}｜5低：{r['l5']:.2f}")
    lines.append("")
lines+=["规则：",
        f"A：5根{PERIOD_NAME}最高≈20根{PERIOD_NAME}最高≈60根{PERIOD_NAME}最高",
        f"B：近2根{PERIOD_NAME}最低≈近5根{PERIOD_NAME}最低",
        "C：沪深主板 + 创业板 + 科创板，非ST",
        f"D：当前{PERIOD_NAME}收盘价突破结构高点","提示：仅用于策略观察，不构成投资建议。"]
print("\n".join(lines))
