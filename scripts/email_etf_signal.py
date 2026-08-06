#!/usr/bin/env python3
"""用 TradingAgents 多智能体分析科创50ETF并发送 QQ 邮件。"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ETF_CODE = os.getenv("ETF_SIGNAL_CODE", "588000")
RECIPIENT = os.getenv("ETF_SIGNAL_RECIPIENT", "1756212064@qq.com")


def run_multi_agent_analysis() -> tuple[str, str]:
    """运行 TradingAgents 完整决策链并返回主题、报告。"""
    from tradingagents.dataflows.tencent_etf import fetch_tencent_etf_data
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    market_data = fetch_tencent_etf_data(ETF_CODE)
    metrics = json.loads(market_data.split("指标: ", 1)[1].split("\n", 1)[0])
    market_date = metrics["last_trade_date"]
    os.environ["CUSTOM_OPENAI_API_KEY"] = os.environ["TERRA_API_KEY"]
    endpoint = os.environ["TERRA_BASE_URL"]
    model = os.getenv("TERRA_MODEL", "gpt-5.6-terra")
    config = {
        **DEFAULT_CONFIG,
        "llm_provider": "custom_openai",
        "quick_think_llm": model,
        "deep_think_llm": model,
        "backend_url": endpoint,
        "custom_openai_base_url": endpoint,
        "online_tools": True,
        "memory_enabled": False,
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
    }
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news"], config=config, debug=False
    )
    state, decision = graph.propagate(ETF_CODE, date.today().isoformat())
    final_decision = (
        decision
        if isinstance(decision, str)
        else json.dumps(decision, ensure_ascii=False, indent=2, default=str)
    )
    signal = next(
        (
            label
            for label, words in {
                "买入": ("买入", "BUY"),
                "卖出": ("卖出", "SELL"),
                "观望": ("观望", "持有", "HOLD"),
            }.items()
            if any(word in final_decision.upper() for word in words)
        ),
        "查看报告",
    )
    reports = [
        ("市场分析师", state.get("market_report")),
        ("新闻分析师", state.get("news_report")),
        ("多空研究辩论", state.get("investment_debate_state")),
        ("交易员", state.get("trader_investment_plan")),
        ("风险委员会", state.get("risk_debate_state")),
    ]
    price_plan = f"""# 下一交易日价格参考

- 最新收盘价：¥{metrics['close']:.3f}
- 回调分批买入参考区间：¥{metrics['reference_buy_zone'][0]:.3f}–¥{metrics['reference_buy_zone'][1]:.3f}
- 突破确认参考价：¥{metrics['breakout_confirmation']:.3f}（需放量确认，不追瞬时冲高）
- 分批卖出/止盈参考区间：¥{metrics['reference_sell_zone'][0]:.3f}–¥{metrics['reference_sell_zone'][1]:.3f}
- 止损参考价：¥{metrics['stop_loss_reference']:.3f}
- 20日支撑/压力：¥{metrics['support_20d']:.3f} / ¥{metrics['resistance_20d']:.3f}
- ATR14：¥{metrics['ATR14']:.3f}
- 有效期：仅下一交易日；若开盘跳空越过区间或出现重大消息，价格参考作废。

价格由腾讯前复权日K的20日高低点与ATR14计算，不是模型预测。应结合最终信号使用：观望时不因触价自动交易。"""
    sections = [price_plan, f"# 最终决策\n\n{final_decision}"]
    sections.extend(
        f"# {title}\n\n{content}"
        for title, content in reports
        if content
    )
    sections.extend(
        [
            f"# 行情输入\n\n{market_data}",
            "风险提示：AI 多智能体结论仅供参考，不构成投资建议。请控制仓位并自行决策。",
        ]
    )
    subject = f"[TradingAgents 科创50ETF] {signal} | 数据截至 {market_date}"
    return subject, "\n\n---\n\n".join(sections)


def send_email(subject: str, body: str) -> None:
    """使用 QQ SMTP SSL 发送邮件。"""
    sender = os.getenv("QQ_EMAIL_ADDRESS", RECIPIENT)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = RECIPIENT
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as smtp:
        smtp.login(sender, os.environ["QQ_EMAIL_AUTH_CODE"])
        smtp.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="分析但不发邮件")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    subject, body = run_multi_agent_analysis()
    if args.dry_run:
        print(subject)
        print(body)
    else:
        send_email(subject, body)
        print(f"已发送：{subject}")


if __name__ == "__main__":
    main()
