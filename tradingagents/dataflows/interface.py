from typing import Annotated, Dict
import time
import os
from .reddit_utils import fetch_top_from_category
from .chinese_finance_utils import get_chinese_social_sentiment
from .googlenews_utils import *
from .finnhub_utils import get_data_in_range

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_dataflow_logging

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')
logger = setup_dataflow_logging()

# 导入港股工具
try:
    from .hk_stock_utils import get_hk_stock_data, get_hk_stock_info
    HK_STOCK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ 港股工具不可用: {e}")
    HK_STOCK_AVAILABLE = False

# 导入AKShare港股工具
try:
    from .akshare_utils import get_hk_stock_data_akshare, get_hk_stock_info_akshare
    AKSHARE_HK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ AKShare港股工具不可用: {e}")
    AKSHARE_HK_AVAILABLE = False

# 尝试导入yfinance相关模块，如果失败则跳过
try:
    from .yfin_utils import *
    YFIN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ yfinance工具不可用: {e}")
    YFIN_AVAILABLE = False

try:
    from .stockstats_utils import *
    STOCKSTATS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ stockstats工具不可用: {e}")
    STOCKSTATS_AVAILABLE = False
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import pandas as pd
from tqdm import tqdm
from openai import OpenAI

# 尝试导入yfinance，如果失败则设置为None
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ yfinance库不可用: {e}")
    yf = None
    YF_AVAILABLE = False
from .config import get_config, set_config, DATA_DIR


def get_finnhub_news(
    ticker: Annotated[
        str,
        "Search query of a company's, e.g. 'AAPL, TSM, etc.",
    ],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
):
    """
    Retrieve news about a company within a time frame

    Args
        ticker (str): ticker for the company you are interested in
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns
        str: dataframe containing the news of the company in the time frame

    """

    start_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    result = get_data_in_range(ticker, before, curr_date, "news_data", DATA_DIR)

    if len(result) == 0:
        error_msg = f"⚠️ 无法获取{ticker}的新闻数据 ({before} 到 {curr_date})\n"
        error_msg += f"可能的原因：\n"
        error_msg += f"1. 数据文件不存在或路径配置错误\n"
        error_msg += f"2. 指定日期范围内没有新闻数据\n"
        error_msg += f"3. 需要先下载或更新Finnhub新闻数据\n"
        error_msg += f"建议：检查数据目录配置或重新获取新闻数据"
        logger.debug(f"📰 [DEBUG] {error_msg}")
        return error_msg

    combined_result = ""
    for day, data in result.items():
        if len(data) == 0:
            continue
        for entry in data:
            current_news = (
                "### " + entry["headline"] + f" ({day})" + "\n" + entry["summary"]
            )
            combined_result += current_news + "\n\n"

    return f"## {ticker} News, from {before} to {curr_date}:\n" + str(combined_result)


def get_finnhub_company_insider_sentiment(
    ticker: Annotated[str, "ticker symbol for the company"],
    curr_date: Annotated[
        str,
        "current date of you are trading at, yyyy-mm-dd",
    ],
    look_back_days: Annotated[int, "number of days to look back"],
):
    """
    Retrieve insider sentiment about a company (retrieved from public SEC information) for the past 15 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading on, yyyy-mm-dd
    Returns:
        str: a report of the sentiment in the past 15 days starting at curr_date
    """

    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    data = get_data_in_range(ticker, before, curr_date, "insider_senti", DATA_DIR)

    if len(data) == 0:
        return ""

    result_str = ""
    seen_dicts = []
    for date, senti_list in data.items():
        for entry in senti_list:
            if entry not in seen_dicts:
                result_str += f"### {entry['year']}-{entry['month']}:\nChange: {entry['change']}\nMonthly Share Purchase Ratio: {entry['mspr']}\n\n"
                seen_dicts.append(entry)

    return (
        f"## {ticker} Insider Sentiment Data for {before} to {curr_date}:\n"
        + result_str
        + "The change field refers to the net buying/selling from all insiders' transactions. The mspr field refers to monthly share purchase ratio."
    )


def get_finnhub_company_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[
        str,
        "current date you are trading at, yyyy-mm-dd",
    ],
    look_back_days: Annotated[int, "how many days to look back"],
):
    """
    Retrieve insider transcaction information about a company (retrieved from public SEC information) for the past 15 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's insider transaction/trading informtaion in the past 15 days
    """

    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    data = get_data_in_range(ticker, before, curr_date, "insider_trans", DATA_DIR)

    if len(data) == 0:
        return ""

    result_str = ""

    seen_dicts = []
    for date, senti_list in data.items():
        for entry in senti_list:
            if entry not in seen_dicts:
                result_str += f"### Filing Date: {entry['filingDate']}, {entry['name']}:\nChange:{entry['change']}\nShares: {entry['share']}\nTransaction Price: {entry['transactionPrice']}\nTransaction Code: {entry['transactionCode']}\n\n"
                seen_dicts.append(entry)

    return (
        f"## {ticker} insider transactions from {before} to {curr_date}:\n"
        + result_str
        + "The change field reflects the variation in share count—here a negative number indicates a reduction in holdings—while share specifies the total number of shares involved. The transactionPrice denotes the per-share price at which the trade was executed, and transactionDate marks when the transaction occurred. The name field identifies the insider making the trade, and transactionCode (e.g., S for sale) clarifies the nature of the transaction. FilingDate records when the transaction was officially reported, and the unique id links to the specific SEC filing, as indicated by the source. Additionally, the symbol ties the transaction to a particular company, isDerivative flags whether the trade involves derivative securities, and currency notes the currency context of the transaction."
    )


