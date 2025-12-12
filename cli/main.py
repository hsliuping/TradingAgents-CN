# 标准库导入
import datetime
import os
import re
import subprocess
import sys
import time
from collections import deque
from difflib import get_close_matches
from functools import wraps
from pathlib import Path
from typing import Optional

# 第三方库导入
import typer
from dotenv import load_dotenv
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# 项目内部导入
from cli.models import AnalystType
from cli.utils import (
    select_analysts,
    select_deep_thinking_agent,
    select_llm_provider,
    select_research_depth,
    select_shallow_thinking_agent,
)
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.utils.logging_manager import get_logger

# 加载环境变量
load_dotenv()

# 常量定义
DEFAULT_MESSAGE_BUFFER_SIZE = 100
DEFAULT_MAX_TOOL_ARGS_LENGTH = 100
DEFAULT_MAX_CONTENT_LENGTH = 200
DEFAULT_MAX_DISPLAY_MESSAGES = 12
DEFAULT_REFRESH_RATE = 4
DEFAULT_API_KEY_DISPLAY_LENGTH = 12

# 初始化日志系统
logger = get_logger("cli")

# CLI专用日志配置：禁用控制台输出，只保留文件日志
def setup_cli_logging():
    """
    CLI模式下的日志配置：移除控制台输出，保持界面清爽
    Configure logging for CLI mode: remove console output to keep interface clean
    """
    import logging
    from tradingagents.utils.logging_manager import get_logger_manager

    logger_manager = get_logger_manager()

    # 获取根日志器
    root_logger = logging.getLogger()

    # 移除所有控制台处理器，只保留文件日志
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and hasattr(handler, 'stream'):
            if handler.stream.name in ['<stderr>', '<stdout>']:
                root_logger.removeHandler(handler)

    # 同时移除tradingagents日志器的控制台处理器
    tradingagents_logger = logging.getLogger('tradingagents')
    for handler in tradingagents_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and hasattr(handler, 'stream'):
            if handler.stream.name in ['<stderr>', '<stdout>']:
                tradingagents_logger.removeHandler(handler)

    # 记录CLI启动日志（只写入文件）
    logger.debug("🚀 CLI模式启动，控制台日志已禁用，保持界面清爽")

# 设置CLI日志配置
setup_cli_logging()

console = Console()

# CLI用户界面管理器
class CLIUserInterface:
    """CLI用户界面管理器：处理用户显示和进度提示"""

    def __init__(self):
        self.console = Console()
        self.logger = get_logger("cli")

    def show_user_message(self, message: str, style: str = ""):
        """显示用户消息"""
        if style:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def show_progress(self, message: str):
        """显示进度信息"""
        self.console.print(f"🔄 {message}")
        # 同时记录到日志文件
        self.logger.info(f"进度: {message}")

    def show_success(self, message: str):
        """显示成功信息"""
        self.console.print(f"[green]✅ {message}[/green]")
        self.logger.info(f"成功: {message}")

    def show_error(self, message: str):
        """显示错误信息"""
        self.console.print(f"[red]❌ {message}[/red]")
        self.logger.error(f"错误: {message}")

    def show_warning(self, message: str):
        """显示警告信息"""
        self.console.print(f"[yellow]⚠️ {message}[/yellow]")
        self.logger.warning(f"警告: {message}")

    def show_step_header(self, step_num: int, title: str):
        """显示步骤标题"""
        self.console.print(f"\n[bold cyan]步骤 {step_num}: {title}[/bold cyan]")
        self.console.print("─" * 60)

    def show_data_info(self, data_type: str, symbol: str, details: str = ""):
        """显示数据获取信息"""
        if details:
            self.console.print(f"📊 {data_type}: {symbol} - {details}")
        else:
            self.console.print(f"📊 {data_type}: {symbol}")

# 创建全局UI管理器
ui = CLIUserInterface()

app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: 多智能体大语言模型金融交易框架 | Multi-Agents LLM Financial Trading Framework",
    add_completion=True,  # Enable shell completion
    rich_markup_mode="rich",  # Enable rich markup
    no_args_is_help=False,  # 不显示帮助，直接进入分析模式
)


# Create a deque to store recent messages with a maximum length
class MessageBuffer:
    def __init__(self, max_length=DEFAULT_MESSAGE_BUFFER_SIZE):
        self.messages = deque(maxlen=max_length)
        self.tool_calls = deque(maxlen=max_length)
        self.current_report = None
        self.final_report = None  # Store the complete final report
        self.agent_status = {
            # Analyst Team
            "Market Analyst": "pending",
            "Social Analyst": "pending",
            "News Analyst": "pending",
            "Fundamentals Analyst": "pending",
            # Research Team
            "Bull Researcher": "pending",
            "Bear Researcher": "pending",
            "Research Manager": "pending",
            # Trading Team
            "Trader": "pending",
            # Risk Management Team
            "Risky Analyst": "pending",
            "Neutral Analyst": "pending",
            "Safe Analyst": "pending",
            # Portfolio Management Team
            "Portfolio Manager": "pending",
        }
        self.current_agent = None
        self.report_sections = {
            "market_report": None,
            "sentiment_report": None,
            "news_report": None,
            "fundamentals_report": None,
            "investment_plan": None,
            "trader_investment_plan": None,
            "final_trade_decision": None,
        }

    def add_message(self, message_type, content):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.append((timestamp, message_type, content))

    def add_tool_call(self, tool_name, args):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.tool_calls.append((timestamp, tool_name, args))

    def update_agent_status(self, agent, status):
        if agent in self.agent_status:
            self.agent_status[agent] = status
            self.current_agent = agent

    def update_report_section(self, section_name, content):
        if section_name in self.report_sections:
            self.report_sections[section_name] = content
            self._update_current_report()

    def _update_current_report(self):
        # For the panel display, only show the most recently updated section
        latest_section = None
        latest_content = None

        # Find the most recently updated section
        for section, content in self.report_sections.items():
            if content is not None:
                latest_section = section
                latest_content = content
               
        if latest_section and latest_content:
            # Format the current section for display
            section_titles = {
                "market_report": "Market Analysis",
                "sentiment_report": "Social Sentiment",
                "news_report": "News Analysis",
                "fundamentals_report": "Fundamentals Analysis",
                "investment_plan": "Research Team Decision",
                "trader_investment_plan": "Trading Team Plan",
                "final_trade_decision": "Portfolio Management Decision",
            }
            self.current_report = (
                f"### {section_titles[latest_section]}\n{latest_content}"
            )

        # Update the final complete report
        self._update_final_report()

    def _update_final_report(self):
        report_parts = []

        # Analyst Team Reports
        if any(
            self.report_sections[section]
            for section in [
                "market_report",
                "sentiment_report",
                "news_report",
                "fundamentals_report",
            ]
        ):
            report_parts.append("## Analyst Team Reports")
            if self.report_sections["market_report"]:
                report_parts.append(
                    f"### Market Analysis\n{self.report_sections['market_report']}"
                )
            if self.report_sections["sentiment_report"]:
                report_parts.append(
                    f"### Social Sentiment\n{self.report_sections['sentiment_report']}"
                )
            if self.report_sections["news_report"]:
                report_parts.append(
                    f"### News Analysis\n{self.report_sections['news_report']}"
                )
            if self.report_sections["fundamentals_report"]:
                report_parts.append(
                    f"### Fundamentals Analysis\n{self.report_sections['fundamentals_report']}"
                )

        # Research Team Reports
        if self.report_sections["investment_plan"]:
            report_parts.append("## Research Team Decision")
            report_parts.append(f"{self.report_sections['investment_plan']}")

        # Trading Team Reports
        if self.report_sections["trader_investment_plan"]:
            report_parts.append("## Trading Team Plan")
            report_parts.append(f"{self.report_sections['trader_investment_plan']}")

        # Portfolio Management Decision
        if self.report_sections["final_trade_decision"]:
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(f"{self.report_sections['final_trade_decision']}")

        self.final_report = "\n\n".join(report_parts) if report_parts else None


message_buffer = MessageBuffer()


