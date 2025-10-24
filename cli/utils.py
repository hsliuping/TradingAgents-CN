import questionary
from typing import List, Optional, Tuple, Dict
from rich.console import Console

from cli.models import AnalystType
from tradingagents.utils.logging_manager import get_logger
from tradingagents.utils.stock_utils import StockUtils

logger = get_logger('cli')
console = Console()

ANALYST_ORDER = [
    ("Market Analyst", AnalystType.MARKET),
    ("Social Media Analyst", AnalystType.SOCIAL),
    ("News Analyst", AnalystType.NEWS),
    ("Fundamentals Analyst", AnalystType.FUNDAMENTALS),
]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        "Enter the ticker symbol to analyze:",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        logger.info("\n[red]No ticker symbol provided. Exiting...[/red]")
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
        "Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "Please enter a valid date in YYYY-MM-DD format.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        logger.info("\n[red]No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts(ticker: str = None) -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""

    # Filter analyst options based on the stock type
    available_analysts = ANALYST_ORDER.copy()

    if ticker:
        # Detect if the ticker belongs to the China A-share market
        if StockUtils.is_china_stock(ticker):
            # The A-share market does not support the social media analyst
            available_analysts = [
                (display, value) for display, value in ANALYST_ORDER
                if value != AnalystType.SOCIAL
            ]
            console.print(
                f"[yellow]💡 Detected China A-share ticker {ticker}. The social media analyst is unavailable due to local data source limitations.[/yellow]"
            )

    choices = questionary.checkbox(
        "Select your analysts team:",
        choices=[
            questionary.Choice(display, value=value) for display, value in available_analysts
        ],
        instruction="\n- Press Space to select or unselect analysts\n- Press 'a' to select or unselect all\n- Press Enter when done",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
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
        logger.info("\n[red]No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    # Define research depth options with their corresponding values
    DEPTH_OPTIONS = [
        ("Shallow - Quick research with limited debate", 1),
        ("Medium - Balanced debate and strategy discussion", 3),
        ("Deep - Comprehensive research with in-depth debate", 5),
    ]

    choice = questionary.select(
        "Select your research depth:",
        choices=[
            questionary.Choice(display, value=value) for display, value in DEPTH_OPTIONS
        ],
        instruction="\n- Use the arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info("\n[red]No research depth selected. Exiting...[/red]")
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
            ("Gemini 2.5 Pro - 🚀 Latest flagship model", "gemini-2.5-pro"),
            ("Gemini 2.5 Flash - ⚡ Fastest current model", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite - 💡 Lightweight and fast", "gemini-2.5-flash-lite"),
            ("Gemini 2.5 Pro-002 - 🔧 Optimized release", "gemini-2.5-pro-002"),
            ("Gemini 2.5 Flash-002 - ⚡ Optimized fast edition", "gemini-2.5-flash-002"),
            ("Gemini 2.5 Flash - Adaptive thinking with cost efficiency", "gemini-2.5-flash-preview-05-20"),
            ("Gemini 2.5 Pro Preview - Preview release", "gemini-2.5-pro-preview-06-05"),
            ("Gemini 2.0 Flash Lite - Lightweight version", "gemini-2.0-flash-lite"),
            ("Gemini 2.0 Flash - Recommended default", "gemini-2.0-flash"),
            ("Gemini 1.5 Pro - High-performance model", "gemini-1.5-pro"),
            ("Gemini 1.5 Flash - Quick response model", "gemini-1.5-flash"),
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
        "dashscope (alibaba cloud)": [
            ("Qwen Turbo - Fast responses for daily conversations", "qwen-turbo"),
            ("Qwen Plus - Balanced performance and cost", "qwen-plus"),
            ("Qwen Max - Highest performance", "qwen-max"),
        ],
        "deepseek v3": [
            ("DeepSeek Chat - General-purpose model for investment analysis", "deepseek-chat"),
        ],
        "custom openai endpoint": [
            ("GPT-4o-mini - Fast and efficient for quick tasks", "gpt-4o-mini"),
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
            ("GPT-3.5-turbo - Cost-effective option", "gpt-3.5-turbo"),
            ("Claude-3-haiku - Fast Anthropic model", "claude-3-haiku-20240307"),
            ("Llama-3.1-8B - Open source model", "meta-llama/llama-3.1-8b-instruct"),
            ("Qwen2.5-7B - Chinese optimized model", "qwen/qwen-2.5-7b-instruct"),
            ("Custom model - Enter a model name manually", "custom"),
        ]
    }

    # Retrieve the available options for the selected provider
    options = SHALLOW_AGENT_OPTIONS[provider.lower()]

    # Prefer domestic LLMs by default when applicable
    default_choice = None
    if "dashscope" in provider.lower():
        default_choice = options[0][1]  # Qwen Turbo
    elif "deepseek" in provider.lower():
        default_choice = options[0][1]  # DeepSeek Chat (recommended)

    choice = questionary.select(
        "Select your quick-thinking LLM engine:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in options
        ],
        default=default_choice,
        instruction="\n- Use the arrow keys to navigate\n- Press Enter to select",
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
            "\n[red]No quick-thinking LLM engine selected. Exiting...[/red]"
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
            ("Gemini 2.5 Pro - 🚀 Latest flagship model", "gemini-2.5-pro"),
            ("Gemini 2.5 Flash - ⚡ Fastest current model", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite - 💡 Lightweight and fast", "gemini-2.5-flash-lite"),
            ("Gemini 2.5 Pro-002 - 🔧 Optimized release", "gemini-2.5-pro-002"),
            ("Gemini 2.5 Flash-002 - ⚡ Optimized fast edition", "gemini-2.5-flash-002"),
            ("Gemini 2.5 Flash - Adaptive thinking with cost efficiency", "gemini-2.5-flash-preview-05-20"),
            ("Gemini 2.5 Pro Preview - Preview release", "gemini-2.5-pro-preview-06-05"),
            ("Gemini 2.0 Flash Lite - Lightweight version", "gemini-2.0-flash-lite"),
            ("Gemini 2.0 Flash - Recommended default", "gemini-2.0-flash"),
            ("Gemini 1.5 Pro - High-performance model", "gemini-1.5-pro"),
            ("Gemini 1.5 Flash - Quick response model", "gemini-1.5-flash"),
        ],
        "openrouter": [
            ("DeepSeek V3 - a 685B-parameter, mixture-of-experts model", "deepseek/deepseek-chat-v3-0324:free"),
            ("Deepseek - latest iteration of the flagship chat model family from the DeepSeek team.", "deepseek/deepseek-chat-v3-0324:free"),
        ],
        "ollama": [
            ("llama3.1 local", "llama3.1"),
            ("qwen3", "qwen3"),
        ],
        "dashscope (alibaba cloud)": [
            ("Qwen Turbo - Fast responses for daily conversations", "qwen-turbo"),
            ("Qwen Plus - Balanced performance and cost", "qwen-plus"),
            ("Qwen Max - Highest performance", "qwen-max"),
            ("Qwen Max Longcontext - Supports extended context", "qwen-max-longcontext"),
        ],
        "deepseek v3": [
            ("DeepSeek Chat - General-purpose model for investment analysis", "deepseek-chat"),
        ],
        "custom openai endpoint": [
            ("GPT-4o - Standard model with solid capabilities", "gpt-4o"),
            ("GPT-4o-mini - Fast and efficient for quick tasks", "gpt-4o-mini"),
            ("o1-preview - Advanced reasoning model", "o1-preview"),
            ("o1-mini - Compact reasoning model", "o1-mini"),
            ("Claude-3-sonnet - Balanced Anthropic model", "claude-3-sonnet-20240229"),
            ("Claude-3-opus - Most capable Anthropic model", "claude-3-opus-20240229"),
            ("Llama-3.1-70B - Large open source model", "meta-llama/llama-3.1-70b-instruct"),
            ("Qwen2.5-72B - Chinese optimized model", "qwen/qwen-2.5-72b-instruct"),
            ("Custom model - Enter a model name manually", "custom"),
        ]
    }
    
    # Retrieve the available options for the selected provider
    options = DEEP_AGENT_OPTIONS[provider.lower()]

    # Prefer domestic LLMs by default when applicable
    default_choice = None
    if "dashscope" in provider.lower():
        default_choice = options[0][1]  # Qwen Turbo
    elif "deepseek" in provider.lower():
        default_choice = options[0][1]  # DeepSeek Chat

    choice = questionary.select(
        "Select your deep-thinking LLM engine:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in options
        ],
        default=default_choice,
        instruction="\n- Use the arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info("\n[red]No deep-thinking LLM engine selected. Exiting...[/red]")
        exit(1)

    return choice

def select_llm_provider() -> tuple[str, str]:
    """Select the LLM provider using interactive selection."""
    # Define LLM provider options with their corresponding endpoints
    BASE_URLS = [
        ("DashScope (Alibaba Cloud)", "https://dashscope.aliyuncs.com/api/v1"),
        ("DeepSeek V3", "https://api.deepseek.com"),
        ("OpenAI", "https://api.openai.com/v1"),
        ("Custom OpenAI Endpoint", "custom"),
        ("Anthropic", "https://api.anthropic.com/"),
        ("Google", "https://generativelanguage.googleapis.com/v1"),
        ("OpenRouter", "https://openrouter.ai/api/v1"),
        ("Ollama", "http://localhost:11434/v1"),
    ]

    choice = questionary.select(
        "Select your LLM provider:",
        choices=[
            questionary.Choice(display, value=(display, value))
            for display, value in BASE_URLS
        ],
        default=(BASE_URLS[0][0], BASE_URLS[0][1]),
        instruction="\n- Use the arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()
    
    if choice is None:
        logger.info("\n[red]No LLM provider selected. Exiting...[/red]")
        exit(1)
    
    display_name, url = choice
    
    # If a custom OpenAI endpoint is selected, prompt the user for the URL
    if url == "custom":
        custom_url = questionary.text(
            "Enter the custom OpenAI endpoint URL:",
            default="https://api.openai.com/v1",
            instruction="Example: https://api.openai.com/v1 or http://localhost:8000/v1"
        ).ask()

        if custom_url is None:
            logger.info("\n[red]No custom URL entered. Exiting...[/red]")
            exit(1)

        url = custom_url
        logger.info(f"You selected: {display_name}\tURL: {url}")

        # Store the value in the environment for downstream usage
        os.environ['CUSTOM_OPENAI_BASE_URL'] = url
    else:
        logger.info(f"You selected: {display_name}\tURL: {url}")

    return display_name, url