def get_simfin_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    data_path = os.path.join(
        DATA_DIR,
        "fundamental_data",
        "simfin_data_all",
        "balance_sheet",
        "companies",
        "us",
        f"us-balance-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")

    # Convert date strings to datetime objects and remove any time components
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()

    # Convert the current date to datetime and normalize
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()

    # Filter the DataFrame for the given ticker and for reports that were published on or before the current date
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]

    # Check if there are any available reports; if not, return a notification
    if filtered_df.empty:
        logger.info(f"No balance sheet available before the given current date.")
        return ""

    # Get the most recent balance sheet by selecting the row with the latest Publish Date
    latest_balance_sheet = filtered_df.loc[filtered_df["Publish Date"].idxmax()]

    # drop the SimFinID column
    latest_balance_sheet = latest_balance_sheet.drop("SimFinId")

    return (
        f"## {freq} balance sheet for {ticker} released on {str(latest_balance_sheet['Publish Date'])[0:10]}: \n"
        + str(latest_balance_sheet)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a breakdown of assets, liabilities, and equity. Assets are grouped as current (liquid items like cash and receivables) and noncurrent (long-term investments and property). Liabilities are split between short-term obligations and long-term debts, while equity reflects shareholder funds such as paid-in capital and retained earnings. Together, these components ensure that total assets equal the sum of liabilities and equity."
    )


def get_simfin_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    data_path = os.path.join(
        DATA_DIR,
        "fundamental_data",
        "simfin_data_all",
        "cash_flow",
        "companies",
        "us",
        f"us-cashflow-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")

    # Convert date strings to datetime objects and remove any time components
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()

    # Convert the current date to datetime and normalize
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()

    # Filter the DataFrame for the given ticker and for reports that were published on or before the current date
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]

    # Check if there are any available reports; if not, return a notification
    if filtered_df.empty:
        logger.info(f"No cash flow statement available before the given current date.")
        return ""

    # Get the most recent cash flow statement by selecting the row with the latest Publish Date
    latest_cash_flow = filtered_df.loc[filtered_df["Publish Date"].idxmax()]

    # drop the SimFinID column
    latest_cash_flow = latest_cash_flow.drop("SimFinId")

    return (
        f"## {freq} cash flow statement for {ticker} released on {str(latest_cash_flow['Publish Date'])[0:10]}: \n"
        + str(latest_cash_flow)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a breakdown of cash movements. Operating activities show cash generated from core business operations, including net income adjustments for non-cash items and working capital changes. Investing activities cover asset acquisitions/disposals and investments. Financing activities include debt transactions, equity issuances/repurchases, and dividend payments. The net change in cash represents the overall increase or decrease in the company's cash position during the reporting period."
    )


def get_simfin_income_statements(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    data_path = os.path.join(
        DATA_DIR,
        "fundamental_data",
        "simfin_data_all",
        "income_statements",
        "companies",
        "us",
        f"us-income-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")

    # Convert date strings to datetime objects and remove any time components
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()

    # Convert the current date to datetime and normalize
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()

    # Filter the DataFrame for the given ticker and for reports that were published on or before the current date
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]

    # Check if there are any available reports; if not, return a notification
    if filtered_df.empty:
        logger.info(f"No income statement available before the given current date.")
        return ""

    # Get the most recent income statement by selecting the row with the latest Publish Date
    latest_income = filtered_df.loc[filtered_df["Publish Date"].idxmax()]

    # drop the SimFinID column
    latest_income = latest_income.drop("SimFinId")

    return (
        f"## {freq} income statement for {ticker} released on {str(latest_income['Publish Date'])[0:10]}: \n"
        + str(latest_income)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a comprehensive breakdown of the company's financial performance. Starting with Revenue, it shows Cost of Revenue and resulting Gross Profit. Operating Expenses are detailed, including SG&A, R&D, and Depreciation. The statement then shows Operating Income, followed by non-operating items and Interest Expense, leading to Pretax Income. After accounting for Income Tax and any Extraordinary items, it concludes with Net Income, representing the company's bottom-line profit or loss for the period."
    )