def create_layout():
    """
    创建CLI界面的布局结构
    Create the layout structure for CLI interface
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_column(
        Layout(name="upper", ratio=3), Layout(name="analysis", ratio=5)
    )
    layout["upper"].split_row(
        Layout(name="progress", ratio=2), Layout(name="messages", ratio=3)
    )
    return layout


def update_display(layout, spinner_text=None):
    """
    更新CLI界面显示内容
    Update CLI interface display content
    
    Args:
        layout: Rich Layout对象
        spinner_text: 可选的spinner文本
    """
    # Header with welcome message
    layout["header"].update(
        Panel(
            "[bold green]Welcome to TradingAgents CLI[/bold green]\n"
            "[dim]© [Tauric Research](https://github.com/TauricResearch)[/dim]",
            title="Welcome to TradingAgents",
            border_style="green",
            padding=(1, 2),
            expand=True,
        )
    )

    # Progress panel showing agent status
    progress_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        box=box.SIMPLE_HEAD,  # Use simple header with horizontal lines
        title=None,  # Remove the redundant Progress title
        padding=(0, 2),  # Add horizontal padding
        expand=True,  # Make table expand to fill available space
    )
    progress_table.add_column("Team", style="cyan", justify="center", width=20)
    progress_table.add_column("Agent", style="green", justify="center", width=20)
    progress_table.add_column("Status", style="yellow", justify="center", width=20)

    # Group agents by team
    teams = {
        "Analyst Team": [
            "Market Analyst",
            "Social Analyst",
            "News Analyst",
            "Fundamentals Analyst",
        ],
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Risky Analyst", "Neutral Analyst", "Safe Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    for team, agents in teams.items():
        # Add first agent with team name
        first_agent = agents[0]
        status = message_buffer.agent_status[first_agent]
        if status == "in_progress":
            spinner = Spinner(
                "dots", text="[blue]in_progress[/blue]", style="bold cyan"
            )
            status_cell = spinner
        else:
            status_color = {
                "pending": "yellow",
                "completed": "green",
                "error": "red",
            }.get(status, "white")
            status_cell = f"[{status_color}]{status}[/{status_color}]"
        progress_table.add_row(team, first_agent, status_cell)

        # Add remaining agents in team
        for agent in agents[1:]:
            status = message_buffer.agent_status[agent]
            if status == "in_progress":
                spinner = Spinner(
                    "dots", text="[blue]in_progress[/blue]", style="bold cyan"
                )
                status_cell = spinner
            else:
                status_color = {
                    "pending": "yellow",
                    "completed": "green",
                    "error": "red",
                }.get(status, "white")
                status_cell = f"[{status_color}]{status}[/{status_color}]"
            progress_table.add_row("", agent, status_cell)

        # Add horizontal line after each team
        progress_table.add_row("─" * 20, "─" * 20, "─" * 20, style="dim")

    layout["progress"].update(
        Panel(progress_table, title="Progress", border_style="cyan", padding=(1, 2))
    )

    # Messages panel showing recent messages and tool calls
    messages_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        expand=True,  # Make table expand to fill available space
        box=box.MINIMAL,  # Use minimal box style for a lighter look
        show_lines=True,  # Keep horizontal lines
        padding=(0, 1),  # Add some padding between columns
    )
    messages_table.add_column("Time", style="cyan", width=8, justify="center")
    messages_table.add_column("Type", style="green", width=10, justify="center")
    messages_table.add_column(
        "Content", style="white", no_wrap=False, ratio=1
    )  # Make content column expand

    # Combine tool calls and messages
    all_messages = []

    # Add tool calls
    for timestamp, tool_name, args in message_buffer.tool_calls:
        # Truncate tool call args if too long
        if isinstance(args, str) and len(args) > DEFAULT_MAX_TOOL_ARGS_LENGTH:
            args = args[:97] + "..."
        all_messages.append((timestamp, "Tool", f"{tool_name}: {args}"))

    # Add regular messages
    for timestamp, msg_type, content in message_buffer.messages:
        # Convert content to string if it's not already
        content_str = content
        if isinstance(content, list):
            # Handle list of content blocks (Anthropic format)
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif item.get('type') == 'tool_use':
                        text_parts.append(f"[Tool: {item.get('name', 'unknown')}]")
                else:
                    text_parts.append(str(item))
            content_str = ' '.join(text_parts)
        elif not isinstance(content_str, str):
            content_str = str(content)
            
        # Truncate message content if too long
        if len(content_str) > DEFAULT_MAX_CONTENT_LENGTH:
            content_str = content_str[:197] + "..."
        all_messages.append((timestamp, msg_type, content_str))

    # Sort by timestamp
    all_messages.sort(key=lambda x: x[0])

    # Calculate how many messages we can show based on available space
    # Start with a reasonable number and adjust based on content length
    max_messages = DEFAULT_MAX_DISPLAY_MESSAGES  # Increased from 8 to better fill the space

    # Get the last N messages that will fit in the panel
    recent_messages = all_messages[-max_messages:]

    # Add messages to table
    for timestamp, msg_type, content in recent_messages:
        # Format content with word wrapping
        wrapped_content = Text(content, overflow="fold")
        messages_table.add_row(timestamp, msg_type, wrapped_content)

    if spinner_text:
        messages_table.add_row("", "Spinner", spinner_text)

    # Add a footer to indicate if messages were truncated
    if len(all_messages) > max_messages:
        messages_table.footer = (
            f"[dim]Showing last {max_messages} of {len(all_messages)} messages[/dim]"
        )

    layout["messages"].update(
        Panel(
            messages_table,
            title="Messages & Tools",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # Analysis panel showing current report
    if message_buffer.current_report:
        layout["analysis"].update(
            Panel(
                Markdown(message_buffer.current_report),
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        layout["analysis"].update(
            Panel(
                "[italic]Waiting for analysis report...[/italic]",
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )

    # Footer with statistics
    tool_calls_count = len(message_buffer.tool_calls)
    llm_calls_count = sum(
        1 for _, msg_type, _ in message_buffer.messages if msg_type == "Reasoning"
    )
    reports_count = sum(
        1 for content in message_buffer.report_sections.values() if content is not None
    )

    stats_table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    stats_table.add_column("Stats", justify="center")
    stats_table.add_row(
        f"Tool Calls: {tool_calls_count} | LLM Calls: {llm_calls_count} | Generated Reports: {reports_count}"
    )

    layout["footer"].update(Panel(stats_table, border_style="grey50"))


def get_user_selections():
    """Get all user selections before starting the analysis display."""
    # Display ASCII art welcome message
    welcome_file = Path(__file__).parent / "static" / "welcome.txt"
    try:
        with open(welcome_file, "r", encoding="utf-8") as f:
            welcome_ascii = f.read()
    except FileNotFoundError:
        welcome_ascii = "TradingAgents"

    # Create welcome box content
    welcome_content = f"{welcome_ascii}\n"
    welcome_content += "[bold green]TradingAgents: 多智能体大语言模型金融交易框架 - CLI[/bold green]\n"
    welcome_content += "[bold green]Multi-Agents LLM Financial Trading Framework - CLI[/bold green]\n\n"
    welcome_content += "[bold]工作流程 | Workflow Steps:[/bold]\n"
    welcome_content += "I. 分析师团队 | Analyst Team → II. 研究团队 | Research Team → III. 交易员 | Trader → IV. 风险管理 | Risk Management → V. 投资组合管理 | Portfolio Management\n\n"
    welcome_content += (
        "[dim]Built by [Tauric Research](https://github.com/TauricResearch)[/dim]"
    )

    # Create and center the welcome box
    welcome_box = Panel(
        welcome_content,
        border_style="green",
        padding=(1, 2),
        title="欢迎使用 TradingAgents | Welcome to TradingAgents",
        subtitle="多智能体大语言模型金融交易框架 | Multi-Agents LLM Financial Trading Framework",
    )
    console.print(Align.center(welcome_box))
    console.print()  # Add a blank line after the welcome box

    # Create a boxed questionnaire for each step
    def create_question_box(title, prompt, default=None):
        box_content = f"[bold]{title}[/bold]\n"
        box_content += f"[dim]{prompt}[/dim]"
        if default:
            box_content += f"\n[dim]Default: {default}[/dim]"
        return Panel(box_content, border_style="blue", padding=(1, 2))

    # Step 1: Market selection
    console.print(
        create_question_box(
            "步骤 1: 选择市场 | Step 1: Select Market",
            "请选择要分析的股票市场 | Please select the stock market to analyze",
            ""
        )
    )
    selected_market = select_market()

    # Step 2: Ticker symbol
    console.print(
        create_question_box(
            "步骤 2: 股票代码 | Step 2: Ticker Symbol",
            f"请输入{selected_market['name']}股票代码 | Enter {selected_market['name']} ticker symbol",
            selected_market['default']
        )
    )
    selected_ticker = get_ticker(selected_market)

    # Step 3: Analysis date
    default_date = datetime.datetime.now().strftime("%Y-%m-%d")
    console.print(
        create_question_box(
            "步骤 3: 分析日期 | Step 3: Analysis Date",
            "请输入分析日期 (YYYY-MM-DD) | Enter the analysis date (YYYY-MM-DD)",
            default_date,
        )
    )
    analysis_date = get_analysis_date()

    # Step 4: Select analysts
    console.print(
        create_question_box(
            "步骤 4: 分析师团队 | Step 4: Analysts Team",
            "选择您的LLM分析师智能体进行分析 | Select your LLM analyst agents for the analysis"
        )
    )
    selected_analysts = select_analysts(selected_ticker)
    console.print(
        f"[green]已选择的分析师 | Selected analysts:[/green] {', '.join(analyst.value for analyst in selected_analysts)}"
    )

    # Step 5: Research depth
    console.print(
        create_question_box(
            "步骤 5: 研究深度 | Step 5: Research Depth",
            "选择您的研究深度级别 | Select your research depth level"
        )
    )
    selected_research_depth = select_research_depth()

    # Step 6: LLM Provider
    console.print(
        create_question_box(
            "步骤 6: LLM提供商 | Step 6: LLM Provider",
            "选择要使用的LLM服务 | Select which LLM service to use"
        )
    )
    selected_llm_provider, backend_url = select_llm_provider()

    # Step 7: Thinking agents
    console.print(
        create_question_box(
            "步骤 7: 思考智能体 | Step 7: Thinking Agents",
            "选择您的思考智能体进行分析 | Select your thinking agents for analysis"
        )
    )
    selected_shallow_thinker = select_shallow_thinking_agent(selected_llm_provider)
    selected_deep_thinker = select_deep_thinking_agent(selected_llm_provider)

    return {
        "ticker": selected_ticker,
        "market": selected_market,
        "analysis_date": analysis_date,
        "analysts": selected_analysts,
        "research_depth": selected_research_depth,
        "llm_provider": selected_llm_provider.lower(),
        "backend_url": backend_url,
        "shallow_thinker": selected_shallow_thinker,
        "deep_thinker": selected_deep_thinker,
    }


def select_market():
    """选择股票市场"""
    markets = {
        "1": {
            "name": "美股",
            "name_en": "US Stock",
            "default": "SPY",
            "examples": ["SPY", "AAPL", "TSLA", "NVDA", "MSFT"],
            "format": "直接输入代码 (如: AAPL)",
            "pattern": r'^[A-Z]{1,5}$',
            "data_source": "yahoo_finance"
        },
        "2": {
            "name": "A股",
            "name_en": "China A-Share",
            "default": "600036",
            "examples": ["000001 (平安银行)", "600036 (招商银行)", "000858 (五粮液)"],
            "format": "6位数字代码 (如: 600036, 000001)",
            "pattern": r'^\d{6}$',
            "data_source": "china_stock"
        },
        "3": {
            "name": "港股",
            "name_en": "Hong Kong Stock",
            "default": "0700.HK",
            "examples": ["0700.HK (腾讯)", "09988.HK (阿里巴巴)", "03690.HK (美团)"],
            "format": "代码.HK (如: 0700.HK, 09988.HK)",
            "pattern": r'^\d{4,5}\.HK$',
            "data_source": "yahoo_finance"
        }
    }

    console.print(f"\n[bold cyan]请选择股票市场 | Please select stock market:[/bold cyan]")
    for key, market in markets.items():
        examples_str = ", ".join(market["examples"][:3])
        console.print(f"[cyan]{key}[/cyan]. 🌍 {market['name']} | {market['name_en']}")
        console.print(f"   示例 | Examples: {examples_str}")

    while True:
        choice = typer.prompt("\n请选择市场 | Select market", default="2")
        if choice in markets:
            selected_market = markets[choice]
            console.print(f"[green]✅ 已选择: {selected_market['name']} | Selected: {selected_market['name_en']}[/green]")
            # 记录系统日志（只写入文件）
            logger.info(f"用户选择市场: {selected_market['name']} ({selected_market['name_en']})")
            return selected_market
        else:
            console.print(f"[red]❌ 无效选择，请输入 1、2 或 3 | Invalid choice, please enter 1, 2, or 3[/red]")
            logger.warning(f"用户输入无效选择: {choice}")


def get_ticker(market):
    """根据选定市场获取股票代码"""
    console.print(f"\n[bold cyan]{market['name']}股票示例 | {market['name_en']} Examples:[/bold cyan]")
    for example in market['examples']:
        console.print(f"  • {example}")

    console.print(f"\n[dim]格式要求 | Format: {market['format']}[/dim]")

    while True:
        ticker = typer.prompt(f"\n请输入{market['name']}股票代码 | Enter {market['name_en']} ticker",
                             default=market['default'])

        # 记录用户输入（只写入文件）
        logger.info(f"用户输入股票代码: {ticker}")

        # 验证股票代码格式
        import re
        
        # 添加边界条件检查
        ticker = ticker.strip()  # 移除首尾空格
        if not ticker:  # 检查空字符串
            console.print(f"[red]❌ 股票代码不能为空 | Ticker cannot be empty[/red]")
            logger.warning(f"用户输入空股票代码")
            continue
            
        ticker_to_check = ticker.upper() if market['data_source'] != 'china_stock' else ticker

        if re.match(market['pattern'], ticker_to_check):
            # 对于A股，返回纯数字代码
            if market['data_source'] == 'china_stock':
                console.print(f"[green]✅ A股代码有效: {ticker} (将使用中国股票数据源)[/green]")
                logger.info(f"A股代码验证成功: {ticker}")
                return ticker
            else:
                console.print(f"[green]✅ 股票代码有效: {ticker.upper()}[/green]")
                logger.info(f"股票代码验证成功: {ticker.upper()}")
                return ticker.upper()
        else:
            console.print(f"[red]❌ 股票代码格式不正确 | Invalid ticker format[/red]")
            console.print(f"[yellow]请使用正确格式: {market['format']}[/yellow]")
            logger.warning(f"股票代码格式验证失败: {ticker}")


def get_analysis_date():
    """Get the analysis date from user input."""
    while True:
        date_str = typer.prompt(
            "请输入分析日期 | Enter analysis date", default=datetime.datetime.now().strftime("%Y-%m-%d")
        )
        try:
            # Validate date format and ensure it's not in the future
            analysis_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if analysis_date.date() > datetime.datetime.now().date():
                console.print(f"[red]错误：分析日期不能是未来日期 | Error: Analysis date cannot be in the future[/red]")
                logger.warning(f"用户输入未来日期: {date_str}")
                continue
            return date_str
        except ValueError:
            console.print(
                "[red]错误：日期格式无效，请使用 YYYY-MM-DD 格式 | Error: Invalid date format. Please use YYYY-MM-DD[/red]"
            )


def display_complete_report(final_state):
    """Display the complete analysis report with team-based panels."""
    logger.info(f"\n[bold green]Complete Analysis Report[/bold green]\n")

    # I. Analyst Team Reports
    analyst_reports = []

    # Market Analyst Report
    if final_state.get("market_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["market_report"]),
                title="Market Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Social Analyst Report
    if final_state.get("sentiment_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["sentiment_report"]),
                title="Social Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # News Analyst Report
    if final_state.get("news_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["news_report"]),
                title="News Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Fundamentals Analyst Report
    if final_state.get("fundamentals_report"):
        analyst_reports.append(
            Panel(
                Markdown(final_state["fundamentals_report"]),
                title="Fundamentals Analyst",
                border_style="blue",
                padding=(1, 2),
            )
        )

    if analyst_reports:
        console.print(
            Panel(
                Columns(analyst_reports, equal=True, expand=True),
                title="I. Analyst Team Reports",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # II. Research Team Reports
    if final_state.get("investment_debate_state"):
        research_reports = []
        debate_state = final_state["investment_debate_state"]

        # Bull Researcher Analysis
        if debate_state.get("bull_history"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["bull_history"]),
                    title="Bull Researcher",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Bear Researcher Analysis
        if debate_state.get("bear_history"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["bear_history"]),
                    title="Bear Researcher",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Research Manager Decision
        if debate_state.get("judge_decision"):
            research_reports.append(
                Panel(
                    Markdown(debate_state["judge_decision"]),
                    title="Research Manager",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        if research_reports:
            console.print(
                Panel(
                    Columns(research_reports, equal=True, expand=True),
                    title="II. Research Team Decision",
                    border_style="magenta",
                    padding=(1, 2),
                )
            )

    # III. Trading Team Reports
    if final_state.get("trader_investment_plan"):
        console.print(
            Panel(
                Panel(
                    Markdown(final_state["trader_investment_plan"]),
                    title="Trader",
                    border_style="blue",
                    padding=(1, 2),
                ),
                title="III. Trading Team Plan",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    # IV. Risk Management Team Reports
    if final_state.get("risk_debate_state"):
        risk_reports = []
        risk_state = final_state["risk_debate_state"]

        # Aggressive (Risky) Analyst Analysis
        if risk_state.get("risky_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["risky_history"]),
                    title="Aggressive Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Conservative (Safe) Analyst Analysis
        if risk_state.get("safe_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["safe_history"]),
                    title="Conservative Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Neutral Analyst Analysis
        if risk_state.get("neutral_history"):
            risk_reports.append(
                Panel(
                    Markdown(risk_state["neutral_history"]),
                    title="Neutral Analyst",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        if risk_reports:
            console.print(
                Panel(
                    Columns(risk_reports, equal=True, expand=True),
                    title="IV. Risk Management Team Decision",
                    border_style="red",
                    padding=(1, 2),
                )
            )

        # V. Portfolio Manager Decision
        if risk_state.get("judge_decision"):
            console.print(
                Panel(
                    Panel(
                        Markdown(risk_state["judge_decision"]),
                        title="Portfolio Manager",
                        border_style="blue",
                        padding=(1, 2),
                    ),
                    title="V. Portfolio Manager Decision",
                    border_style="green",
                    padding=(1, 2),
                )
            )


def update_research_team_status(status):
    """
    更新所有研究团队成员和交易员的状态
    Update status for all research team members and trader
    
    Args:
        status: 新的状态值
    """
    research_team = ["Bull Researcher", "Bear Researcher", "Research Manager", "Trader"]
    for agent in research_team:
        message_buffer.update_agent_status(agent, status)

def extract_content_string(content):
    """
    从各种消息格式中提取字符串内容
    Extract string content from various message formats
    
    Args:
        content: 消息内容，可能是字符串、列表或其他格式
    
    Returns:
        str: 提取的字符串内容
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Handle Anthropic's list format
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get('type')  # 缓存type值
                if item_type == 'text':
                    text_parts.append(item.get('text', ''))
                elif item_type == 'tool_use':
                    tool_name = item.get('name', 'unknown')  # 缓存name值
                    text_parts.append(f"[Tool: {tool_name}]")
            else:
                text_parts.append(str(item))
        return ' '.join(text_parts)
    else:
        return str(content)

