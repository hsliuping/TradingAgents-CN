#!/usr/bin/env python3
"""
优化的A股数据获取工具
集成缓存策略和Tushare数据接口，提高数据获取效率
"""

import os
import time
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from typing import Optional, Dict, Any
from .cache import get_cache
from tradingagents.config.config_manager import config_manager

from tradingagents.config.runtime_settings import get_float, get_timezone_name
# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')

# 导入 MongoDB 缓存适配器
from .cache.mongodb_cache_adapter import get_mongodb_cache_adapter, get_stock_data_with_fallback, get_financial_data_with_fallback

# 导入数据质量验证和量化评分模块
from tradingagents.dataflows.data_validator import (
    annotate_fundamentals_with_validation,
    validate_pe,
    detect_industry,
)
from tradingagents.quantitative_scoring import compute_quantitative_score


class OptimizedChinaDataProvider:
    """优化的A股数据提供器 - 集成缓存和Tushare数据接口"""

    def __init__(self):
        self.cache = get_cache()
        self.config = config_manager.load_settings()
        self.last_api_call = 0
        self.min_api_interval = get_float("TA_CHINA_MIN_API_INTERVAL_SECONDS", "ta_china_min_api_interval_seconds", 0.5)

        logger.info(f"📊 优化A股数据提供器初始化完成")

    def _wait_for_rate_limit(self):
        """等待API限制"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call

        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            time.sleep(wait_time)

        self.last_api_call = time.time()

    def _format_financial_data_to_fundamentals(self, financial_data: Dict[str, Any], symbol: str) -> str:
        """将MongoDB财务数据转换为基本面分析格式"""
        try:
            # 提取关键财务指标
            revenue = financial_data.get('total_revenue', 'N/A')
            net_profit = financial_data.get('net_profit', 'N/A')
            total_assets = financial_data.get('total_assets', 'N/A')
            total_equity = financial_data.get('total_equity', 'N/A')
            report_period = financial_data.get('report_period', 'N/A')

            # 格式化数值（如果是数字则添加千分位，否则显示原值）
            def format_number(value):
                if isinstance(value, (int, float)):
                    return f"{value:,.2f}"
                return str(value)

            revenue_str = format_number(revenue)
            net_profit_str = format_number(net_profit)
            total_assets_str = format_number(total_assets)
            total_equity_str = format_number(total_equity)

            # 计算财务比率
            roe = 'N/A'
            if isinstance(net_profit, (int, float)) and isinstance(total_equity, (int, float)) and total_equity != 0:
                roe = f"{(net_profit / total_equity * 100):.2f}%"

            roa = 'N/A'
            if isinstance(net_profit, (int, float)) and isinstance(total_assets, (int, float)) and total_assets != 0:
                roa = f"{(net_profit / total_assets * 100):.2f}%"

            # 格式化输出
            fundamentals_report = f"""
# {symbol} 基本面数据分析

## 📊 财务概况
- **报告期**: {report_period}
- **营业收入**: {revenue_str} 元
- **净利润**: {net_profit_str} 元
- **总资产**: {total_assets_str} 元
- **股东权益**: {total_equity_str} 元

## 📈 财务比率
- **净资产收益率(ROE)**: {roe}
- **总资产收益率(ROA)**: {roa}

## 📝 数据说明
- 数据来源: MongoDB财务数据库
- 更新时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
- 数据类型: 同步财务数据
"""
            return fundamentals_report.strip()

        except Exception as e:
            logger.warning(f"⚠️ 格式化财务数据失败: {e}")
            return f"# {symbol} 基本面数据\n\n❌ 数据格式化失败: {str(e)}"

    def get_stock_data(self, symbol: str, start_date: str, end_date: str,
                      force_refresh: bool = False) -> str:
        """
        获取A股数据 - 优先使用缓存

        Args:
            symbol: 股票代码（6位数字）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_refresh: 是否强制刷新缓存

        Returns:
            格式化的股票数据字符串
        """
        logger.info(f"📈 获取A股数据: {symbol} ({start_date} 到 {end_date})")

        # 1. 优先尝试从MongoDB获取（如果启用了TA_USE_APP_CACHE）
        if not force_refresh:
            adapter = get_mongodb_cache_adapter()
            if adapter.use_app_cache:
                df = adapter.get_historical_data(symbol, start_date, end_date)
                if df is not None and not df.empty:
                    logger.info(f"📊 [数据来源: MongoDB] 使用MongoDB历史数据: {symbol} ({len(df)}条记录)")
                    return df.to_string()

        # 2. 检查文件缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                data_source="unified"  # 统一数据源（Tushare/AKShare/BaoStock）
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ [数据来源: 文件缓存] 从缓存加载A股数据: {symbol}")
                    return cached_data

        # 缓存未命中，从统一数据源接口获取
        logger.info(f"🌐 [数据来源: API调用] 从统一数据源接口获取数据: {symbol}")

        try:
            # API限制处理
            self._wait_for_rate_limit()

            # 调用统一数据源接口（默认Tushare，支持备用数据源）
            from .data_source_manager import get_china_stock_data_unified

            formatted_data = get_china_stock_data_unified(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # 检查是否获取成功
            if "❌" in formatted_data or "错误" in formatted_data:
                logger.error(f"❌ [数据来源: API失败] 数据源API调用失败: {symbol}")
                # 尝试从旧缓存获取数据
                old_cache = self._try_get_old_cache(symbol, start_date, end_date)
                if old_cache:
                    logger.info(f"📁 [数据来源: 过期缓存] 使用过期缓存数据: {symbol}")
                    return old_cache

                # 生成备用数据
                logger.warning(f"⚠️ [数据来源: 备用数据] 生成备用数据: {symbol}")
                return self._generate_fallback_data(symbol, start_date, end_date, "数据源API调用失败")

            # 保存到缓存
            self.cache.save_stock_data(
                symbol=symbol,
                data=formatted_data,
                start_date=start_date,
                end_date=end_date,
                data_source="unified"  # 使用统一数据源标识
            )

            logger.info(f"✅ [数据来源: API调用成功] A股数据获取成功: {symbol}")
            return formatted_data

        except Exception as e:
            error_msg = f"Tushare数据接口调用异常: {str(e)}"
            logger.error(f"❌ {error_msg}")

            # 尝试从旧缓存获取数据
            old_cache = self._try_get_old_cache(symbol, start_date, end_date)
            if old_cache:
                logger.info(f"📁 使用过期缓存数据: {symbol}")
                return old_cache

            # 生成备用数据
            return self._generate_fallback_data(symbol, start_date, end_date, error_msg)

    def get_fundamentals_data(self, symbol: str, force_refresh: bool = False) -> str:
        """
        获取A股基本面数据 - 优先使用缓存

        Args:
            symbol: 股票代码
            force_refresh: 是否强制刷新缓存

        Returns:
            格式化的基本面数据字符串
        """
        logger.info(f"📊 获取A股基本面数据: {symbol}")

        # 1. 优先尝试从MongoDB获取财务数据（如果启用了TA_USE_APP_CACHE）
        if not force_refresh:
            adapter = get_mongodb_cache_adapter()
            if adapter.use_app_cache:
                financial_data = adapter.get_financial_data(symbol)
                if financial_data:
                    logger.info(f"💰 [数据来源: MongoDB财务数据] 使用MongoDB财务数据: {symbol}")
                    # 将财务数据转换为基本面分析格式
                    return self._format_financial_data_to_fundamentals(financial_data, symbol)

        # 2. 检查文件缓存（除非强制刷新）
        if not force_refresh:
            # 查找基本面数据缓存
            for metadata_file in self.cache.metadata_dir.glob(f"*_meta.json"):
                try:
                    import json
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    if (metadata.get('symbol') == symbol and
                        metadata.get('data_type') == 'fundamentals' and
                        metadata.get('market_type') == 'china'):

                        cache_key = metadata_file.stem.replace('_meta', '')
                        if self.cache.is_cache_valid(cache_key, symbol=symbol, data_type='fundamentals'):
                            cached_data = self.cache.load_stock_data(cache_key)
                            if cached_data:
                                logger.info(f"⚡ [数据来源: 文件缓存] 从缓存加载A股基本面数据: {symbol}")
                                return cached_data
                except Exception:
                    continue

        # 缓存未命中，生成基本面分析
        logger.debug(f"🔍 [数据来源: 生成分析] 生成A股基本面分析: {symbol}")

        try:
            # 基本面分析只需要基础信息，不需要完整的历史交易数据
            # 获取股票基础信息（公司名称、当前价格等）
            stock_basic_info = self._get_stock_basic_info_only(symbol)

            # 生成基本面分析报告
            fundamentals_data = self._generate_fundamentals_report(symbol, stock_basic_info)

            # 保存到缓存
            self.cache.save_fundamentals_data(
                symbol=symbol,
                fundamentals_data=fundamentals_data,
                data_source="unified_analysis"  # 统一数据源分析
            )

            logger.info(f"✅ [数据来源: 生成分析成功] A股基本面数据生成成功: {symbol}")
            return fundamentals_data

        except Exception as e:
            error_msg = f"基本面数据生成失败: {str(e)}"
            logger.error(f"❌ [数据来源: 生成失败] {error_msg}")
            logger.warning(f"⚠️ [数据来源: 备用数据] 生成备用基本面数据: {symbol}")
            return self._generate_fallback_fundamentals(symbol, error_msg)

    def _get_stock_basic_info_only(self, symbol: str) -> str:
        """
        获取股票基础信息（仅用于基本面分析）
        不获取历史交易数据，只获取公司名称、当前价格等基础信息
        """
        logger.debug(f"📊 [基本面优化] 获取{symbol}基础信息（不含历史数据）")

        try:
            # 从统一接口获取股票基本信息
            from .interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(symbol)

            # 如果获取成功，直接返回基础信息
            if stock_info and "股票名称:" in stock_info:
                logger.debug(f"📊 [基本面优化] 成功获取{symbol}基础信息，无需历史数据")
                return stock_info

            # 如果基础信息获取失败，尝试从缓存获取最基本的信息
            try:
                from tradingagents.config.runtime_settings import use_app_cache_enabled
                if use_app_cache_enabled(False):
                    from .cache.app_adapter import get_market_quote_dataframe
                    df_q = get_market_quote_dataframe(symbol)
                    if df_q is not None and not df_q.empty:
                        row_q = df_q.iloc[-1]
                        current_price = str(row_q.get('close', 'N/A'))
                        change_pct = f"{float(row_q.get('pct_chg', 0)):+.2f}%" if row_q.get('pct_chg') is not None else 'N/A'
                        volume = str(row_q.get('volume', 'N/A'))

                        # 构造基础信息格式
                        basic_info = f"""股票代码: {symbol}
股票名称: 未知公司
当前价格: {current_price}
涨跌幅: {change_pct}
成交量: {volume}"""
                        logger.debug(f"📊 [基本面优化] 从缓存构造{symbol}基础信息")
                        return basic_info
            except Exception as e:
                logger.debug(f"📊 [基本面优化] 从缓存获取基础信息失败: {e}")

            # 如果都失败了，返回最基本的信息
            return f"股票代码: {symbol}\n股票名称: 未知公司\n当前价格: N/A\n涨跌幅: N/A\n成交量: N/A"

        except Exception as e:
            logger.warning(f"⚠️ [基本面优化] 获取{symbol}基础信息失败: {e}")
            return f"股票代码: {symbol}\n股票名称: 未知公司\n当前价格: N/A\n涨跌幅: N/A\n成交量: N/A"

    def _generate_fundamentals_report(self, symbol: str, stock_data: str, analysis_modules: str = "standard") -> str:
        """基于股票数据生成真实的基本面分析报告
        
        Args:
            symbol: 股票代码
            stock_data: 股票数据
            analysis_modules: 分析模块级别 ("basic", "standard", "full", "detailed", "comprehensive")
        """

        # 添加详细的股票代码追踪日志
        logger.debug(f"🔍 [股票代码追踪] _generate_fundamentals_report 接收到的股票代码: '{symbol}' (类型: {type(symbol)})")
        logger.debug(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.debug(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")
        logger.debug(f"🔍 [股票代码追踪] 接收到的股票数据前200字符: {stock_data[:200] if stock_data else 'None'}")

        # 从股票数据中提取信息
        company_name = "未知公司"
        current_price = "N/A"
        volume = "N/A"
        change_pct = "N/A"

        # 首先尝试从统一接口获取股票基本信息
        try:
            logger.debug(f"🔍 [股票代码追踪] 尝试获取{symbol}的基本信息...")
            from .interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(symbol)
            logger.debug(f"🔍 [股票代码追踪] 获取到的股票信息: {stock_info}")

            if "股票名称:" in stock_info:
                lines = stock_info.split('\n')
                for line in lines:
                    if "股票名称:" in line:
                        company_name = line.split(':')[1].strip()
                        logger.debug(f"🔍 [股票代码追踪] 从统一接口获取到股票名称: {company_name}")
                        break
        except Exception as e:
            logger.warning(f"⚠️ 获取股票基本信息失败: {e}")

        # 若仍缺失当前价格/涨跌幅/成交量，且启用app缓存，则直接读取 market_quotes 兜底
        try:
            if (current_price == "N/A" or change_pct == "N/A" or volume == "N/A"):
                from tradingagents.config.runtime_settings import use_app_cache_enabled  # type: ignore
                if use_app_cache_enabled(False):
                    from .cache.app_adapter import get_market_quote_dataframe
                    df_q = get_market_quote_dataframe(symbol)
                    if df_q is not None and not df_q.empty:
                        row_q = df_q.iloc[-1]
                        if current_price == "N/A" and row_q.get('close') is not None:
                            current_price = str(row_q.get('close'))
                            logger.debug(f"🔍 [股票代码追踪] 从market_quotes补齐当前价格: {current_price}")
                        if change_pct == "N/A" and row_q.get('pct_chg') is not None:
                            try:
                                change_pct = f"{float(row_q.get('pct_chg')):+.2f}%"
                            except Exception:
                                change_pct = str(row_q.get('pct_chg'))
                            logger.debug(f"🔍 [股票代码追踪] 从market_quotes补齐涨跌幅: {change_pct}")
                        if volume == "N/A" and row_q.get('volume') is not None:
                            volume = str(row_q.get('volume'))
                            logger.debug(f"🔍 [股票代码追踪] 从market_quotes补齐成交量: {volume}")
        except Exception as _qe:
            logger.debug(f"🔍 [股票代码追踪] 读取market_quotes失败（忽略）: {_qe}")

        # 然后从股票数据中提取价格信息
        if "股票名称:" in stock_data:
            lines = stock_data.split('\n')
            for line in lines:
                if "股票名称:" in line and company_name == "未知公司":
                    company_name = line.split(':')[1].strip()
                elif "当前价格:" in line:
                    current_price = line.split(':')[1].strip()
                elif "最新价格:" in line or "💰 最新价格:" in line:
                    # 兼容另一种模板输出
                    try:
                        current_price = line.split(':', 1)[1].strip().lstrip('¥').strip()
                    except Exception:
                        current_price = line.split(':')[-1].strip()
                elif "涨跌幅:" in line:
                    change_pct = line.split(':')[1].strip()
                elif "成交量:" in line:
                    volume = line.split(':')[1].strip()

        # 尝试从股票数据表格中提取最新价格信息
        if current_price == "N/A" and stock_data:
            try:
                lines = stock_data.split('\n')
                for i, line in enumerate(lines):
                    if "最新数据:" in line and i + 1 < len(lines):
                        # 查找数据行
                        for j in range(i + 1, min(i + 5, len(lines))):
                            data_line = lines[j].strip()
                            if data_line and not data_line.startswith('日期') and not data_line.startswith('-'):
                                # 尝试解析数据行
                                parts = data_line.split()
                                if len(parts) >= 4:
                                    try:
                                        # 假设格式: 日期 股票代码 开盘 收盘 最高 最低 成交量 成交额...
                                        current_price = parts[3]  # 收盘价
                                        logger.debug(f"🔍 [股票代码追踪] 从数据表格提取到收盘价: {current_price}")
                                        break
                                    except (IndexError, ValueError):
                                        continue
                        break
            except Exception as e:
                logger.debug(f"🔍 [股票代码追踪] 解析股票数据表格失败: {e}")

        # 根据股票代码判断行业和基本信息
        logger.debug(f"🔍 [股票代码追踪] 调用 _get_industry_info，传入参数: '{symbol}'")
        industry_info = self._get_industry_info(symbol)
        logger.debug(f"🔍 [股票代码追踪] _get_industry_info 返回结果: {industry_info}")

        # 尝试获取财务指标，如果失败则返回简化的基本面报告
        logger.debug(f"🔍 [股票代码追踪] 调用 _estimate_financial_metrics，传入参数: '{symbol}'")
        try:
            financial_estimates = self._estimate_financial_metrics(symbol, current_price)
            logger.debug(f"🔍 [股票代码追踪] _estimate_financial_metrics 返回结果: {financial_estimates}")
        except Exception as e:
            logger.warning(f"⚠️ [基本面分析] 无法获取财务指标: {e}")
            logger.info(f"📊 [基本面分析] 返回简化的基本面报告（无财务指标）")

            # 返回简化的基本面报告（不包含财务指标）
            simplified_report = f"""# 中国A股基本面分析报告 - {symbol} (简化版)

## 📊 基本信息
- **股票代码**: {symbol}
- **公司名称**: {company_name}
- **所属行业**: {industry_info.get('industry', '未知')}
- **当前价格**: {current_price}
- **涨跌幅**: {change_pct}
- **成交量**: {volume}

## 📈 行业分析
{industry_info.get('analysis', '暂无行业分析')}

## ⚠️ 数据说明
由于无法获取完整的财务数据，本报告仅包含基本价格信息和行业分析。
建议：
1. 查看公司最新财报获取详细财务数据
2. 关注行业整体走势
3. 结合技术分析进行综合判断

---
**生成时间**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: 基础市场数据
"""
            return simplified_report.strip()

        logger.debug(f"🔍 [股票代码追踪] 开始生成报告，使用股票代码: '{symbol}'")

        # 检查数据来源并生成相应说明
        data_source_note = ""
        data_source = financial_estimates.get('data_source', '')

        if any("（估算值）" in str(v) for v in financial_estimates.values() if isinstance(v, str)):
            data_source_note = "\n⚠️ **数据说明**: 部分财务指标为估算值，建议结合最新财报数据进行分析"
        elif data_source == "AKShare":
            data_source_note = "\n✅ **数据说明**: 财务指标基于AKShare真实财务数据计算"
        elif data_source == "Tushare":
            data_source_note = "\n✅ **数据说明**: 财务指标基于Tushare真实财务数据计算"
        else:
            data_source_note = "\n✅ **数据说明**: 财务指标基于真实财务数据计算"

        # 根据分析模块级别调整报告内容
        logger.debug(f"🔍 [基本面分析] 使用分析模块级别: {analysis_modules}")
        
        if analysis_modules == "basic":
            # 基础模式：只包含核心财务指标
            report = f"""# 中国A股基本面分析报告 - {symbol} (基础版)

## 📊 股票基本信息
- **股票代码**: {symbol}
- **股票名称**: {company_name}
- **当前股价**: {current_price}
- **涨跌幅**: {change_pct}
- **分析日期**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y年%m月%d日')}{data_source_note}

## 💰 核心财务指标
- **总市值**: {financial_estimates.get('total_mv', 'N/A')}
- **流通市值**: {financial_estimates.get('circ_mv', 'N/A')}
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **净资产收益率(ROE)**: {financial_estimates.get('roe', 'N/A')}
- **资产负债率**: {financial_estimates.get('debt_ratio', 'N/A')}

## 📊 行业相对估值（广发证券）
- **PE 行业均值**: {financial_estimates.get('pe_industry_avg', 'N/A')}
- **PE 历史百分位**: {financial_estimates.get('pe_percentile', 'N/A')}
- **PB 行业均值**: {financial_estimates.get('pb_industry_avg', 'N/A')}
- **PB 历史百分位**: {financial_estimates.get('pb_percentile', 'N/A')}