def get_google_news(
    query: Annotated[str, "Query to search with"],
    curr_date: Annotated[str, "Curr date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"] = 7,
) -> str:
    # 判断是否为A股查询
    is_china_stock = False
    if any(code in query for code in ['SH', 'SZ', 'XSHE', 'XSHG']) or query.isdigit() or (len(query) == 6 and query[:6].isdigit()):
        is_china_stock = True
    
    # 尝试使用StockUtils判断
    try:
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(query.split()[0])
        if market_info['is_china']:
            is_china_stock = True
    except Exception:
        # 如果StockUtils判断失败，使用上面的简单判断
        pass
    
    # 对A股查询添加中文关键词
    if is_china_stock:
        logger.info(f"[Google新闻] 检测到A股查询: {query}，使用中文搜索")
        if '股票' not in query and '股价' not in query and '公司' not in query:
            query = f"{query} 股票 公司 财报 新闻"
    
    query = query.replace(" ", "+")

    start_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    logger.info(f"[Google新闻] 开始获取新闻，查询: {query}, 时间范围: {before} 至 {curr_date}")
    news_results = getNewsData(query, before, curr_date)

    news_str = ""

    for news in news_results:
        news_str += (
            f"### {news['title']} (source: {news['source']}) \n\n{news['snippet']}\n\n"
        )

    if len(news_results) == 0:
        logger.warning(f"[Google新闻] 未找到相关新闻，查询: {query}")
        return ""

    logger.info(f"[Google新闻] 成功获取 {len(news_results)} 条新闻，查询: {query}")
    return f"## {query.replace('+', ' ')} Google News, from {before} to {curr_date}:\n\n{news_str}"


def get_reddit_global_news(
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
    max_limit_per_day: Annotated[int, "Maximum number of news per day"],
) -> str:
    """
    Retrieve the latest top reddit news
    Args:
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the latest news articles posts on reddit and meta information in these columns: "created_utc", "id", "title", "selftext", "score", "num_comments", "url"
    """

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    posts = []
    # iterate from start_date to end_date
    curr_date = datetime.strptime(before, "%Y-%m-%d")

    total_iterations = (start_date - curr_date).days + 1
    pbar = tqdm(desc=f"Getting Global News on {start_date}", total=total_iterations)

    while curr_date <= start_date:
        curr_date_str = curr_date.strftime("%Y-%m-%d")
        fetch_result = fetch_top_from_category(
            "global_news",
            curr_date_str,
            max_limit_per_day,
            data_path=os.path.join(DATA_DIR, "reddit_data"),
        )
        posts.extend(fetch_result)
        curr_date += relativedelta(days=1)
        pbar.update(1)

    pbar.close()

    if len(posts) == 0:
        return ""

    news_str = ""
    for post in posts:
        if post["content"] == "":
            news_str += f"### {post['title']}\n\n"
        else:
            news_str += f"### {post['title']}\n\n{post['content']}\n\n"

    return f"## Global News Reddit, from {before} to {curr_date}:\n{news_str}"


def get_reddit_company_news(
    ticker: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
    max_limit_per_day: Annotated[int, "Maximum number of news per day"],
) -> str:
    """
    Retrieve the latest top reddit news
    Args:
        ticker: ticker symbol of the company
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the latest news articles posts on reddit and meta information in these columns: "created_utc", "id", "title", "selftext", "score", "num_comments", "url"
    """

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    posts = []
    # iterate from start_date to end_date
    curr_date = datetime.strptime(before, "%Y-%m-%d")

    total_iterations = (start_date - curr_date).days + 1
    pbar = tqdm(
        desc=f"Getting Company News for {ticker} on {start_date}",
        total=total_iterations,
    )

    while curr_date <= start_date:
        curr_date_str = curr_date.strftime("%Y-%m-%d")
        fetch_result = fetch_top_from_category(
            "company_news",
            curr_date_str,
            max_limit_per_day,
            ticker,
            data_path=os.path.join(DATA_DIR, "reddit_data"),
        )
        posts.extend(fetch_result)
        curr_date += relativedelta(days=1)

        pbar.update(1)

    pbar.close()

    if len(posts) == 0:
        return ""

    news_str = ""
    for post in posts:
        if post["content"] == "":
            news_str += f"### {post['title']}\n\n"
        else:
            news_str += f"### {post['title']}\n\n{post['content']}\n\n"

    return f"##{ticker} News Reddit, from {before} to {curr_date}:\n\n{news_str}"


def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
    online: Annotated[bool, "to fetch data online or offline"],
) -> str:

    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    end_date = curr_date
    curr_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date - relativedelta(days=look_back_days)

    if not online:
        # read from YFin data
        data = pd.read_csv(
            os.path.join(
                DATA_DIR,
                f"market_data/price_data/{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
            )
        )
        data["Date"] = pd.to_datetime(data["Date"], utc=True)
        dates_in_df = data["Date"].astype(str).str[:10]

        ind_string = ""
        while curr_date >= before:
            # only do the trading dates
            if curr_date.strftime("%Y-%m-%d") in dates_in_df.values:
                indicator_value = get_stockstats_indicator(
                    symbol, indicator, curr_date.strftime("%Y-%m-%d"), online
                )

                ind_string += f"{curr_date.strftime('%Y-%m-%d')}: {indicator_value}\n"

            curr_date = curr_date - relativedelta(days=1)
    else:
        # online gathering
        ind_string = ""
        while curr_date >= before:
            indicator_value = get_stockstats_indicator(
                symbol, indicator, curr_date.strftime("%Y-%m-%d"), online
            )

            ind_string += f"{curr_date.strftime('%Y-%m-%d')}: {indicator_value}\n"

            curr_date = curr_date - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    online: Annotated[bool, "to fetch data online or offline"],
) -> str:

    curr_date = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date.strftime("%Y-%m-%d")

    try:
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
            os.path.join(DATA_DIR, "market_data", "price_data"),
            online=online,
        )
    except Exception as e:
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
        )
        return ""

    return str(indicator_value)


