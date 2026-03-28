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
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **净资产收益率(ROE)**: {financial_estimates.get('roe', 'N/A')}
- **资产负债率**: {financial_estimates.get('debt_ratio', 'N/A')}

## 💡 基础评估
- **基本面评分**: {financial_estimates['fundamental_score']}/10
- **风险等级**: {financial_estimates['risk_level']}

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
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **市销率(PS)**: {financial_estimates.get('ps', 'N/A')}
- **股息收益率**: {financial_estimates.get('dividend_yield', 'N/A')}

### 盈利能力指标
- **净资产收益率(ROE)**: {financial_estimates['roe']}
- **总资产收益率(ROA)**: {financial_estimates['roa']}
- **毛利率**: {financial_estimates['gross_margin']}
- **净利率**: {financial_estimates['net_margin']}

### 财务健康度
- **资产负债率**: {financial_estimates['debt_ratio']}
- **流动比率**: {financial_estimates['current_ratio']}
- **速动比率**: {financial_estimates['quick_ratio']}
- **现金比率**: {financial_estimates['cash_ratio']}

## 📈 行业分析
{industry_info['analysis']}

## 🎯 投资价值评估
### 估值水平分析
{self._analyze_valuation(financial_estimates)}

### 成长性分析
{self._analyze_growth_potential(symbol, industry_info)}

## 💡 投资建议
- **基本面评分**: {financial_estimates['fundamental_score']}/10
- **估值吸引力**: {financial_estimates['valuation_score']}/10
- **成长潜力**: {financial_estimates['growth_score']}/10
- **风险等级**: {financial_estimates['risk_level']}

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
- **市盈率(PE)**: {financial_estimates.get('pe', 'N/A')}
- **市盈率TTM(PE_TTM)**: {financial_estimates.get('pe_ttm', 'N/A')}
- **市净率(PB)**: {financial_estimates.get('pb', 'N/A')}
- **市销率(PS)**: {financial_estimates.get('ps', 'N/A')}
- **股息收益率**: {financial_estimates.get('dividend_yield', 'N/A')}

### 盈利能力指标
- **净资产收益率(ROE)**: {financial_estimates.get('roe', 'N/A')}
- **总资产收益率(ROA)**: {financial_estimates.get('roa', 'N/A')}
- **毛利率**: {financial_estimates.get('gross_margin', 'N/A')}
- **净利率**: {financial_estimates.get('net_margin', 'N/A')}

### 财务健康度
- **资产负债率**: {financial_estimates['debt_ratio']}
- **流动比率**: {financial_estimates['current_ratio']}
- **速动比率**: {financial_estimates['quick_ratio']}
- **现金比率**: {financial_estimates['cash_ratio']}

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
- **基本面评分**: {financial_estimates['fundamental_score']}/10
- **估值吸引力**: {financial_estimates['valuation_score']}/10
- **成长潜力**: {financial_estimates['growth_score']}/10
- **风险等级**: {financial_estimates['risk_level']}

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

---
**重要声明**: 本报告基于公开数据和模型估算生成，仅供参考，不构成投资建议。
实际投资决策请结合最新财报数据和专业分析师意见。