def check_api_keys(llm_provider: str) -> bool:
    """检查必要的API密钥是否已配置"""

    missing_keys = []

    # 检查LLM提供商对应的API密钥
    if "阿里百炼" in llm_provider or "dashscope" in llm_provider.lower():
        if not os.getenv("DASHSCOPE_API_KEY"):
            missing_keys.append("DASHSCOPE_API_KEY (阿里百炼)")
    elif "openai" in llm_provider.lower():
        if not os.getenv("OPENAI_API_KEY"):
            missing_keys.append("OPENAI_API_KEY")
    elif "anthropic" in llm_provider.lower():
        if not os.getenv("ANTHROPIC_API_KEY"):
            missing_keys.append("ANTHROPIC_API_KEY")
    elif "google" in llm_provider.lower():
        if not os.getenv("GOOGLE_API_KEY"):
            missing_keys.append("GOOGLE_API_KEY")

    # 检查金融数据API密钥
    if not os.getenv("FINNHUB_API_KEY"):
        missing_keys.append("FINNHUB_API_KEY (金融数据)")

    if missing_keys:
        logger.error("[red]❌ 缺少必要的API密钥 | Missing required API keys[/red]")
        for key in missing_keys:
            logger.info(f"   • {key}")

        logger.info(f"\n[yellow]💡 解决方案 | Solutions:[/yellow]")
        logger.info(f"1. 在项目根目录创建 .env 文件 | Create .env file in project root:")
        logger.info(f"   DASHSCOPE_API_KEY=your_dashscope_key")
        logger.info(f"   FINNHUB_API_KEY=your_finnhub_key")
        logger.info(f"\n2. 或设置环境变量 | Or set environment variables")
        logger.info(f"\n3. 运行 'python -m cli.main config' 查看详细配置说明")

        return False

    return True

