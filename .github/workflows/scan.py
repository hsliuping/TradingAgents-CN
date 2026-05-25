import time
import requests
import pandas as pd
import akshare as ak
import json
import os
import sys

PERIOD = "30"  # 30分钟K
PERIOD_NAME = "30分钟"

# ================== 市场代码转换 ==================
def market_symbol(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith(("600", "601", "603", "605", "688")):
        return "sh" + code
    return "sz" + code

# ================== 新浪30分钟K ==================
def get_30m_kline_sina(code: str) -> pd.DataFrame:
    symbol = market_symbol(code)
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
        "var%20KLC_ML=/CN_MinlineService.getMinlineData"
    )
    params = {"symbol": symbol, "scale": "30", "ma": "no", "datalen": "120"}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
        "Accept": "*/*",
        "Connection": "close",
    }

    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    text = r.text
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise RuntimeError("新浪接口返回格式异常")
    data = json.loads(text[start:end+1])
    if not data:
        raise RuntimeError("新浪接口返回空K线")

    rows = []
    for x in data:
        rows.append({
            "时间": x.get("day"),
            "开盘": x.get("open"),
            "最高": x.get("high"),
            "最低": x.get("low"),
            "收盘": x.get("close"),
            "成交额": x.get("volume", 0),
        })

    df = pd.DataFrame(rows)
    for col in ["开盘", "收盘", "最高", "最低", "成交额"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["收盘", "最高", "最低"]).tail(90).reset_index(drop=True)
    if len(df) < 60:
        raise RuntimeError(f"{PERIOD_NAME}K线不足60根，当前{len(df)}根")
    return df

# ================== akshare备用 ==================
def get_30m_kline_akshare(code: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist_min_em(symbol=str(code).zfill(6), period=PERIOD, adjust="qfq")
    if df is None or df.empty:
        raise RuntimeError("akshare返回空数据")
    need_cols = ["时间", "开盘", "收盘", "最高", "最低", "成交额"]
    df = df[need_cols].copy()
    for col in ["开盘", "收盘", "最高", "最低", "成交额"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["收盘", "最高", "最低"]).tail(90).reset_index(drop=True)
    if len(df) < 60:
        raise RuntimeError(f"{PERIOD_NAME}K线不足60根，当前{len(df)}根")
    return df

# ================== 主接口 ==================
def get_30m_kline(code: str) -> pd.DataFrame:
    code = str(code).zfill(6)
    errors = []

    # 先走新浪
    for i in range(3):
        try:
            time.sleep(2 + i)
            return get_30m_kline_sina(code)
        except Exception as e:
            errors.append(f"新浪第{i+1}次失败：{type(e).__name__}: {e}")
            print(errors[-1])
            time.sleep(3 + i*2)

    # 再走akshare
    for i in range(3):
        try:
            time.sleep(2 + i)
            return get_30m_kline_akshare(code)
        except Exception as e:
            errors.append(f"akshare第{i+1}次失败：{type(e).__name__}: {e}")
            print(errors[-1])
            time.sleep(3 + i*2)

    raise RuntimeError("30分钟K线获取失败：" + "；".join(errors[-4:]))

# ================== Telegram推送 ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    r = requests.post(url, data=data, timeout=15)
    r.raise_for_status()

# ================== 主运行 ==================
if __name__ == "__main__":
    # 股票池，可直接通过环境变量或文件替换
    STOCKS = [
        ("600006", "东风股份"),
        ("002463", "沪电股份")
    ]
    msg_lines = []
    for code, name in STOCKS:
        try:
            df = get_30m_kline(code)
            msg_lines.append(f"{code} {name} | OK | 最新收盘 {df['收盘'].iloc[-1]}")
        except Exception as e:
            msg_lines.append(f"{code} {name} | ERROR | {e}")

    msg_text = "\n".join(msg_lines)
    print(msg_text)
    send_telegram(msg_text)