def get_YFin_data_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    # calculate past days
    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    start_date = before.strftime("%Y-%m-%d")

    # read in data
    data = pd.read_csv(
        os.path.join(
            DATA_DIR,
            f"market_data/price_data/{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
        )
    )

    # Extract just the date part for comparison
    data["DateOnly"] = data["Date"].str[:10]

    # Filter data between the start and end dates (inclusive)
    filtered_data = data[
        (data["DateOnly"] >= start_date) & (data["DateOnly"] <= curr_date)
    ]

    # Drop the temporary column we created
    filtered_data = filtered_data.drop("DateOnly", axis=1)

    # Set pandas display options to show the full DataFrame
    with pd.option_context(
        "display.max_rows", None, "display.max_columns", None, "display.width", None
    ):
        df_string = filtered_data.to_string()

    return (
        f"## Raw Market Data for {symbol} from {start_date} to {curr_date}:\n\n"
        + df_string
    )


def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    # 检查yfinance是否可用
    if not YF_AVAILABLE or yf is None:
        return "yfinance库不可用，无法获取美股数据"

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Create ticker object
    ticker = yf.Ticker(symbol.upper())

    # Fetch historical data for the specified date range
    data = ticker.history(start=start_date, end=end_date)

    # Check if data is empty
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


def get_YFin_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    # read in data
    data = pd.read_csv(
        os.path.join(
            DATA_DIR,
            f"market_data/price_data/{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
        )
    )

    if end_date > "2025-03-25":
        raise Exception(
            f"Get_YFin_Data: {end_date} is outside of the data range of 2015-01-01 to 2025-03-25"
        )

    # Extract just the date part for comparison
    data["DateOnly"] = data["Date"].str[:10]

    # Filter data between the start and end dates (inclusive)
    filtered_data = data[
        (data["DateOnly"] >= start_date) & (data["DateOnly"] <= end_date)
    ]

    # Drop the temporary column we created
    filtered_data = filtered_data.drop("DateOnly", axis=1)

    # remove the index from the dataframe
    filtered_data = filtered_data.reset_index(drop=True)

    return filtered_data


def get_stock_news_openai(ticker, curr_date):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search Social Media for {ticker} from 7 days before {curr_date} to {curr_date}? Make sure you only get the data posted during that period.",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return response.output[1].content[0].text


def get_global_news_openai(curr_date):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search global or macroeconomics news from 7 days before {curr_date} to {curr_date} that would be informative for trading purposes? Make sure you only get the data posted during that period.",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return response.output[1].content[0].text