def run_analysis():
    import time
    start_time = time.time()  # 记录开始时间
    
    # First get all user selections
    selections = get_user_selections()

    # Check API keys before proceeding
    if not check_api_keys(selections["llm_provider"]):
        ui.show_error("分析终止 | Analysis terminated")
        return

    # 显示分析开始信息
    ui.show_step_header(1, "准备分析环境 | Preparing Analysis Environment")
    ui.show_progress(f"正在分析股票: {selections['ticker']}")
    ui.show_progress(f"分析日期: {selections['analysis_date']}")
    ui.show_progress(f"选择的分析师: {', '.join(analyst.value for analyst in selections['analysts'])}")

    # Create config with selected research depth
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = selections["research_depth"]
    config["max_risk_discuss_rounds"] = selections["research_depth"]
    config["quick_think_llm"] = selections["shallow_thinker"]
    config["deep_think_llm"] = selections["deep_thinker"]
    config["backend_url"] = selections["backend_url"]
    # 处理LLM提供商名称，确保正确识别
    selected_llm_provider_name = selections["llm_provider"].lower()
    if "阿里百炼" in selections["llm_provider"] or "dashscope" in selected_llm_provider_name:
        config["llm_provider"] = "dashscope"
    elif "deepseek" in selected_llm_provider_name or "DeepSeek" in selections["llm_provider"]:
        config["llm_provider"] = "deepseek"
    elif "openai" in selected_llm_provider_name and "自定义" not in selections["llm_provider"]:
        config["llm_provider"] = "openai"
    elif "自定义openai端点" in selected_llm_provider_name or "自定义" in selections["llm_provider"]:
        config["llm_provider"] = "custom_openai"
        # 从环境变量获取自定义URL
        custom_url = os.getenv('CUSTOM_OPENAI_BASE_URL', selections["backend_url"])
        config["custom_openai_base_url"] = custom_url
        config["backend_url"] = custom_url
    elif "anthropic" in selected_llm_provider_name:
        config["llm_provider"] = "anthropic"
    elif "google" in selected_llm_provider_name:
        config["llm_provider"] = "google"
    else:
        config["llm_provider"] = selected_llm_provider_name

    # Initialize the graph
    ui.show_progress("正在初始化分析系统...")
    try:
        graph = TradingAgentsGraph(
            [analyst.value for analyst in selections["analysts"]], config=config, debug=True
        )
        ui.show_success("分析系统初始化完成")
    except ImportError as e:
        ui.show_error(f"模块导入失败 | Module import failed: {str(e)}")
        ui.show_warning("💡 请检查依赖安装 | Please check dependencies installation")
        return
    except ValueError as e:
        ui.show_error(f"配置参数错误 | Configuration error: {str(e)}")
        ui.show_warning("💡 请检查配置参数 | Please check configuration parameters")
        return
    except Exception as e:
        ui.show_error(f"初始化失败 | Initialization failed: {str(e)}")
        ui.show_warning("💡 请检查API密钥配置 | Please check API key configuration")
        return

    # Create result directory
    results_dir = Path(config["results_dir"]) / selections["ticker"] / selections["analysis_date"]
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    def save_message_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, message_type, content = obj.messages[-1]
            content = content.replace("\n", " ")  # Replace newlines with spaces
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [{message_type}] {content}\n")
        return wrapper
    
    def save_tool_call_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, tool_name, args = obj.tool_calls[-1]
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")
        return wrapper

    def save_report_section_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(section_name, content):
            func(section_name, content)
            if section_name in obj.report_sections and obj.report_sections[section_name] is not None:
                content = obj.report_sections[section_name]
                if content:
                    file_name = f"{section_name}.md"
                    with open(report_dir / file_name, "w", encoding="utf-8") as f:
                        f.write(content)
        return wrapper

    message_buffer.add_message = save_message_decorator(message_buffer, "add_message")
    message_buffer.add_tool_call = save_tool_call_decorator(message_buffer, "add_tool_call")
    message_buffer.update_report_section = save_report_section_decorator(message_buffer, "update_report_section")

    # Now start the display layout
    layout = create_layout()

    with Live(layout, refresh_per_second=DEFAULT_REFRESH_RATE) as live:
        # Initial display
        update_display(layout)

        # Add initial messages
        message_buffer.add_message("System", f"Selected ticker: {selections['ticker']}")
        message_buffer.add_message(
            "System", f"Analysis date: {selections['analysis_date']}"
        )
        message_buffer.add_message(
            "System",
            f"Selected analysts: {', '.join(analyst.value for analyst in selections['analysts'])}",
        )
        update_display(layout)

        # Reset agent statuses
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "pending")

        # Reset report sections
        for section in message_buffer.report_sections:
            message_buffer.report_sections[section] = None
        message_buffer.current_report = None
        message_buffer.final_report = None

        # Update agent status to in_progress for the first analyst
        first_analyst = f"{selections['analysts'][0].value.capitalize()} Analyst"
        message_buffer.update_agent_status(first_analyst, "in_progress")
        update_display(layout)

        # Create spinner text
        spinner_text = (
            f"Analyzing {selections['ticker']} on {selections['analysis_date']}..."
        )
        update_display(layout, spinner_text)

        # 显示数据预获取和验证阶段
        ui.show_step_header(2, "数据验证阶段 | Data Validation Phase")
        ui.show_progress("🔍 验证股票代码并预获取数据...")

        try:
            from tradingagents.utils.stock_validator import prepare_stock_data

            # 确定市场类型
            market_type_map = {
                "china_stock": "A股",
                "yahoo_finance": "港股" if ".HK" in selections["ticker"] else "美股"
            }

            # 获取选定市场的数据源类型
            selected_market = None
            for choice, market in {
                "1": {"data_source": "yahoo_finance"},
                "2": {"data_source": "china_stock"},
                "3": {"data_source": "yahoo_finance"}
            }.items():
                # 这里需要从用户选择中获取市场类型，暂时使用代码推断
                pass

            # 根据股票代码推断市场类型
            if re.match(r'^\d{6}$', selections["ticker"]):
                market_type = "A股"
            elif ".HK" in selections["ticker"].upper():
                market_type = "港股"
            else:
                market_type = "美股"

            # 预获取股票数据（默认30天历史数据）
            preparation_result = prepare_stock_data(
                stock_code=selections["ticker"],
                market_type=market_type,
                period_days=30,
                analysis_date=selections["analysis_date"]
            )

            if not preparation_result.is_valid:
                ui.show_error(f"❌ 股票数据验证失败: {preparation_result.error_message}")
                ui.show_warning(f"💡 建议: {preparation_result.suggestion}")
                logger.error(f"股票数据验证失败: {preparation_result.error_message}")
                return

            # 数据预获取成功
            ui.show_success(f"✅ 数据准备完成: {preparation_result.stock_name} ({preparation_result.market_type})")
            ui.show_user_message(f"📊 缓存状态: {preparation_result.cache_status}", "dim")
            logger.info(f"股票数据预获取成功: {preparation_result.stock_name}")

        except Exception as e:
            ui.show_error(f"❌ 数据预获取过程中发生错误: {str(e)}")
            ui.show_warning("💡 请检查网络连接或稍后重试")
            logger.error(f"数据预获取异常: {str(e)}")
            return

        # 显示数据获取阶段
        ui.show_step_header(3, "数据获取阶段 | Data Collection Phase")
        ui.show_progress("正在获取股票基本信息...")

        # Initialize state and get graph args
        init_agent_state = graph.propagator.create_initial_state(
            selections["ticker"], selections["analysis_date"]
        )
        args = graph.propagator.get_graph_args()

        ui.show_success("数据获取准备完成")

        # 显示分析阶段
        ui.show_step_header(4, "智能分析阶段 | AI Analysis Phase (预计耗时约10分钟)")
        ui.show_progress("启动分析师团队...")
        ui.show_user_message("💡 提示：智能分析包含多个团队协作，请耐心等待约10分钟", "dim")

        # Stream the analysis
        trace = []
        current_analyst = None
        analysis_steps = {
            "market_report": "📈 市场分析师",
            "fundamentals_report": "📊 基本面分析师",
            "technical_report": "🔍 技术分析师",
            "sentiment_report": "💭 情感分析师",
            "final_report": "🤖 信号处理器"
        }

        # 跟踪已完成的分析师，避免重复提示
        completed_analysts = set()

        for chunk in graph.graph.stream(init_agent_state, **args):
            if len(chunk["messages"]) > 0:
                # Get the last message from the chunk
                last_message = chunk["messages"][-1]

                # Extract message content and type
                if hasattr(last_message, "content"):
                    content = extract_content_string(last_message.content)  # Use the helper function
                    msg_type = "Reasoning"
                else:
                    content = str(last_message)
                    msg_type = "System"

                # Add message to buffer
                message_buffer.add_message(msg_type, content)                

                # If it's a tool call, add it to tool calls
                if hasattr(last_message, "tool_calls"):
                    for tool_call in last_message.tool_calls:
                        # Handle both dictionary and object tool calls
                        if isinstance(tool_call, dict):
                            message_buffer.add_tool_call(
                                tool_call["name"], tool_call["args"]
                            )
                        else:
                            message_buffer.add_tool_call(tool_call.name, tool_call.args)

                # Update reports and agent status based on chunk content
                # Analyst Team Reports
                if "market_report" in chunk and chunk["market_report"]:
                    # 只在第一次完成时显示提示
                    if "market_report" not in completed_analysts:
                        ui.show_success("📈 市场分析完成")
                        completed_analysts.add("market_report")
                        # 调试信息（写入日志文件）
                        logger.info(f"首次显示市场分析完成提示，已完成分析师: {completed_analysts}")
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(f"跳过重复的市场分析完成提示，已完成分析师: {completed_analysts}")

                    message_buffer.update_report_section(
                        "market_report", chunk["market_report"]
                    )
                    message_buffer.update_agent_status("Market Analyst", "completed")
                    # Set next analyst to in_progress
                    if "social" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "Social Analyst", "in_progress"
                        )

                if "sentiment_report" in chunk and chunk["sentiment_report"]:
                    # 只在第一次完成时显示提示
                    if "sentiment_report" not in completed_analysts:
                        ui.show_success("💭 情感分析完成")
                        completed_analysts.add("sentiment_report")
                        # 调试信息（写入日志文件）
                        logger.info(f"首次显示情感分析完成提示，已完成分析师: {completed_analysts}")
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(f"跳过重复的情感分析完成提示，已完成分析师: {completed_analysts}")

                    message_buffer.update_report_section(
                        "sentiment_report", chunk["sentiment_report"]
                    )
                    message_buffer.update_agent_status("Social Analyst", "completed")
                    # Set next analyst to in_progress
                    if "news" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "News Analyst", "in_progress"
                        )

                if "news_report" in chunk and chunk["news_report"]:
                    # 只在第一次完成时显示提示
                    if "news_report" not in completed_analysts:
                        ui.show_success("📰 新闻分析完成")
                        completed_analysts.add("news_report")
                        # 调试信息（写入日志文件）
                        logger.info(f"首次显示新闻分析完成提示，已完成分析师: {completed_analysts}")
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(f"跳过重复的新闻分析完成提示，已完成分析师: {completed_analysts}")

                    message_buffer.update_report_section(
                        "news_report", chunk["news_report"]
                    )
                    message_buffer.update_agent_status("News Analyst", "completed")
                    # Set next analyst to in_progress
                    if "fundamentals" in selections["analysts"]:
                        message_buffer.update_agent_status(
                            "Fundamentals Analyst", "in_progress"
                        )

                if "fundamentals_report" in chunk and chunk["fundamentals_report"]:
                    # 只在第一次完成时显示提示
                    if "fundamentals_report" not in completed_analysts:
                        ui.show_success("📊 基本面分析完成")
                        completed_analysts.add("fundamentals_report")
                        # 调试信息（写入日志文件）
                        logger.info(f"首次显示基本面分析完成提示，已完成分析师: {completed_analysts}")
                    else:
                        # 调试信息（写入日志文件）
                        logger.debug(f"跳过重复的基本面分析完成提示，已完成分析师: {completed_analysts}")

                    message_buffer.update_report_section(
                        "fundamentals_report", chunk["fundamentals_report"]
                    )
                    message_buffer.update_agent_status(
                        "Fundamentals Analyst", "completed"
                    )
                    # Set all research team members to in_progress
                    update_research_team_status("in_progress")

                # Research Team - Handle Investment Debate State
                if (
                    "investment_debate_state" in chunk
                    and chunk["investment_debate_state"]
                ):
                    debate_state = chunk["investment_debate_state"]

                    # Update Bull Researcher status and report
                    if "bull_history" in debate_state and debate_state["bull_history"]:
                        # 显示研究团队开始工作
                        if "research_team_started" not in completed_analysts:
                            ui.show_progress("🔬 研究团队开始深度分析...")
                            completed_analysts.add("research_team_started")

                        # Keep all research team members in progress
                        update_research_team_status("in_progress")
                        # Extract latest bull response
                        bull_responses = debate_state["bull_history"].split("\n")
                        latest_bull = bull_responses[-1] if bull_responses else ""
                        if latest_bull:
                            message_buffer.add_message("Reasoning", latest_bull)
                            # Update research report with bull's latest analysis
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"### Bull Researcher Analysis\n{latest_bull}",
                            )

                    # Update Bear Researcher status and report
                    if "bear_history" in debate_state and debate_state["bear_history"]:
                        # Keep all research team members in progress
                        update_research_team_status("in_progress")
                        # Extract latest bear response
                        bear_responses = debate_state["bear_history"].split("\n")
                        latest_bear = bear_responses[-1] if bear_responses else ""
                        if latest_bear:
                            message_buffer.add_message("Reasoning", latest_bear)
                            # Update research report with bear's latest analysis
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"{message_buffer.report_sections['investment_plan']}\n\n### Bear Researcher Analysis\n{latest_bear}",
                            )

                    # Update Research Manager status and final decision
                    if (
                        "judge_decision" in debate_state
                        and debate_state["judge_decision"]
                    ):
                        # 显示研究团队完成
                        if "research_team" not in completed_analysts:
                            ui.show_success("🔬 研究团队分析完成")
                            completed_analysts.add("research_team")

                        # Keep all research team members in progress until final decision
                        update_research_team_status("in_progress")
                        message_buffer.add_message(
                            "Reasoning",
                            f"Research Manager: {debate_state['judge_decision']}",
                        )
                        # Update research report with final decision
                        message_buffer.update_report_section(
                            "investment_plan",
                            f"{message_buffer.report_sections['investment_plan']}\n\n### Research Manager Decision\n{debate_state['judge_decision']}",
                        )
                        # Mark all research team members as completed
                        update_research_team_status("completed")
                        # Set first risk analyst to in_progress
                        message_buffer.update_agent_status(
                            "Risky Analyst", "in_progress"
                        )

                # Trading Team
                if (
                    "trader_investment_plan" in chunk
                    and chunk["trader_investment_plan"]
                ):
                    # 显示交易团队开始工作
                    if "trading_team_started" not in completed_analysts:
                        ui.show_progress("💼 交易团队制定投资计划...")
                        completed_analysts.add("trading_team_started")

                    # 显示交易团队完成
                    if "trading_team" not in completed_analysts:
                        ui.show_success("💼 交易团队计划完成")
                        completed_analysts.add("trading_team")

                    message_buffer.update_report_section(
                        "trader_investment_plan", chunk["trader_investment_plan"]
                    )
                    # Set first risk analyst to in_progress
                    message_buffer.update_agent_status("Risky Analyst", "in_progress")

                # Risk Management Team - Handle Risk Debate State
                if "risk_debate_state" in chunk and chunk["risk_debate_state"]:
                    risk_state = chunk["risk_debate_state"]

                    # Update Risky Analyst status and report
                    if (
                        "current_risky_response" in risk_state
                        and risk_state["current_risky_response"]
                    ):
                        # 显示风险管理团队开始工作
                        if "risk_team_started" not in completed_analysts:
                            ui.show_progress("⚖️ 风险管理团队评估投资风险...")
                            completed_analysts.add("risk_team_started")

                        message_buffer.update_agent_status(
                            "Risky Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Risky Analyst: {risk_state['current_risky_response']}",
                        )
                        # Update risk report with risky analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Risky Analyst Analysis\n{risk_state['current_risky_response']}",
                        )

                    # Update Safe Analyst status and report
                    if (
                        "current_safe_response" in risk_state
                        and risk_state["current_safe_response"]
                    ):
                        message_buffer.update_agent_status(
                            "Safe Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Safe Analyst: {risk_state['current_safe_response']}",
                        )
                        # Update risk report with safe analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Safe Analyst Analysis\n{risk_state['current_safe_response']}",
                        )

                    # Update Neutral Analyst status and report
                    if (
                        "current_neutral_response" in risk_state
                        and risk_state["current_neutral_response"]
                    ):
                        message_buffer.update_agent_status(
                            "Neutral Analyst", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Neutral Analyst: {risk_state['current_neutral_response']}",
                        )
                        # Update risk report with neutral analyst's latest analysis only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Neutral Analyst Analysis\n{risk_state['current_neutral_response']}",
                        )

                    # Update Portfolio Manager status and final decision
                    if "judge_decision" in risk_state and risk_state["judge_decision"]:
                        # 显示风险管理团队完成
                        if "risk_management" not in completed_analysts:
                            ui.show_success("⚖️ 风险管理团队分析完成")
                            completed_analysts.add("risk_management")

                        message_buffer.update_agent_status(
                            "Portfolio Manager", "in_progress"
                        )
                        message_buffer.add_message(
                            "Reasoning",
                            f"Portfolio Manager: {risk_state['judge_decision']}",
                        )
                        # Update risk report with final decision only
                        message_buffer.update_report_section(
                            "final_trade_decision",
                            f"### Portfolio Manager Decision\n{risk_state['judge_decision']}",
                        )
                        # Mark risk analysts as completed
                        message_buffer.update_agent_status("Risky Analyst", "completed")
                        message_buffer.update_agent_status("Safe Analyst", "completed")
                        message_buffer.update_agent_status(
                            "Neutral Analyst", "completed"
                        )
                        message_buffer.update_agent_status(
                            "Portfolio Manager", "completed"
                        )

                # Update the display
                update_display(layout)

            trace.append(chunk)

        # 显示最终决策阶段
        ui.show_step_header(5, "投资决策生成 | Investment Decision Generation")
        ui.show_progress("正在处理投资信号...")

        # Get final state and decision
        final_state = trace[-1]
        decision = graph.process_signal(final_state["final_trade_decision"], selections['ticker'])

        ui.show_success("🤖 投资信号处理完成")

        # Update all agent statuses to completed
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "completed")

        message_buffer.add_message(
            "Analysis", f"Completed analysis for {selections['analysis_date']}"
        )

        # Update final report sections
        for section in message_buffer.report_sections.keys():
            if section in final_state:
                message_buffer.update_report_section(section, final_state[section])

        # 显示报告生成完成
        ui.show_step_header(6, "分析报告生成 | Analysis Report Generation")
        ui.show_progress("正在生成最终报告...")

        # Display the complete final report
        display_complete_report(final_state)

        ui.show_success("📋 分析报告生成完成")
        ui.show_success(f"🎉 {selections['ticker']} 股票分析全部完成！")
        
        # 记录总执行时间
        total_time = time.time() - start_time
        ui.show_user_message(f"⏱️ 总分析时间: {total_time:.1f}秒", "dim")

        update_display(layout)


