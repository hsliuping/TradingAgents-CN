from typing import Annotated, Dict
from .chinese_finance_utils import get_chinese_social_sentiment

# 尝试导入yfinance相关模块，如果失败则跳过
# 移除非A股相关的工具导入
YFIN_AVAILABLE = False
STOCKSTATS_AVAILABLE = False
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import pandas as pd
from tqdm import tqdm
from openai import OpenAI

# 移除yfinance依赖
yf = None
YF_AVAILABLE = False
from .config import get_config, set_config, DATA_DIR

# 移除非A股相关函数 - FinnHub新闻
# def get_finnhub_news() - 已移除，专注于中国A股数据


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


# 移除非A股相关函数 - SimFin美国财务数据
# def get_simfin_balance_sheet() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - SimFin美国财务数据
# def get_simfin_cashflow() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - SimFin美国财务数据
# def get_simfin_income_statements() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - Google新闻
# def get_google_news() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - Reddit全球新闻
# def get_reddit_global_news() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - Reddit公司新闻
# def get_reddit_company_news() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - 技术指标分析
# def get_stock_stats_indicators_window() - 已移除，专注于中国A股数据


# 移除非A股相关函数 - 技术指标获取
# def get_stockstats_indicator() - 已移除，专注于中国A股数据


# 移除YFinance数据获取函数 - 专注于中国A股数据


# 移除YFinance在线数据获取函数 - 专注于中国A股数据


# 移除YFinance本地数据获取函数 - 专注于中国A股数据


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
                print(f"💾 [DEBUG] 从缓存加载Finnhub基本面数据: {ticker}")
                return cached_data
        
        # 获取Finnhub API密钥
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            return "错误：未配置FINNHUB_API_KEY环境变量"
        
        # 初始化Finnhub客户端
        finnhub_client = finnhub.Client(api_key=api_key)
        
        print(f"📊 [DEBUG] 使用Finnhub API获取 {ticker} 的基本面数据...")
        
        # 获取基本财务数据
        try:
            basic_financials = finnhub_client.company_basic_financials(ticker, 'all')
        except Exception as e:
            print(f"❌ [DEBUG] Finnhub基本财务数据获取失败: {str(e)}")
            basic_financials = None
        
        # 获取公司概况
        try:
            company_profile = finnhub_client.company_profile2(symbol=ticker)
        except Exception as e:
            print(f"❌ [DEBUG] Finnhub公司概况获取失败: {str(e)}")
            company_profile = None
        
        # 获取收益数据
        try:
            earnings = finnhub_client.company_earnings(ticker, limit=4)
        except Exception as e:
            print(f"❌ [DEBUG] Finnhub收益数据获取失败: {str(e)}")
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
            if 'peBasicExclExtraTTM' in metrics:
                report += f"| 市盈率 (PE) | {metrics['peBasicExclExtraTTM']:.2f} |\n"
            if 'psAnnual' in metrics:
                report += f"| 市销率 (PS) | {metrics['psAnnual']:.2f} |\n"
            if 'pbAnnual' in metrics:
                report += f"| 市净率 (PB) | {metrics['pbAnnual']:.2f} |\n"
            
            # 盈利能力指标
            if 'roeTTM' in metrics:
                report += f"| 净资产收益率 (ROE) | {metrics['roeTTM']:.2f}% |\n"
            if 'roaTTM' in metrics:
                report += f"| 总资产收益率 (ROA) | {metrics['roaTTM']:.2f}% |\n"
            if 'netProfitMarginTTM' in metrics:
                report += f"| 净利润率 | {metrics['netProfitMarginTTM']:.2f}% |\n"
            
            # 财务健康指标
            if 'currentRatioAnnual' in metrics:
                report += f"| 流动比率 | {metrics['currentRatioAnnual']:.2f} |\n"
            if 'totalDebt/totalEquityAnnual' in metrics:
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
        
        print(f"📊 [DEBUG] Finnhub基本面数据获取完成，报告长度: {len(report)}")
        return report
        
    except ImportError:
        return "错误：未安装finnhub-python库，请运行: pip install finnhub-python"
    except Exception as e:
        print(f"❌ [DEBUG] Finnhub基本面数据获取失败: {str(e)}")
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
                print(f"💾 [DEBUG] 从缓存加载OpenAI基本面数据: {ticker}")
                return cached_data
        
        config = get_config()
        
        # 检查是否配置了OpenAI相关设置
        if not config.get("backend_url") or not config.get("quick_think_llm"):
            print(f"📊 [DEBUG] OpenAI配置不完整，直接使用Finnhub API")
            return get_fundamentals_finnhub(ticker, curr_date)
        
        print(f"📊 [DEBUG] 尝试使用OpenAI获取 {ticker} 的基本面数据...")
        
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
        
        print(f"📊 [DEBUG] OpenAI基本面数据获取成功，长度: {len(result)}")
        return result
        
    except Exception as e:
        print(f"❌ [DEBUG] OpenAI基本面数据获取失败: {str(e)}")
        print(f"📊 [DEBUG] 回退到Finnhub API...")
        return get_fundamentals_finnhub(ticker, curr_date)


