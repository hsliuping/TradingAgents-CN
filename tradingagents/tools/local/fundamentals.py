import logging
from typing import Annotated, Optional
try:
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_tool_call
from tradingagents.default_config import DEFAULT_CONFIG

logger = get_logger("tools.local.fundamentals")

def create_unified_fundamentals_tool(toolkit):
    """创建统一基本面分析工具函数"""
    
    class UnifiedFundamentalsInput(BaseModel):
        ticker: str = Field(description="股票代码（支持A股、港股、美股）")
        start_date: Optional[str] = Field(default=None, description="开始日期，格式：YYYY-MM-DD")
        end_date: Optional[str] = Field(default=None, description="结束日期，格式：YYYY-MM-DD")
        curr_date: Optional[str] = Field(default=None, description="当前日期，格式：YYYY-MM-DD")

    def _generate_report(analyzer, ticker: str, current_price_data: str, analysis_modules: str) -> str:
        """优先使用公开接口生成报告，回退到兼容的私有方法。"""
        public_fn = getattr(analyzer, "generate_fundamentals_report", None)
        if callable(public_fn):
            return public_fn(ticker, current_price_data, analysis_modules)
        private_fn = getattr(analyzer, "_generate_fundamentals_report", None)
        if callable(private_fn):  # pragma: no cover - 兼容旧版
            return private_fn(ticker, current_price_data, analysis_modules)
        raise RuntimeError("缺少基本面报告生成方法")

    def _append_result(bucket, title: str, fn):
        try:
            result = fn()
            bucket.append(f"{title}\n{result}")
            return True
        except Exception as exc:  # noqa: BLE001 - 外部数据源保护
            logger.error("❌ [统一基本面工具] %s 失败: %s", title, exc)
            bucket.append(f"{title}\n获取失败: {exc}")
            return False

    @log_tool_call(tool_name="get_stock_fundamentals_unified", log_args=True)
    def get_stock_fundamentals_unified(
        ticker: str,
        start_date: str = None,
        end_date: str = None,
        curr_date: str = None
    ) -> str:
        """
        统一的股票基本面分析工具
        自动识别股票类型（A股、港股、美股）并调用相应的数据源
        支持基于分析级别的数据获取策略
        """
        logger.info(f"📊 [统一基本面工具] 分析股票: {ticker}")

        # 分级分析已废弃，统一使用标准深度
        data_depth = "standard"
        logger.info("🔧 [分析深度] 已取消分级分析，使用标准数据深度")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] 统一基本面工具接收到的原始股票代码: '{ticker}' (类型: {type(ticker)})")
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(ticker))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(ticker))}")

        original_ticker = ticker

        try:
            from tradingagents.utils.stock_utils import StockUtils
            from datetime import datetime, timedelta

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"🔍 [股票代码追踪] StockUtils.get_market_info 返回的市场信息: {market_info}")
            logger.info(f"📊 [统一基本面工具] 股票类型: {market_info['market_name']}")
            logger.info(f"📊 [统一基本面工具] 货币: {market_info['currency_name']} ({market_info['currency_symbol']})")

            if str(ticker) != str(original_ticker):
                logger.warning(f"🔍 [股票代码追踪] 警告：股票代码发生了变化！原始: '{original_ticker}' -> 当前: '{ticker}'")

            # 设置默认日期
            if not curr_date:
                curr_date = datetime.now().strftime('%Y-%m-%d')
        
            if data_depth == "basic":
                analysis_modules = "basic"
                logger.info(f"📊 [基本面策略] 快速分析模式：获取基础财务指标")
            elif data_depth == "standard":
                analysis_modules = "standard"
                logger.info(f"📊 [基本面策略] 标准分析模式：获取标准财务分析")
            elif data_depth == "full":
                analysis_modules = "full"
                logger.info(f"📊 [基本面策略] 深度分析模式：获取完整基本面分析")
            elif data_depth == "comprehensive":
                analysis_modules = "comprehensive"
                logger.info(f"📊 [基本面策略] 全面分析模式：获取综合基本面分析")
            else:
                analysis_modules = "standard"
                logger.info(f"📊 [基本面策略] 默认模式：获取标准基本面分析")
            
            days_to_fetch = 10  # 固定获取10天数据
            days_to_analyze = 2  # 只分析最近2天

            logger.info(f"📅 [基本面策略] 获取{days_to_fetch}天数据，分析最近{days_to_analyze}天")

            if not start_date:
                start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')

            if not end_date:
                end_date = curr_date

            result_data = []

            if is_china:
                # 中国A股：基本面分析优化策略
                logger.info(f"🇨🇳 [统一基本面工具] 处理A股数据，数据深度: {data_depth}...")
                logger.info(f"🔍 [股票代码追踪] 进入A股处理分支，ticker: '{ticker}'")
                logger.info(f"💡 [优化策略] 基本面分析只获取当前价格和财务数据，不获取历史日线数据")

                try:
                    # 获取最新股价信息（只需要最近1-2天的数据）
                    recent_end_date = curr_date
                    recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')

                    from tradingagents.dataflows.interface import get_china_stock_data_unified
                    logger.info(f"🔍 [股票代码追踪] 调用 get_china_stock_data_unified（仅获取最新价格），传入参数: ticker='{ticker}', start_date='{recent_start_date}', end_date='{recent_end_date}'")
                    current_price_data = get_china_stock_data_unified(ticker, recent_start_date, recent_end_date)

                    logger.info(f"🔍 [基本面工具调试] A股价格数据返回长度: {len(current_price_data)}")
                    result_data.append(f"## A股当前价格信息\n{current_price_data}")
                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] A股价格数据获取失败: {e}")
                    result_data.append(f"## A股当前价格信息\n获取失败: {e}")
                    current_price_data = ""

                try:
                    # 获取基本面财务数据
                    from tradingagents.dataflows.providers.china.optimized import OptimizedChinaDataProvider
                    analyzer = OptimizedChinaDataProvider()
                    logger.info(f"🔍 [股票代码追踪] 调用 OptimizedChinaDataProvider 生成报告，传入参数: ticker='{ticker}', analysis_modules='{analysis_modules}'")

                    fundamentals_data = _generate_report(analyzer, ticker, current_price_data, analysis_modules)

                    logger.info(f"🔍 [基本面工具调试] A股基本面数据返回长度: {len(fundamentals_data)}")
                    result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] A股基本面数据获取失败: {e}")
                    result_data.append(f"## A股基本面财务数据\n获取失败: {e}")

            elif is_hk:
                # 港股
                logger.info(f"🇭🇰 [统一基本面工具] 处理港股数据，数据深度: {data_depth}...")

                hk_data_success = False
                logger.info(f"🔍 [港股基本面] 根据 data_depth 调整抓取强度")

                allow_full_fetch = data_depth in ["full", "comprehensive", "深度", "全面"]
                if allow_full_fetch:
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_data_unified
                        hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                        logger.info(f"🔍 [基本面工具调试] 港股数据返回长度: {len(hk_data)}")

                        if hk_data and len(hk_data) > 100 and "❌" not in hk_data:
                            result_data.append(f"## 港股数据\n{hk_data}")
                            hk_data_success = True
                            logger.info(f"✅ [统一基本面工具] 港股主要数据源成功")
                        else:
                            logger.warning(f"⚠️ [统一基本面工具] 港股主要数据源质量不佳")

                    except Exception as e:
                        logger.error(f"❌ [基本面工具调试] 港股数据获取失败: {e}")
                else:
                    logger.info("ℹ️ [港股基本面] 轻量模式：跳过重型数据抓取，直接返回基础信息")

                # 备用方案
                if not hk_data_success:
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_info_unified
                        hk_info = get_hk_stock_info_unified(ticker)

                        basic_info = f"""## 港股基础信息

**股票代码**: {ticker}
**股票名称**: {hk_info.get('name', f'港股{ticker}')}
**交易货币**: 港币 (HK$)
**交易所**: 香港交易所 (HKG)
**数据源**: {hk_info.get('source', '基础信息')}

⚠️ 注意：详细的价格和财务数据暂时无法获取，建议稍后重试或使用其他数据源。
"""
                        result_data.append(basic_info)
                        logger.info(f"✅ [统一基本面工具] 港股备用信息成功")

                    except Exception as e2:
                        fallback_info = f"## 港股信息（备用）\n\n❌ 数据获取遇到问题: {str(e2)}"
                        result_data.append(fallback_info)
                        logger.error(f"❌ [统一基本面工具] 港股所有数据源都失败: {e2}")

            else:
                # 美股
                logger.info(f"🇺🇸 [统一基本面工具] 处理美股数据...")
                logger.info(f"🔍 [美股基本面] 根据 data_depth 调整抓取强度")

                def _fetch_us():
                    from tradingagents.dataflows.interface import get_fundamentals_openai
                    return get_fundamentals_openai(ticker, curr_date)

                if data_depth in ["basic", "standard", "快速", "基础", "标准"]:
                    _append_result(result_data, "## 美股基本面数据（轻量）", _fetch_us)
                else:
                    success = _append_result(result_data, "## 美股基本面数据", _fetch_us)
                    if not success:
                        logger.warning("⚠️ [统一基本面工具] 美股数据重试可考虑降级到轻量模式")

            # 组合所有数据
            combined_result = f"""# {ticker} 基本面分析数据

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析日期**: {curr_date}
**数据深度级别**: {data_depth}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""
            return combined_result

        except Exception as e:
            error_msg = f"统一基本面分析工具执行失败: {str(e)}"
            logger.error(f"❌ [统一基本面工具] {error_msg}")
            return error_msg

    # 设置工具属性
    get_stock_fundamentals_unified.name = "get_stock_fundamentals_unified"
    get_stock_fundamentals_unified.description = """
统一股票基本面分析工具 - 获取股票的财务数据和估值指标。
自动识别股票类型（A股/港股/美股）并调用最佳数据源。
返回数据包括：市盈率(PE)、市净率(PB)、净资产收益率(ROE)、营收增长、利润增长等核心财务指标。
"""
    get_stock_fundamentals_unified.args_schema = UnifiedFundamentalsInput
    
    return get_stock_fundamentals_unified