def get_fundamentals_finnhub(ticker, curr_date):
    """
    使用Finnhub API获取股票基本面数据作为OpenAI的备选方案
    Args:
        ticker (str): 股票代码
        curr_date (str): 当前日期，格式为yyyy-mm-dd
    Returns:
        str: 格式化的基本面数据报告
    """
    try:
        import finnhub
        import os
        from .cache_manager import get_cache
        
        # 检查缓存
        cache = get_cache()
        cached_key = cache.find_cached_fundamentals_data(ticker, data_source="finnhub")
        if cached_key:
            cached_data = cache.load_fundamentals_data(cached_key)
            if cached_data:
                logger.debug(f"💾 [DEBUG] 从缓存加载Finnhub基本面数据: {ticker}")
                return cached_data
        
        # 获取Finnhub API密钥
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            return "错误：未配置FINNHUB_API_KEY环境变量"
        
        # 初始化Finnhub客户端
        finnhub_client = finnhub.Client(api_key=api_key)
        
        logger.debug(f"📊 [DEBUG] 使用Finnhub API获取 {ticker} 的基本面数据...")
        
        # 获取基本财务数据
        try:
            basic_financials = finnhub_client.company_basic_financials(ticker, 'all')
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub基本财务数据获取失败: {str(e)}")
            basic_financials = None
        
        # 获取公司概况
        try:
            company_profile = finnhub_client.company_profile2(symbol=ticker)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub公司概况获取失败: {str(e)}")
            company_profile = None
        
        # 获取收益数据
        try:
            earnings = finnhub_client.company_earnings(ticker, limit=4)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub收益数据获取失败: {str(e)}")
            earnings = None
        
        # 格式化报告
        report = f"# {ticker} 基本面分析报告（Finnhub数据源）\n\n"
        report += f"**数据获取时间**: {curr_date}\n"
        report += f"**数据来源**: Finnhub API\n\n"
        
        # 公司概况部分
        if company_profile:
            report += "## 公司概况\n"
            report += f"- **公司名称**: {company_profile.get('name', 'N/A')}\n"
            report += f"- **行业**: {company_profile.get('finnhubIndustry', 'N/A')}\n"
            report += f"- **国家**: {company_profile.get('country', 'N/A')}\n"
            report += f"- **货币**: {company_profile.get('currency', 'N/A')}\n"
            report += f"- **市值**: {company_profile.get('marketCapitalization', 'N/A')} 百万美元\n"
            report += f"- **流通股数**: {company_profile.get('shareOutstanding', 'N/A')} 百万股\n\n"
        
        # 基本财务指标
        if basic_financials and 'metric' in basic_financials:
            metrics = basic_financials['metric']
            report += "## 关键财务指标\n"
            report += "| 指标 | 数值 |\n"
            report += "|------|------|\n"
            
            # 估值指标
            if 'peBasicExclExtraTTM' in metrics and metrics['peBasicExclExtraTTM'] is not None:
                report += f"| 市盈率 (PE) | {metrics['peBasicExclExtraTTM']:.2f} |\n"
            if 'psAnnual' in metrics and metrics['psAnnual'] is not None:
                report += f"| 市销率 (PS) | {metrics['psAnnual']:.2f} |\n"
            if 'pbAnnual' in metrics and metrics['pbAnnual'] is not None:
                report += f"| 市净率 (PB) | {metrics['pbAnnual']:.2f} |\n"
            
            # 盈利能力指标
            if 'roeTTM' in metrics and metrics['roeTTM'] is not None:
                report += f"| 净资产收益率 (ROE) | {metrics['roeTTM']:.2f}% |\n"
            if 'roaTTM' in metrics and metrics['roaTTM'] is not None:
                report += f"| 总资产收益率 (ROA) | {metrics['roaTTM']:.2f}% |\n"
            if 'netProfitMarginTTM' in metrics and metrics['netProfitMarginTTM'] is not None:
                report += f"| 净利润率 | {metrics['netProfitMarginTTM']:.2f}% |\n"
            
            # 财务健康指标
            if 'currentRatioAnnual' in metrics and metrics['currentRatioAnnual'] is not None:
                report += f"| 流动比率 | {metrics['currentRatioAnnual']:.2f} |\n"
            if 'totalDebt/totalEquityAnnual' in metrics and metrics['totalDebt/totalEquityAnnual'] is not None:
                report += f"| 负债权益比 | {metrics['totalDebt/totalEquityAnnual']:.2f} |\n"
            
            report += "\n"
        
        # 收益历史
        if earnings:
            report += "## 收益历史\n"
            report += "| 季度 | 实际EPS | 预期EPS | 差异 |\n"
            report += "|------|---------|---------|------|\n"
            for earning in earnings[:4]:  # 显示最近4个季度
                actual = earning.get('actual', 'N/A')
                estimate = earning.get('estimate', 'N/A')
                period = earning.get('period', 'N/A')
                surprise = earning.get('surprise', 'N/A')
                report += f"| {period} | {actual} | {estimate} | {surprise} |\n"
            report += "\n"
        
        # 数据可用性说明
        report += "## 数据说明\n"
        report += "- 本报告使用Finnhub API提供的官方财务数据\n"
        report += "- 数据来源于公司财报和SEC文件\n"
        report += "- TTM表示过去12个月数据\n"
        report += "- Annual表示年度数据\n\n"
        
        if not basic_financials and not company_profile and not earnings:
            report += "⚠️ **警告**: 无法获取该股票的基本面数据，可能原因：\n"
            report += "- 股票代码不正确\n"
            report += "- Finnhub API限制\n"
            report += "- 该股票暂无基本面数据\n"
        
        # 保存到缓存
        if report and len(report) > 100:  # 只有当报告有实际内容时才缓存
            cache.save_fundamentals_data(ticker, report, data_source="finnhub")
        
        logger.debug(f"📊 [DEBUG] Finnhub基本面数据获取完成，报告长度: {len(report)}")
        return report
        
    except ImportError:
        return "错误：未安装finnhub-python库，请运行: pip install finnhub-python"
    except Exception as e:
        logger.error(f"❌ [DEBUG] Finnhub基本面数据获取失败: {str(e)}")
        return f"Finnhub基本面数据获取失败: {str(e)}"