# ==================== Tushare数据接口 ====================

def get_china_stock_data_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD"],
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD"]
) -> str:
    """
    使用Tushare获取中国A股历史数据

    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据报告
    """
    try:
        from .tushare_adapter import get_tushare_adapter

        print(f"📊 [Tushare] 获取{ticker}股票数据...")

        adapter = get_tushare_adapter()
        data = adapter.get_stock_data(ticker, start_date, end_date)

        if data is not None and not data.empty:
            # 获取股票基本信息
            stock_info = adapter.get_stock_info(ticker)
            stock_name = stock_info.get('name', f'股票{ticker}') if stock_info else f'股票{ticker}'

            # 计算最新价格和涨跌幅
            latest_data = data.iloc[-1]
            current_price = f"¥{latest_data['close']:.2f}"

            if len(data) > 1:
                prev_close = data.iloc[-2]['close']
                change = latest_data['close'] - prev_close
                change_pct = (change / prev_close) * 100
                change_pct_str = f"{change_pct:+.2f}%"
            else:
                change_pct_str = "N/A"

            # 格式化成交量 - 修复成交量显示问题
            volume = 0
            if 'vol' in latest_data.index:
                volume = latest_data['vol']
            elif 'volume' in latest_data.index:
                volume = latest_data['volume']

            # 处理NaN值
            import pandas as pd
            if pd.isna(volume):
                volume = 0

            if volume > 10000:
                volume_str = f"{volume/10000:.1f}万手"
            elif volume > 0:
                volume_str = f"{volume:.0f}手"
            else:
                volume_str = "暂无数据"

            # 转换为与TDX兼容的字符串格式
            result = f"# {ticker} 股票数据分析\n\n"
            result += f"## 📊 实时行情\n"
            result += f"- 股票名称: {stock_name}\n"
            result += f"- 股票代码: {ticker}\n"
            result += f"- 当前价格: {current_price}\n"
            result += f"- 涨跌幅: {change_pct_str}\n"
            result += f"- 成交量: {volume_str}\n"
            result += f"- 数据来源: Tushare\n\n"
            result += f"## 📈 历史数据概览\n"
            result += f"- 数据期间: {start_date} 至 {end_date}\n"
            result += f"- 数据条数: {len(data)}条\n"

            if len(data) > 0:
                period_high = data['high'].max()
                period_low = data['low'].min()
                result += f"- 期间最高: ¥{period_high:.2f}\n"
                result += f"- 期间最低: ¥{period_low:.2f}\n\n"

            result += "## 📋 最新交易数据\n"
            result += data.tail(5).to_string(index=False)

            return result
        else:
            return f"❌ 未能获取{ticker}的股票数据"

    except Exception as e:
        print(f"❌ [Tushare] 获取股票数据失败: {e}")
        return f"❌ 获取{ticker}股票数据失败: {e}"


