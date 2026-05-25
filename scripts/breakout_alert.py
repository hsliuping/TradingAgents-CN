cat > scripts/breakout_alert.py <<'PY'
import os
import time
import random
import traceback
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
import akshare as ak


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
THREAD_ID = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "")

MAX_MSG_LEN = 3300
KLT = 30
TIMEOUT = 15
RETRY = 5
SLEEP_MIN = 0.8
SLEEP_MAX = 2.0

# 你的等突破规则
TOL = 0.01  # 1%误差
MAX_STOCKS = int(os.getenv("MAX_STOCKS", "0"))  # 0 = 全市场；测试可填 20


def bj_now():
    return datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=8))
    ).strftime("%Y-%m-%d %H:%M:%S")


def short_err(e, limit=220):
    s = str(e).replace("\n", " ")
    if len(s) > limit:
        s = s[:limit] + "..."
    return f"{type(e).__name__}: {s}"


def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("Telegram 未配置，直接打印：")
        print(text)
        return

    text = str(text)
    chunks = [text[i:i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]

    for idx, chunk in enumerate(chunks, 1):
        data = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if THREAD_ID:
            data["message_thread_id"] = THREAD_ID

        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data=data,
                timeout=20,
            )
            print("Telegram:", r.status_code, r.text[:300])
        except Exception as e:
            print("Telegram发送失败:", repr(e))

        time.sleep(0.5)


def normalize_code(code):
    code = str(code).strip()
    if code.endswith(".SZ") or code.endswith(".SH"):
        code = code[:6]
    return code.zfill(6)


def secid_of(code):
    code = normalize_code(code)
    if code.startswith(("6", "9")):
        return f"1.{code}"   # 上海
    return f"0.{code}"       # 深圳 / 创业板 / 科创以外多数