@app.command(
    name="analyze",
    help="开始股票分析 | Start stock analysis"
)
def analyze():
    """
    启动交互式股票分析工具
    Launch interactive stock analysis tool
    """
    run_analysis()


@app.command(
    name="config",
    help="配置设置 | Configuration settings"
)
def config():
    """
    显示和配置系统设置
    Display and configure system settings
    """
    logger.info(f"\n[bold blue]🔧 TradingAgents 配置 | Configuration[/bold blue]")
    logger.info(f"\n[yellow]当前支持的LLM提供商 | Supported LLM Providers:[/yellow]")

    providers_table = Table(show_header=True, header_style="bold magenta")
    providers_table.add_column("提供商 | Provider", style="cyan")
    providers_table.add_column("模型 | Models", style="green")
    providers_table.add_column("状态 | Status", style="yellow")
    providers_table.add_column("说明 | Description")

    providers_table.add_row(
        "🇨🇳 阿里百炼 (DashScope)",
        "qwen-turbo, qwen-plus, qwen-max",
        "✅ 推荐 | Recommended",
        "国产大模型，中文优化 | Chinese-optimized"
    )
    providers_table.add_row(
        "🌍 OpenAI",
        "gpt-4o, gpt-4o-mini, gpt-3.5-turbo",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API"
    )
    providers_table.add_row(
        "🤖 Anthropic",
        "claude-3-opus, claude-3-sonnet",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API"
    )
    providers_table.add_row(
        "🔍 Google AI",
        "gemini-pro, gemini-2.0-flash",
        "✅ 支持 | Supported",
        "需要国外API | Requires overseas API"
    )

    console.print(providers_table)

    # 检查API密钥状态
    logger.info(f"\n[yellow]API密钥状态 | API Key Status:[/yellow]")

    api_keys_table = Table(show_header=True, header_style="bold magenta")
    api_keys_table.add_column("API密钥 | API Key", style="cyan")
    api_keys_table.add_column("状态 | Status", style="yellow")
    api_keys_table.add_column("说明 | Description")

    # 检查各个API密钥
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")

    api_keys_table.add_row(
        "DASHSCOPE_API_KEY",
        "✅ 已配置" if dashscope_key else "❌ 未配置",
        f"阿里百炼 | {dashscope_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..." if dashscope_key else "阿里百炼API密钥"
    )
    api_keys_table.add_row(
        "FINNHUB_API_KEY",
        "✅ 已配置" if finnhub_key else "❌ 未配置",
        f"金融数据 | {finnhub_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..." if finnhub_key else "金融数据API密钥"
    )
    api_keys_table.add_row(
        "OPENAI_API_KEY",
        "✅ 已配置" if openai_key else "❌ 未配置",
        f"OpenAI | {openai_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..." if openai_key else "OpenAI API密钥"
    )
    api_keys_table.add_row(
        "ANTHROPIC_API_KEY",
        "✅ 已配置" if anthropic_key else "❌ 未配置",
        f"Anthropic | {anthropic_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..." if anthropic_key else "Anthropic API密钥"
    )
    api_keys_table.add_row(
        "GOOGLE_API_KEY",
        "✅ 已配置" if google_key else "❌ 未配置",
        f"Google AI | {google_key[:DEFAULT_API_KEY_DISPLAY_LENGTH]}..." if google_key else "Google AI API密钥"
    )

    console.print(api_keys_table)

    logger.info(f"\n[yellow]配置API密钥 | Configure API Keys:[/yellow]")
    logger.info(f"1. 编辑项目根目录的 .env 文件 | Edit .env file in project root")
    logger.info(f"2. 或设置环境变量 | Or set environment variables:")
    logger.info(f"   - DASHSCOPE_API_KEY (阿里百炼)")
    logger.info(f"   - OPENAI_API_KEY (OpenAI)")
    logger.info(f"   - FINNHUB_API_KEY (金融数据 | Financial data)")

    # 如果缺少关键API密钥，给出提示
    if not dashscope_key or not finnhub_key:
        logger.warning("[red]⚠️ 警告 | Warning:[/red]")
        if not dashscope_key:
            logger.info(f"   • 缺少阿里百炼API密钥，无法使用推荐的中文优化模型")
        if not finnhub_key:
            logger.info(f"   • 缺少金融数据API密钥，无法获取实时股票数据")

    logger.info(f"\n[yellow]示例程序 | Example Programs:[/yellow]")
    logger.info(f"• python examples/dashscope/demo_dashscope_chinese.py  # 中文分析演示")
    logger.info(f"• python examples/dashscope/demo_dashscope_simple.py   # 简单测试")
    logger.info(f"• python tests/integration/test_dashscope_integration.py  # 集成测试")