**数据来源**: {data_source if data_source else "多源数据"}数据接口 + 基本面分析模型
**生成时间**: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}
"""

        return report

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
        """获取真实财务指标（从 MongoDB、AKShare、Tushare 获取，失败则抛出异常）"""

        # 提取价格数值
        try:
            price_value = float(current_price.replace('¥', '').replace(',', ''))
        except:
            price_value = 10.0  # 默认值

        # 尝试获取真实财务数据
        real_metrics = self._get_real_financial_metrics(symbol, price_value)
        if real_metrics:
            logger.info(f"✅ 使用真实财务数据: {symbol}")
            return real_metrics

        # 如果无法获取真实数据，抛出异常
        error_msg = f"无法获取股票 {symbol} 的财务数据。已尝试所有数据源（MongoDB、AKShare、Tushare）均失败。"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)

    def _get_real_financial_metrics(self, symbol: str, price_value: float) -> dict:
        """获取真实财务指标 - 优先使用数据库缓存，再使用API"""
        try:
            # 🔥 优先从 market_quotes 获取实时股价，替换传入的 price_value
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            db_client = None

            if db_manager.is_mongodb_available():
                try:
                    db_client = db_manager.get_mongodb_client()
                    db = db_client['tradingagents']

                    # 标准化股票代码为6位
                    code6 = symbol.replace('.SH', '').replace('.SZ', '').zfill(6)

                    # 从 market_quotes 获取实时股价
                    quote = db.market_quotes.find_one({"code": code6})
                    if quote and quote.get("close"):
                        realtime_price = float(quote.get("close"))
                        logger.info(f"✅ 从 market_quotes 获取实时股价: {code6} = {realtime_price}元 (原价格: {price_value}元)")
                        price_value = realtime_price
                    else:
                        logger.info(f"⚠️ market_quotes 中未找到{code6}的实时股价，使用传入价格: {price_value}元")
                except Exception as e:
                    logger.warning(f"⚠️ 从 market_quotes 获取实时股价失败: {e}，使用传入价格: {price_value}元")
            else:
                logger.info(f"⚠️ MongoDB 不可用，使用传入价格: {price_value}元")

            # 第一优先级：从 MongoDB stock_financial_data 集合获取标准化财务数据
            from tradingagents.config.runtime_settings import use_app_cache_enabled
            if use_app_cache_enabled(False):
                logger.info(f"🔍 优先从 MongoDB stock_financial_data 集合获取{symbol}财务数据")

                # 直接从 MongoDB 获取标准化的财务数据
                from tradingagents.dataflows.cache.mongodb_cache_adapter import get_mongodb_cache_adapter
                adapter = get_mongodb_cache_adapter()
                financial_data = adapter.get_financial_data(symbol)

                if financial_data:
                    logger.info(f"✅ [财务数据] 从 stock_financial_data 集合获取{symbol}财务数据")
                    # 解析 MongoDB 标准化的财务数据
                    metrics = self._parse_mongodb_financial_data(financial_data, price_value)
                    if metrics:
                        logger.info(f"✅ MongoDB 财务数据解析成功，返回指标")
                        return metrics
                    else:
                        logger.warning(f"⚠️ MongoDB 财务数据解析失败")
                else:
                    logger.info(f"🔄 MongoDB 未找到{symbol}财务数据，尝试从 AKShare API 获取")
            else:
                logger.info(f"🔄 数据库缓存未启用，直接从AKShare API获取{symbol}财务数据")

            # 第二优先级：从AKShare API获取
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
                        return metrics
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
                return metrics

        except Exception as e:
            logger.debug(f"获取{symbol}真实财务数据失败: {e}")

        return None

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

            # 计算 PE/PB - 优先使用实时计算，降级到静态数据
            # 同时获取 PE 和 PE_TTM 两个指标
            pe_value = None
            pe_ttm_value = None
            pb_value = None
            is_loss_stock = False  # 🔥 标记是否为亏损股

            try:
                # 优先使用实时计算
                from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback
                from tradingagents.config.database_manager import get_database_manager

                db_manager = get_database_manager()
                if db_manager.is_mongodb_available():
                    client = db_manager.get_mongodb_client()
                    # 从symbol中提取股票代码
                    stock_code = latest_indicators.get('code') or latest_indicators.get('symbol', '').replace('.SZ', '').replace('.SH', '')

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
                        metrics["total_mv"] = "N/A"
                        logger.warning(f"⚠️ [总市值-全部失败] 无可用总市值数据")

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
                    # 使用市值/营业收入计算PS
                    money_cap = latest_indicators.get('money_cap')
                    if money_cap and money_cap > 0:
                        ps_calculated = money_cap / revenue_for_ps
                        metrics["ps"] = f"{ps_calculated:.2f}倍"
                        logger.debug(f"✅ 计算PS({revenue_type}): 市值{money_cap}万元 / 营业收入{revenue_for_ps}万元 = {metrics['ps']}")
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

    def _parse_akshare_financial_data(self, financial_data: dict, stock_info: dict, price_value: float) -> dict:
        """解析AKShare财务数据为指标"""
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
        valuation_score = financial_estimates['valuation_score']

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
        risk_level = financial_estimates['risk_level']

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
        fundamental_score = financial_estimates['fundamental_score']
        valuation_score = financial_estimates['valuation_score']
        growth_score = financial_estimates['growth_score']

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


class OptimizedChinaDataFlow(OptimizedChinaDataProvider):
    """
    旧类名兼容层。
    """

    pass

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