def search_china_stocks_tushare(
    keyword: Annotated[str, "搜索关键词，可以是股票名称或代码"]
) -> str:
    """
    使用Tushare搜索中国A股股票

    Args:
        keyword: 搜索关键词

    Returns:
        str: 搜索结果
    """
    try:
        from .tushare_adapter import get_tushare_adapter

        print(f"🔍 [Tushare] 搜索股票: {keyword}")

        adapter = get_tushare_adapter()
        results = adapter.search_stocks(keyword)

        if results is not None and not results.empty:
            result = f"搜索关键词: {keyword}\n"
            result += f"找到 {len(results)} 只股票:\n\n"

            # 显示前10个结果
            for idx, row in results.head(10).iterrows():
                result += f"代码: {row.get('symbol', '')}\n"
                result += f"名称: {row.get('name', '未知')}\n"
                result += f"行业: {row.get('industry', '未知')}\n"
                result += f"地区: {row.get('area', '未知')}\n"
                result += f"上市日期: {row.get('list_date', '未知')}\n"
                result += "-" * 30 + "\n"

            return result
        else:
            return f"❌ 未找到匹配'{keyword}'的股票"

    except Exception as e:
        print(f"❌ [Tushare] 搜索股票失败: {e}")
        return f"❌ 搜索股票失败: {e}"


def get_china_stock_fundamentals_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"]
) -> str:
    """
    使用Tushare获取中国A股基本面数据

    Args:
        ticker: 股票代码

    Returns:
        str: 基本面分析报告
    """
    try:
        from .tushare_adapter import get_tushare_adapter

        print(f"📊 [Tushare] 获取{ticker}基本面数据...")

        adapter = get_tushare_adapter()
        fundamentals = adapter.get_fundamentals(ticker)

        return fundamentals

    except Exception as e:
        print(f"❌ [Tushare] 获取基本面数据失败: {e}")
        return f"❌ 获取{ticker}基本面数据失败: {e}"


def get_china_stock_info_tushare(
    ticker: Annotated[str, "中国股票代码，如：000001、600036等"]
) -> str:
    """
    使用Tushare获取中国A股基本信息

    Args:
        ticker: 股票代码

    Returns:
        str: 股票基本信息
    """
    try:
        from .tushare_adapter import get_tushare_adapter

        print(f"📊 [Tushare] 获取{ticker}基本信息...")

        adapter = get_tushare_adapter()
        info = adapter.get_stock_info(ticker)

        if info and info.get('name'):
            result = f"股票代码: {ticker}\n"
            result += f"股票名称: {info.get('name', '未知')}\n"
            result += f"所属地区: {info.get('area', '未知')}\n"
            result += f"所属行业: {info.get('industry', '未知')}\n"
            result += f"上市市场: {info.get('market', '未知')}\n"
            result += f"上市日期: {info.get('list_date', '未知')}\n"
            result += f"数据来源: {info.get('source', 'tushare')}\n"

            return result
        else:
            return f"❌ 未能获取{ticker}的基本信息"

    except Exception as e:
        print(f"❌ [Tushare] 获取股票信息失败: {e}")
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
    try:
        from .data_source_manager import get_china_stock_data_unified

        print(f"📊 [统一接口] 获取{ticker}股票数据...")

        result = get_china_stock_data_unified(ticker, start_date, end_date)
        return result

    except Exception as e:
        print(f"❌ [统一接口] 获取股票数据失败: {e}")
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

        print(f"📊 [统一接口] 获取{ticker}基本信息...")

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
        print(f"❌ [统一接口] 获取股票信息失败: {e}")
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

        # 映射字符串到枚举
        source_mapping = {
            'tushare': ChinaDataSource.TUSHARE,
            'akshare': ChinaDataSource.AKSHARE,
            'baostock': ChinaDataSource.BAOSTOCK,
            'tdx': ChinaDataSource.TDX
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
        print(f"❌ 数据源切换失败: {e}")
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
        print(f"❌ 获取数据源信息失败: {e}")
        return f"❌ 获取数据源信息失败: {e}"