@app.command(
    name="version",
    help="版本信息 | Version information"
)
def version():
    """
    显示版本信息
    Display version information
    """
    # 读取版本号
    try:
        with open("VERSION", "r", encoding="utf-8") as f:
            version = f.read().strip()
    except FileNotFoundError:
        version = "1.0.0"

    logger.info(f"\n[bold blue]📊 TradingAgents 版本信息 | Version Information[/bold blue]")
    logger.info(f"[green]版本 | Version:[/green] {version} [yellow](预览版 | Preview)[/yellow]")
    logger.info(f"[green]发布日期 | Release Date:[/green] 2025-06-26")
    logger.info(f"[green]框架 | Framework:[/green] 多智能体金融交易分析 | Multi-Agent Financial Trading Analysis")
    logger.info(f"[green]支持的语言 | Languages:[/green] 中文 | English")
    logger.info(f"[green]开发状态 | Development Status:[/green] [yellow]早期预览版，功能持续完善中[/yellow]")
    logger.info(f"[green]基于项目 | Based on:[/green] [blue]TauricResearch/TradingAgents[/blue]")
    logger.info(f"[green]创建目的 | Purpose:[/green] [cyan]更好地在中国推广TradingAgents[/cyan]")
    logger.info(f"[green]主要功能 | Features:[/green]")
    logger.info(f"  • 🤖 多智能体协作分析 | Multi-agent collaborative analysis")
    logger.info(f"  • 🇨🇳 阿里百炼大模型支持 | Alibaba DashScope support")
    logger.info(f"  • 📈 实时股票数据分析 | Real-time stock data analysis")
    logger.info(f"  • 🧠 智能投资建议 | Intelligent investment recommendations")
    logger.debug(f"  • 🔍 风险评估 | Risk assessment")

    logger.warning(f"\n[yellow]⚠️  预览版本提醒 | Preview Version Notice:[/yellow]")
    logger.info(f"  • 这是早期预览版本，功能仍在完善中")
    logger.info(f"  • 建议仅在测试环境中使用")
    logger.info(f"  • 投资建议仅供参考，请谨慎决策")
    logger.info(f"  • 欢迎反馈问题和改进建议")

    logger.info(f"\n[blue]🙏 致敬源项目 | Tribute to Original Project:[/blue]")
    logger.info(f"  • 💎 感谢 Tauric Research 团队提供的珍贵源码")
    logger.info(f"  • 🔄 感谢持续的维护、更新和改进工作")
    logger.info(f"  • 🌍 感谢选择Apache 2.0协议的开源精神")
    logger.info(f"  • 🎯 本项目旨在更好地在中国推广TradingAgents")
    logger.info(f"  • 🔗 源项目: https://github.com/TauricResearch/TradingAgents")