def get_fundamentals_openai(ticker, curr_date):
    """
    获取股票基本面数据，优先使用OpenAI，失败时回退到Finnhub API
    支持缓存机制以提高性能
    Args:
        ticker (str): 股票代码
        curr_date (str): 当前日期，格式为yyyy-mm-dd
    Returns:
        str: 基本面数据报告
    """
    try:
        from .cache_manager import get_cache
        
        # 检查缓存 - 优先检查OpenAI缓存
        cache = get_cache()
        cached_key = cache.find_cached_fundamentals_data(ticker, data_source="openai")
        if cached_key:
            cached_data = cache.load_fundamentals_data(cached_key)
            if cached_data:
                logger.debug(f"💾 [DEBUG] 从缓存加载OpenAI基本面数据: {ticker}")
                return cached_data
        
        config = get_config()

        # 检查是否配置了OpenAI API Key（这是最关键的检查）
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.debug(f"📊 [DEBUG] 未配置OPENAI_API_KEY，跳过OpenAI API，直接使用Finnhub")
            return get_fundamentals_finnhub(ticker, curr_date)

        # 检查是否配置了OpenAI相关设置
        if not config.get("backend_url") or not config.get("quick_think_llm"):
            logger.debug(f"📊 [DEBUG] OpenAI配置不完整，直接使用Finnhub API")
            return get_fundamentals_finnhub(ticker, curr_date)

        # 检查backend_url是否是OpenAI的URL
        backend_url = config.get("backend_url", "")
        if "openai.com" not in backend_url:
            logger.debug(f"📊 [DEBUG] backend_url不是OpenAI API ({backend_url})，跳过OpenAI，使用Finnhub")
            return get_fundamentals_finnhub(ticker, curr_date)
        
        logger.debug(f"📊 [DEBUG] 尝试使用OpenAI获取 {ticker} 的基本面数据...")
        
        client = OpenAI(base_url=config["backend_url"])

        response = client.responses.create(
            model=config["quick_think_llm"],
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Can you search Fundamental for discussions on {ticker} during of the month before {curr_date} to the month of {curr_date}. Make sure you only get the data posted during that period. List as a table, with PE/PS/Cash flow/ etc",
                        }
                    ],
                }
            ],
            text={"format": {"type": "text"}},
            reasoning={},
            tools=[
                {
                    "type": "web_search_preview",
                    "user_location": {"type": "approximate"},
                    "search_context_size": "low",
                }
            ],
            temperature=1,
            max_output_tokens=4096,
            top_p=1,
            store=True,
        )

        result = response.output[1].content[0].text
        
        # 保存到缓存
        if result and len(result) > 100:  # 只有当结果有实际内容时才缓存
            cache.save_fundamentals_data(ticker, result, data_source="openai")
        
        logger.debug(f"📊 [DEBUG] OpenAI基本面数据获取成功，长度: {len(result)}")
        return result
        
    except Exception as e:
        logger.error(f"❌ [DEBUG] OpenAI基本面数据获取失败: {str(e)}")
        logger.debug(f"📊 [DEBUG] 回退到Finnhub API...")
        return get_fundamentals_finnhub(ticker, curr_date)


# ==================== Tushare数据接口 ====================

def get_china_stock_data_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD"]
) -> str:
    """
    使用Tushare获取中国A股历史数据
    重定向到data_source_manager，避免循环调用

    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据报告
    """
    try:
        from .data_source_manager import get_data_source_manager

        logger.debug(f"📊 [Tushare] 获取{ticker}股票数据...")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] get_china_stock_data_tushare 接收到的股票代码: '{ticker}' (类型: {type(ticker)})")
        logger.info(f"🔍 [股票代码追踪] 重定向到data_source_manager")

        manager = get_data_source_manager()
        return manager.get_china_stock_data_tushare(ticker, start_date, end_date)

    except Exception as e:
        logger.error(f"❌ [Tushare] 获取股票数据失败: {e}")
        return f"❌ 获取{ticker}股票数据失败: {e}"


def search_china_stocks_tushare(
    keyword: Annotated[str, "搜索关键词，可以是股票名称或代码"]
) -> str:
    """
    使用Tushare搜索中国A股股票
    重定向到data_source_manager，避免循环调用

    Args:
        keyword: 搜索关键词

    Returns:
        str: 搜索结果
    """
    try:
        from .data_source_manager import get_data_source_manager

        logger.debug(f"🔍 [Tushare] 搜索股票: {keyword}")
        logger.info(f"🔍 [股票代码追踪] 重定向到data_source_manager")

        manager = get_data_source_manager()
        return manager.search_china_stocks_tushare(keyword)

    except Exception as e:
        logger.error(f"❌ [Tushare] 搜索股票失败: {e}")
        return f"❌ 搜索股票失败: {e}"


def get_china_stock_fundamentals_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"]
) -> str:
    """
    使用Tushare获取中国A股基本面数据
    重定向到data_source_manager，避免循环调用

    Args:
        ticker: 股票代码

    Returns:
        str: 基本面分析报告
    """
    try:
        from .data_source_manager import get_data_source_manager

        logger.debug(f"📊 [Tushare] 获取{ticker}基本面数据...")
        logger.info(f"🔍 [股票代码追踪] 重定向到data_source_manager")

        manager = get_data_source_manager()
        return manager.get_china_stock_fundamentals_tushare(ticker)

    except Exception as e:
        logger.error(f"❌ [Tushare] 获取基本面数据失败: {e}")
        return f"❌ 获取{ticker}基本面数据失败: {e}"


def get_china_stock_info_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"]
) -> str:
    """
    使用Tushare获取中国A股基本信息
    重定向到data_source_manager，避免循环调用

    Args:
        ticker: 股票代码

    Returns:
        str: 股票基本信息
    """
    try:
        from .data_source_manager import get_data_source_manager

        logger.debug(f"📊 [Tushare] 获取{ticker}基本信息...")
        logger.info(f"🔍 [股票代码追踪] 重定向到data_source_manager")

        manager = get_data_source_manager()
        return manager.get_china_stock_info_tushare(ticker)

    except Exception as e:
        logger.error(f"❌ [Tushare] 获取股票信息失败: {e}", exc_info=True)
        return f"❌ 获取{ticker}股票信息失败: {e}"


# ==================== 统一数据源接口 ====================

