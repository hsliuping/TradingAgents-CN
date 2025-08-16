import questionary
from typing import List, Optional, Tuple, Dict
from rich.console import Console

from cli.models import AnalystType
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('cli')
console = Console()

ANALYST_ORDER = [
    ("市场分析师 | Market Analyst", AnalystType.MARKET),
    ("社交媒体分析师 | Social Media Analyst", AnalystType.SOCIAL),
    ("新闻分析师 | News Analyst", AnalystType.NEWS),
    ("基本面分析师 | Fundamentals Analyst", AnalystType.FUNDAMENTALS),
]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        "请输入要分析的股票代码 | Enter the ticker symbol to analyze:",
        validate=lambda x: len(x.strip()) > 0 or "请输入有效的股票代码 | Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        logger.info(f"\n[red]未提供股票代码，退出程序... | No ticker symbol provided. Exiting...[/red]")
        exit(1)

    return ticker.strip().upper()


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""
    import re
    from datetime import datetime

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    date = questionary.text(
        "请输入分析日期 (YYYY-MM-DD) | Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "请输入有效的日期格式 YYYY-MM-DD | Please enter a valid date in YYYY-MM-DD format.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        logger.info(f"\n[red]未提供日期，退出程序... | No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts() -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""
    choices = questionary.checkbox(
        "选择您的分析师团队 | Select Your [Analysts Team]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in ANALYST_ORDER
        ],
        instruction="\n- 按空格键选择/取消选择分析师 | Press Space to select/unselect analysts\n- 按 'a' 键全选/取消全选 | Press 'a' to select/unselect all\n- 按回车键完成选择 | Press Enter when done",
        validate=lambda x: len(x) > 0 or "您必须至少选择一个分析师 | You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        logger.info(f"\n[red]未选择分析师，退出程序... | No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    # Define research depth options with their corresponding values
    DEPTH_OPTIONS = [
        ("浅层 - 快速研究，少量辩论和策略讨论 | Shallow - Quick research, few debate rounds", 1),
        ("中等 - 中等程度，适度的辩论和策略讨论 | Medium - Moderate debate and strategy discussion", 3),
        ("深度 - 全面研究，深入的辩论和策略讨论 | Deep - Comprehensive research, in-depth debate", 5),
    ]

    choice = questionary.select(
        "选择您的研究深度 | Select Your [Research Depth]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in DEPTH_OPTIONS
        ],
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info(f"\n[red]未选择研究深度，退出程序... | No research depth selected. Exiting...[/red]")
        exit(1)

    return choice


def select_shallow_thinking_agent(provider) -> str:
    """Select shallow thinking llm engine using an interactive selection."""

    # Define shallow thinking llm engine options with their corresponding model names
    SHALLOW_AGENT_OPTIONS = {
        "openai": [
            ("GPT-4o-mini - Fast and efficient for quick tasks", "gpt-4o-mini"),
            ("GPT-4.1-nano - Ultra-lightweight model for basic operations", "gpt-4.1-nano"),
            ("GPT-4.1-mini - Compact model with good performance", "gpt-4.1-mini"),
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
        ],
        "anthropic": [
            ("Claude Haiku 3.5 - Fast inference and standard capabilities", "claude-3-5-haiku-latest"),
            ("Claude Sonnet 3.5 - Highly capable standard model", "claude-3-5-sonnet-latest"),
            ("Claude Sonnet 3.7 - Exceptional hybrid reasoning and agentic capabilities", "claude-3-7-sonnet-latest"),
            ("Claude Sonnet 4 - High performance and excellent reasoning", "claude-sonnet-4-0"),
        ],
        "google": [
            ("Gemini 2.5 Pro - 🚀 最新旗舰模型", "gemini-2.5-pro"),
            ("Gemini 2.5 Flash - ⚡ 最新快速模型", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite - 💡 轻量快速", "gemini-2.5-flash-lite"),
            ("Gemini 2.5 Pro-002 - 🔧 优化版本", "gemini-2.5-pro-002"),
            ("Gemini 2.5 Flash-002 - ⚡ 优化快速版", "gemini-2.5-flash-002"),
            ("Gemini 2.5 Flash - Adaptive thinking, cost efficiency", "gemini-2.5-flash-preview-05-20"),
            ("Gemini 2.5 Pro Preview - 预览版本", "gemini-2.5-pro-preview-06-05"),
            ("Gemini 2.0 Flash Lite - 轻量版本", "gemini-2.0-flash-lite"),
            ("Gemini 2.0 Flash - 推荐使用", "gemini-2.0-flash"),
            ("Gemini 1.5 Pro - 强大性能", "gemini-1.5-pro"),
            ("Gemini 1.5 Flash - 快速响应", "gemini-1.5-flash"),
        ],
        "openrouter": [
            ("Meta: Llama 4 Scout", "meta-llama/llama-4-scout:free"),
            ("Meta: Llama 3.3 8B Instruct - A lightweight and ultra-fast variant of Llama 3.3 70B", "meta-llama/llama-3.3-8b-instruct:free"),
            ("google/gemini-2.0-flash-exp:free - Gemini Flash 2.0 offers a significantly faster time to first token", "google/gemini-2.0-flash-exp:free"),
        ],
        "ollama": [
            ("llama3.1 local", "llama3.1"),
            ("llama3.2 local", "llama3.2"),
        ],
        "阿里百炼 (dashscope)": [
            ("通义千问 Turbo - 快速响应，适合日常对话", "qwen-turbo"),
            ("通义千问 Plus - 平衡性能和成本", "qwen-plus"),
            ("通义千问 Max - 最强性能", "qwen-max"),
        ],
        "deepseek v3": [
            ("DeepSeek Chat - 通用对话模型，适合股票投资分析", "deepseek-chat"),
        ],
        "🔧 自定义openai端点": [
            ("GPT-4o-mini - Fast and efficient for quick tasks", "gpt-4o-mini"),
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
            ("GPT-3.5-turbo - Cost-effective option", "gpt-3.5-turbo"),
            ("Claude-3-haiku - Fast Anthropic model", "claude-3-haiku-20240307"),
            ("Llama-3.1-8B - Open source model", "meta-llama/llama-3.1-8b-instruct"),
            ("Qwen2.5-7B - Chinese optimized model", "qwen/qwen-2.5-7b-instruct"),
            ("自定义模型 - 手动输入模型名称", "custom"),
        ]
    }

    # 获取选项列表
    options = SHALLOW_AGENT_OPTIONS[provider.lower()]

    # 为国产LLM设置默认选择
    default_choice = None
    if "阿里百炼" in provider:
        default_choice = options[0][1]  # 通义千问 Turbo
    elif "deepseek" in provider.lower():
        default_choice = options[0][1]  # DeepSeek Chat (推荐选择)

    choice = questionary.select(
        "选择您的快速思考LLM引擎 | Select Your [Quick-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in options
        ],
        default=default_choice,
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print(
            "\n[red]未选择快速思考LLM引擎，退出程序... | No shallow thinking llm engine selected. Exiting...[/red]"
        )
        exit(1)

    return choice


def select_deep_thinking_agent(provider) -> str:
    """Select deep thinking llm engine using an interactive selection."""

    # Define deep thinking llm engine options with their corresponding model names
    DEEP_AGENT_OPTIONS = {
        "openai": [
            ("GPT-4.1-nano - Ultra-lightweight model for basic operations", "gpt-4.1-nano"),
            ("GPT-4.1-mini - Compact model with good performance", "gpt-4.1-mini"),
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
            ("o4-mini - Specialized reasoning model (compact)", "o4-mini"),
            ("o3-mini - Advanced reasoning model (lightweight)", "o3-mini"),
            ("o3 - Full advanced reasoning model", "o3"),
            ("o1 - Premier reasoning and problem-solving model", "o1"),
        ],
        "anthropic": [
            ("Claude Haiku 3.5 - Fast inference and standard capabilities", "claude-3-5-haiku-latest"),
            ("Claude Sonnet 3.5 - Highly capable standard model", "claude-3-5-sonnet-latest"),
            ("Claude Sonnet 3.7 - Exceptional hybrid reasoning and agentic capabilities", "claude-3-7-sonnet-latest"),
            ("Claude Sonnet 4 - High performance and excellent reasoning", "claude-sonnet-4-0"),
            ("Claude Opus 4 - Most powerful Anthropic model", "	claude-opus-4-0"),
        ],
        "google": [
            ("Gemini 2.5 Pro - 🚀 最新旗舰模型", "gemini-2.5-pro"),
            ("Gemini 2.5 Flash - ⚡ 最新快速模型", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite - 💡 轻量快速", "gemini-2.5-flash-lite"),
            ("Gemini 2.5 Pro-002 - 🔧 优化版本", "gemini-2.5-pro-002"),
            ("Gemini 2.5 Flash-002 - ⚡ 优化快速版", "gemini-2.5-flash-002"),
            ("Gemini 2.5 Flash - Adaptive thinking, cost efficiency", "gemini-2.5-flash-preview-05-20"),
            ("Gemini 2.5 Pro Preview - 预览版本", "gemini-2.5-pro-preview-06-05"),
            ("Gemini 2.0 Flash Lite - 轻量版本", "gemini-2.0-flash-lite"),
            ("Gemini 2.0 Flash - 推荐使用", "gemini-2.0-flash"),
            ("Gemini 1.5 Pro - 强大性能", "gemini-1.5-pro"),
            ("Gemini 1.5 Flash - 快速响应", "gemini-1.5-flash"),
        ],
        "openrouter": [
            ("DeepSeek V3 - a 685B-parameter, mixture-of-experts model", "deepseek/deepseek-chat-v3-0324:free"),
            ("Deepseek - latest iteration of the flagship chat model family from the DeepSeek team.", "deepseek/deepseek-chat-v3-0324:free"),
        ],
        "ollama": [
            ("llama3.1 local", "llama3.1"),
            ("qwen3", "qwen3"),
        ],
        "阿里百炼 (dashscope)": [
            ("通义千问 Turbo - 快速响应，适合日常对话", "qwen-turbo"),
            ("通义千问 Plus - 平衡性能和成本", "qwen-plus"),
            ("通义千问 Max - 最强性能", "qwen-max"),
            ("通义千问 Max 长文本版 - 支持超长上下文", "qwen-max-longcontext"),
        ],
        "deepseek v3": [
            ("DeepSeek Chat - 通用对话模型，适合股票投资分析", "deepseek-chat"),
        ],
        "🔧 自定义openai端点": [
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
            ("GPT-4o-mini - Fast and efficient for quick tasks", "gpt-4o-mini"),
            ("o1-preview - Advanced reasoning model", "o1-preview"),
            ("o1-mini - Compact reasoning model", "o1-mini"),
            ("Claude-3-sonnet - Balanced Anthropic model", "claude-3-sonnet-20240229"),
            ("Claude-3-opus - Most capable Anthropic model", "claude-3-opus-20240229"),
            ("Llama-3.1-70B - Large open source model", "meta-llama/llama-3.1-70b-instruct"),
            ("Qwen2.5-72B - Chinese optimized model", "qwen/qwen-2.5-72b-instruct"),
            ("自定义模型 - 手动输入模型名称", "custom"),
        ]
    }
    
    # 获取选项列表
    options = DEEP_AGENT_OPTIONS[provider.lower()]

    # 为国产LLM设置默认选择
    default_choice = None
    if "阿里百炼" in provider:
        default_choice = options[0][1]  # 通义千问 Turbo
    elif "deepseek" in provider.lower():
        default_choice = options[0][1]  # DeepSeek Chat

    choice = questionary.select(
        "选择您的深度思考LLM引擎 | Select Your [Deep-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in options
        ],
        default=default_choice,
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info(f"\n[red]未选择深度思考LLM引擎，退出程序... | No deep thinking llm engine selected. Exiting...[/red]")
        exit(1)

    return choice

def select_llm_provider() -> tuple[str, str]:
    """Select the LLM provider using interactive selection."""
    # Define LLM provider options with their corresponding endpoints
    # 国产LLM作为默认推荐选项放在前面
    BASE_URLS = [
        ("阿里百炼 (DashScope)", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("DeepSeek V3", "https://api.deepseek.com"),
        ("OpenAI", "https://api.openai.com/v1"),
        ("🔧 自定义OpenAI端点", "custom"),
        ("Anthropic", "https://api.anthropic.com/"),
        ("Google", "https://generativelanguage.googleapis.com/v1"),
        ("Openrouter", "https://openrouter.ai/api/v1"),
        ("Ollama", "http://localhost:11434/v1"),
    ]
    
    choice = questionary.select(
        "选择您的LLM提供商 | Select your LLM Provider:",
        choices=[
            questionary.Choice(display, value=(display, value))
            for display, value in BASE_URLS
        ],
        default=(BASE_URLS[0][0], BASE_URLS[0][1]),  # 默认选择阿里百炼的完整值
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select\n- 🇨🇳 推荐使用阿里百炼 (默认选择)",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()
    
    if choice is None:
        logger.info(f"\n[red]未选择LLM提供商，退出程序... | No LLM provider selected. Exiting...[/red]")
        exit(1)
    
    display_name, url = choice
    
    # 如果选择了自定义OpenAI端点，询问用户输入URL
    if url == "custom":
        custom_url = questionary.text(
            "请输入自定义OpenAI端点URL | Please enter custom OpenAI endpoint URL:",
            default="https://api.openai.com/v1",
            instruction="例如: https://api.openai.com/v1 或 http://localhost:8000/v1"
        ).ask()
        
        if custom_url is None:
            logger.info(f"\n[red]未输入自定义URL，退出程序... | No custom URL entered. Exiting...[/red]")
            exit(1)
            
        url = custom_url
        logger.info(f"您选择了 | You selected: {display_name}\tURL: {url}")
        
        # 设置环境变量以便后续使用
        os.environ['CUSTOM_OPENAI_BASE_URL'] = url
    else:
        logger.info(f"您选择了 | You selected: {display_name}\tURL: {url}")

    return display_name, url