@app.command(
    name="data-config",
    help="数据目录配置 | Data directory configuration"
)
def data_config(
    show: bool = typer.Option(False, "--show", "-s", help="显示当前配置 | Show current configuration"),
    set_dir: Optional[str] = typer.Option(None, "--set", "-d", help="设置数据目录 | Set data directory"),
    reset: bool = typer.Option(False, "--reset", "-r", help="重置为默认配置 | Reset to default configuration")
):
    """
    配置数据目录路径
    Configure data directory paths
    """
    from tradingagents.config.config_manager import config_manager

    # 使用 config_manager 的方法
    get_data_dir = config_manager.get_data_dir
    set_data_dir = config_manager.set_data_dir
    
    logger.info(f"\n[bold blue]📁 数据目录配置 | Data Directory Configuration[/bold blue]")
    
    if reset:
        # 重置为默认配置
        default_data_dir = os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data")
        set_data_dir(default_data_dir)
        logger.info(f"[green]✅ 已重置数据目录为默认路径: {default_data_dir}[/green]")
        return
    
    if set_dir:
        # 设置新的数据目录
        try:
            set_data_dir(set_dir)
            logger.info(f"[green]✅ 数据目录已设置为: {set_dir}[/green]")
            
            # 显示创建的目录结构
            if os.path.exists(set_dir):
                logger.info(f"\n[blue]📂 目录结构:[/blue]")
                for root, dirs, files in os.walk(set_dir):
                    level = root.replace(set_dir, '').count(os.sep)
                    if level > 2:  # 限制显示深度
                        continue
                    indent = '  ' * level
                    logger.info(f"{indent}📁 {os.path.basename(root)}/")
        except Exception as e:
            logger.error(f"[red]❌ 设置数据目录失败: {e}[/red]")
        return
    
    # 显示当前配置（默认行为或使用--show）
    settings = config_manager.load_settings()
    current_data_dir = get_data_dir()
    
    # 配置信息表格
    config_table = Table(show_header=True, header_style="bold magenta")
    config_table.add_column("配置项 | Configuration", style="cyan")
    config_table.add_column("路径 | Path", style="green")
    config_table.add_column("状态 | Status", style="yellow")
    
    directories = {
        "数据目录 | Data Directory": settings.get("data_dir", "未配置"),
        "缓存目录 | Cache Directory": settings.get("cache_dir", "未配置"),
        "结果目录 | Results Directory": settings.get("results_dir", "未配置")
    }
    
    for name, path in directories.items():
        if path and path != "未配置":
            status = "✅ 存在" if os.path.exists(path) else "❌ 不存在"
        else:
            status = "⚠️ 未配置"
        config_table.add_row(name, str(path), status)
    
    console.print(config_table)
    
    # 环境变量信息
    logger.info(f"\n[blue]🌍 环境变量 | Environment Variables:[/blue]")
    env_table = Table(show_header=True, header_style="bold magenta")
    env_table.add_column("环境变量 | Variable", style="cyan")
    env_table.add_column("值 | Value", style="green")
    
    env_vars = {
        "TRADINGAGENTS_DATA_DIR": os.getenv("TRADINGAGENTS_DATA_DIR", "未设置"),
        "TRADINGAGENTS_CACHE_DIR": os.getenv("TRADINGAGENTS_CACHE_DIR", "未设置"),
        "TRADINGAGENTS_RESULTS_DIR": os.getenv("TRADINGAGENTS_RESULTS_DIR", "未设置")
    }
    
    for var, value in env_vars.items():
        env_table.add_row(var, value)
    
    console.print(env_table)
    
    # 使用说明
    logger.info(f"\n[yellow]💡 使用说明 | Usage:[/yellow]")
    logger.info(f"• 设置数据目录: tradingagents data-config --set /path/to/data")
    logger.info(f"• 重置为默认: tradingagents data-config --reset")
    logger.info(f"• 查看当前配置: tradingagents data-config --show")
    logger.info(f"• 环境变量优先级最高 | Environment variables have highest priority")


