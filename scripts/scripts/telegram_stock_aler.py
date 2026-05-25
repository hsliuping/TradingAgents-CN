#!/usr/bin/env python3
import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))


def send_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    thread_id = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "").strip()

    if not token or not chat_id:
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }

    if thread_id:
        data["message_thread_id"] = thread_id

    encoded = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=encoded, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
        result = json.loads(body)
        if not result.get("ok"):
            raise RuntimeError(body)


def main() -> None:
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")

    symbols = os.getenv("WATCH_SYMBOLS", "002463.SZ,600519.SH,300750.SZ").strip()

    text = f"""📈 <b>TradingAgents-CN 定时检查</b>

时间：{now} 北京时间
自选股：{symbols}

状态：GitHub Actions 已正常运行 ✅

当前为轻量版：
1. 不占用 VM
2. 不启动 Docker
3. 不跑 MongoDB
4. 先验证 Telegram 通道

下一步可接入：
- A股等突破规则
- TradingAgents-CN 分析脚本
- 每日 09:35 / 11:30 / 14:30 自动提醒
"""

    send_telegram(text)


if __name__ == "__main__":
    main()