## 📊 行业相对估值（申万一级）
- **申万行业**: {financial_estimates.get('sw_industry_name', 'N/A')} ({financial_estimates.get('sw_industry_code', 'N/A')})
- **申万行业 PE_TTM**: {financial_estimates.get('sw_industry_pe_ttm', 'N/A')}
- **申万行业 PE_静态**: {financial_estimates.get('sw_industry_pe_static', 'N/A')}
- **申万行业 PB**: {financial_estimates.get('sw_industry_pb', 'N/A')}
- **申万行业股息率**: {financial_estimates.get('sw_industry_dividend_yield', 'N/A')}
- **申万行业成份股数**: {financial_estimates.get('sw_industry_constituents', 'N/A')}

{financial_estimates.get('sw_sub_industries_md', '')}

> ⚠️ 广发行业 PE 可能包含异常 PE 子行业（如电力归到含光伏/新能源发电的全行业），请结合下方申万二级/三级子行业 PE 列表与可比公司列表综合判断行业基准是否合理

## 📊 同行业可比公司 PE 列表
{financial_estimates.get('peer_pe_list', 'N/A')}

## 💡 基础评估
- **基本面评分**: {financial_estimates.get('fundamental_score', 'N/A')}/10
- **风险等级**: {financial_estimates.get('risk_level', 'N/A')}

---
**重要声明**: 本报告基于公开数据和模型估算生成，仅供参考，不构成投资建议。
**数据来源**: {data_source if data_source else "多源数据"}数据接口
**生成时间**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
"""
        elif analysis_modules in ["standard", "full"]:
            # 标准/完整模式：包含详细分析
            report = f"""# 中国A股基本面分析报告 - {symbol}

## 📊 股票基本信息
- **股票代码**: {symbol}
- **股票名称**: {company_name}
- **所属行业**: {industry_info['industry']}
- **市场板块**: {industry_info['market']}
- **当前股价**: {current_price}
- **涨跌幅**: {change_pct}
- **成交量**: {volume}
- **分析日期**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y年%m月%d日')}{data_source_note}

## 💰 财务数据分析

### 估值指标
- **总市值**: {financial_estimates.get('total_mv', 'N/A')}
- **流通市值**: {financial_estimates.get('circ_mv', 'N/A')}
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **市销率(PS)**: {financial_estimates.get('ps', 'N/A')}
- **股息收益率**: {financial_estimates.get('dividend_yield', 'N/A')}

### 行业相对估值（广发证券）
- **PE 行业均值**: {financial_estimates.get('pe_industry_avg', 'N/A')}
- **PE 历史百分位**: {financial_estimates.get('pe_percentile', 'N/A')}
- **PB 行业均值**: {financial_estimates.get('pb_industry_avg', 'N/A')}
- **PB 历史百分位**: {financial_estimates.get('pb_percentile', 'N/A')}

### 行业相对估值（申万一级）
- **申万行业**: {financial_estimates.get('sw_industry_name', 'N/A')} ({financial_estimates.get('sw_industry_code', 'N/A')})
- **申万行业 PE_TTM**: {financial_estimates.get('sw_industry_pe_ttm', 'N/A')}
- **申万行业 PE_静态**: {financial_estimates.get('sw_industry_pe_static', 'N/A')}
- **申万行业 PB**: {financial_estimates.get('sw_industry_pb', 'N/A')}
- **申万行业股息率**: {financial_estimates.get('sw_industry_dividend_yield', 'N/A')}
- **申万行业成份股数**: {financial_estimates.get('sw_industry_constituents', 'N/A')}

{financial_estimates.get('sw_sub_industries_md', '')}

> ⚠️ 广发行业 PE 可能包含异常 PE 子行业（如电力归到含光伏/新能源发电的全行业），请结合下方申万二级/三级子行业 PE 列表与可比公司列表综合判断行业基准是否合理

### 同行业可比公司 PE 列表
{financial_estimates.get('peer_pe_list', 'N/A')}

### 盈利能力指标
- **净资产收益率(ROE)**: {financial_estimates.get('roe', 'N/A')}
- **总资产收益率(ROA)**: {financial_estimates.get('roa', 'N/A')}
- **毛利率**: {financial_estimates.get('gross_margin', 'N/A')}
- **净利率**: {financial_estimates.get('net_margin', 'N/A')}

### 财务健康度
- **资产负债率**: {financial_estimates.get('debt_ratio', 'N/A')}
- **流动比率**: {financial_estimates.get('current_ratio', 'N/A')}
- **速动比率**: {financial_estimates.get('quick_ratio', 'N/A')}
- **现金比率**: {financial_estimates.get('cash_ratio', 'N/A')}

## 📈 行业分析
{industry_info['analysis']}

## 🎯 投资价值评估
### 估值水平分析
{self._analyze_valuation(financial_estimates)}

### 成长性分析
{self._analyze_growth_potential(symbol, industry_info)}

## 💡 投资建议
- **基本面评分**: {financial_estimates.get('fundamental_score', 'N/A')}/10
- **估值吸引力**: {financial_estimates.get('valuation_score', 'N/A')}/10
- **成长潜力**: {financial_estimates.get('growth_score', 'N/A')}/10
- **风险等级**: {financial_estimates.get('risk_level', 'N/A')}

{self._generate_investment_advice(financial_estimates, industry_info)}

