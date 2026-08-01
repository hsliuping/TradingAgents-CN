#!/usr/bin/env python3
"""
TradingAgents-CN MiMo 金融分析 CLI
使用 MiMo 模型进行 A 股分析
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置环境变量
os.environ["CUSTOM_OPENAI_API_KEY"] = os.getenv(
    "CUSTOM_OPENAI_API_KEY",
    "tp-c4jtwblts1dhiba52a71y1skvrrkknbqkd3koucfn2jccrqm"
)
os.environ["CUSTOM_OPENAI_BASE_URL"] = os.getenv(
    "CUSTOM_OPENAI_BASE_URL",
    "https://token-plan-cn.xiaomimimo.com/v1"
)

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

console = Console()


def create_config():
    """创建 MiMo 模型配置"""
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "custom_openai"
    config["backend_url"] = os.environ["CUSTOM_OPENAI_BASE_URL"]
    config["custom_openai_base_url"] = os.environ["CUSTOM_OPENAI_BASE_URL"]
    config["deep_think_llm"] = "mimo-v2.5-pro"
    config["quick_think_llm"] = "mimo-v2.5-pro"
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["online_tools"] = True
    config["online_news"] = True
    return config


def validate_stock_code(code: str) -> str:
    """验证并标准化股票代码"""
    code = code.strip()
    # 移除可能的后缀
    for suffix in [".SH", ".SZ", ".sh", ".sz"]:
        code = code.replace(suffix, "")

    if not code.isdigit() or len(code) != 6:
        console.print(f"[red]错误: 无效的股票代码 '{code}'，A股代码应为6位数字[/red]")
        sys.exit(1)

    return code


def run_analysis(stock_code: str, query: str, date: str = None):
    """运行股票分析"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    config = create_config()

    console.print(Panel.fit(
        f"[bold cyan]TradingAgents-CN MiMo 金融分析[/bold cyan]\n"
        f"股票代码: {stock_code}\n"
        f"分析日期: {date}\n"
        f"分析问题: {query}\n"
        f"模型: mimo-v2.5-pro",
        title="分析配置",
        border_style="cyan"
    ))

    # 初始化分析系统
    with console.status("[bold green]正在初始化分析系统..."):
        try:
            # 使用支持的分析师类型: market, social, news, fundamentals
            analysts = [
                "market", "social", "news", "fundamentals"
            ]
            graph = TradingAgentsGraph(analysts, config=config, debug=False)
        except Exception as e:
            console.print(f"[red]初始化失败: {e}[/red]")
            sys.exit(1)

    console.print("[green]✓ 分析系统初始化完成[/green]")
    console.print()

    # 运行分析
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[bold cyan]正在进行多智能体分析...", total=None)

        try:
            final_state, decision = graph.propagate(stock_code, date)
        except Exception as e:
            console.print(f"[red]分析过程出错: {e}[/red]")
            sys.exit(1)

    elapsed_time = time.time() - start_time

    # 输出分析报告
    console.print()
    console.print("=" * 70)
    console.print(Panel.fit(
        f"[bold green]分析完成[/bold green]\n"
        f"耗时: {elapsed_time:.1f} 秒",
        title="完成",
        border_style="green"
    ))
    console.print("=" * 70)

    # 输出最终决策
    console.print()
    # 处理 decision 可能是字典或字符串的情况
    if isinstance(decision, dict):
        decision_text = decision.get("content", decision.get("reasoning", str(decision)))
    else:
        decision_text = decision if decision else "无分析结果"
    console.print(Panel(
        Markdown(decision_text) if decision_text else "无分析结果",
        title="📊 投资决策建议",
        border_style="blue",
        padding=(1, 2)
    ))

    # 输出各分析师报告
    report_sections = {
        "market_report": "📈 市场分析报告",
        "fundamentals_report": "📊 基本面分析报告",
        "technical_report": "🔍 技术分析报告",
        "sentiment_report": "💭 情绪分析报告",
        "news_report": "📰 新闻分析报告",
        "investment_plan": "📋 投资计划",
        "trader_decision": "🎯 交易决策",
        "risk_analysis": "⚠️ 风险分析",
    }

    if final_state:
        console.print()
        console.print("[bold]详细分析报告:[/bold]")
        console.print("=" * 70)

        for key, title in report_sections.items():
            if key in final_state and final_state[key]:
                console.print()
                console.print(Panel(
                    Markdown(final_state[key]),
                    title=title,
                    border_style="cyan",
                    padding=(1, 2)
                ))

    # 保存报告
    save_report(stock_code, date, query, decision, final_state, elapsed_time)

    return decision


def save_report(stock_code: str, date: str, query: str, decision: str,
                final_state: dict, elapsed_time: float):
    """保存分析报告到文件"""
    results_dir = Path("./results") / stock_code / date
    results_dir.mkdir(parents=True, exist_ok=True)

    report_file = results_dir / "analysis_report.md"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# 股票分析报告\n\n")
        f.write(f"- **股票代码**: {stock_code}\n")
        f.write(f"- **分析日期**: {date}\n")
        f.write(f"- **分析问题**: {query}\n")
        f.write(f"- **分析耗时**: {elapsed_time:.1f} 秒\n")
        f.write(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 投资决策建议\n\n")
        f.write(f"{decision}\n\n")
        f.write(f"---\n\n")

        if final_state:
            report_sections = {
                "market_report": "市场分析报告",
                "fundamentals_report": "基本面分析报告",
                "technical_report": "技术分析报告",
                "sentiment_report": "情绪分析报告",
                "news_report": "新闻分析报告",
                "investment_plan": "投资计划",
                "trader_decision": "交易决策",
                "risk_analysis": "风险分析",
            }

            for key, title in report_sections.items():
                if key in final_state and final_state[key]:
                    f.write(f"## {title}\n\n")
                    f.write(f"{final_state[key]}\n\n")
                    f.write(f"---\n\n")

    console.print(f"\n[dim]报告已保存到: {report_file}[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="TradingAgents-CN MiMo 金融分析 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 600519 "这只股票到今年年底还能持有吗？"
  %(prog)s 000001 "分析一下平安银行的投资价值"
  %(prog)s 600036 "招商银行现在适合买入吗？" --date 2025-01-15
        """
    )
    parser.add_argument(
        "stock_code",
        help="A股股票代码（6位数字，如 600519）"
    )
    parser.add_argument(
        "query",
        help="分析要求（如：这只股票到今年年底还能持有吗？）"
    )
    parser.add_argument(
        "--date", "-d",
        default=None,
        help="分析日期（YYYY-MM-DD格式，默认今天）"
    )

    args = parser.parse_args()

    # 验证股票代码
    stock_code = validate_stock_code(args.stock_code)

    # 运行分析
    run_analysis(stock_code, args.query, args.date)


if __name__ == "__main__":
    main()