@app.command(
    name="examples",
    help="示例程序 | Example programs"
)
def examples():
    """
    显示可用的示例程序
    Display available example programs
    """
    logger.info(f"\n[bold blue]📚 TradingAgents 示例程序 | Example Programs[/bold blue]")

    examples_table = Table(show_header=True, header_style="bold magenta")
    examples_table.add_column("类型 | Type", style="cyan")
    examples_table.add_column("文件名 | Filename", style="green")
    examples_table.add_column("说明 | Description")

    examples_table.add_row(
        "🇨🇳 阿里百炼",
        "examples/dashscope/demo_dashscope_chinese.py",
        "中文优化的股票分析演示 | Chinese-optimized stock analysis"
    )
    examples_table.add_row(
        "🇨🇳 阿里百炼",
        "examples/dashscope/demo_dashscope.py",
        "完整功能演示 | Full feature demonstration"
    )
    examples_table.add_row(
        "🇨🇳 阿里百炼",
        "examples/dashscope/demo_dashscope_simple.py",
        "简化测试版本 | Simplified test version"
    )
    examples_table.add_row(
        "🌍 OpenAI",
        "examples/openai/demo_openai.py",
        "OpenAI模型演示 | OpenAI model demonstration"
    )
    examples_table.add_row(
        "🧪 测试",
        "tests/integration/test_dashscope_integration.py",
        "集成测试 | Integration test"
    )
    examples_table.add_row(
        "📁 配置演示",
        "examples/data_dir_config_demo.py",
        "数据目录配置演示 | Data directory configuration demo"
    )

    console.print(examples_table)

    logger.info(f"\n[yellow]运行示例 | Run Examples:[/yellow]")
    logger.info(f"1. 确保已配置API密钥 | Ensure API keys are configured")
    logger.info(f"2. 选择合适的示例程序运行 | Choose appropriate example to run")
    logger.info(f"3. 推荐从中文版本开始 | Recommended to start with Chinese version")


@app.command(
    name="test",
    help="运行测试 | Run tests"
)
def test():
    """
    运行系统测试
    Run system tests
    """
    logger.info(f"\n[bold blue]🧪 TradingAgents 测试 | Tests[/bold blue]")

    logger.info(f"[yellow]正在运行集成测试... | Running integration tests...[/yellow]")

    try:
        result = subprocess.run([
            sys.executable,
            "tests/integration/test_dashscope_integration.py"
        ], capture_output=True, text=True, cwd=".")

        if result.returncode == 0:
            logger.info(f"[green]✅ 测试通过 | Tests passed[/green]")
            console.print(result.stdout)
        else:
            logger.error(f"[red]❌ 测试失败 | Tests failed[/red]")
            console.print(result.stderr)

    except Exception as e:
        logger.error(f"[red]❌ 测试执行错误 | Test execution error: {e}[/red]")
        logger.info(f"\n[yellow]手动运行测试 | Manual test execution:[/yellow]")
        logger.info(f"python tests/integration/test_dashscope_integration.py")


@app.command(
    name="help",
    help="中文帮助 | Chinese help"
)
def help_chinese():
    """
    显示中文帮助信息
    Display Chinese help information
    """
    logger.info(f"\n[bold blue]📖 TradingAgents 中文帮助 | Chinese Help[/bold blue]")

    logger.info(f"\n[bold yellow]🚀 快速开始 | Quick Start:[/bold yellow]")
    logger.info(f"1. [cyan]python -m cli.main config[/cyan]     # 查看配置信息")
    logger.info(f"2. [cyan]python -m cli.main examples[/cyan]   # 查看示例程序")
    logger.info(f"3. [cyan]python -m cli.main test[/cyan]       # 运行测试")
    logger.info(f"4. [cyan]python -m cli.main analyze[/cyan]    # 开始股票分析")

    logger.info(f"\n[bold yellow]📋 主要命令 | Main Commands:[/bold yellow]")

    commands_table = Table(show_header=True, header_style="bold magenta")
    commands_table.add_column("命令 | Command", style="cyan")
    commands_table.add_column("功能 | Function", style="green")
    commands_table.add_column("说明 | Description")

    commands_table.add_row(
        "analyze",
        "股票分析 | Stock Analysis",
        "启动交互式多智能体股票分析工具"
    )
    commands_table.add_row(
        "config",
        "配置设置 | Configuration",
        "查看和配置LLM提供商、API密钥等设置"
    )
    commands_table.add_row(
        "examples",
        "示例程序 | Examples",
        "查看可用的演示程序和使用说明"
    )
    commands_table.add_row(
        "test",
        "运行测试 | Run Tests",
        "执行系统集成测试，验证功能正常"
    )
    commands_table.add_row(
        "version",
        "版本信息 | Version",
        "显示软件版本和功能特性信息"
    )

    console.print(commands_table)

    logger.info(f"\n[bold yellow]🇨🇳 推荐使用阿里百炼大模型:[/bold yellow]")
    logger.info(f"• 无需翻墙，网络稳定")
    logger.info(f"• 中文理解能力强")
    logger.info(f"• 成本相对较低")
    logger.info(f"• 符合国内合规要求")

    logger.info(f"\n[bold yellow]📞 获取帮助 | Get Help:[/bold yellow]")
    logger.info(f"• 项目文档: docs/ 目录")
    logger.info(f"• 示例程序: examples/ 目录")
    logger.info(f"• 集成测试: tests/ 目录")
    logger.info(f"• GitHub: https://github.com/TauricResearch/TradingAgents")


def main():
    """主函数 - 默认进入分析模式"""

    # 如果没有参数，直接进入分析模式
    if len(sys.argv) == 1:
        run_analysis()
    else:
        # 有参数时使用typer处理命令
        try:
            app()
        except SystemExit as e:
            # 只在退出码为2（typer的未知命令错误）时提供智能建议
            if e.code == 2 and len(sys.argv) > 1:
                unknown_command = sys.argv[1]
                available_commands = ['analyze', 'config', 'version', 'data-config', 'examples', 'test', 'help']
                
                # 使用difflib找到最相似的命令
                suggestions = get_close_matches(unknown_command, available_commands, n=3, cutoff=0.6)
                
                if suggestions:
                    logger.error(f"\n[red]❌ 未知命令: '{unknown_command}'[/red]")
                    logger.info(f"[yellow]💡 您是否想要使用以下命令之一？[/yellow]")
                    for suggestion in suggestions:
                        logger.info(f"   • [cyan]python -m cli.main {suggestion}[/cyan]")
                    logger.info(f"\n[dim]使用 [cyan]python -m cli.main help[/cyan] 查看所有可用命令[/dim]")
                else:
                    logger.error(f"\n[red]❌ 未知命令: '{unknown_command}'[/red]")
                    logger.info(f"[yellow]使用 [cyan]python -m cli.main help[/cyan] 查看所有可用命令[/yellow]")
            raise e

if __name__ == "__main__":
    main()