---
**重要声明**: 本报告基于公开数据和模型估算生成，仅供参考，不构成投资建议。
**数据来源**: {data_source if data_source else "多源数据"}数据接口
**生成时间**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:  # detailed, comprehensive
            # 详细/全面模式：包含最完整的分析
            report = f"""# 中国A股基本面分析报告 - {symbol} (全面版)

## 📊 股票基本信息
- **股票代码**: {symbol}
- **股票名称**: {company_name}
- **所属行业**: {industry_info['industry']}
- **市场板块**: {industry_info['market']}
- **当前股价**: {current_price}
- **涨跌幅**: {change_pct}
- **成交量**: {volume}
- **分析日期**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y年%m月%d日')}{data_source_note}

## 💰 财务数据分析

### 估值指标
- **总市值**: {financial_estimates.get('total_mv', 'N/A')}
- **流通市值**: {financial_estimates.get('circ_mv', 'N/A')}
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **市销率(PS)**: {financial_estimates.get('ps', 'N/A')}
- **股息收益率**: {financial_estimates.get('dividend_yield', 'N/A')}

### 行业相对估值（广发证券）
- **PE 行业均值**: {financial_estimates.get('pe_industry_avg', 'N/A')}
- **PE 历史百分位**: {financial_estimates.get('pe_percentile', 'N/A')}
- **PB 行业均值**: {financial_estimates.get('pb_industry_avg', 'N/A')}
- **PB 历史百分位**: {financial_estimates.get('pb_percentile', 'N/A')}

### 盈利能力指标
- **净资产收益率(ROE)**: {financial_estimates.get('roe', 'N/A')}
- **总资产收益率(ROA)**: {financial_estimates.get('roa', 'N/A')}
- **毛利率**: {financial_estimates.get('gross_margin', 'N/A')}
- **净利率**: {financial_estimates.get('net_margin', 'N/A')}

### 财务健康度
- **资产负债率**: {financial_estimates.get('debt_ratio', 'N/A')}
- **流动比率**: {financial_estimates.get('current_ratio', 'N/A')}
- **速动比率**: {financial_estimates.get('quick_ratio', 'N/A')}
- **现金比率**: {financial_estimates.get('cash_ratio', 'N/A')}

## 📈 行业分析

### 行业地位
{industry_info['analysis']}

### 竞争优势
- **市场份额**: {industry_info['market_share']}
- **品牌价值**: {industry_info['brand_value']}
- **技术优势**: {industry_info['tech_advantage']}

## 🎯 投资价值评估

### 估值水平分析
{self._analyze_valuation(financial_estimates)}

### 成长性分析
{self._analyze_growth_potential(symbol, industry_info)}

### 风险评估
{self._analyze_risks(symbol, financial_estimates, industry_info)}

## 💡 投资建议

### 综合评分
- **基本面评分**: {financial_estimates.get('fundamental_score', 'N/A')}/10
- **估值吸引力**: {financial_estimates.get('valuation_score', 'N/A')}/10
- **成长潜力**: {financial_estimates.get('growth_score', 'N/A')}/10
- **风险等级**: {financial_estimates.get('risk_level', 'N/A')}

### 操作建议
{self._generate_investment_advice(financial_estimates, industry_info)}

### 绝对估值
- **DCF估值**：基于现金流贴现的内在价值
- **资产价值**：净资产重估价值
- **分红收益率**：股息回报分析

## 风险分析
### 系统性风险
- **宏观经济风险**：经济周期对公司的影响
- **政策风险**：行业政策变化的影响
- **市场风险**：股市波动对估值的影响

### 非系统性风险
- **经营风险**：公司特有的经营风险
- **财务风险**：债务结构和偿债能力风险
- **管理风险**：管理层变动和决策风险

## 投资建议
### 综合评价
基于以上分析，该股票的投资价值评估：

**优势：**
- A股市场上市公司，监管相对完善
- 具备一定的市场地位和品牌价值
- 财务信息透明度较高

**风险：**
- 需要关注宏观经济环境变化
- 行业竞争加剧的影响
- 政策调整对业务的潜在影响

### 操作建议
- **投资策略**：建议采用价值投资策略，关注长期基本面
- **仓位建议**：根据风险承受能力合理配置仓位
- **关注指标**：重点关注ROE、PE、现金流等核心指标

|---
**重要声明**: 本报告基于公开数据和模型估算生成，仅供参考，不构成投资建议。
实际投资决策请结合最新财报数据和专业分析师意见。

**数据来源**: {data_source if data_source else "多源数据"}数据接口 + 基本面分析模型
**生成时间**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}

---

## 🔍 数据质量验证 & 量化评分（辅助参考）

{self._append_data_validation_and_scoring(symbol, company_name, financial_estimates, industry_info)}
"""

        return report

    def _append_data_validation_and_scoring(
        self,
        symbol: str,
        company_name: str,
        financial_estimates: dict,
        industry_info: dict,
    ) -> str:
        """
        在基本面报告末尾附加数据质量验证和量化评分。
        帮助下游LLM判断数据可靠性，并提供一致的量化基准。

        Returns:
            str: 格式化的验证和评分文本
        """
        try:
            from tradingagents.dataflows.data_validator import (
                annotate_fundamentals_with_validation as _annotate,
                validate_pe as _val_pe,
                detect_industry as _detect_ind,
            )
            from tradingagents.quantitative_scoring import (
                compute_quantitative_score as _score,
            )

            lines = []

            # ---- 1. 数据质量验证 ----
            pe_raw = financial_estimates.get("pe", financial_estimates.get("pe_ttm"))
            pb_raw = financial_estimates.get("pb")
            sector = industry_info.get("industry", "")

            annotations = _annotate(
                {"pe": pe_raw, "pb": pb_raw},
                company_name,
                sector,
                symbol,
            )

            pe_check = annotations.get("pe_validation", {})
            if pe_check.get("severity") in ("warning", "error"):
                lines.append(f"⚠️ **数据质量提示**: {pe_check.get('message', '')}")
                hint = annotations.get("pe_annual_hint")
                if hint:
                    lines.append(f"   {hint}")
                ind_range = pe_check.get("industry_pe_range")
                if ind_range:
                    lines.append(
                        f"   ℹ️ 行业{_detect_ind(company_name, sector)}合理PE范围: "
                        f"[{ind_range[0]}, {ind_range[1]}]"
                    )

            pb_check = annotations.get("pb_validation", {})
            if pb_check.get("severity") in ("warning", "error"):
                lines.append(f"⚠️ **数据质量提示**: {pb_check.get('message', '')}")

            if not lines:
                lines.append("✅ 数据质量检查通过，未发现异常。")

            # ---- 2. 量化评分 ----
            def _sf(v):
                """安全的浮点数转换"""
                if v is None or v == "N/A":
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            pe = _sf(pe_raw)
            pb = _sf(pb_raw)
            roe = _sf(financial_estimates.get("roe"))
            gross_margin = _sf(financial_estimates.get("gross_margin"))
            debt_ratio = _sf(financial_estimates.get("debt_ratio"))

            score_result = _score(
                fundamentals={
                    "pe": pe,
                    "pb": pb,
                    "roe": roe,
                    "gross_margin": gross_margin,
                    "debt_ratio": debt_ratio,
                },
                technical={},  # 技术数据在market_report中，此处仅给基本面分
                company_name=company_name,
                sector=sector,
            )

            lines.append("")
            lines.append("### 📊 量化评分总计（0-100）")
            lines.append(f"| 维度 | 得分 | 说明 |")
            lines.append(f"|------|:---:|------|")
            lines.append(
                f"| **总分** | **{score_result['total_score']}** | "
                f"建议: {score_result['suggested_action']} |"
            )
            score_detail = score_result.get("detail", {})

            pe_detail = score_detail.get("pe", {})
            lines.append(
                f"| PE估值 | {pe_detail.get('score', 'N/A')} | "
                f"{pe_detail.get('note', '')} |"
            )
            pb_detail = score_detail.get("pb", {})
            lines.append(
                f"| PB估值 | {pb_detail.get('score', 'N/A')} | "
                f"{pb_detail.get('note', '')} |"
            )
            roe_detail = score_detail.get("roe", {})
            lines.append(
                f"| ROE质量 | {roe_detail.get('score', 'N/A')} | "
                f"{roe_detail.get('note', '')} |"
            )
            debt_detail = score_detail.get("debt_ratio", {})
            lines.append(
                f"| 负债风险 | {debt_detail.get('score', 'N/A')} | "
                f"{debt_detail.get('note', '')} |"
            )

            macro_info = score_detail.get("macro", {})
            lines.append(
                f"| 行业属性 | {macro_info.get('score', 'N/A')} | "
                f"{macro_info.get('note', '')} |"
            )

            lines.append("")
            lines.append(
                "> ⚠️ 量化评分为辅助参考，最终决策请结合辩论和实际市场状况。"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"⚠️ 数据验证/评分生成失败（不影响主报告）: {e}")
            return "数据质量验证暂不可用。"

    def _get_industry_info(self, symbol: str) -> dict:
        """根据股票代码获取行业信息（优先使用数据库真实数据）"""

        # 添加详细的股票代码追踪日志
        logger.debug(f"🔍 [股票代码追踪] _get_industry_info 接收到的股票代码: '{symbol}' (类型: {type(symbol)})")
        logger.debug(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.debug(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")

        # 首先尝试从数据库获取真实的行业信息
        try:
            from .cache.app_adapter import get_basics_from_cache
            doc = get_basics_from_cache(symbol)
            if doc:
                # 只记录关键字段，避免打印完整文档
                logger.debug(f"🔍 [股票代码追踪] 从数据库获取到基础信息: code={doc.get('code')}, name={doc.get('name')}, industry={doc.get('industry')}")

                # 规范化行业与板块（避免把"中小板/创业板"等板块值误作行业）
                board_labels = {'主板', '中小板', '创业板', '科创板'}
                raw_industry = (doc.get('industry') or doc.get('industry_name') or '').strip()
                sec_or_cat = (doc.get('sec') or doc.get('category') or '').strip()
                market_val = (doc.get('market') or '').strip()
                industry_val = raw_industry or sec_or_cat or '未知'

                # 如果industry字段是板块名，则将其用于market；industry改用更细分类（sec/category）
                if raw_industry in board_labels:
                    if not market_val:
                        market_val = raw_industry
                    if sec_or_cat:
                        industry_val = sec_or_cat
                    logger.debug(f"🔧 [字段归一化] industry原值='{raw_industry}' → 行业='{industry_val}', 市场/板块='{market_val}'")

                # 构建行业信息
                info = {
                    "industry": industry_val or '未知',
                    "market": market_val or doc.get('market', '未知'),
                    "type": self._get_market_type_by_code(symbol)
                }

                logger.debug(f"🔍 [股票代码追踪] 从数据库获取的行业信息: {info}")

                # 添加特殊股票的详细分析
                if symbol in self._get_special_stocks():
                    info.update(self._get_special_stocks()[symbol])
                else:
                    info.update({
                        "analysis": f"该股票属于{info['industry']}行业，在{info['market']}上市交易。",
                        "market_share": "待分析",
                        "brand_value": "待评估",
                        "tech_advantage": "待分析"
                    })

                return info

        except Exception as e:
            logger.warning(f"⚠️ 从数据库获取行业信息失败: {e}")

        # 备用方案：使用代码前缀判断（但修正了行业/市场的映射）
        logger.debug(f"🔍 [股票代码追踪] 使用备用方案，基于代码前缀判断")
        code_prefix = symbol[:3]
        logger.debug(f"🔍 [股票代码追踪] 提取的代码前缀: '{code_prefix}'")

        # 修正后的映射表：区分行业和市场板块
        market_map = {
            "000": {"market": "主板", "exchange": "深圳证券交易所", "type": "综合"},
            "001": {"market": "主板", "exchange": "深圳证券交易所", "type": "综合"},
            "002": {"market": "主板", "exchange": "深圳证券交易所", "type": "成长型"},  # 002开头现在也是主板
            "003": {"market": "创业板", "exchange": "深圳证券交易所", "type": "创新型"},
            "300": {"market": "创业板", "exchange": "深圳证券交易所", "type": "高科技"},
            "600": {"market": "主板", "exchange": "上海证券交易所", "type": "大盘蓝筹"},
            "601": {"market": "主板", "exchange": "上海证券交易所", "type": "大盘蓝筹"},
            "603": {"market": "主板", "exchange": "上海证券交易所", "type": "中小盘"},
            "688": {"market": "科创板", "exchange": "上海证券交易所", "type": "科技创新"},
        }

        market_info = market_map.get(code_prefix, {
            "market": "未知市场",
            "exchange": "未知交易所",
            "type": "综合"
        })

        info = {
            "industry": "未知",  # 无法从代码前缀准确判断具体行业
            "market": market_info["market"],
            "type": market_info["type"]
        }

        # 特殊股票的详细信息
        special_stocks = self._get_special_stocks()
        if symbol in special_stocks:
            info.update(special_stocks[symbol])
        else:
            info.update({
                "analysis": f"该股票在{info['market']}上市交易，具体行业信息需要进一步查询。",
                "market_share": "待分析",
                "brand_value": "待评估",
                "tech_advantage": "待分析"
            })

        return info

    def _get_market_type_by_code(self, symbol: str) -> str:
        """根据股票代码判断市场类型"""
        code_prefix = symbol[:3]
        type_map = {
            "000": "综合", "001": "综合", "002": "成长型", "003": "创新型",
            "300": "高科技", "600": "大盘蓝筹", "601": "大盘蓝筹",
            "603": "中小盘", "688": "科技创新"
        }
        return type_map.get(code_prefix, "综合")

    def _get_special_stocks(self) -> dict:
        """获取特殊股票的详细信息"""
        return {
            "000001": {
                "industry": "银行业",
                "analysis": "平安银行是中国领先的股份制商业银行，在零售银行业务方面具有显著优势。",
                "market_share": "股份制银行前列",
                "brand_value": "知名金融品牌",
                "tech_advantage": "金融科技创新领先"
            },
            "600036": {
                "industry": "银行业",
                "analysis": "招商银行是中国优质的股份制银行，零售银行业务和财富管理业务领先。",
                "market_share": "股份制银行龙头",
                "brand_value": "优质银行品牌",
                "tech_advantage": "数字化银行先锋"
            },
            "000002": {
                "industry": "房地产",
                "analysis": "万科A是中国房地产行业龙头企业，在住宅开发领域具有领先地位。",
                "market_share": "房地产行业前三",
                "brand_value": "知名地产品牌",
                "tech_advantage": "绿色建筑技术"
            },
            "002475": {
                "industry": "元器件",
                "analysis": "立讯精密是全球领先的精密制造服务商，主要从事连接器、声学、无线充电等产品的研发制造。",
                "market_share": "消费电子连接器龙头",
                "brand_value": "精密制造知名品牌",
                "tech_advantage": "精密制造技术领先"
            }
        }

    def _estimate_financial_metrics(self, symbol: str, current_price: str) -> dict:
        """获取真实财务指标（从 MongoDB、AKShare、BaoStock 获取，失败则抛出异常）"""

        # 🔴 修复：验证股价是否有效，拒绝使用默认值
        price_value = None
        try:
            if current_price and current_price != 'N/A':
                price_str = current_price.replace('¥', '').replace(',', '').strip()
                price_value = float(price_str)
                # 基本验证：股价应该在合理范围内（0.01 ~ 10000元）
                if price_value <= 0 or price_value > 10000:
                    logger.warning(f"⚠️ [股价验证失败] 股价值异常: {price_value}元，期望范围: 0.01~10000元")
                    price_value = None
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"⚠️ [股价验证失败] 股价解析失败: {current_price}, 错误: {e}")

        # 如果股价无效，尝试从BaoStock获取实时PE/PB
        if price_value is None:
            logger.warning(f"⚠️ [PE/PB计算] 股价无效({current_price})，尝试从BaoStock获取实时数据: {symbol}")
            
            # 🔥 优先尝试BaoStock获取实时PE/PB
            baostock_metrics = self._get_baostock_pe_pb(symbol)
            if baostock_metrics:
                logger.info(f"✅ [BaoStock] 获取成功: {symbol} PE={baostock_metrics['pe']}, PB={baostock_metrics['pb']}")
                
                # 🔥 使用BaoStock数据构建财务指标
                from .providers.china.akshare import get_akshare_provider
                import asyncio
                
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                akshare_provider = get_akshare_provider()
                
                try:
                    # 尝试获取完整财务数据
                    financial_data = loop.run_until_complete(
                        akshare_provider.get_stock_financial_data(symbol)
                    )
                    
                    if financial_data:
                        # 合并BaoStock的PE/PB数据
                        # 创建临时的stock_info字典
                        stock_info = {
                            'code': symbol,
                            'price': baostock_metrics.get('current_price_numeric', 10.0),
                        }
                        metrics = self._parse_akshare_financial_data(financial_data, stock_info, baostock_metrics.get('current_price_numeric', 10.0))
                        if metrics:
                            logger.info(f"✅ [财务指标] 合并BaoStock PE/PB成功: {symbol}")
                            return metrics
                except Exception as e:
                    logger.warning(f"⚠️ [AKShare] 获取财务数据失败: {e}")
                
                # 如果AKShare失败，直接返回BaoStock的PE/PB数据
                return baostock_metrics
            
            # 🔥 如果BaoStock也失败，抛出明确的告警错误
            error_msg = (
                f"🔴 [数据获取失败告警] 股票 {symbol} 无法获取有效估值数据！\n"
                f"   - 股价获取失败: {current_price}\n"
                f"   - BaoStock PE/PB获取失败\n"
                f"   - 请检查网络连接或股票代码是否正确"
            )
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 股价有效，继续正常流程
        logger.info(f"📊 [股价验证通过] {symbol} 股价: {price_value}元")

        # 🔥 开关：BaoStock 早返回 vs 完整路径
        # - False（默认）：股价有效时不立即返回，继续走 _get_real_financial_metrics 拿三表和市值，
        #   最后用 BaoStock 数据补/覆盖 PE/PB。这样能在保留 PE/PB 准确性的同时拿到完整财报数据。
        # - True：旧行为，BaoStock 命中就立即返回（无财报数据，仅 PE/PB + 市值）。
        BAOSTOCK_FAST_RETURN = False

        # 先尝试 BaoStock 拿 PE/PB（准确性高）
        logger.info(f"🔍 [PE/PB优化] 股价有效，优先从BaoStock获取PE/PB数据以确保准确性")
        baostock_metrics = self._get_baostock_pe_pb(symbol)
        if baostock_metrics:
            logger.info(f"✅ [BaoStock] 获取成功: {symbol} PE={baostock_metrics['pe']}, PB={baostock_metrics['pb']}")

            # 旧行为：BaoStock 命中立即返回（无财报数据）
            if BAOSTOCK_FAST_RETURN:
                logger.info(f"⚡ [BaoStock-快路径] BAOSTOCK_FAST_RETURN=True，直接返回 BaoStock 数据")
                return baostock_metrics

            # 新行为：继续走完整路径，拿三表和其他指标
            logger.info(f"🔄 [BaoStock-完整路径] 股价有效，继续走 _get_real_financial_metrics 拿三表和市值")
            real_metrics = self._get_real_financial_metrics(symbol, price_value)
            if real_metrics:
                # 用 BaoStock 的 PE/PE_TTM/PB 覆盖（准确性更高），保留 real_metrics 的其他字段
                # real_metrics 里如果已经有 total_mv/circ_mv 也保留（除非 BaoStock 路径已补）
                logger.info(f"✅ [BaoStock-合并] 使用 BaoStock PE/PB 覆盖，保留 real_metrics 的财报数据")
                real_metrics['pe'] = baostock_metrics['pe']
                real_metrics['pe_ttm'] = baostock_metrics['pe_ttm']
                real_metrics['pb'] = baostock_metrics['pb']
                # 如果 real_metrics 没有市值字段，用 BaoStock 路径已补的市值
                if 'total_mv' not in real_metrics and 'total_mv' in baostock_metrics:
                    real_metrics['total_mv'] = baostock_metrics['total_mv']
                if 'circ_mv' not in real_metrics and 'circ_mv' in baostock_metrics:
                    real_metrics['circ_mv'] = baostock_metrics['circ_mv']
                # 标注 PE/PB 数据来源
                real_metrics['pe_pb_source'] = 'BaoStock'
                # 保留 BaoStock 的分析日期（更准确）
                if baostock_metrics.get('analysis_date'):
                    real_metrics['analysis_date'] = baostock_metrics['analysis_date']
                return real_metrics
            else:
                # 完整路径失败，回退到 BaoStock 数据（已含市值）
                logger.warning(f"⚠️ [BaoStock-完整路径] _get_real_financial_metrics 失败，回退到 BaoStock 数据")
                return baostock_metrics
        else:
            # BaoStock 失败，走原有财务数据获取逻辑
            logger.warning(f"⚠️ [PE/PB优化] BaoStock获取失败，尝试AKShare获取财务数据")
            real_metrics = self._get_real_financial_metrics(symbol, price_value)
            if real_metrics:
                logger.info(f"✅ 使用真实财务数据: {symbol}")
                return real_metrics

        # 如果无法获取真实数据，抛出异常
        error_msg = f"无法获取股票 {symbol} 的财务数据。已尝试所有数据源（MongoDB、AKShare、BaoStock）均失败。"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)

    def _get_baostock_pe_pb(self, symbol: str) -> Optional[dict]:
        """
        🔥 从BaoStock获取实时PE/PB数据（新增方法）
        
        Args:
            symbol: 6位股票代码（如：600930）
        
        Returns:
            dict: 包含 PE、PB、PE_TTM 等指标的字典，失败返回 None
        
        Raises:
            不抛出异常，只记录日志并返回 None
        """
        try:
            import baostock as bs
            from datetime import datetime, timedelta
            
            # 标准化股票代码
            code = str(symbol).zfill(6)
            if code.startswith('6'):
                bs_code = f"sh.{code}"
            else:
                bs_code = f"sz.{code}"
            
            logger.info(f"🔍 [BaoStock] 开始获取 {symbol} 的PE/PB数据 (代码: {bs_code})")
            
            # 登录BaoStock
            bs.login()
            
            try:
                # 获取最近10个交易日的日线数据（包含PE/PB）
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
                
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    'date,close,peTTM,pbMRQ',
                    start_date=start_date,
                    end_date=end_date,
                    frequency='d',
                    adjustflag='3'
                )
                
                data_list = []
                while rs.error_code == '0' and rs.next():
                    data_list.append(rs.get_row_data())
                
                if not data_list:
                    logger.warning(f"⚠️ [BaoStock] 无数据返回: {symbol}, bs_code={bs_code}")
                    return None
                
                # 获取最新有效数据
                latest_valid = None
                for row in reversed(data_list):
                    if row[2] and row[2] != 'None' and row[3] and row[3] != 'None':
                        latest_valid = row
                        break
                
                if not latest_valid:
                    logger.warning(f"⚠️ [BaoStock] 所有数据PE/PB均为空: {symbol}")
                    return None
                
                # 解析数据
                date = latest_valid[0]
                price = float(latest_valid[1]) if latest_valid[1] and latest_valid[1] != 'None' else None
                pe_ttm = float(latest_valid[2]) if latest_valid[2] and latest_valid[2] != 'None' else None
                pb = float(latest_valid[3]) if latest_valid[3] and latest_valid[3] != 'None' else None
                
                if not pe_ttm or not pb:
                    logger.warning(f"⚠️ [BaoStock] PE/PB解析失败: PE={pe_ttm}, PB={pb}")
                    return None
                
                logger.info(f"✅ [BaoStock] 获取成功: {symbol} 日期={date}, 股价={price}元, PE_TTM={pe_ttm:.2f}, PB={pb:.2f}")

                # 计算基本面评分
                fundamental_score = self._calculate_pe_pb_score(pe_ttm, pb)

                # 🔥 方案A：补总市值/流通市值（BaoStock 不返回市值字段，调东财 push2 一次拿两个字段）
                # 东财 push2 接口字段：f117=总市值（元），f85=流通市值（元）
                market_value_data = None
                try:
                    from .providers.china.eastmoney_quote import EastMoneyQuoteProvider
                    market_value_data = EastMoneyQuoteProvider.get_market_value(symbol)
                    if market_value_data:
                        logger.info(
                            f"✅ [BaoStock-补市值] 来源=EastMoney push2: "
                            f"总市值={market_value_data.get('total_mv')}亿元, "
                            f"流通市值={market_value_data.get('circ_mv')}亿元"
                        )
                    else:
                        logger.warning(f"⚠️ [BaoStock-补市值] EastMoney push2 未返回数据: {symbol}")
                except Exception as mv_e:
                    logger.warning(f"⚠️ [BaoStock-补市值] 获取市值失败: {mv_e}")

                # 🔥 广发 Skills 接口：补行业相对估值字段（PE/PB 行业均值、历史百分位）+ 总市值优先层
                # 广发返回的 total_mv 准确度高于东财 push2，作为市值的优先来源
                gf_valuation = None
                try:
                    from .providers.china.gf_quote import GFQuoteProvider
                    gf_valuation = GFQuoteProvider.get_valuation(symbol)
                    if gf_valuation:
                        logger.info(
                            f"✅ [广发-估值] {symbol}: 总市值={gf_valuation.get('total_mv')}亿元, "
                            f"PE_TTM={gf_valuation.get('pe_ttm')}, PE行业均值={gf_valuation.get('pe_ttm_avg')}, "
                            f"PE百分位={gf_valuation.get('pe_ttm_percent')}%, PB={gf_valuation.get('pb')}, "
                            f"PB行业均值={gf_valuation.get('pb_avg')}, PB百分位={gf_valuation.get('pb_percent')}%"
                        )
                    else:
                        logger.warning(f"⚠️ [广发-估值] 未返回数据: {symbol}")
                except Exception as gf_e:
                    logger.warning(f"⚠️ [广发-估值] 获取失败: {gf_e}")

                result = {
                    'pe': f"{pe_ttm:.1f}倍",
                    'pe_ttm': f"{pe_ttm:.1f}倍",
                    'pb': f"{pb:.2f}倍",
                    'price': f"¥{price:.2f}" if price else None,
                    'current_price_numeric': price,
                    'data_source': 'BaoStock',
                    'fundamental_score': fundamental_score,
                    'analysis_date': date,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }

                # 合并市值字段：广发优先，东财兜底
                # 1) 总市值：广发 > 东财
                if gf_valuation and gf_valuation.get('total_mv') and gf_valuation['total_mv'] > 0:
                    result['total_mv'] = f"{gf_valuation['total_mv']:.2f}亿元 (广发)"
                elif market_value_data and market_value_data.get('total_mv') and market_value_data['total_mv'] > 0:
                    result['total_mv'] = f"{market_value_data['total_mv']:.2f}亿元 (实时)"

                # 2) 流通市值：东财 stock/get 的 f85 实测返回错误值（300750 返回 42.57亿，实际应≈15000亿）
                #    改用腾讯 qt.gtimg 的 parts[44] 作为流通市值数据源（2026-07-09 实测验证准确）
                from tradingagents.dataflows.providers.china.eastmoney_quote import TencentQuoteProvider
                tencent_data = None
                try:
                    tencent_data = TencentQuoteProvider.get_market_value(symbol)
                    if tencent_data and tencent_data.get('circ_mv'):
                        circ_mv_tx = tencent_data['circ_mv']
                        if circ_mv_tx > 0:
                            result['circ_mv'] = f"{circ_mv_tx:.2f}亿元 (腾讯实时)"
                            logger.info(f"✅ [BaoStock-补流通市值] 来源=Tencent parts[44]: 流通市值={circ_mv_tx:.2f}亿元")
                except Exception as e_tx:
                    logger.warning(f"⚠️ 腾讯获取流通市值失败: {e_tx}")

                # 东财 total_share 仍可用（总股本数据不影响流通市值正确性）
                if market_value_data and market_value_data.get('total_share'):
                    result['total_share'] = f"{market_value_data['total_share']:.2f}亿股"

                # 3) 行业相对估值字段（广发提供，当前完全缺失的新指标）
                if gf_valuation:
                    if gf_valuation.get('pe_ttm_avg') is not None:
                        result['pe_industry_avg'] = f"{gf_valuation['pe_ttm_avg']:.2f}倍"
                    if gf_valuation.get('pe_ttm_percent') is not None:
                        result['pe_percentile'] = f"{gf_valuation['pe_ttm_percent']:.2f}%"
                    if gf_valuation.get('pb_avg') is not None:
                        result['pb_industry_avg'] = f"{gf_valuation['pb_avg']:.2f}倍"
                    if gf_valuation.get('pb_percent') is not None:
                        result['pb_percentile'] = f"{gf_valuation['pb_percent']:.2f}%"
                    if gf_valuation.get('list_date'):
                        result['list_date'] = gf_valuation['list_date']
                    # 标注市值来源（便于追溯）
                    if 'total_mv' in result and '(广发)' in result['total_mv']:
                        result['market_value_source'] = 'GF-Skills'

                # 🔥 申万一级行业 PE 补充层：多源口径对比 + 同行业可比公司 PE 列表
                # 广发行业 PE 口径可能包含异常 PE 子行业（如电力归到含光伏/新能源发电的全行业）
                # 申万一级 31 个行业分类更稳定，成份股更纯
                sub_industries = None  # 预初始化，避免内部 try 失败时引用未定义变量
                try:
                    sw_data = self._get_sw_industry_valuation(symbol)
                    if sw_data:
                        result['sw_industry_name'] = sw_data['industry_name']
                        result['sw_industry_code'] = sw_data['industry_code']
                        result['sw_industry_pe_ttm'] = f"{sw_data['pe_ttm']:.2f}倍"
                        result['sw_industry_pe_static'] = f"{sw_data['pe_static']:.2f}倍"
                        result['sw_industry_pb'] = f"{sw_data['pb']:.2f}倍"
                        result['sw_industry_dividend_yield'] = f"{sw_data['dividend_yield']:.2f}%"
                        result['sw_industry_constituents'] = sw_data['constituents']
                        logger.info(
                            f"✅ [申万-行业PE] {symbol}: 行业={sw_data['industry_name']}, "
                            f"PE_TTM={sw_data['pe_ttm']:.2f}, PB={sw_data['pb']:.2f}, "
                            f"股息率={sw_data['dividend_yield']:.2f}%, 成份股={sw_data['constituents']}"
                        )

                        # 🔥 申万二级/三级子行业 PE 多层口径
                        # 申万一级"公用事业"过粗，二级"电力"PE_TTM≈18 才是合理基准
                        # 三级"核力发电"PE_TTM≈21 是最精确的同业口径
                        try:
                            sub_industries = self._get_sw_sub_industries(
                                sw_data['industry_code'], sw_data['industry_name']
                            )
                            if sub_industries:
                                # 拼装 markdown 字符串给报告模板直接展示
                                md_lines = []
                                if sub_industries['level2_list']:
                                    md_lines.append(f"**申万二级子行业（{sw_data['industry_name']} 下属）**")
                                    md_lines.append("")
                                    md_lines.append("| 行业代码 | 行业名称 | 成份股 | PE_TTM | PE_静态 | PB | 股息率 |")
                                    md_lines.append("|:--------|:--------|:------:|:------:|:------:|:--:|:------:|")
                                    for r in sub_industries['level2_list']:
                                        md_lines.append(
                                            f"| {r['code']} | {r['name']} | {r['constituents']} | "
                                            f"{r['pe_ttm']:.2f} | {r['pe_static']:.2f} | {r['pb']:.2f} | {r['dividend_yield']:.2f}% |"
                                        )
                                    md_lines.append("")

                                if sub_industries['level3_list_under_power']:
                                    md_lines.append("**申万三级子行业（电力下属，最精确同业口径）**")
                                    md_lines.append("")
                                    md_lines.append("| 行业代码 | 行业名称 | 成份股 | PE_TTM | PE_静态 | PB | 股息率 |")
                                    md_lines.append("|:--------|:--------|:------:|:------:|:------:|:--:|:------:|")
                                    for r in sub_industries['level3_list_under_power']:
                                        md_lines.append(
                                            f"| {r['code']} | {r['name']} | {r['constituents']} | "
                                            f"{r['pe_ttm']:.2f} | {r['pe_static']:.2f} | {r['pb']:.2f} | {r['dividend_yield']:.2f}% |"
                                        )
                                    md_lines.append("")
                                    md_lines.append(
                                        "> 💡 上述为申万二级 \"电力\" 下属的三级子行业 PE 列表，"
                                        f"请结合个股所属细分行业（如 {symbol} 所属的核力/火力/水力/风力/光伏发电）"
                                        "优先参照对应子行业 PE_TTM 作为同业基准"
                                    )

                                if md_lines:
                                    result['sw_sub_industries_md'] = "\n".join(md_lines)
                                    logger.info(
                                        f"✅ [申万-多层] {symbol}: 二级子行业 {len(sub_industries['level2_list'])} 个, "
                                        f"电力下属三级 {len(sub_industries['level3_list_under_power'])} 个"
                                    )
                        except Exception as sub_e:
                            logger.warning(f"⚠️ [申万-二级/三级] 获取失败: {sub_e}")
                except Exception as sw_e:
                    logger.warning(f"⚠️ [申万-行业PE] 获取失败: {sw_e}")

                # 🔥 同行业可比公司 PE 列表（让 LLM 自己判断行业基准是否合理）
                try:
                    peer_list_md = self._get_peer_pe_list(symbol)
                    if peer_list_md:
                        result['peer_pe_list'] = peer_list_md
                except Exception as peer_e:
                    logger.warning(f"⚠️ [可比公司PE列表] 获取失败: {peer_e}")

                return result

            finally:
                bs.logout()
                
        except ImportError:
            logger.error(f"❌ [BaoStock] 模块未安装，请运行: pip install baostock")
            return None
        except Exception as e:
            logger.error(f"❌ [BaoStock] 获取失败: {symbol}, 错误类型: {type(e).__name__}, 错误信息: {e}")
            return None

    # 申万一级行业 → 同行业龙头股映射（用于"同行业可比公司 PE 列表"）
    # 注：申万一级 31 个行业，这里只列常见行业的代表性龙头，其他行业按需扩展
    _SW_INDUSTRY_PEERS = {
        '801160.SI': ['600011', '600027', '600023', '600795', '601991', '601985'],  # 公用事业：华能/华电/浙能/国电/大唐/中国核电
        '801780.SI': ['601398', '601939', '601288', '601988', '600036'],  # 银行
        '801120.SI': ['600519', '000858', '600809', '000568', '002304'],  # 食品饮料（白酒）
        '801790.SI': ['601318', '601628', '600030', '601688', '601601'],  # 非银金融
        '801180.SI': ['000002', '600048', '001979', '600340', '600606'],  # 房地产
        '801110.SI': ['000333', '600690', '000651', '002508', '600690'],  # 家用电器
        '801150.SI': ['600276', '000538', '600436', '300015', '600085'],  # 医药生物
        '801730.SI': ['300750', '002594', '601012', '002129', '600089'],  # 电力设备（新能源）
        '801080.SI': ['688981', '603501', '002049', '600584', '300142'],  # 电子
        '801880.SI': ['600104', '601238', '000625', '601633', '600006'],  # 汽车
        '801050.SI': ['601899', '600547', '601898', '600489', '002460'],  # 有色金属
        '801950.SI': ['601088', '600188', '601225', '600971', '600997'],  # 煤炭
        '801960.SI': ['601857', '600028', '600585', '002493', '600346'],  # 石油石化
        '801040.SI': ['600019', '600010', '000898', '600010', '000709'],  # 钢铁
    }

    def _get_sw_industry_valuation(self, symbol: str) -> Optional[dict]:
        """获取个股所属申万一级行业的 PE/PB/股息率

        实现：
        1. 调用 ak.sw_index_first_info() 拿申万一级 31 个行业的 PE/PB 全表
        2. 通过 ak.stock_individual_info_em 拿个股的"行业"字段（东财行业名）
        3. 用 hardcoded 东财行业名 → 申万一级代码 映射表查找
        4. 返回对应行业的 PE_TTM / PE_静态 / PB / 股息率 / 成份股个数

        失败时返回 None（不影响现有数据）
        """
        import akshare as ak

        # 1) 拿申万一级行业 PE 全表
        try:
            sw_df = ak.sw_index_first_info()
        except Exception as e:
            logger.warning(f"⚠️ [申万] sw_index_first_info 调用失败: {e}")
            return None

        if sw_df is None or len(sw_df) == 0:
            return None

        # 2) 拿个股行业（东财口径）
        industry_name_em = None
        for _ in range(2):
            try:
                info_df = ak.stock_individual_info_em(symbol=symbol)
                if info_df is not None and len(info_df) > 0:
                    row = info_df[info_df['item'] == '行业']
                    if len(row) > 0:
                        industry_name_em = str(row.iloc[0]['value']).strip()
                        break
            except Exception:
                import time
                time.sleep(0.5)
            break

        # 2.1) 兜底：东财接口失败时，用 hardcoded 反向映射表查申万行业
        # 从 _SW_INDUSTRY_PEERS 反向构建"股票代码 → 申万一级代码"映射
        sw_code_from_map = None
        for sw_code, peer_list in self._SW_INDUSTRY_PEERS.items():
            if symbol in peer_list:
                sw_code_from_map = sw_code
                break

        # 如果东财接口失败但 hardcoded 映射命中，直接用 hardcoded 结果
        if not industry_name_em and sw_code_from_map:
            logger.info(f"[申万] 东财接口失败，用 hardcoded 映射: {symbol} → {sw_code_from_map}")
            row = sw_df[sw_df['行业代码'] == sw_code_from_map]
            if len(row) > 0:
                r = row.iloc[0]
                return {
                    'industry_code': sw_code_from_map,
                    'industry_name': str(r['行业名称']),
                    'constituents': int(r['成份个数']),
                    'pe_static': float(r['静态市盈率']) if r['静态市盈率'] is not None else 0.0,
                    'pe_ttm': float(r['TTM(滚动)市盈率']) if r['TTM(滚动)市盈率'] is not None else 0.0,
                    'pb': float(r['市净率']) if r['市净率'] is not None else 0.0,
                    'dividend_yield': float(r['静态股息率']) if r['静态股息率'] is not None else 0.0,
                }

        if not industry_name_em:
            logger.debug(f"[申万] 未拿到 {symbol} 的东财行业名，且不在 hardcoded 映射表里，跳过")
            return None

        # 3) 东财行业名 → 申万一级代码 映射
        sw_code = self._map_em_industry_to_sw(industry_name_em, sw_df)
        if not sw_code:
            logger.debug(f"[申万] 东财行业 '{industry_name_em}' 未找到申万映射，跳过")
            return None

        # 4) 在申万全表里查对应行业
        row = sw_df[sw_df['行业代码'] == sw_code]
        if len(row) == 0:
            return None
        r = row.iloc[0]

        return {
            'industry_code': sw_code,
            'industry_name': str(r['行业名称']),
            'constituents': int(r['成份个数']),
            'pe_static': float(r['静态市盈率']) if r['静态市盈率'] is not None else 0.0,
            'pe_ttm': float(r['TTM(滚动)市盈率']) if r['TTM(滚动)市盈率'] is not None else 0.0,
            'pb': float(r['市净率']) if r['市净率'] is not None else 0.0,
            'dividend_yield': float(r['静态股息率']) if r['静态股息率'] is not None else 0.0,
        }

    def _get_sw_sub_industries(self, sw_level1_code: str, sw_level1_name: str) -> Optional[dict]:
        """🔥 获取申万一级下所有二级子行业 + 电力子行业下的三级子行业 PE 多层口径

        Args:
            sw_level1_code: 申万一级代码，如 '801160.SI'
            sw_level1_name: 申万一级名称，如 '公用事业'

        Returns:
            {
                'level2_list': [{code, name, parent, constituents, pe_ttm, pe_static, pb, dividend_yield}, ...],
                'level3_list_under_power': [{code, name, parent, constituents, pe_ttm, pe_static, pb, dividend_yield}, ...],
            }
            level3_list_under_power 是申万二级"电力"下属的所有三级子行业
            (适用于电力股、热力股等公用事业子类)

        失败时返回 None
        """
        import akshare as ak

        result = {'level2_list': [], 'level3_list_under_power': []}

        # 1) 拿申万二级行业全表
        try:
            sw2_df = ak.sw_index_second_info()
        except Exception as e:
            logger.warning(f"⚠️ [申万-二级] sw_index_second_info 调用失败: {e}")
            return None

        if sw2_df is None or len(sw2_df) == 0:
            return None

        # 2) 过滤出"上级行业=申万一级名称"的所有二级子行业
        level2_rows = sw2_df[sw2_df['上级行业'] == sw_level1_name]
        for _, r in level2_rows.iterrows():
            result['level2_list'].append({
                'code': str(r['行业代码']),
                'name': str(r['行业名称']),
                'parent': str(r['上级行业']),
                'constituents': int(r['成份个数']) if r['成份个数'] is not None else 0,
                'pe_static': float(r['静态市盈率']) if r['静态市盈率'] is not None else 0.0,
                'pe_ttm': float(r['TTM(滚动)市盈率']) if r['TTM(滚动)市盈率'] is not None else 0.0,
                'pb': float(r['市净率']) if r['市净率'] is not None else 0.0,
                'dividend_yield': float(r['静态股息率']) if r['静态股息率'] is not None else 0.0,
            })

        # 3) 拿申万三级行业全表，过滤出"上级行业=电力"的所有三级子行业
        # 电力股通常归申万二级"电力"下，包括：火电/水电/核电/风电/光伏/热力/其他能源发电/电能综合服务
        try:
            sw3_df = ak.sw_index_third_info()
        except Exception as e:
            logger.warning(f"⚠️ [申万-三级] sw_index_third_info 调用失败: {e}")
            return result  # 二级数据已有，三级失败不影响

        if sw3_df is None or len(sw3_df) == 0:
            return result

        # "电力"是申万二级下的固定名称
        level3_rows = sw3_df[sw3_df['上级行业'] == '电力']
        for _, r in level3_rows.iterrows():
            result['level3_list_under_power'].append({
                'code': str(r['行业代码']),
                'name': str(r['行业名称']),
                'parent': str(r['上级行业']),
                'constituents': int(r['成份个数']) if r['成份个数'] is not None else 0,
                'pe_static': float(r['静态市盈率']) if r['静态市盈率'] is not None else 0.0,
                'pe_ttm': float(r['TTM(滚动)市盈率']) if r['TTM(滚动)市盈率'] is not None else 0.0,
                'pb': float(r['市净率']) if r['市净率'] is not None else 0.0,
                'dividend_yield': float(r['静态股息率']) if r['静态股息率'] is not None else 0.0,
            })

        return result

    def _map_em_industry_to_sw(self, em_name: str, sw_df) -> Optional[str]:
        """东财行业名 → 申万一级代码 映射

        优先用名称包含匹配（如东财"电力行业" → 申万"公用事业"）
        """
        # 简化映射表：东财行业名关键词 → 申万一级代码
        # 申万 31 个一级代码已通过 sw_index_first_info 拿到
        keyword_map = {
            '电力': '801160.SI',  # 公用事业
            '燃气': '801160.SI',
            '水务': '801160.SI',
            '环保': '801160.SI',
            '银行': '801780.SI',
            '保险': '801790.SI',
            '证券': '801790.SI',
            '白酒': '801120.SI',
            '食品': '801120.SI',
            '饮料': '801120.SI',
            '家电': '801110.SI',
            '医药': '801150.SI',
            '生物': '801150.SI',
            '医疗': '801150.SI',
            '电池': '801730.SI',
            '光伏': '801730.SI',
            '新能源': '801730.SI',
            '半导体': '801080.SI',
            '芯片': '801080.SI',
            '电子': '801080.SI',
            '汽车': '801880.SI',
            '有色': '801050.SI',
            '煤炭': '801950.SI',
            '石油': '801960.SI',
            '石化': '801960.SI',
            '钢铁': '801040.SI',
            '房地产': '801180.SI',
            '地产': '801180.SI',
            '计算机': '801750.SI',
            '软件': '801750.SI',
            '通信': '801770.SI',
            '传媒': '801760.SI',
            '军工': '801740.SI',
            '国防': '801740.SI',
            '农业': '801010.SI',
            '化工': '801030.SI',
            '建材': '801710.SI',
            '建筑': '801720.SI',
            '机械': '801890.SI',
            '交通运输': '801170.SI',
            '商贸': '801200.SI',
            '社会服务': '801210.SI',
            '纺织': '801130.SI',
            '轻工': '801140.SI',
            '美容': '801980.SI',
            '环保': '801970.SI',
        }

        for kw, sw_code in keyword_map.items():
            if kw in em_name:
                return sw_code

        # 兜底：直接在申万表里查名称完全匹配
        row = sw_df[sw_df['行业名称'] == em_name]
        if len(row) > 0:
            return str(row.iloc[0]['行业代码'])

        return None

    def _get_peer_pe_list(self, symbol: str) -> Optional[str]:
        """获取同行业可比公司 PE/PB 列表（markdown 字符串）

        实现：
        1. 先拿申万一级代码
        2. 从 hardcoded 龙头股映射表拿同行业 3-5 只龙头
        3. 对每只龙头调广发 API get_valuation 拿 PE_TTM / PB / 总市值
        4. 组装成 markdown 表格字符串

        失败时返回 None
        """
        # 1) 拿申万一级代码（复用 _get_sw_industry_valuation 的逻辑）
        sw_data = self._get_sw_industry_valuation(symbol)
        if not sw_data:
            return None

        sw_code = sw_data['industry_code']
        sw_name = sw_data['industry_name']

        # 2) 拿同行业龙头股
        peer_codes = self._SW_INDUSTRY_PEERS.get(sw_code, [])
        if not peer_codes:
            logger.debug(f"[可比公司] 申万行业 {sw_code} 无龙头股映射，跳过")
            return None

        # 把目标股票本身也加进去
        all_codes = [symbol] + [c for c in peer_codes if c != symbol]

        # 3) 对每只调广发 API 拿估值
        from .providers.china.gf_quote import GFQuoteProvider
        rows = []
        for code in all_codes:
            try:
                val = GFQuoteProvider.get_valuation(code)
                if val:
                    name = val.get('name') or code
                    rows.append({
                        'code': code,
                        'name': name,
                        'pe_ttm': val.get('pe_ttm'),
                        'pb': val.get('pb'),
                        'total_mv': val.get('total_mv'),
                    })
            except Exception:
                continue

        if not rows:
            return None

        # 4) 组装 markdown 表格
        md_lines = [
            f"**所属申万一级行业**: {sw_name} ({sw_code})，成份股 {sw_data['constituents']} 只",
            "",
            "| 代码 | 名称 | PE_TTM | PB | 总市值(亿) |",
            "|:----|:----|:------:|:--:|:--------:|",
        ]
        for r in rows:
            pe_str = f"{r['pe_ttm']:.2f}" if r['pe_ttm'] is not None else "N/A"
            pb_str = f"{r['pb']:.2f}" if r['pb'] is not None else "N/A"
            mv_str = f"{r['total_mv']:.1f}" if r['total_mv'] is not None else "N/A"
            md_lines.append(f"| {r['code']} | {r['name']} | {pe_str} | {pb_str} | {mv_str} |")

        # 加一行行业 PE 中位数
        pe_vals = [r['pe_ttm'] for r in rows if r['pe_ttm'] is not None]
        if pe_vals:
            pe_sorted = sorted(pe_vals)
            median_pe = pe_sorted[len(pe_sorted) // 2]
            md_lines.append("")
            md_lines.append(f"**同行业 PE_TTM 中位数**: {median_pe:.2f} 倍（含目标公司）")
            md_lines.append(f"**申万行业 PE_TTM**: {sw_data['pe_ttm']:.2f} 倍")

        return "\n".join(md_lines)

    def _calculate_pe_pb_score(self, pe_ttm: float, pb: float) -> float:
        """
        🔥 根据PE/PB计算基本面评分
        
        Args:
            pe_ttm: 市盈率（TTM）
            pb: 市净率
        
        Returns:
            float: 评分结果（0-10分）
        """
        # 基于PE/PB的量化评分逻辑
        # PE评分（满分5分）
        if pe_ttm < 10:
            pe_score = 5.0  # 极低估值
        elif pe_ttm < 20:
            pe_score = 4.5  # 低估
        elif pe_ttm < 30:
            pe_score = 4.0  # 合理偏低
        elif pe_ttm < 40:
            pe_score = 3.5  # 合理
        elif pe_ttm < 50:
            pe_score = 3.0  # 偏高
        elif pe_ttm < 60:
            pe_score = 2.5  # 高估
        else:
            pe_score = 2.0  # 极高估
        
        # PB评分（满分5分）
        if pb < 1:
            pb_score = 5.0  # 极低估值
        elif pb < 2:
            pb_score = 4.5  # 低估
        elif pb < 3:
            pb_score = 4.0  # 合理偏低
        elif pb < 4:
            pb_score = 3.5  # 合理
        elif pb < 5:
            pb_score = 3.0  # 偏高
        else:
            pb_score = 2.5  # 高估
        
        # 综合评分
        total_score = (pe_score + pb_score) / 2
        return round(total_score, 1)

    def _get_real_financial_metrics(self, symbol: str, price_value: float) -> dict:
        """获取真实财务指标 - 直接走 API（MongoDB 缓存已禁用）"""
        try:
            # 🚫 项目策略：完全不用 MongoDB 缓存，直接走 API
            #    传入的 price_value 来自 BaoStock 实时股价，已经是最新价，无需再查 market_quotes
            logger.info(f"🔄 [跳过MongoDB] 直接从API获取{symbol}财务数据，股价: {price_value}元")

            # 第一优先级：从AKShare API获取
            from .providers.china.akshare import get_akshare_provider
            import asyncio

            akshare_provider = get_akshare_provider()

            if akshare_provider.connected:
                # AKShare的get_financial_data是异步方法，需要使用asyncio运行
                loop = asyncio.get_event_loop()
                financial_data = loop.run_until_complete(akshare_provider.get_financial_data(symbol))

                if financial_data and any(not v.empty if hasattr(v, 'empty') else bool(v) for v in financial_data.values()):
                    logger.info(f"✅ AKShare财务数据获取成功: {symbol}")
                    # 获取股票基本信息（也是异步方法）
                    stock_info = loop.run_until_complete(akshare_provider.get_stock_basic_info(symbol))

                    # 解析AKShare财务数据
                    logger.debug(f"🔧 调用AKShare解析函数，股价: {price_value}")
                    metrics = self._parse_akshare_financial_data(financial_data, stock_info, price_value)
                    logger.debug(f"🔧 AKShare解析结果: {metrics}")
                    if metrics:
                        logger.info(f"✅ AKShare解析成功，返回指标")
                        # 缓存原始财务数据到数据库（而不是解析后的指标）
                        self._cache_raw_financial_data(symbol, financial_data, stock_info)
                        return self._supplement_with_gf_indicators(metrics, symbol)
                    else:
                        logger.warning(f"⚠️ AKShare解析失败，返回None")
                else:
                    logger.warning(f"⚠️ AKShare未获取到{symbol}财务数据，尝试Tushare")
            else:
                logger.warning(f"⚠️ AKShare未连接，尝试Tushare")

            # 第三优先级：使用Tushare数据源
            logger.info(f"🔄 使用Tushare备用数据源获取{symbol}财务数据")
            from .providers.china.tushare import get_tushare_provider
            import asyncio

            provider = get_tushare_provider()
            if not provider.connected:
                logger.debug(f"Tushare未连接，无法获取{symbol}真实财务数据")
                return None

            # 获取财务数据（异步方法）
            loop = asyncio.get_event_loop()
            financial_data = loop.run_until_complete(provider.get_financial_data(symbol))
            if not financial_data:
                logger.debug(f"未获取到{symbol}的财务数据")
                return None

            # 获取股票基本信息（异步方法）
            stock_info = loop.run_until_complete(provider.get_stock_basic_info(symbol))

            # 解析Tushare财务数据
            metrics = self._parse_financial_data(financial_data, stock_info, price_value)
            if metrics:
                # 缓存原始财务数据到数据库
                self._cache_raw_financial_data(symbol, financial_data, stock_info)
                return self._supplement_with_gf_indicators(metrics, symbol)

        except Exception as e:
            logger.debug(f"获取{symbol}真实财务数据失败: {e}")

        # 🔥 兜底：广发 Skills 工具2（compare_indicator_post）
        # 当 MongoDB/AKShare/Tushare 三表全部失败时，用广发接口拿财务指标 5 大维度
        # 优点：返回精炼的指标摘要，无需解析三表原始数据
        # 限制：必须传2只股票，会用行业映射表选同业对比股
        try:
            from .providers.china.gf_quote import GFQuoteProvider
            from datetime import datetime as _dt
            import time as _time
            now = _dt.now()
            y = now.year
            # 报告期 fallback 顺序：当年最近报告期 → 上一年年报 → 上一年三季报 → 上一年中报
            # 注意：广发工具2 对未披露的报告期返回空，需要按顺序 fallback
            report_periods = []
            if now.month <= 4:
                report_periods.append((str(y - 1), 12))  # 上一年年报
            elif now.month <= 8:
                report_periods.append((str(y), 1))  # 当年一季报
                report_periods.append((str(y - 1), 12))  # 兜底：上一年年报
            elif now.month <= 10:
                report_periods.append((str(y), 6))  # 当年中报
                report_periods.append((str(y), 1))  # 兜底：当年一季报
            else:
                report_periods.append((str(y), 9))  # 当年三季报
                report_periods.append((str(y), 6))  # 兜底：当年中报
            report_periods.append((str(y - 1), 12))  # 上一年年报
            report_periods.append((str(y - 1), 9))  # 上一年三季报

            # 去重（保持顺序）
            seen = set()
            unique_periods = []
            for p in report_periods:
                if p not in seen:
                    seen.add(p)
                    unique_periods.append(p)

            logger.info(f"🔄 [广发-兜底] 三表全部失败，尝试用广发工具2获取 {symbol} 财务指标 "
                        f"(候选报告期: {unique_periods})")
            gf_indicators = None
            used_period = None
            for gf_year, gf_report_type in unique_periods:
                gf_indicators = GFQuoteProvider.get_financial_indicators(symbol, gf_year, gf_report_type)
                if gf_indicators:
                    used_period = (gf_year, gf_report_type)
                    break
                _time.sleep(0.2)

            if gf_indicators:
                rt_name = {1: '一季报', 6: '中报', 9: '三季报', 12: '年报'}.get(
                    used_period[1] if used_period else None, '?'
                )
                logger.info(f"✅ [广发-兜底] 获取成功: {symbol}, "
                            f"报告期: {used_period[0] if used_period else '?'} {rt_name}, "
                            f"字段数={len(gf_indicators)}")
                metrics = self._parse_gf_financial_indicators(gf_indicators, price_value)
                if metrics and used_period:
                    rt_name = {1: '一季报', 6: '中报', 9: '三季报', 12: '年报'}.get(used_period[1], '?')
                    metrics['supplementary_source'] = f'GF-Skills compare_indicator_post ({used_period[0]} {rt_name})'
                return metrics
            else:
                logger.warning(f"⚠️ [广发-兜底] 所有报告期均未返回数据: {symbol}")
        except Exception as gf_e:
            logger.warning(f"⚠️ [广发-兜底] 获取财务指标失败: {gf_e}")

        return None

    def _parse_gf_financial_indicators(self, gf_data: dict, price_value: float) -> dict:
        """解析广发工具2返回的财务指标为 metrics 字典

        广发返回的指标已经是精炼摘要，直接映射到现有 metrics 字段名。
        """
        metrics = {
            'data_source': 'GF-Skills',
            'price': f"¥{price_value:.2f}" if price_value else None,
            'current_price_numeric': price_value,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # 盈利能力
        if gf_data.get('roe') is not None:
            metrics['roe'] = f"{float(gf_data['roe']):.2f}%"
        if gf_data.get('net_profit2totalincome') is not None:
            metrics['net_margin'] = f"{float(gf_data['net_profit2totalincome']):.2f}%"
        if gf_data.get('sale_gross_rate') is not None:
            metrics['gross_margin'] = f"{float(gf_data['sale_gross_rate']):.2f}%"

        # 资本结构/财务健康度
        if gf_data.get('liablity2asset') is not None:
            metrics['debt_ratio'] = f"{float(gf_data['liablity2asset']):.2f}%"
        if gf_data.get('equity2asset') is not None:
            metrics['equity_ratio'] = f"{float(gf_data['equity2asset']):.2f}%"
        if gf_data.get('quick_ratio') is not None:
            metrics['quick_ratio'] = f"{float(gf_data['quick_ratio']):.2f}"

        # 现金流
        if gf_data.get('cashflow_oper2income') is not None:
            metrics['cashflow_income_ratio'] = f"{float(gf_data['cashflow_oper2income']):.2f}"
        if gf_data.get('net_cashflow_oper2net_profit') is not None:
            metrics['cashflow_profit_ratio'] = f"{float(gf_data['net_cashflow_oper2net_profit']):.2f}"
        if gf_data.get('net_cashflow_oper_ps') is not None:
            metrics['ocf_per_share'] = f"{float(gf_data['net_cashflow_oper_ps']):.2f}元"

        # 成长性
        if gf_data.get('operate_income_yoy') is not None:
            metrics['revenue_yoy'] = f"{float(gf_data['operate_income_yoy']):.2f}%"
        if gf_data.get('net_profit_yoy') is not None:
            metrics['net_profit_yoy'] = f"{float(gf_data['net_profit_yoy']):.2f}%"
        if gf_data.get('total_asset_yoy') is not None:
            metrics['asset_yoy'] = f"{float(gf_data['total_asset_yoy']):.2f}%"
        if gf_data.get('equity_growth_rate') is not None:
            metrics['equity_yoy'] = f"{float(gf_data['equity_growth_rate']):.2f}%"

        # 运营效率
        if gf_data.get('inventory_turnover') is not None:
            metrics['inventory_turnover'] = f"{float(gf_data['inventory_turnover']):.2f}次"
        if gf_data.get('acctreceivable_turnover') is not None:
            metrics['receivables_turnover'] = f"{float(gf_data['acctreceivable_turnover']):.2f}次"
        if gf_data.get('totalasset_turnover') is not None:
            metrics['asset_turnover'] = f"{float(gf_data['totalasset_turnover']):.2f}次"

        # 其他
        if gf_data.get('goodwill2equity') is not None:
            metrics['goodwill_ratio'] = f"{float(gf_data['goodwill2equity']):.2f}%"
        if gf_data.get('interest_coverage_ratio') is not None:
            metrics['interest_coverage'] = f"{float(gf_data['interest_coverage_ratio']):.2f}"
        if gf_data.get('end_date'):
            metrics['report_date'] = gf_data['end_date']
        if gf_data.get('peer_stock_name'):
            metrics['peer_stock'] = gf_data['peer_stock_name']

        logger.info(f"✅ [广发-解析] 解析完成，共 {len(metrics)} 个字段")
        return metrics

    def _supplement_with_gf_indicators(self, metrics: dict, symbol: str) -> dict:
        """🔥 广发补充层：用广发工具2 补充 metrics 里缺失或 N/A 的财务字段

        策略：
        - 不覆盖 metrics 里已有的有效字段（非 N/A、非空）
        - 只补充 metrics 里缺失或为 "N/A" 的字段
        - 即使 AKShare/Tushare 已拿到部分数据，也调一次广发工具2 补齐缺失项

        补充字段（来自广发 compare_indicator_post）：
        - 盈利：roe / net_margin / gross_margin
        - 资本结构：debt_ratio / equity_ratio / quick_ratio
        - 现金流：cashflow_income_ratio / cashflow_profit_ratio / ocf_per_share
        - 成长性：revenue_yoy / net_profit_yoy / asset_yoy / equity_yoy
        - 运营效率：inventory_turnover / receivables_turnover / asset_turnover
        - 其他：goodwill_ratio / interest_coverage / report_date / peer_stock
        """
        if not metrics:
            return metrics

        # 1) 收集 metrics 里缺失或 N/A 的字段
        missing_keys = []
        for k, v in metrics.items():
            if v is None or v == "N/A" or v == "" or (isinstance(v, str) and v.strip() in ("N/A", "")):
                missing_keys.append(k)

        # 即使没有缺失字段，也尝试拿成长性/周转率等"现有 metrics 通常不包含"的字段
        # 这些字段是广发工具2 独有的补充项，不在 AKShare/Tushare 解析结果里
        gf_only_fields = [
            'cashflow_income_ratio', 'cashflow_profit_ratio', 'ocf_per_share',
            'revenue_yoy', 'net_profit_yoy', 'asset_yoy', 'equity_yoy',
            'inventory_turnover', 'receivables_turnover', 'asset_turnover',
            'goodwill_ratio', 'interest_coverage', 'report_date', 'peer_stock',
        ]
        for f in gf_only_fields:
            if f not in metrics:
                missing_keys.append(f)

        if not missing_keys:
            return metrics  # 无缺失，无需补充

        # 2) 调广发工具2 拿补充数据
        # 报告期 fallback 顺序：当年最近报告期 → 上一年年报 → 上一年三季报 → 上一年中报
        try:
            from .providers.china.gf_quote import GFQuoteProvider
            from datetime import datetime as _dt
            now = _dt.now()
            y = now.year
            # 按"最近披露"优先级排列：当年一季报 → 上一年年报 → 上一年三季报 → 上一年中报
            # 注意：广发工具2 对未披露的报告期返回空，需要按顺序 fallback
            report_periods = []
            if now.month <= 4:
                report_periods.append((str(y - 1), 12))  # 上一年年报
            elif now.month <= 8:
                report_periods.append((str(y), 1))  # 当年一季报
                report_periods.append((str(y - 1), 12))  # 兜底：上一年年报
            elif now.month <= 10:
                report_periods.append((str(y), 6))  # 当年中报
                report_periods.append((str(y), 1))  # 兜底：当年一季报
            else:
                report_periods.append((str(y), 9))  # 当年三季报
                report_periods.append((str(y), 6))  # 兜底：当年中报
            # 再加几个明确的 fallback
            report_periods.append((str(y - 1), 12))  # 上一年年报
            report_periods.append((str(y - 1), 9))  # 上一年三季报

            # 去重（保持顺序）
            seen = set()
            unique_periods = []
            for p in report_periods:
                if p not in seen:
                    seen.add(p)
                    unique_periods.append(p)

            gf_data = None
            used_period = None
            for gf_year, gf_report_type in unique_periods:
                gf_data = GFQuoteProvider.get_financial_indicators(symbol, gf_year, gf_report_type)
                if gf_data:
                    used_period = (gf_year, gf_report_type)
                    logger.debug(f"[广发-补充] {symbol} 命中报告期 year={gf_year}, report_type={gf_report_type}")
                    break
                # 节流，避免连续高频请求
                import time as _time
                _time.sleep(0.2)

            if not gf_data:
                logger.debug(f"[广发-补充] {symbol} 所有报告期均未返回数据，跳过补充")
                return metrics

            gf_metrics = self._parse_gf_financial_indicators(gf_data, 0.0)
            if not gf_metrics:
                return metrics

            # 3) 只补充缺失或 N/A 的字段（不覆盖已有数据）
            supplemented = 0
            for k, v in gf_metrics.items():
                if k in ('data_source', 'price', 'current_price_numeric', 'updated_at'):
                    continue
                # 当前 metrics 里该字段为空/N/A 或不存在 → 补充
                current = metrics.get(k)
                if current is None or current == "N/A" or current == "":
                    if v is not None and v != "N/A" and v != "":
                        metrics[k] = v
                        supplemented += 1

            if supplemented > 0:
                # 标注实际命中的报告期（便于追溯）
                if used_period:
                    used_y, used_rt = used_period
                    rt_name = {1: '一季报', 6: '中报', 9: '三季报', 12: '年报'}.get(used_rt, '?')
                    metrics['supplementary_source'] = f'GF-Skills compare_indicator_post ({used_y} {rt_name})'
                else:
                    metrics['supplementary_source'] = 'GF-Skills compare_indicator_post'
                logger.info(
                    f"✅ [广发-补充] {symbol} 补充 {supplemented} 个缺失字段 "
                    f"(报告期: {used_period}), "
                    f"字段: {[k for k in gf_metrics if k in metrics and metrics[k] != 'N/A' and k not in ('data_source','price','updated_at','supplementary_source')][:8]}..."
                )
        except Exception as e:
            logger.warning(f"⚠️ [广发-补充] {symbol} 补充失败: {e}")

        return metrics

    def _parse_mongodb_financial_data(self, financial_data: dict, price_value: float) -> dict:
        """解析 MongoDB 标准化的财务数据为指标"""
        try:
            logger.debug(f"📊 [财务数据] 开始解析 MongoDB 财务数据，包含字段: {list(financial_data.keys())}")

            metrics = {}

            # MongoDB 的 financial_data 是扁平化的结构，直接包含所有财务指标
            # 不再是嵌套的 {balance_sheet, income_statement, ...} 结构

            # 直接从 financial_data 中提取指标
            latest_indicators = financial_data

            # ROE - 净资产收益率 (添加范围验证)
            roe = latest_indicators.get('roe') or latest_indicators.get('roe_waa')
            if roe is not None and str(roe) != 'nan' and roe != '--':
                try:
                    roe_val = float(roe)
                    # ROE 通常在 -100% 到 100% 之间，极端情况可能超出
                    if -200 <= roe_val <= 200:
                        metrics["roe"] = f"{roe_val:.1f}%"
                    else:
                        logger.warning(f"⚠️ ROE 数据异常: {roe_val}，超出合理范围 [-200%, 200%]，设为 N/A")
                        metrics["roe"] = "N/A"
                except (ValueError, TypeError):
                    metrics["roe"] = "N/A"
            else:
                metrics["roe"] = "N/A"

            # ROA - 总资产收益率 (添加范围验证)
            roa = latest_indicators.get('roa') or latest_indicators.get('roa2')
            if roa is not None and str(roa) != 'nan' and roa != '--':
                try:
                    roa_val = float(roa)
                    # ROA 通常在 -50% 到 50% 之间
                    if -100 <= roa_val <= 100:
                        metrics["roa"] = f"{roa_val:.1f}%"
                    else:
                        logger.warning(f"⚠️ ROA 数据异常: {roa_val}，超出合理范围 [-100%, 100%]，设为 N/A")
                        metrics["roa"] = "N/A"
                except (ValueError, TypeError):
                    metrics["roa"] = "N/A"
            else:
                metrics["roa"] = "N/A"

            # 毛利率 - 添加范围验证
            gross_margin = latest_indicators.get('gross_margin')
            if gross_margin is not None and str(gross_margin) != 'nan' and gross_margin != '--':
                try:
                    gross_margin_val = float(gross_margin)
                    # 验证范围：毛利率应该在 -100% 到 100% 之间
                    # 如果超出范围，可能是数据错误（如存储的是绝对金额而不是百分比）
                    if -100 <= gross_margin_val <= 100:
                        metrics["gross_margin"] = f"{gross_margin_val:.1f}%"
                    else:
                        logger.warning(f"⚠️ 毛利率数据异常: {gross_margin_val}，超出合理范围 [-100%, 100%]，设为 N/A")
                        metrics["gross_margin"] = "N/A"
                except (ValueError, TypeError):
                    metrics["gross_margin"] = "N/A"
            else:
                metrics["gross_margin"] = "N/A"

            # 净利率 - 添加范围验证
            net_margin = latest_indicators.get('netprofit_margin')
            if net_margin is not None and str(net_margin) != 'nan' and net_margin != '--':
                try:
                    net_margin_val = float(net_margin)
                    # 验证范围：净利率应该在 -100% 到 100% 之间
                    if -100 <= net_margin_val <= 100:
                        metrics["net_margin"] = f"{net_margin_val:.1f}%"
                    else:
                        logger.warning(f"⚠️ 净利率数据异常: {net_margin_val}，超出合理范围 [-100%, 100%]，设为 N/A")
                        metrics["net_margin"] = "N/A"
                except (ValueError, TypeError):
                    metrics["net_margin"] = "N/A"
            else:
                metrics["net_margin"] = "N/A"

            # 计算 PE/PB - 降级链（按数据准确性从高到低）
            # 同时获取 PE 和 PE_TTM 两个指标
            pe_value = None
            pe_ttm_value = None
            pb_value = None
            is_loss_stock = False  # 🔥 标记是否为亏损股
            # 修复：_parse_mongodb_financial_data 没有 symbol 参数，从 financial_data 取
            code6 = (
                financial_data.get("code")
                or financial_data.get("symbol", "").replace(".SZ", "").replace(".SH", "")
            ).zfill(6) if (
                financial_data.get("code") or financial_data.get("symbol")
            ) else ""

            # 🔥 第 1 层：stock_basic_info 静态（Tushare daily_basic 官方静态）— 最准
            pe_static = latest_indicators.get('pe')
            pe_ttm_static = latest_indicators.get('pe_ttm')
            pb_static = latest_indicators.get('pb')
            if pe_ttm_static is not None and pe_ttm_static > 0 and str(pe_ttm_static) != 'nan' and pe_ttm_static != '--':
                pe_ttm_value = float(pe_ttm_static)
                metrics["pe_ttm"] = f"{pe_ttm_value:.2f}倍"
                logger.info(f"✅ [PE_TTM-第1层成功] 来自 stock_basic_info: {pe_ttm_value}倍")
            if pe_static is not None and pe_static > 0 and str(pe_static) != 'nan' and pe_static != '--':
                pe_value = float(pe_static)
                metrics["pe"] = f"{pe_value:.2f}倍"
                logger.info(f"✅ [PE-第1层成功] 来自 stock_basic_info: {pe_value}倍")
            if pb_static is not None and pb_static > 0 and str(pb_static) != 'nan' and pb_static != '--':
                pb_value = float(pb_static)
                metrics["pb"] = f"{pb_value:.2f}倍"
                logger.info(f"✅ [PB-第1层成功] 来自 stock_basic_info: {pb_value}倍")

            # 🔥 第 2 层：BaoStock（独立数据源、含 PE/PB）
            if not metrics.get("pe") or not metrics.get("pb"):
                try:
                    baostock_metrics = self._get_baostock_pe_pb(code6)
                    if baostock_metrics:
                        if not metrics.get("pe") and baostock_metrics.get("pe"):
                            pe_value = baostock_metrics["pe"]
                            metrics["pe"] = f"{pe_value:.2f}倍"
                            logger.info(f"✅ [PE-第2层成功] 来自 BaoStock: {pe_value}倍")
                        if not metrics.get("pe_ttm") and baostock_metrics.get("pe_ttm"):
                            pe_ttm_value = baostock_metrics["pe_ttm"]
                            metrics["pe_ttm"] = f"{pe_ttm_value:.2f}倍"
                            logger.info(f"✅ [PE_TTM-第2层成功] 来自 BaoStock: {pe_ttm_value}倍")
                        if not metrics.get("pb") and baostock_metrics.get("pb"):
                            pb_value = baostock_metrics["pb"]
                            metrics["pb"] = f"{pb_value:.2f}倍"
                            logger.info(f"✅ [PB-第2层成功] 来自 BaoStock: {pb_value}倍")
                except Exception as e:
                    logger.warning(f"⚠️ [BaoStock-第2层异常] {e}")

            # 🔥 第 3 层：腾讯 qt.gtimg（轻量级、含 PE_TTM/PB）
            if not metrics.get("pe_ttm") or not metrics.get("pb"):
                try:
                    from tradingagents.dataflows.providers.china.eastmoney_quote import TencentQuoteProvider
                    tx_quote = TencentQuoteProvider.get_market_value(code6)
                    if tx_quote:
                        if not metrics.get("pe_ttm") and tx_quote.get("pe_ttm"):
                            pe_ttm_value = tx_quote["pe_ttm"]
                            metrics["pe_ttm"] = f"{pe_ttm_value:.2f}倍"
                            logger.info(f"✅ [PE_TTM-第3层成功] 来自 Tencent: {pe_ttm_value}倍")
                        if not metrics.get("pb") and tx_quote.get("pb"):
                            pb_value = tx_quote["pb"]
                            metrics["pb"] = f"{pb_value:.2f}倍"
                            logger.info(f"✅ [PB-第3层成功] 来自 Tencent: {pb_value}倍")
                except Exception as e:
                    logger.warning(f"⚠️ [Tencent-第3层异常] {e}")

            # 🔥 第 4 层：东财 push2（可能被风控、含动态 PE/PB）
            if not metrics.get("pe") or not metrics.get("pb"):
                try:
                    from tradingagents.dataflows.providers.china.eastmoney_quote import EastMoneyQuoteProvider
                    em_quote = EastMoneyQuoteProvider.get_market_value(code6)
                    if em_quote:
                        if not metrics.get("pe") and em_quote.get("pe_dynamic"):
                            pe_value = em_quote["pe_dynamic"]
                            metrics["pe"] = f"{pe_value:.2f}倍"
                            logger.info(f"✅ [PE-第4层成功] 来自 EastMoney: {pe_value}倍")
                        if not metrics.get("pb") and em_quote.get("pb"):
                            pb_value = em_quote["pb"]
                            metrics["pb"] = f"{pb_value:.2f}倍"
                            logger.info(f"✅ [PB-第4层成功] 来自 EastMoney: {pb_value}倍")
                except Exception as e:
                    logger.warning(f"⚠️ [EastMoney-第4层异常] {e}")

            # 如果前 4 层都拿到了 PE/PB，提前返回（避免被后续降级逻辑重写）
            if metrics.get("pe") and metrics.get("pe_ttm") and metrics.get("pb"):
                logger.info(f"✅ [PE/PB] 前 4 层完整命中，跳过 MongoDB 动态计算和后续降级")
                return metrics
            elif metrics.get("pe") and metrics.get("pe_ttm") and not metrics.get("pb"):
                logger.info(f"⚠️ [PE/PB] PE/PE_TTM 已拿到，PB 缺失，继续 MongoDB 动态补 PB")
            elif not metrics.get("pe") and not metrics.get("pe_ttm") and metrics.get("pb"):
                logger.info(f"⚠️ [PE/PB] PB 已拿到，PE 缺失，继续 MongoDB 动态补 PE")
            else:
                logger.info(f"⚠️ [PE/PB] 前 4 层不完整，降级到 MongoDB 动态计算")

            # 🔥 第 5 层（兜底）：MongoDB 动态计算（实时股价 × TTM 净利润）
            # 注意：依赖 TTM 季度数据，对亏损股/重组股不可靠，仅作为最后兜底
            try:
                # 优先使用实时计算
                from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback
                from tradingagents.config.database_manager import get_database_manager

                db_manager = get_database_manager()
                if db_manager.is_mongodb_available():
                    client = db_manager.get_mongodb_client()
                    # 从symbol中提取股票代码
                    stock_code = code6 or latest_indicators.get('code') or latest_indicators.get('symbol', '').replace('.SZ', '').replace('.SH', '')

                    logger.info(f"📊 [PE计算] 开始计算股票 {stock_code} 的PE/PB")

                    if stock_code:
                        logger.info(f"📊 [PE计算-第1层] 尝试实时计算 PE/PB (股票代码: {stock_code})")

                        # 获取实时PE/PB
                        realtime_metrics = get_pe_pb_with_fallback(stock_code, client)

                        if realtime_metrics:
                            # 获取市值数据（优先保存）
                            market_cap = realtime_metrics.get('market_cap')
                            if market_cap is not None and market_cap > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["total_mv"] = f"{market_cap:.2f}亿元{realtime_tag}"
                                logger.info(f"✅ [总市值获取成功] 总市值={market_cap:.2f}亿元 | 实时={is_realtime}")

                            # 使用实时PE（动态市盈率）
                            pe_value = realtime_metrics.get('pe')
                            if pe_value is not None and pe_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe"] = f"{pe_value:.1f}倍{realtime_tag}"

                                # 详细日志
                                price = realtime_metrics.get('price', 'N/A')
                                market_cap_log = realtime_metrics.get('market_cap', 'N/A')
                                source = realtime_metrics.get('source', 'unknown')
                                updated_at = realtime_metrics.get('updated_at', 'N/A')

                                logger.info(f"✅ [PE计算-第1层成功] PE={pe_value:.2f}倍 | 来源={source} | 实时={is_realtime}")
                                logger.info(f"   └─ 计算数据: 股价={price}元, 市值={market_cap_log}亿元, 更新时间={updated_at}")
                            elif pe_value is None:
                                # 🔥 PE 为 None，检查是否是亏损股
                                pe_ttm_check = latest_indicators.get('pe_ttm')
                                # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                                if pe_ttm_check is None or pe_ttm_check <= 0 or str(pe_ttm_check) == 'nan' or pe_ttm_check == '--':
                                    is_loss_stock = True
                                    logger.info(f"⚠️ [PE计算-第1层] PE为None且pe_ttm={pe_ttm_check}，确认为亏损股")

                            # 使用实时PE_TTM（TTM市盈率）
                            pe_ttm_value = realtime_metrics.get('pe_ttm')
                            if pe_ttm_value is not None and pe_ttm_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe_ttm"] = f"{pe_ttm_value:.1f}倍{realtime_tag}"
                                logger.info(f"✅ [PE_TTM计算-第1层成功] PE_TTM={pe_ttm_value:.2f}倍 | 来源={source} | 实时={is_realtime}")
                            elif pe_ttm_value is None and not is_loss_stock:
                                # 🔥 PE_TTM 为 None，再次检查是否是亏损股
                                pe_ttm_check = latest_indicators.get('pe_ttm')
                                # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                                if pe_ttm_check is None or pe_ttm_check <= 0 or str(pe_ttm_check) == 'nan' or pe_ttm_check == '--':
                                    is_loss_stock = True
                                    logger.info(f"⚠️ [PE_TTM计算-第1层] PE_TTM为None且pe_ttm={pe_ttm_check}，确认为亏损股")

                            # 使用实时PB
                            pb_value = realtime_metrics.get('pb')
                            if pb_value is not None and pb_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pb"] = f"{pb_value:.2f}倍{realtime_tag}"
                                logger.info(f"✅ [PB计算-第1层成功] PB={pb_value:.2f}倍 | 来源={realtime_metrics.get('source')} | 实时={is_realtime}")
                        else:
                            # 🔥 检查是否因为亏损导致返回 None
                            # 从 stock_basic_info 获取 pe_ttm 判断是否亏损
                            pe_ttm_static = latest_indicators.get('pe_ttm')
                            # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                            if pe_ttm_static is None or pe_ttm_static <= 0 or str(pe_ttm_static) == 'nan' or pe_ttm_static == '--':
                                is_loss_stock = True
                                logger.info(f"⚠️ [PE计算-第1层失败] 检测到亏损股（pe_ttm={pe_ttm_static}），跳过降级计算")
                            else:
                                logger.warning(f"⚠️ [PE计算-第1层失败] 实时计算返回空结果，将尝试降级计算")

            except Exception as e:
                logger.warning(f"⚠️ [PE计算-第1层异常] 实时计算失败: {e}，将尝试降级计算")

            # 如果实时计算失败，尝试从 latest_indicators 获取总市值
            if "total_mv" not in metrics:
                logger.info(f"📊 [总市值-第2层] 尝试从 stock_basic_info 获取")
                total_mv_static = latest_indicators.get('total_mv')
                if total_mv_static is not None and total_mv_static > 0:
                    metrics["total_mv"] = f"{total_mv_static:.2f}亿元"
                    logger.info(f"✅ [总市值-第2层成功] 总市值={total_mv_static:.2f}亿元 (来源: stock_basic_info)")
                else:
                    # 尝试从 money_cap 计算（万元转亿元）
                    money_cap = latest_indicators.get('money_cap')
                    if money_cap is not None and money_cap > 0:
                        total_mv_yi = money_cap / 10000
                        metrics["total_mv"] = f"{total_mv_yi:.2f}亿元"
                        logger.info(f"✅ [总市值-第3层成功] 总市值={total_mv_yi:.2f}亿元 (从money_cap转换)")
                    else:
                        # 🔥 第 4 层：腾讯 qt.gtimg 兜底（轻量级、稳定、含市值/PE/PB）
                        try:
                            from tradingagents.dataflows.providers.china.eastmoney_quote import TencentQuoteProvider
                            tx_quote = TencentQuoteProvider.get_market_value(symbol)
                            if tx_quote and tx_quote.get("total_mv", 0) > 0:
                                metrics["total_mv"] = f"{tx_quote['total_mv']:.2f}亿元 (实时)"
                                if tx_quote.get("pe_ttm"):
                                    metrics["pe_ttm_fallback"] = f"{tx_quote['pe_ttm']:.2f}倍"
                                if tx_quote.get("pb"):
                                    metrics["pb_fallback"] = f"{tx_quote['pb']:.2f}倍"
                                if tx_quote.get("price"):
                                    metrics["price_fallback"] = f"{tx_quote['price']:.2f}元"
                                logger.info(f"✅ [总市值-第4层成功] 来源=Tencent qt.gtimg: {tx_quote['total_mv']:.2f}亿元")
                            else:
                                # 🔥 第 5 层：东财 push2 兜底（可能被风控）
                                from tradingagents.dataflows.providers.china.eastmoney_quote import EastMoneyQuoteProvider
                                em_quote = EastMoneyQuoteProvider.get_market_value(symbol)
                                if em_quote and em_quote.get("total_mv", 0) > 0:
                                    metrics["total_mv"] = f"{em_quote['total_mv']:.2f}亿元 (实时)"
                                    if em_quote.get("pb"):
                                        metrics["pb_fallback"] = f"{em_quote['pb']:.2f}倍"
                                    if em_quote.get("total_share"):
                                        metrics["total_share"] = f"{em_quote['total_share']:.2f}亿股"
                                    logger.info(f"✅ [总市值-第5层成功] 来源=EastMoney push2: {em_quote['total_mv']:.2f}亿元")
                                else:
                                    metrics["total_mv"] = "N/A"
                                    logger.warning(f"⚠️ [总市值-全部失败] 腾讯/东财兜底均失败")
                        except Exception as e:
                            metrics["total_mv"] = "N/A"
                            logger.warning(f"⚠️ [总市值-兜底异常] {e}")

            # 如果实时计算失败，尝试传统计算方式
            if pe_value is None:
                # 🔥 如果已经确认是亏损股，直接设置 PE 为 N/A，不再尝试降级计算
                if is_loss_stock:
                    metrics["pe"] = "N/A"
                    logger.info(f"⚠️ [PE计算-亏损股] 已确认为亏损股，PE设置为N/A，跳过第2层计算")
                else:
                    logger.info(f"📊 [PE计算-第2层] 尝试使用市值/净利润计算")

                    net_profit = latest_indicators.get('net_profit')

                    # 🔥 关键修复：检查净利润是否为正数（亏损股不计算PE）
                    if net_profit and net_profit > 0:
                        try:
                            # 使用市值/净利润计算PE
                            money_cap = latest_indicators.get('money_cap')
                            if money_cap and money_cap > 0:
                                pe_calculated = money_cap / net_profit
                                metrics["pe"] = f"{pe_calculated:.1f}倍"
                                logger.info(f"✅ [PE计算-第2层成功] PE={pe_calculated:.2f}倍")
                                logger.info(f"   └─ 计算公式: 市值({money_cap}万元) / 净利润({net_profit}万元)")
                            else:
                                logger.warning(f"⚠️ [PE计算-第2层失败] 市值无效: {money_cap}，尝试第3层")

                                # 第三层降级：直接使用 latest_indicators 中的 pe 字段（仅当为正数时）
                                pe_static = latest_indicators.get('pe')
                                if pe_static is not None and str(pe_static) != 'nan' and pe_static != '--':
                                    try:
                                        pe_float = float(pe_static)
                                        # 🔥 只接受正数的 PE
                                        if pe_float > 0:
                                            metrics["pe"] = f"{pe_float:.1f}倍"
                                            logger.info(f"✅ [PE计算-第3层成功] 使用静态PE: {metrics['pe']}")
                                            logger.info(f"   └─ 数据来源: stock_basic_info.pe")
                                        else:
                                            metrics["pe"] = "N/A"
                                            logger.info(f"⚠️ [PE计算-第3层跳过] 静态PE为负数或零（亏损股）: {pe_float}")
                                    except (ValueError, TypeError):
                                        metrics["pe"] = "N/A"
                                        logger.error(f"❌ [PE计算-第3层失败] 静态PE格式错误: {pe_static}")
                                else:
                                    metrics["pe"] = "N/A"
                                    logger.error(f"❌ [PE计算-全部失败] 无可用PE数据")
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            metrics["pe"] = "N/A"
                            logger.error(f"❌ [PE计算-第2层异常] 计算失败: {e}")
                    elif net_profit and net_profit < 0:
                        # 🔥 亏损股：PE 设置为 N/A
                        metrics["pe"] = "N/A"
                        logger.info(f"⚠️ [PE计算-亏损股] 净利润为负数（{net_profit}万元），PE设置为N/A")
                    else:
                        logger.warning(f"⚠️ [PE计算-第2层跳过] 净利润无效: {net_profit}，尝试第3层")

                        # 第三层降级：直接使用 latest_indicators 中的 pe 字段（仅当为正数时）
                        pe_static = latest_indicators.get('pe')
                        if pe_static is not None and str(pe_static) != 'nan' and pe_static != '--':
                            try:
                                pe_float = float(pe_static)
                                # 🔥 只接受正数的 PE
                                if pe_float > 0:
                                    metrics["pe"] = f"{pe_float:.1f}倍"
                                    logger.info(f"✅ [PE计算-第3层成功] 使用静态PE: {metrics['pe']}")
                                    logger.info(f"   └─ 数据来源: stock_basic_info.pe")
                                else:
                                    metrics["pe"] = "N/A"
                                    logger.info(f"⚠️ [PE计算-第3层跳过] 静态PE为负数或零（亏损股）: {pe_float}")
                            except (ValueError, TypeError):
                                metrics["pe"] = "N/A"
                                logger.error(f"❌ [PE计算-第3层失败] 静态PE格式错误: {pe_static}")
                        else:
                            metrics["pe"] = "N/A"
                            logger.error(f"❌ [PE计算-全部失败] 无可用PE数据")

            # 如果 PE_TTM 未获取到，尝试从静态数据获取
            if pe_ttm_value is None:
                # 🔥 如果已经确认是亏损股，直接设置 PE_TTM 为 N/A
                if is_loss_stock:
                    metrics["pe_ttm"] = "N/A"
                    logger.info(f"⚠️ [PE_TTM计算-亏损股] 已确认为亏损股，PE_TTM设置为N/A")
                else:
                    logger.info(f"📊 [PE_TTM计算-第2层] 尝试从静态数据获取")
                    pe_ttm_static = latest_indicators.get('pe_ttm')
                    if pe_ttm_static is not None and str(pe_ttm_static) != 'nan' and pe_ttm_static != '--':
                        try:
                            pe_ttm_float = float(pe_ttm_static)
                            # 🔥 只接受正数的 PE_TTM（亏损股不显示PE_TTM）
                            if pe_ttm_float > 0:
                                metrics["pe_ttm"] = f"{pe_ttm_float:.1f}倍"
                                logger.info(f"✅ [PE_TTM计算-第2层成功] 使用静态PE_TTM: {metrics['pe_ttm']}")
                                logger.info(f"   └─ 数据来源: stock_basic_info.pe_ttm")
                            else:
                                metrics["pe_ttm"] = "N/A"
                                logger.info(f"⚠️ [PE_TTM计算-第2层跳过] 静态PE_TTM为负数或零（亏损股）: {pe_ttm_float}")
                        except (ValueError, TypeError):
                            metrics["pe_ttm"] = "N/A"
                            logger.error(f"❌ [PE_TTM计算-第2层失败] 静态PE_TTM格式错误: {pe_ttm_static}")
                    else:
                        metrics["pe_ttm"] = "N/A"
                        logger.warning(f"⚠️ [PE_TTM计算-全部失败] 无可用PE_TTM数据")

            if pb_value is None:
                total_equity = latest_indicators.get('total_hldr_eqy_exc_min_int')
                if total_equity and total_equity > 0:
                    try:
                        # 使用市值/净资产计算PB
                        money_cap = latest_indicators.get('money_cap')
                        if money_cap and money_cap > 0:
                            # 注意单位转换：money_cap 是万元，total_equity 是元
                            # PB = 市值(万元) * 10000 / 净资产(元)
                            pb_calculated = (money_cap * 10000) / total_equity
                            metrics["pb"] = f"{pb_calculated:.2f}倍"
                            logger.info(f"✅ [PB计算-第2层成功] PB={pb_calculated:.2f}倍")
                            logger.info(f"   └─ 计算公式: 市值{money_cap}万元 * 10000 / 净资产{total_equity}元 = {metrics['pb']}")
                        else:
                            # 第三层降级：直接使用 latest_indicators 中的 pb 字段
                            pb_static = latest_indicators.get('pb') or latest_indicators.get('pb_mrq')
                            if pb_static is not None and str(pb_static) != 'nan' and pb_static != '--':
                                try:
                                    metrics["pb"] = f"{float(pb_static):.2f}倍"
                                    logger.info(f"✅ [PB计算-第3层成功] 使用静态PB: {metrics['pb']}")
                                    logger.info(f"   └─ 数据来源: stock_basic_info.pb")
                                except (ValueError, TypeError):
                                    metrics["pb"] = "N/A"
                            else:
                                metrics["pb"] = "N/A"
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        logger.error(f"❌ [PB计算-第2层异常] 计算失败: {e}")
                        metrics["pb"] = "N/A"
                else:
                    # 第三层降级：直接使用 latest_indicators 中的 pb 字段
                    pb_static = latest_indicators.get('pb') or latest_indicators.get('pb_mrq')
                    if pb_static is not None and str(pb_static) != 'nan' and pb_static != '--':
                        try:
                            metrics["pb"] = f"{float(pb_static):.2f}倍"
                            logger.info(f"✅ [PB计算-第3层成功] 使用静态PB: {metrics['pb']}")
                            logger.info(f"   └─ 数据来源: stock_basic_info.pb")
                        except (ValueError, TypeError):
                            metrics["pb"] = "N/A"
                    else:
                        metrics["pb"] = "N/A"

            # 资产负债率
            debt_ratio = latest_indicators.get('debt_to_assets')
            if debt_ratio is not None and str(debt_ratio) != 'nan' and debt_ratio != '--':
                try:
                    metrics["debt_ratio"] = f"{float(debt_ratio):.1f}%"
                except (ValueError, TypeError):
                    metrics["debt_ratio"] = "N/A"
            else:
                metrics["debt_ratio"] = "N/A"

            # 计算 PS - 市销率（使用TTM营业收入）
            # 优先使用 TTM 营业收入，如果没有则使用单期营业收入
            revenue_ttm = latest_indicators.get('revenue_ttm')
            revenue = latest_indicators.get('revenue')

            # 选择使用哪个营业收入数据
            revenue_for_ps = revenue_ttm if revenue_ttm and revenue_ttm > 0 else revenue
            revenue_type = "TTM" if revenue_ttm and revenue_ttm > 0 else "单期"

            if revenue_for_ps and revenue_for_ps > 0:
                try:
                    # 🔥 修复：money_cap 是"货币资金"不是"总市值"，PS = 总市值 / 营业收入
                    # total_mv 单位是"亿元"，revenue 单位是"万元"，统一转为"元"
                    total_mv_yi = latest_indicators.get('total_mv')
                    if total_mv_yi and total_mv_yi > 0:
                        total_mv_yuan = total_mv_yi * 1e8       # 亿元 → 元
                        revenue_yuan = revenue_for_ps * 1e4      # 万元 → 元
                        ps_calculated = total_mv_yuan / revenue_yuan
                        metrics["ps"] = f"{ps_calculated:.2f}倍"
                        logger.debug(f"✅ 计算PS({revenue_type}): 总市值{total_mv_yi}亿元 / 营业收入{revenue_for_ps}万元 = {metrics['ps']}")
                    else:
                        metrics["ps"] = "N/A"
                except (ValueError, TypeError, ZeroDivisionError):
                    metrics["ps"] = "N/A"
            else:
                metrics["ps"] = "N/A"

            # 股息收益率 - 暂时设为N/A，需要股息数据
            metrics["dividend_yield"] = "N/A"
            metrics["current_ratio"] = latest_indicators.get('current_ratio', 'N/A')
            metrics["quick_ratio"] = latest_indicators.get('quick_ratio', 'N/A')
            metrics["cash_ratio"] = latest_indicators.get('cash_ratio', 'N/A')

            # 添加评分字段（使用默认值）
            metrics["fundamental_score"] = 7.0  # 基于真实数据的默认评分
            metrics["valuation_score"] = 6.5
            metrics["growth_score"] = 7.0
            metrics["risk_level"] = "中等"

            logger.info(f"✅ MongoDB 财务数据解析成功: ROE={metrics.get('roe')}, ROA={metrics.get('roa')}, 毛利率={metrics.get('gross_margin')}, 净利率={metrics.get('net_margin')}")
            return metrics

        except Exception as e:
            logger.error(f"❌ MongoDB财务数据解析失败: {e}", exc_info=True)
            return None

    def _parse_akshare_financial_data(self, financial_data: dict, stock_info: dict, price_value: float, baostock_metrics: dict = None) -> dict:
        """解析AKShare财务数据为指标
        
        Args:
            financial_data: AKShare财务数据字典
            stock_info: 股票信息字典
            price_value: 当前股价
            baostock_metrics: 可选的BaoStock PE/PB数据，用于数据融合
        """
        try:
            # 获取最新的财务数据
            balance_sheet = financial_data.get('balance_sheet', [])
            income_statement = financial_data.get('income_statement', [])
            cash_flow = financial_data.get('cash_flow', [])
            main_indicators = financial_data.get('main_indicators')

            # main_indicators 可能是 DataFrame 或 list（to_dict('records') 的结果）
            if main_indicators is None:
                logger.warning("AKShare主要财务指标为空")
                return None

            # 检查是否为空
            if isinstance(main_indicators, list):
                if not main_indicators:
                    logger.warning("AKShare主要财务指标列表为空")
                    return None
                # 列表格式：[{指标: 值, ...}, ...]
                # 转换为 DataFrame 以便统一处理
                import pandas as pd
                main_indicators = pd.DataFrame(main_indicators)
            elif hasattr(main_indicators, 'empty') and main_indicators.empty:
                logger.warning("AKShare主要财务指标DataFrame为空")
                return None

            # main_indicators是DataFrame，需要转换为字典格式便于查找
            # 获取最新数据列（第3列，索引为2）
            latest_col = main_indicators.columns[2] if len(main_indicators.columns) > 2 else None
            if not latest_col:
                logger.warning("AKShare主要财务指标缺少数据列")
                return None

            logger.info(f"📅 使用AKShare最新数据期间: {latest_col}")

            # 创建指标名称到值的映射
            indicators_dict = {}
            for _, row in main_indicators.iterrows():
                indicator_name = row['指标']
                value = row[latest_col]
                indicators_dict[indicator_name] = value

            logger.debug(f"AKShare主要财务指标数量: {len(indicators_dict)}")

            # 计算财务指标
            metrics = {}

            # 🔥 优先尝试使用实时 PE/PB 计算（与 MongoDB 解析保持一致）
            pe_value = None
            pe_ttm_value = None
            pb_value = None

            # 🔥 如果传入了BaoStock数据，优先使用它
            if baostock_metrics:
                logger.info(f"✅ [PE/PB融合] 使用BaoStock数据源")
                pe_str = baostock_metrics.get('pe', '')
                pe_ttm_str = baostock_metrics.get('pe_ttm', '')
                pb_str = baostock_metrics.get('pb', '')
                
                if '倍' in pe_str:
                    pe_value = float(pe_str.replace('倍', '').strip())
                    metrics["pe"] = f"{pe_value:.1f}倍 (BaoStock)"
                    logger.info(f"✅ [BaoStock-PE] PE={pe_value:.1f}倍")
                
                if '倍' in pe_ttm_str:
                    pe_ttm_value = float(pe_ttm_str.replace('倍', '').strip())
                    metrics["pe_ttm"] = f"{pe_ttm_value:.1f}倍 (BaoStock)"
                    logger.info(f"✅ [BaoStock-PE_TTM] PE_TTM={pe_ttm_value:.1f}倍")
                
                if '倍' in pb_str:
                    pb_value = float(pb_str.replace('倍', '').strip())
                    metrics["pb"] = f"{pb_value:.2f}倍 (BaoStock)"
                    logger.info(f"✅ [BaoStock-PB] PB={pb_value:.2f}倍")
                
                # 更新price_value
                if baostock_metrics.get('current_price_numeric'):
                    price_value = baostock_metrics['current_price_numeric']
                    metrics['price'] = f"¥{price_value:.2f}"
                    logger.info(f"✅ [BaoStock-股价] 股价={price_value:.2f}元")

            try:
                # 获取股票代码
                stock_code = stock_info.get('code', '').replace('.SH', '').replace('.SZ', '').zfill(6)
                if stock_code:
                    logger.info(f"📊 [AKShare-PE计算-第1层] 尝试使用实时PE/PB计算: {stock_code}")

                    from tradingagents.config.database_manager import get_database_manager
                    from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback

                    db_manager = get_database_manager()
                    if db_manager.is_mongodb_available():
                        client = db_manager.get_mongodb_client()

                        # 获取实时PE/PB
                        realtime_metrics = get_pe_pb_with_fallback(stock_code, client)

                        if realtime_metrics:
                            # 获取总市值
                            market_cap = realtime_metrics.get('market_cap')
                            if market_cap is not None and market_cap > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["total_mv"] = f"{market_cap:.2f}亿元{realtime_tag}"
                                logger.info(f"✅ [AKShare-总市值获取成功] 总市值={market_cap:.2f}亿元 | 实时={is_realtime}")

                            # 使用实时PE
                            pe_value = realtime_metrics.get('pe')
                            if pe_value is not None and pe_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe"] = f"{pe_value:.1f}倍{realtime_tag}"
                                logger.info(f"✅ [AKShare-PE计算-第1层成功] PE={pe_value:.2f}倍 | 来源={realtime_metrics.get('source')} | 实时={is_realtime}")

                            # 使用实时PE_TTM
                            pe_ttm_value = realtime_metrics.get('pe_ttm')
                            if pe_ttm_value is not None and pe_ttm_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe_ttm"] = f"{pe_ttm_value:.1f}倍{realtime_tag}"
                                logger.info(f"✅ [AKShare-PE_TTM计算-第1层成功] PE_TTM={pe_ttm_value:.2f}倍")

                            # 使用实时PB
                            pb_value = realtime_metrics.get('pb')
                            if pb_value is not None and pb_value > 0:
                                is_realtime = realtime_metrics.get('is_realtime', False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pb"] = f"{pb_value:.2f}倍{realtime_tag}"
                                logger.info(f"✅ [AKShare-PB计算-第1层成功] PB={pb_value:.2f}倍")
                        else:
                            logger.warning(f"⚠️ [AKShare-PE计算-第1层失败] 实时计算返回空结果，将尝试降级计算")
            except Exception as e:
                logger.warning(f"⚠️ [AKShare-PE计算-第1层异常] 实时计算失败: {e}，将尝试降级计算")
            
            # 🔥 如果MongoDB的实时计算失败，尝试从BaoStock获取PE/PB（新增降级方案）
            if pe_value is None or pb_value is None:
                logger.info(f"🔄 [AKShare-PE计算-降级方案] 尝试从BaoStock获取PE/PB")
                try:
                    baostock_metrics = self._get_baostock_pe_pb(stock_code)
                    if baostock_metrics:
                        # 使用BaoStock的数据填充PE/PB
                        if pe_value is None:
                            pe_str = baostock_metrics.get('pe', '')
                            if '倍' in pe_str:
                                pe_value = float(pe_str.replace('倍', ''))
                                metrics["pe"] = f"{pe_value:.1f}倍 (BaoStock)"
                                logger.info(f"✅ [AKShare-BaoStock降级] PE={pe_value:.1f}倍")
                        
                        if pe_ttm_value is None:
                            pe_ttm_str = baostock_metrics.get('pe_ttm', '')
                            if '倍' in pe_ttm_str:
                                pe_ttm_value = float(pe_ttm_str.replace('倍', ''))
                                metrics["pe_ttm"] = f"{pe_ttm_value:.1f}倍 (BaoStock)"
                                logger.info(f"✅ [AKShare-BaoStock降级] PE_TTM={pe_ttm_value:.1f}倍")
                        
                        if pb_value is None:
                            pb_str = baostock_metrics.get('pb', '')
                            if '倍' in pb_str:
                                pb_value = float(pb_str.replace('倍', ''))
                                metrics["pb"] = f"{pb_value:.2f}倍 (BaoStock)"
                                logger.info(f"✅ [AKShare-BaoStock降级] PB={pb_value:.2f}倍")
                        
                        # 如果有股价信息，也更新总市值
                        if baostock_metrics.get('current_price_numeric') and metrics.get('total_mv') == 'N/A':
                            # 需要总股本来计算市值，这里暂时跳过
                            pass
                except Exception as e:
                    logger.warning(f"⚠️ [AKShare-BaoStock降级失败] {e}")

            # 获取ROE - 直接从指标中获取
            roe_value = indicators_dict.get('净资产收益率(ROE)')
            if roe_value is not None and str(roe_value) != 'nan' and roe_value != '--':
                try:
                    roe_val = float(roe_value)
                    # ROE通常是百分比形式
                    metrics["roe"] = f"{roe_val:.1f}%"
                    logger.debug(f"✅ 获取ROE: {metrics['roe']}")
                except (ValueError, TypeError):
                    metrics["roe"] = "N/A"
            else:
                metrics["roe"] = "N/A"

            # 如果实时计算失败，尝试从 stock_info 获取总市值
            if "total_mv" not in metrics:
                logger.info(f"📊 [AKShare-总市值-第2层] 尝试从 stock_info 获取")
                total_mv_static = stock_info.get('total_mv')
                if total_mv_static is not None and total_mv_static > 0:
                    metrics["total_mv"] = f"{total_mv_static:.2f}亿元"
                    logger.info(f"✅ [AKShare-总市值-第2层成功] 总市值={total_mv_static:.2f}亿元")
                else:
                    metrics["total_mv"] = "N/A"
                    logger.warning(f"⚠️ [AKShare-总市值-全部失败] 无可用总市值数据")

            # 🔥 如果实时计算失败，降级到传统计算方式
            if pe_value is None:
                logger.info(f"📊 [AKShare-PE计算-第2层] 尝试使用股价/EPS计算")

                # 计算 PE - 优先使用 TTM 数据
                # 尝试从 main_indicators DataFrame 计算 TTM EPS
                ttm_eps = None
                try:
                    # main_indicators 是 DataFrame，包含多期数据
                    # 尝试计算 TTM EPS
                    if '基本每股收益' in main_indicators['指标'].values:
                        # 提取基本每股收益的所有期数数据
                        eps_row = main_indicators[main_indicators['指标'] == '基本每股收益']
                        if not eps_row.empty:
                            # 获取所有数值列（排除'指标'列）
                            value_cols = [col for col in eps_row.columns if col != '指标']

                            # 构建 DataFrame 用于 TTM 计算
                            import pandas as pd
                            eps_data = []
                            for col in value_cols:
                                eps_val = eps_row[col].iloc[0]
                                if eps_val is not None and str(eps_val) != 'nan' and eps_val != '--':
                                    eps_data.append({'报告期': col, '基本每股收益': eps_val})

                            if len(eps_data) >= 2:
                                eps_df = pd.DataFrame(eps_data)
                                # 使用 TTM 计算函数
                                from scripts.sync_financial_data import _calculate_ttm_metric
                                ttm_eps = _calculate_ttm_metric(eps_df, '基本每股收益')
                                if ttm_eps:
                                    logger.info(f"✅ 计算 TTM EPS: {ttm_eps:.4f} 元")
                except Exception as e:
                    logger.debug(f"计算 TTM EPS 失败: {e}")

                # 使用 TTM EPS 或单期 EPS 计算 PE
                eps_for_pe = ttm_eps if ttm_eps else None
                pe_type = "TTM" if ttm_eps else "单期"

                if not eps_for_pe:
                    # 降级到单期 EPS
                    eps_value = indicators_dict.get('基本每股收益')
                    if eps_value is not None and str(eps_value) != 'nan' and eps_value != '--':
                        try:
                            eps_for_pe = float(eps_value)
                        except (ValueError, TypeError):
                            pass

                if eps_for_pe and eps_for_pe > 0:
                    pe_val = price_value / eps_for_pe
                    metrics["pe"] = f"{pe_val:.1f}倍"
                    logger.info(f"✅ [AKShare-PE计算-第2层成功] PE({pe_type}): 股价{price_value} / EPS{eps_for_pe:.4f} = {metrics['pe']}")
                elif eps_for_pe and eps_for_pe <= 0:
                    metrics["pe"] = "N/A（亏损）"
                    logger.warning(f"⚠️ [AKShare-PE计算-第2层失败] 亏损股票，EPS={eps_for_pe}")
                else:
                    metrics["pe"] = "N/A"
                    logger.error(f"❌ [AKShare-PE计算-全部失败] 无可用EPS数据")

            # 🔥 如果实时PB计算失败，降级到传统计算方式
            if pb_value is None:
                logger.info(f"📊 [AKShare-PB计算-第2层] 尝试使用股价/BPS计算")

                # 获取每股净资产 - 用于计算PB
                bps_value = indicators_dict.get('每股净资产_最新股数')
                if bps_value is not None and str(bps_value) != 'nan' and bps_value != '--':
                    try:
                        bps_val = float(bps_value)
                        if bps_val > 0:
                            # 计算PB = 股价 / 每股净资产
                            pb_val = price_value / bps_val
                            metrics["pb"] = f"{pb_val:.2f}倍"
                            logger.info(f"✅ [AKShare-PB计算-第2层成功] PB: 股价{price_value} / BPS{bps_val} = {metrics['pb']}")
                        else:
                            metrics["pb"] = "N/A"
                            logger.warning(f"⚠️ [AKShare-PB计算-第2层失败] BPS无效: {bps_val}")
                    except (ValueError, TypeError) as e:
                        metrics["pb"] = "N/A"
                        logger.error(f"❌ [AKShare-PB计算-第2层异常] {e}")
                else:
                    metrics["pb"] = "N/A"
                    logger.error(f"❌ [AKShare-PB计算-全部失败] 无可用BPS数据")

            # 尝试获取其他指标
            # 总资产收益率(ROA)
            roa_value = indicators_dict.get('总资产报酬率')
            if roa_value is not None and str(roa_value) != 'nan' and roa_value != '--':
                try:
                    roa_val = float(roa_value)
                    metrics["roa"] = f"{roa_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["roa"] = "N/A"
            else:
                metrics["roa"] = "N/A"

            # 毛利率
            gross_margin_value = indicators_dict.get('毛利率')
            if gross_margin_value is not None and str(gross_margin_value) != 'nan' and gross_margin_value != '--':
                try:
                    gross_margin_val = float(gross_margin_value)
                    metrics["gross_margin"] = f"{gross_margin_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["gross_margin"] = "N/A"
            else:
                metrics["gross_margin"] = "N/A"

            # 销售净利率
            net_margin_value = indicators_dict.get('销售净利率')
            if net_margin_value is not None and str(net_margin_value) != 'nan' and net_margin_value != '--':
                try:
                    net_margin_val = float(net_margin_value)
                    metrics["net_margin"] = f"{net_margin_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["net_margin"] = "N/A"
            else:
                metrics["net_margin"] = "N/A"

            # 资产负债率
            debt_ratio_value = indicators_dict.get('资产负债率')
            if debt_ratio_value is not None and str(debt_ratio_value) != 'nan' and debt_ratio_value != '--':
                try:
                    debt_ratio_val = float(debt_ratio_value)
                    metrics["debt_ratio"] = f"{debt_ratio_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["debt_ratio"] = "N/A"
            else:
                metrics["debt_ratio"] = "N/A"

            # 流动比率
            current_ratio_value = indicators_dict.get('流动比率')
            if current_ratio_value is not None and str(current_ratio_value) != 'nan' and current_ratio_value != '--':
                try:
                    current_ratio_val = float(current_ratio_value)
                    metrics["current_ratio"] = f"{current_ratio_val:.2f}"
                except (ValueError, TypeError):
                    metrics["current_ratio"] = "N/A"
            else:
                metrics["current_ratio"] = "N/A"

            # 速动比率
            quick_ratio_value = indicators_dict.get('速动比率')
            if quick_ratio_value is not None and str(quick_ratio_value) != 'nan' and quick_ratio_value != '--':
                try:
                    quick_ratio_val = float(quick_ratio_value)
                    metrics["quick_ratio"] = f"{quick_ratio_val:.2f}"
                except (ValueError, TypeError):
                    metrics["quick_ratio"] = "N/A"
            else:
                metrics["quick_ratio"] = "N/A"

            # 计算 PS - 市销率（优先使用 TTM 营业收入）
            # 尝试从 main_indicators DataFrame 计算 TTM 营业收入
            ttm_revenue = None
            try:
                if '营业收入' in main_indicators['指标'].values:
                    revenue_row = main_indicators[main_indicators['指标'] == '营业收入']
                    if not revenue_row.empty:
                        value_cols = [col for col in revenue_row.columns if col != '指标']

                        import pandas as pd
                        revenue_data = []
                        for col in value_cols:
                            rev_val = revenue_row[col].iloc[0]
                            if rev_val is not None and str(rev_val) != 'nan' and rev_val != '--':
                                revenue_data.append({'报告期': col, '营业收入': rev_val})

                        if len(revenue_data) >= 2:
                            revenue_df = pd.DataFrame(revenue_data)
                            from scripts.sync_financial_data import _calculate_ttm_metric
                            ttm_revenue = _calculate_ttm_metric(revenue_df, '营业收入')
                            if ttm_revenue:
                                logger.info(f"✅ 计算 TTM 营业收入: {ttm_revenue:.2f} 万元")
            except Exception as e:
                logger.debug(f"计算 TTM 营业收入失败: {e}")

            # 计算 PS
            revenue_for_ps = ttm_revenue if ttm_revenue else None
            ps_type = "TTM" if ttm_revenue else "单期"

            if not revenue_for_ps:
                # 降级到单期营业收入
                revenue_value = indicators_dict.get('营业收入')
                if revenue_value is not None and str(revenue_value) != 'nan' and revenue_value != '--':
                    try:
                        revenue_for_ps = float(revenue_value)
                    except (ValueError, TypeError):
                        pass

            if revenue_for_ps and revenue_for_ps > 0:
                # 获取总股本计算市值
                total_share = stock_info.get('total_share') if stock_info else None
                if total_share and total_share > 0:
                    # 市值（万元）= 股价（元）× 总股本（万股）
                    market_cap = price_value * total_share
                    ps_val = market_cap / revenue_for_ps
                    metrics["ps"] = f"{ps_val:.2f}倍"
                    logger.info(f"✅ 计算PS({ps_type}): 市值{market_cap:.2f}万元 / 营业收入{revenue_for_ps:.2f}万元 = {metrics['ps']}")
                else:
                    metrics["ps"] = "N/A（无总股本数据）"
                    logger.warning(f"⚠️ 无法计算PS: 缺少总股本数据")
            else:
                metrics["ps"] = "N/A"

            # 补充其他指标的默认值
            metrics.update({
                "dividend_yield": "待查询",
                "cash_ratio": "待分析"
            })

            # 评分（基于AKShare数据的简化评分）
            fundamental_score = self._calculate_fundamental_score(metrics, stock_info)
            valuation_score = self._calculate_valuation_score(metrics)
            growth_score = self._calculate_growth_score(metrics, stock_info)
            risk_level = self._calculate_risk_level(metrics, stock_info)

            metrics.update({
                "fundamental_score": fundamental_score,
                "valuation_score": valuation_score,
                "growth_score": growth_score,
                "risk_level": risk_level,
                "data_source": "AKShare"
            })

            logger.info(f"✅ AKShare财务数据解析成功: PE={metrics['pe']}, PB={metrics['pb']}, ROE={metrics['roe']}")
            return metrics

        except Exception as e:
            logger.error(f"❌ AKShare财务数据解析失败: {e}")
            return None

    def _parse_financial_data(self, financial_data: dict, stock_info: dict, price_value: float) -> dict:
        """解析财务数据为指标"""
        try:
            # 获取最新的财务数据
            balance_sheet = financial_data.get('balance_sheet', [])
            income_statement = financial_data.get('income_statement', [])
            cash_flow = financial_data.get('cash_flow', [])

            if not (balance_sheet or income_statement):
                return None

            latest_balance = balance_sheet[0] if balance_sheet else {}
            latest_income = income_statement[0] if income_statement else {}
            latest_cash = cash_flow[0] if cash_flow else {}

            # 计算财务指标
            metrics = {}

            # 基础数据
            total_assets = latest_balance.get('total_assets', 0) or 0
            total_liab = latest_balance.get('total_liab', 0) or 0
            total_equity = latest_balance.get('total_hldr_eqy_exc_min_int', 0) or 0

            # 计算 TTM 营业收入和净利润
            # Tushare income_statement 的数据是累计值（从年初到报告期）
            # 需要使用 TTM 公式计算
            ttm_revenue = None
            ttm_net_income = None

            try:
                if len(income_statement) >= 2:
                    # 准备数据用于 TTM 计算
                    import pandas as pd

                    # 构建营业收入 DataFrame
                    revenue_data = []
                    for stmt in income_statement:
                        end_date = stmt.get('end_date')
                        revenue = stmt.get('total_revenue')
                        if end_date and revenue is not None:
                            revenue_data.append({'报告期': str(end_date), '营业收入': float(revenue)})

                    if len(revenue_data) >= 2:
                        revenue_df = pd.DataFrame(revenue_data)
                        from scripts.sync_financial_data import _calculate_ttm_metric
                        ttm_revenue = _calculate_ttm_metric(revenue_df, '营业收入')
                        if ttm_revenue:
                            logger.info(f"✅ Tushare 计算 TTM 营业收入: {ttm_revenue:.2f} 万元")

                    # 构建净利润 DataFrame
                    profit_data = []
                    for stmt in income_statement:
                        end_date = stmt.get('end_date')
                        profit = stmt.get('n_income')
                        if end_date and profit is not None:
                            profit_data.append({'报告期': str(end_date), '净利润': float(profit)})

                    if len(profit_data) >= 2:
                        profit_df = pd.DataFrame(profit_data)
                        ttm_net_income = _calculate_ttm_metric(profit_df, '净利润')
                        if ttm_net_income:
                            logger.info(f"✅ Tushare 计算 TTM 净利润: {ttm_net_income:.2f} 万元")
            except Exception as e:
                logger.warning(f"⚠️ Tushare TTM 计算失败: {e}")

            # 降级到单期数据
            total_revenue = ttm_revenue if ttm_revenue else (latest_income.get('total_revenue', 0) or 0)
            net_income = ttm_net_income if ttm_net_income else (latest_income.get('n_income', 0) or 0)
            operate_profit = latest_income.get('operate_profit', 0) or 0

            revenue_type = "TTM" if ttm_revenue else "单期"
            profit_type = "TTM" if ttm_net_income else "单期"

            # 获取实际总股本计算市值
            # 优先从 stock_info 获取，如果没有则无法计算准确的估值指标
            total_share = stock_info.get('total_share') if stock_info else None

            if total_share and total_share > 0:
                # 市值（元）= 股价（元）× 总股本（万股）× 10000
                market_cap = price_value * total_share * 10000
                market_cap_yi = market_cap / 100000000  # 转换为亿元
                metrics["total_mv"] = f"{market_cap_yi:.2f}亿元"
                logger.info(f"✅ [Tushare-总市值计算成功] 总市值={market_cap_yi:.2f}亿元 (股价{price_value}元 × 总股本{total_share}万股)")
            else:
                logger.error(f"❌ {stock_info.get('code', 'Unknown')} 无法获取总股本，无法计算准确的估值指标")
                market_cap = None
                metrics["total_mv"] = "N/A"

            # 计算各项指标（只有在有准确市值时才计算）
            if market_cap:
                # PE比率（优先使用 TTM 净利润）
                if net_income > 0:
                    pe_ratio = market_cap / (net_income * 10000)  # 转换单位
                    metrics["pe"] = f"{pe_ratio:.1f}倍"
                    logger.info(f"✅ Tushare 计算PE({profit_type}): 市值{market_cap/100000000:.2f}亿元 / 净利润{net_income:.2f}万元 = {pe_ratio:.1f}倍")
                else:
                    metrics["pe"] = "N/A（亏损）"

                # PB比率（净资产使用最新期数据，相对准确）
                if total_equity > 0:
                    pb_ratio = market_cap / (total_equity * 10000)
                    metrics["pb"] = f"{pb_ratio:.2f}倍"
                else:
                    metrics["pb"] = "N/A"

                # PS比率（优先使用 TTM 营业收入）
                if total_revenue > 0:
                    ps_ratio = market_cap / (total_revenue * 10000)
                    metrics["ps"] = f"{ps_ratio:.1f}倍"
                    logger.info(f"✅ Tushare 计算PS({revenue_type}): 市值{market_cap/100000000:.2f}亿元 / 营业收入{total_revenue:.2f}万元 = {ps_ratio:.1f}倍")
                else:
                    metrics["ps"] = "N/A"
            else:
                # 无法获取总股本，无法计算估值指标
                metrics["pe"] = "N/A（无总股本数据）"
                metrics["pb"] = "N/A（无总股本数据）"
                metrics["ps"] = "N/A（无总股本数据）"

            # ROE
            if total_equity > 0 and net_income > 0:
                roe = (net_income / total_equity) * 100
                metrics["roe"] = f"{roe:.1f}%"
            else:
                metrics["roe"] = "N/A"

            # ROA
            if total_assets > 0 and net_income > 0:
                roa = (net_income / total_assets) * 100
                metrics["roa"] = f"{roa:.1f}%"
            else:
                metrics["roa"] = "N/A"

            # 净利率
            if total_revenue > 0 and net_income > 0:
                net_margin = (net_income / total_revenue) * 100
                metrics["net_margin"] = f"{net_margin:.1f}%"
            else:
                metrics["net_margin"] = "N/A"

            # 资产负债率
            if total_assets > 0:
                debt_ratio = (total_liab / total_assets) * 100
                metrics["debt_ratio"] = f"{debt_ratio:.1f}%"
            else:
                metrics["debt_ratio"] = "N/A"

            # 其他指标设为默认值
            metrics.update({
                "dividend_yield": "待查询",
                "gross_margin": "待计算",
                "current_ratio": "待计算",
                "quick_ratio": "待计算",
                "cash_ratio": "待分析"
            })

            # 评分（基于真实数据的简化评分）
            fundamental_score = self._calculate_fundamental_score(metrics, stock_info)
            valuation_score = self._calculate_valuation_score(metrics)
            growth_score = self._calculate_growth_score(metrics, stock_info)
            risk_level = self._calculate_risk_level(metrics, stock_info)

            metrics.update({
                "fundamental_score": fundamental_score,
                "valuation_score": valuation_score,
                "growth_score": growth_score,
                "risk_level": risk_level
            })

            return metrics

        except Exception as e:
            logger.error(f"解析财务数据失败: {e}")
            return None

    def _calculate_fundamental_score(self, metrics: dict, stock_info: dict) -> float:
        """计算基本面评分"""
        score = 5.0  # 基础分

        # ROE评分
        roe_str = metrics.get("roe", "N/A")
        if roe_str != "N/A":
            try:
                roe = float(roe_str.replace("%", ""))
                if roe > 15:
                    score += 1.5
                elif roe > 10:
                    score += 1.0
                elif roe > 5:
                    score += 0.5
            except:
                pass

        # 净利率评分
        net_margin_str = metrics.get("net_margin", "N/A")
        if net_margin_str != "N/A":
            try:
                net_margin = float(net_margin_str.replace("%", ""))
                if net_margin > 20:
                    score += 1.0
                elif net_margin > 10:
                    score += 0.5
            except:
                pass

        return min(score, 10.0)

    def _calculate_valuation_score(self, metrics: dict) -> float:
        """计算估值评分"""
        score = 5.0  # 基础分

        # PE评分
        pe_str = metrics.get("pe", "N/A")
        if pe_str != "N/A" and "亏损" not in pe_str:
            try:
                pe = float(pe_str.replace("倍", ""))
                if pe < 15:
                    score += 2.0
                elif pe < 25:
                    score += 1.0
                elif pe > 50:
                    score -= 1.0
            except:
                pass

        # PB评分
        pb_str = metrics.get("pb", "N/A")
        if pb_str != "N/A":
            try:
                pb = float(pb_str.replace("倍", ""))
                if pb < 1.5:
                    score += 1.0
                elif pb < 3:
                    score += 0.5
                elif pb > 5:
                    score -= 0.5
            except:
                pass

        return min(max(score, 1.0), 10.0)

    def _calculate_growth_score(self, metrics: dict, stock_info: dict) -> float:
        """计算成长性评分"""
        score = 6.0  # 基础分

        # 根据行业调整
        industry = stock_info.get('industry', '')
        if '科技' in industry or '软件' in industry or '互联网' in industry:
            score += 1.0
        elif '银行' in industry or '保险' in industry:
            score -= 0.5

        return min(max(score, 1.0), 10.0)

    def _calculate_risk_level(self, metrics: dict, stock_info: dict) -> str:
        """计算风险等级"""
        # 资产负债率
        debt_ratio_str = metrics.get("debt_ratio", "N/A")
        if debt_ratio_str != "N/A":
            try:
                debt_ratio = float(debt_ratio_str.replace("%", ""))
                if debt_ratio > 70:
                    return "较高"
                elif debt_ratio > 50:
                    return "中等"
                else:
                    return "较低"
            except:
                pass

        # 根据行业判断
        industry = stock_info.get('industry', '')
        if '银行' in industry:
            return "中等"
        elif '科技' in industry or '创业板' in industry:
            return "较高"

        return "中等"



    def _analyze_valuation(self, financial_estimates: dict) -> str:
        """分析估值水平"""
        try:
            valuation_score = float(financial_estimates.get('valuation_score', 5))
        except (ValueError, TypeError):
            valuation_score = 5.0

        if valuation_score >= 8:
            return "当前估值水平较为合理，具有一定的投资价值。市盈率和市净率相对较低，安全边际较高。"
        elif valuation_score >= 6:
            return "估值水平适中，需要结合基本面和成长性综合判断投资价值。"
        else:
            return "当前估值偏高，投资需谨慎。建议等待更好的买入时机。"

    def _analyze_growth_potential(self, symbol: str, industry_info: dict) -> str:
        """分析成长潜力"""
        if symbol.startswith(('000001', '600036')):
            return "银行业整体增长稳定，受益于经济发展和金融深化。数字化转型和财富管理业务是主要增长点。"
        elif symbol.startswith('300'):
            return "创业板公司通常具有较高的成长潜力，但也伴随着较高的风险。需要关注技术创新和市场拓展能力。"
        else:
            return "成长潜力需要结合具体行业和公司基本面分析。建议关注行业发展趋势和公司竞争优势。"

    def _analyze_risks(self, symbol: str, financial_estimates: dict, industry_info: dict) -> str:
        """分析投资风险"""
        risk_level = financial_estimates.get('risk_level', '中等')

        risk_analysis = f"**风险等级**: {risk_level}\n\n"

        if symbol.startswith(('000001', '600036')):
            risk_analysis += """**主要风险**:
- 利率环境变化对净息差的影响
- 信贷资产质量风险
- 监管政策变化风险
- 宏观经济下行对银行业的影响"""
        elif symbol.startswith('300'):
            risk_analysis += """**主要风险**:
- 技术更新换代风险
- 市场竞争加剧风险
- 估值波动较大
- 业绩不确定性较高"""
        else:
            risk_analysis += """**主要风险**:
- 行业周期性风险
- 宏观经济环境变化
- 市场竞争风险
- 政策调整风险"""

        return risk_analysis

    def _generate_investment_advice(self, financial_estimates: dict, industry_info: dict) -> str:
        """生成投资建议"""
        # 处理可能的字符串类型评分
        try:
            fundamental_score = float(financial_estimates.get('fundamental_score', 5))
        except (ValueError, TypeError):
            fundamental_score = 5.0
        
        try:
            valuation_score = float(financial_estimates.get('valuation_score', 5))
        except (ValueError, TypeError):
            valuation_score = 5.0
        
        try:
            growth_score = float(financial_estimates.get('growth_score', 5))
        except (ValueError, TypeError):
            growth_score = 5.0

        total_score = (fundamental_score + valuation_score + growth_score) / 3

        if total_score >= 7.5:
            return """**投资建议**: 🟢 **买入**
- 基本面良好，估值合理，具有较好的投资价值
- 建议分批建仓，长期持有
- 适合价值投资者和稳健型投资者"""
        elif total_score >= 6.0:
            return """**投资建议**: 🟡 **观望**
- 基本面一般，需要进一步观察
- 可以小仓位试探，等待更好时机
- 适合有经验的投资者"""
        else:
            return """**投资建议**: 🔴 **回避**
- 当前风险较高，不建议投资
- 建议等待基本面改善或估值回落
- 风险承受能力较低的投资者应避免"""

    def _try_get_old_cache(self, symbol: str, start_date: str, end_date: str) -> Optional[str]:
        """尝试获取过期的缓存数据作为备用"""
        try:
            # 查找任何相关的缓存，不考虑TTL
            for metadata_file in self.cache.metadata_dir.glob(f"*_meta.json"):
                try:
                    import json

                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    if (metadata.get('symbol') == symbol and
                        metadata.get('data_type') == 'stock_data' and
                        metadata.get('market_type') == 'china'):

                        cache_key = metadata_file.stem.replace('_meta', '')
                        cached_data = self.cache.load_stock_data(cache_key)
                        if cached_data:
                            return cached_data + "\n\n⚠️ 注意: 使用的是过期缓存数据"
                except Exception:
                    continue
        except Exception:
            pass

        return None

    def _generate_fallback_data(self, symbol: str, start_date: str, end_date: str, error_msg: str) -> str:
        """生成备用数据"""
        return f"""# {symbol} A股数据获取失败

## ❌ 错误信息
{error_msg}

## 📊 模拟数据（仅供演示）
- 股票代码: {symbol}
- 股票名称: 模拟公司
- 数据期间: {start_date} 至 {end_date}
- 模拟价格: ¥{random.uniform(10, 50):.2f}
- 模拟涨跌: {random.uniform(-5, 5):+.2f}%

## ⚠️ 重要提示
由于数据接口限制或网络问题，无法获取实时数据。
建议稍后重试或检查网络连接。

生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _generate_fallback_fundamentals(self, symbol: str, error_msg: str) -> str:
        """生成备用基本面数据"""
        return f"""# {symbol} A股基本面分析失败

## ❌ 错误信息
{error_msg}

## 📊 基本信息
- 股票代码: {symbol}
- 分析状态: 数据获取失败
- 建议: 稍后重试或检查网络连接

生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
"""


# 全局实例
_china_data_provider = None

def get_optimized_china_data_provider() -> OptimizedChinaDataProvider:
    """获取全局A股数据提供器实例"""
    global _china_data_provider
    if _china_data_provider is None:
        _china_data_provider = OptimizedChinaDataProvider()
    return _china_data_provider


def get_china_stock_data_cached(symbol: str, start_date: str, end_date: str,
                               force_refresh: bool = False) -> str:
    """
    获取A股数据的便捷函数

    Args:
        symbol: 股票代码（6位数字）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        force_refresh: 是否强制刷新缓存

    Returns:
        格式化的股票数据字符串
    """
    provider = get_optimized_china_data_provider()
    return provider.get_stock_data(symbol, start_date, end_date, force_refresh)


def get_china_fundamentals_cached(symbol: str, force_refresh: bool = False) -> str:
    """
    获取A股基本面数据的便捷函数

    Args:
        symbol: 股票代码（6位数字）
        force_refresh: 是否强制刷新缓存

    Returns:
        格式化的基本面数据字符串
    """
    provider = get_optimized_china_data_provider()
    return provider.get_fundamentals_data(symbol, force_refresh)


# 在OptimizedChinaDataProvider类中添加缓存方法
def _add_financial_cache_methods():
    """为OptimizedChinaDataProvider类添加财务数据缓存方法"""

    def _get_cached_raw_financial_data(self, symbol: str) -> dict:
        """从数据库缓存获取原始财务数据"""
        try:
            from .cache.app_adapter import get_mongodb_client
            client = get_mongodb_client()
            if not client:
                logger.debug(f"📊 [财务缓存] MongoDB客户端不可用")
                return None

            db = client.get_database('tradingagents')

            # 第一优先级：从 stock_financial_data 集合读取（定时任务同步的持久化数据）
            stock_financial_collection = db.stock_financial_data

            # 尝试使用 symbol 或 code 字段查询（兼容不同的同步服务）
            financial_doc = stock_financial_collection.find_one({
                '$or': [
                    {'symbol': symbol},
                    {'code': symbol}
                ]
            }, sort=[('updated_at', -1)])

            if financial_doc:
                logger.info(f"✅ [财务数据] 从 stock_financial_data 集合获取{symbol}财务数据")
                # 将数据库文档转换为财务数据格式
                financial_data = {}

                # 提取各类财务数据
                # 第一优先级：检查 raw_data 字段（Tushare 同步服务使用的结构）
                if 'raw_data' in financial_doc and isinstance(financial_doc['raw_data'], dict):
                    raw_data = financial_doc['raw_data']
                    # 映射字段名：raw_data 中使用 cashflow_statement，我们需要 cash_flow
                    if 'balance_sheet' in raw_data and raw_data['balance_sheet']:
                        financial_data['balance_sheet'] = raw_data['balance_sheet']
                    if 'income_statement' in raw_data and raw_data['income_statement']:
                        financial_data['income_statement'] = raw_data['income_statement']
                    if 'cashflow_statement' in raw_data and raw_data['cashflow_statement']:
                        financial_data['cash_flow'] = raw_data['cashflow_statement']  # 注意字段名映射
                    if 'financial_indicators' in raw_data and raw_data['financial_indicators']:
                        financial_data['main_indicators'] = raw_data['financial_indicators']  # 注意字段名映射
                    if 'main_business' in raw_data and raw_data['main_business']:
                        financial_data['main_business'] = raw_data['main_business']

                # 第二优先级：检查 financial_data 嵌套字段
                elif 'financial_data' in financial_doc and isinstance(financial_doc['financial_data'], dict):
                    nested_data = financial_doc['financial_data']
                    if 'balance_sheet' in nested_data:
                        financial_data['balance_sheet'] = nested_data['balance_sheet']
                    if 'income_statement' in nested_data:
                        financial_data['income_statement'] = nested_data['income_statement']
                    if 'cash_flow' in nested_data:
                        financial_data['cash_flow'] = nested_data['cash_flow']
                    if 'main_indicators' in nested_data:
                        financial_data['main_indicators'] = nested_data['main_indicators']

                # 第三优先级：直接从文档根级别读取
                else:
                    if 'balance_sheet' in financial_doc and financial_doc['balance_sheet']:
                        financial_data['balance_sheet'] = financial_doc['balance_sheet']
                    if 'income_statement' in financial_doc and financial_doc['income_statement']:
                        financial_data['income_statement'] = financial_doc['income_statement']
                    if 'cash_flow' in financial_doc and financial_doc['cash_flow']:
                        financial_data['cash_flow'] = financial_doc['cash_flow']
                    if 'main_indicators' in financial_doc and financial_doc['main_indicators']:
                        financial_data['main_indicators'] = financial_doc['main_indicators']

                if financial_data:
                    logger.info(f"📊 [财务数据] 成功提取{symbol}的财务数据，包含字段: {list(financial_data.keys())}")
                    return financial_data
                else:
                    logger.warning(f"⚠️ [财务数据] {symbol}的 stock_financial_data 记录存在但无有效财务数据字段")
            else:
                logger.debug(f"📊 [财务数据] stock_financial_data 集合中未找到{symbol}的记录")

            # 第二优先级：从 financial_data_cache 集合读取（临时缓存）
            collection = db.financial_data_cache

            # 查找缓存的原始财务数据
            cache_doc = collection.find_one({
                'symbol': symbol,
                'cache_type': 'raw_financial_data'
            }, sort=[('updated_at', -1)])

            if cache_doc:
                # 检查缓存是否过期（24小时）
                from datetime import datetime, timedelta
                cache_time = cache_doc.get('updated_at')
                if cache_time and datetime.now() - cache_time < timedelta(hours=24):
                    financial_data = cache_doc.get('financial_data', {})
                    if financial_data:
                        logger.info(f"✅ [财务缓存] 从 financial_data_cache 获取{symbol}原始财务数据")
                        return financial_data
                else:
                    logger.debug(f"📊 [财务缓存] {symbol}原始财务数据缓存已过期")
            else:
                logger.debug(f"📊 [财务缓存] 未找到{symbol}原始财务数据缓存")

        except Exception as e:
            logger.debug(f"📊 [财务缓存] 获取{symbol}原始财务数据缓存失败: {e}")

        return None

    def _get_cached_stock_info(self, symbol: str) -> dict:
        """从数据库缓存获取股票基本信息"""
        try:
            from .cache.app_adapter import get_mongodb_client
            client = get_mongodb_client()
            if not client:
                return {}

            db = client.get_database('tradingagents')
            collection = db.stock_basic_info

            # 查找股票基本信息
            doc = collection.find_one({'code': symbol})
            if doc:
                return {
                    'symbol': symbol,
                    'name': doc.get('name', ''),
                    'industry': doc.get('industry', ''),
                    'market': doc.get('market', ''),
                    'source': 'database_cache'
                }
        except Exception as e:
            logger.debug(f"📊 获取{symbol}股票基本信息缓存失败: {e}")

        return {}

    def _restore_financial_data_format(self, cached_data: dict) -> dict:
        """将缓存的财务数据恢复为DataFrame格式"""
        try:
            import pandas as pd
            restored_data = {}

            for key, value in cached_data.items():
                if isinstance(value, list) and value:  # 如果是list格式的数据
                    # 转换回DataFrame
                    restored_data[key] = pd.DataFrame(value)
                else:
                    restored_data[key] = value

            return restored_data
        except Exception as e:
            logger.debug(f"📊 恢复财务数据格式失败: {e}")
            return cached_data

    def _cache_raw_financial_data(self, symbol: str, financial_data: dict, stock_info: dict):
        """将原始财务数据缓存到数据库"""
        try:
            from tradingagents.config.runtime_settings import use_app_cache_enabled
            if not use_app_cache_enabled(False):
                logger.debug(f"📊 [财务缓存] 应用缓存未启用，跳过缓存保存")
                return

            from .cache.app_adapter import get_mongodb_client
            client = get_mongodb_client()
            if not client:
                logger.debug(f"📊 [财务缓存] MongoDB客户端不可用")
                return

            db = client.get_database('tradingagents')
            collection = db.financial_data_cache

            from datetime import datetime

            # 将DataFrame转换为可序列化的格式
            serializable_data = {}
            for key, value in financial_data.items():
                if hasattr(value, 'to_dict'):  # pandas DataFrame
                    serializable_data[key] = value.to_dict('records')
                else:
                    serializable_data[key] = value

            cache_doc = {
                'symbol': symbol,
                'cache_type': 'raw_financial_data',
                'financial_data': serializable_data,
                'stock_info': stock_info,
                'updated_at': datetime.now()
            }

            # 使用upsert更新或插入
            collection.replace_one(
                {'symbol': symbol, 'cache_type': 'raw_financial_data'},
                cache_doc,
                upsert=True
            )

            logger.info(f"✅ [财务缓存] {symbol}原始财务数据已缓存到数据库")

        except Exception as e:
            logger.debug(f"📊 [财务缓存] 缓存{symbol}原始财务数据失败: {e}")

    # 将方法添加到类中
    OptimizedChinaDataProvider._get_cached_raw_financial_data = _get_cached_raw_financial_data
    OptimizedChinaDataProvider._get_cached_stock_info = _get_cached_stock_info
    OptimizedChinaDataProvider._restore_financial_data_format = _restore_financial_data_format
    OptimizedChinaDataProvider._cache_raw_financial_data = _cache_raw_financial_data

# 执行方法添加
_add_financial_cache_methods()