def get_china_stock_data_unified(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的中国A股数据获取接口
    自动使用配置的数据源（默认Tushare），支持备用数据源

    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据报告
    """
    # 记录详细的输入参数
    logger.info(f"📊 [统一接口] 开始获取中国股票数据",
               extra={
                   'function': 'get_china_stock_data_unified',
                   'ticker': ticker,
                   'start_date': start_date,
                   'end_date': end_date,
                   'event_type': 'unified_data_call_start'
               })

    # 添加详细的股票代码追踪日志
    logger.info(f"🔍 [股票代码追踪] get_china_stock_data_unified 接收到的原始股票代码: '{ticker}' (类型: {type(ticker)})")
    logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(ticker))}")
    logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(ticker))}")

    start_time = time.time()

    try:
        from .data_source_manager import get_china_stock_data_unified

        result = get_china_stock_data_unified(ticker, start_date, end_date)

        # 记录详细的输出结果
        duration = time.time() - start_time
        result_length = len(result) if result else 0
        is_success = result and "❌" not in result and "错误" not in result

        if is_success:
            logger.info(f"✅ [统一接口] 中国股票数据获取成功",
                       extra={
                           'function': 'get_china_stock_data_unified',
                           'ticker': ticker,
                           'start_date': start_date,
                           'end_date': end_date,
                           'duration': duration,
                           'result_length': result_length,
                           'result_preview': result[:300] + '...' if result_length > 300 else result,
                           'event_type': 'unified_data_call_success'
                       })
        else:
            logger.warning(f"⚠️ [统一接口] 中国股票数据质量异常",
                          extra={
                              'function': 'get_china_stock_data_unified',
                              'ticker': ticker,
                              'start_date': start_date,
                              'end_date': end_date,
                              'duration': duration,
                              'result_length': result_length,
                              'result_preview': result[:300] + '...' if result_length > 300 else result,
                              'event_type': 'unified_data_call_warning'
                          })

        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ [统一接口] 获取股票数据失败: {e}",
                    extra={
                        'function': 'get_china_stock_data_unified',
                        'ticker': ticker,
                        'start_date': start_date,
                        'end_date': end_date,
                        'duration': duration,
                        'error': str(e),
                        'event_type': 'unified_data_call_error'
                    }, exc_info=True)
        return f"❌ 获取{ticker}股票数据失败: {e}"


def get_china_stock_info_unified(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"]
) -> str:
    """
    统一的中国A股基本信息获取接口
    自动使用配置的数据源（默认Tushare）

    Args:
        ticker: 股票代码

    Returns:
        str: 股票基本信息
    """
    try:
        from .data_source_manager import get_china_stock_info_unified

        logger.info(f"📊 [统一接口] 获取{ticker}基本信息...")

        info = get_china_stock_info_unified(ticker)

        if info and info.get('name'):
            result = f"股票代码: {ticker}\n"
            result += f"股票名称: {info.get('name', '未知')}\n"
            result += f"所属地区: {info.get('area', '未知')}\n"
            result += f"所属行业: {info.get('industry', '未知')}\n"
            result += f"上市市场: {info.get('market', '未知')}\n"
            result += f"上市日期: {info.get('list_date', '未知')}\n"
            result += f"数据来源: {info.get('source', 'unknown')}\n"

            return result
        else:
            return f"❌ 未能获取{ticker}的基本信息"

    except Exception as e:
        logger.error(f"❌ [统一接口] 获取股票信息失败: {e}")
        return f"❌ 获取{ticker}股票信息失败: {e}"


def switch_china_data_source(
    source: Annotated[str, "数据源名称：tushare, akshare, baostock"]
) -> str:
    """
    切换中国股票数据源

    Args:
        source: 数据源名称

    Returns:
        str: 切换结果
    """
    try:
        from .data_source_manager import get_data_source_manager, ChinaDataSource

        # 映射字符串到枚举（移除TDX支持）
        source_mapping = {
            'tushare': ChinaDataSource.TUSHARE,
            'akshare': ChinaDataSource.AKSHARE,
            'baostock': ChinaDataSource.BAOSTOCK
        }

        if source.lower() not in source_mapping:
            return f"❌ 不支持的数据源: {source}。支持的数据源: {list(source_mapping.keys())}"

        manager = get_data_source_manager()
        target_source = source_mapping[source.lower()]

        if manager.set_current_source(target_source):
            return f"✅ 数据源已切换到: {source}"
        else:
            return f"❌ 数据源切换失败: {source} 不可用"

    except Exception as e:
        logger.error(f"❌ 数据源切换失败: {e}")
        return f"❌ 数据源切换失败: {e}"


def get_current_china_data_source() -> str:
    """
    获取当前中国股票数据源

    Returns:
        str: 当前数据源信息
    """
    try:
        from .data_source_manager import get_data_source_manager

        manager = get_data_source_manager()
        current = manager.get_current_source()
        available = manager.available_sources

        result = f"当前数据源: {current.value}\n"
        result += f"可用数据源: {[s.value for s in available]}\n"
        result += f"默认数据源: {manager.default_source.value}\n"

        return result

    except Exception as e:
        logger.error(f"❌ 获取数据源信息失败: {e}")
        return f"❌ 获取数据源信息失败: {e}"


# ==================== 港股数据接口 ====================

def get_hk_stock_data_unified(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取港股数据的统一接口

    Args:
        symbol: 港股代码 (如: 0700.HK)
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        str: 格式化的港股数据
    """
    try:
        logger.info(f"🇭🇰 获取港股数据: {symbol}")

        # 优先使用AKShare港股数据（国内数据源，港股支持更好，更稳定）
        if AKSHARE_HK_AVAILABLE:
            try:
                logger.info(f"🔄 优先使用AKShare获取港股数据: {symbol}")
                result = get_hk_stock_data_akshare(symbol, start_date, end_date)
                if result and "❌" not in result:
                    logger.info(f"✅ AKShare港股数据获取成功: {symbol}")
                    return result
                else:
                    logger.error(f"⚠️ AKShare返回错误结果，尝试备用方案")
            except Exception as e:
                logger.error(f"⚠️ AKShare港股数据获取失败: {e}")

        # 备用方案1：使用Yahoo Finance港股工具
        if HK_STOCK_AVAILABLE:
            try:
                logger.info(f"🔄 使用Yahoo Finance备用方案获取港股数据: {symbol}")
                result = get_hk_stock_data(symbol, start_date, end_date)
                if result and "❌" not in result:
                    logger.info(f"✅ Yahoo Finance港股数据获取成功: {symbol}")
                    return result
                else:
                    logger.error(f"⚠️ Yahoo Finance返回错误结果")
            except Exception as e:
                logger.error(f"⚠️ Yahoo Finance港股数据获取失败: {e}")

        # 备用方案2：使用FINNHUB（付费用户可用）
        try:
            from .optimized_us_data import get_us_stock_data_cached
            logger.info(f"🔄 使用FINNHUB获取港股数据: {symbol}")
            result = get_us_stock_data_cached(symbol, start_date, end_date)
            if result and "❌" not in result:
                return result
        except Exception as e:
            logger.error(f"⚠️ FINNHUB港股数据获取失败: {e}")

        # 所有数据源都失败
        error_msg = f"❌ 无法获取港股{symbol}数据 - 所有数据源都不可用"
        print(error_msg)
        return error_msg

    except Exception as e:
        logger.error(f"❌ 获取港股数据失败: {e}")
        return f"❌ 获取港股{symbol}数据失败: {e}"


def get_hk_stock_info_unified(symbol: str) -> Dict:
    """
    获取港股信息的统一接口

    Args:
        symbol: 港股代码

    Returns:
        Dict: 港股信息
    """
    try:
        # 优先使用AKShare（国内数据源，港股支持更好）
        if AKSHARE_HK_AVAILABLE:
            try:
                logger.info(f"🔄 优先使用AKShare获取港股信息: {symbol}")
                result = get_hk_stock_info_akshare(symbol)
                if result and 'error' not in result and not result.get('name', '').startswith('港股'):
                    logger.info(f"✅ AKShare成功获取港股信息: {symbol} -> {result.get('name', 'N/A')}")
                    return result
                else:
                    logger.warning(f"⚠️ AKShare返回默认信息，尝试备用方案")
            except Exception as e:
                logger.error(f"⚠️ AKShare港股信息获取失败: {e}")

        # 备用方案1：使用Yahoo Finance港股工具
        if HK_STOCK_AVAILABLE:
            try:
                logger.info(f"🔄 使用Yahoo Finance备用方案获取港股信息: {symbol}")
                result = get_hk_stock_info(symbol)
                if result and 'error' not in result and not result.get('name', '').startswith('港股'):
                    logger.info(f"✅ Yahoo Finance成功获取港股信息: {symbol} -> {result.get('name', 'N/A')}")
                    return result
                else:
                    logger.warning(f"⚠️ Yahoo Finance返回默认信息")
            except Exception as e:
                logger.error(f"⚠️ Yahoo Finance港股信息获取失败: {e}")

        # 备用方案2：返回基本信息
        logger.info(f"🔄 使用默认信息: {symbol}")
        return {
            'symbol': symbol,
            'name': f'港股{symbol}',
            'currency': 'HKD',
            'exchange': 'HKG',
            'source': 'fallback'
        }

    except Exception as e:
        logger.error(f"❌ 获取港股信息失败: {e}")
        return {
            'symbol': symbol,
            'name': f'港股{symbol}',
            'currency': 'HKD',
            'exchange': 'HKG',
            'source': 'error',
            'error': str(e)
        }


def get_stock_data_by_market(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    根据股票市场类型自动选择数据源获取数据

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据
    """
    try:
        from .utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(symbol)

        if market_info['is_china']:
            # 中国A股
            return get_china_stock_data_unified(symbol, start_date, end_date)
        elif market_info['is_hk']:
            # 港股
            return get_hk_stock_data_unified(symbol, start_date, end_date)
        else:
            # 美股或其他
            from .optimized_us_data import get_us_stock_data_cached

            return get_us_stock_data_cached(symbol, start_date, end_date)

    except Exception as e:
        logger.error(f"❌ 获取股票数据失败: {e}")
        return f"❌ 获取股票{symbol}数据失败: {e}"