def get_stock_pool():
    """
    优先读 watchlist.txt。
    没有 watchlist.txt 时，扫全A。
    watchlist.txt 格式：
    002463 沪电股份
    600006 东风股份
    """
    if os.path.exists("watchlist.txt"):
        arr = []
        with open("watchlist.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.replace(",", " ").split()
                code = normalize_code(parts[0])
                name = parts[1] if len(parts) > 1 else code
                arr.append({"code": code, "name": name})
        return arr

    df = ak.stock_zh_a_spot_em()

    code_col = "代码" if "代码" in df.columns else "code"
    name_col = "名称" if "名称" in df.columns else "name"

    arr = []
    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        name = str(row[name_col])

        # 排除 ST / 退市
        if "ST" in name.upper() or "退" in name:
            continue

        # 主板 + 创业板 + 科创板
        if not code.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688")):
            continue

        arr.append({"code": code, "name": name})

    if MAX_STOCKS > 0:
        arr = arr[:MAX_STOCKS]

    return arr


def get_30m_kline(code):
    code = normalize_code(code)
    secid = secid_of(code)

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "beg": "19000101",
        "end": "20500101",
        "rtntype": "6",
        "secid": secid,
        "klt": str(KLT),
        "fqt": "1",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json,text/plain,*/*",
        "Connection": "close",
    }

    last_error = None

    for i in range(1, RETRY + 1):
        try:
            with requests.Session() as s:
                r = s.get(url, params=params, headers=headers, timeout=TIMEOUT)
                r.raise_for_status()
                js = r.json()

            data = js.get("data") or {}
            klines = data.get("klines") or []

            if not klines:
                raise RuntimeError("东方财富返回空K线")

            rows = []
            for x in klines:
                p = x.split(",")
                rows.append({
                    "datetime": p[0],
                    "open": float(p[1]),
                    "close": float(p[2]),
                    "high": float(p[3]),
                    "low": float(p[4]),
                    "volume": float(p[5]),
                    "amount": float(p[6]),
                })

            df = pd.DataFrame(rows)
            return df

        except Exception as e:
            last_error = e
            print(f"{code} 第{i}次获取K线失败: {short_err(e, 500)}")
            time.sleep(1.5 * i + random.uniform(SLEEP_MIN, SLEEP_MAX))

    raise RuntimeError(f"30分钟K线连续失败{RETRY}次：{short_err(last_error, 300)}")


def near(a, b, tol=TOL):
    if b == 0:
        return False
    return abs(a - b) / abs(b) <= tol


def analyze_one(code, name):
    code = normalize_code(code)

    try:
        df = get_30m_kline(code)
    except Exception as e:
        return {
            "code": code,
            "name": name,
            "status": "ERROR",
            "reason": short_err(e, 350),
        }

    if len(df) < 65:
        return {
            "code": code,
            "name": name,
            "status": "SKIP",
            "reason": f"K线不足，当前只有{len(df)}根",
        }

    last = df.iloc[-1]

    high5 = df["high"].tail(5).max()
    high20 = df["high"].tail(20).max()
    high60 = df["high"].tail(60).max()

    low2 = df["low"].tail(2).min()
    low5 = df["low"].tail(5).min()

    # 结构高点：不含当前这一根，避免自己突破自己
    structure_high = df["high"].iloc[-61:-1].max()
    close_now = float(last["close"])

    A = near(high5, high20) and near(high20, high60)
    B = near(low2, low5)
    D = close_now > structure_high

    if A and B and D:
        return {
            "code": code,
            "name": name,
            "status": "BREAK",
            "close": close_now,
            "structure_high": float(structure_high),
            "reason": "满足 A+B+D：高点压缩 + 低点承接 + 当前30分钟收盘突破结构高点",
        }

    return {
        "code": code,
        "name": name,
        "status": "WAIT",
        "close": close_now,
        "structure_high": float(structure_high),
        "reason": f"A={A}, B={B}, D={D}",
    }


def main():
    print("开始扫描，北京时间：", bj_now())

    try:
        pool = get_stock_pool()
    except Exception as e:
        msg = f"""A股等突破扫描失败

北京时间：{bj_now()}

阶段：获取股票池失败
原因：{short_err(e, 600)}

判断：
大概率是 AkShare / 东方财富行情接口临时断开。
"""
        send_telegram(msg)
        return 0

    total = len(pool)
    breaks = []
    errors = []
    waits = 0
    skips = 0

    for idx, item in enumerate(pool, 1):
        code = item["code"]
        name = item["name"]

        print(f"[{idx}/{total}] {code} {name}")

        res = analyze_one(code, name)

        if res["status"] == "BREAK":
            breaks.append(res)
        elif res["status"] == "ERROR":
            errors.append(res)
        elif res["status"] == "SKIP":
            skips += 1
        else:
            waits += 1

        # 降低东方财富断连概率
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    lines = []
    lines.append("A股等突破扫描结果")
    lines.append("退出码：0")
    lines.append(f"北京时间：{bj_now()}")
    lines.append("")
    lines.append("===== 汇总 =====")
    lines.append(f"扫描数量：{total}")
    lines.append(f"突破数量：{len(breaks)}")
    lines.append(f"等待数量：{waits}")
    lines.append(f"跳过数量：{skips}")
    lines.append(f"失败数量：{len(errors)}")
    lines.append("")

    if breaks:
        lines.append("===== 突破候选 =====")
        for r in breaks[:50]:
            lines.append(
                f"{r['code']} {r['name']} | BREAK | 收盘:{r['close']:.2f} | 结构高点:{r['structure_high']:.2f}"
            )
            lines.append(f"原因：{r['reason']}")
            lines.append("")
    else:
        lines.append("===== 突破候选 =====")
        lines.append("暂无符合条件。")
        lines.append("")

    if errors:
        lines.append("===== 数据源失败摘要 =====")
        lines.append("说明：单只股票失败已跳过，不影响整体扫描。")
        for r in errors[:20]:
            lines.append(f"{r['code']} {r['name']} | ERROR | {r['reason']}")
        if len(errors) > 20:
            lines.append(f"... 其余 {len(errors) - 20} 条失败已省略")
        lines.append("")

    lines.append("规则：")
    lines.append("A：5根30分钟最高≈20根30分钟最高≈60根30分钟最高")
    lines.append("B：近2根30分钟最低≈近5根30分钟最低")
    lines.append("C：沪深主板 + 创业板 + 科创板，非ST")
    lines.append("D：当前30分钟收盘价突破结构高点")
    lines.append("")
    lines.append("提示：仅用于策略观察，不构成投资建议。")

    msg = "\n".join(lines)
    send_telegram(msg)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        msg = f"""A股等突破扫描异常

北京时间：{bj_now()}

错误类型：
{type(e).__name__}

错误摘要：
{short_err(e, 800)}

提示：
已截断错误内容，避免 Telegram message is too long。
"""
        send_telegram(msg)
        print(traceback.format_exc())
        raise SystemExit(0)
PY

echo "✅ 已覆盖 scripts/breakout_alert.py"
