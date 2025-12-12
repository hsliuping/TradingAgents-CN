#!/usr/bin/env python3
"""
增强版综合回测分析文件
Enhanced Comprehensive Backtest Analysis

修复数据问题并增加Agent分析过程记录
"""

import os
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np
import logging
import re

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_chinese_font():
    """设置中文字体"""
    try:
        import matplotlib.font_manager as fm
        chinese_fonts = ['Noto Sans CJK JP', 'Noto Serif CJK JP', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        font_candidates = [font for font in chinese_fonts if font in available_fonts]
        if font_candidates:
            plt.rcParams['font.sans-serif'] = font_candidates + plt.rcParams['font.sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            print(f"✅ 使用中文字体: {font_candidates[0]}")
            return True
        else:
            print("⚠️ 未找到中文字体，使用默认字体")
            return False
    except Exception as e:
        print(f"⚠️ 中文字体设置失败: {e}")
        return False

def clean_eval_string(s):
    """安全地解析字符串中的数据，处理numpy类型"""
    if not isinstance(s, str):
        return s

    # 替换numpy类型
    s = s.replace('np.float64(', '').replace('np.int64(', '').replace(')', '')
    s = s.replace('nan', '0.0').replace('NaN', '0.0')

    try:
        return eval(s)
    except:
        return {}

def get_stock_name_from_code(stock_code):
    """直接从接口获取股票名称，不使用缓存和硬编码"""
    try:
        import tushare as ts
        from tradingagents.config.database_manager import DatabaseManager

        # 获取token
        token = None
        try:
            db_manager = DatabaseManager()
            config_collection = db_manager.mongo_client.tradingagents.tushare_configs
            config = config_collection.find_one({"is_active": True})
            if config:
                token = config.get("token_key")
        except:
            pass

        if not token:
            token = os.getenv('TUSHARE_TOKEN')

        if token:
            ts.set_token(token)
            pro = ts.pro_api()

            # 直接查询股票基本信息
            stock_info = pro.stock_basic(ts_code=f'{stock_code}.SZ', fields='ts_code,symbol,name')

            if stock_info is not None and not stock_info.empty:
                stock_name = stock_info['name'].iloc[0]
                logger.info(f"直接获取到股票名称: {stock_code} -> {stock_name}")
                return stock_name
            else:
                raise Exception(f"无法获取股票 {stock_code} 的基本信息")
        else:
            raise Exception("未配置Tushare Token")

    except Exception as e:
        logger.error(f"获取股票名称失败: {e}")
        raise Exception(f"无法获取股票 {stock_code} 的名称，接口调用失败: {e}")

def get_qfq_price_data_direct(stock_code, start_date, end_date):
    """直接获取前复权价格数据，不使用缓存"""
    try:
        import tushare as ts
        from tradingagents.config.database_manager import DatabaseManager

        # 获取token
        token = None
        try:
            db_manager = DatabaseManager()
            config_collection = db_manager.mongo_client.tradingagents.tushare_configs
            config = config_collection.find_one({"is_active": True})
            if config:
                token = config.get("token_key")
        except:
            pass

        if not token:
            token = os.getenv('TUSHARE_TOKEN')

        if token:
            ts.set_token(token)

            # 转换日期格式
            start_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y%m%d')
            end_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y%m%d')

            logger.info(f"直接获取前复权价格数据: {stock_code}, {start_str} - {end_str}")

            # 获取前复权数据
            df = ts.pro_bar(
                ts_code=f'{stock_code}.SZ',
                start_date=start_str,
                end_date=end_str,
                freq='D',
                adj='qfq'  # 前复权
            )

            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条前复权数据")
                logger.info(f"前复权价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")

                # 转换为标准格式
                df_standard = pd.DataFrame({
                    'date': pd.to_datetime(df['trade_date']),
                    'open': df['open'],
                    'high': df['high'],
                    'low': df['low'],
                    'close': df['close'],
                    'volume': df['vol']
                }).sort_values('date')

                return df_standard
            else:
                raise Exception("接口返回空数据")
        else:
            raise Exception("未配置Tushare Token")

    except Exception as e:
        logger.error(f"获取前复权价格数据失败: {e}")
        raise Exception(f"无法获取股票 {stock_code} 在 {start_date} 到 {end_date} 的前复权价格数据: {e}")

def extract_real_price_data(market_state, daily_return):
    """从真实数据中提取价格信息，失败则直接报错"""
    try:
        individual_analysis = market_state.get("individual_analyses", {})
        if not individual_analysis:
            raise Exception("market_state 中缺少 individual_analyses")

        first_stock = list(individual_analysis.values())[0]
        tech_analysis = first_stock.get("technical_analysis", {})
        if not tech_analysis:
            raise Exception("individual_analyses 中缺少 technical_analysis")

        indicators = tech_analysis.get("indicators", {})
        if not indicators:
            raise Exception("technical_analysis 中缺少 indicators")

        # 检查必需的价格字段
        current_price = indicators.get("current_price")
        if current_price is None or current_price <= 0:
            raise Exception(f"无效的当前价格: {current_price}")

        # 直接使用接口数据，不做任何计算和模拟
        return {
            "current_price": current_price,
            "open": indicators.get("open", current_price),
            "high": indicators.get("high", current_price),
            "low": indicators.get("low", current_price),
            "volume": indicators.get("volume", 0),
            "rsi": indicators.get("rsi", 50.0),
            "ma5": indicators.get("ma5", current_price),
            "ma20": indicators.get("ma20", current_price),
            "price_source": "QFQ_API_DATA"  # 前复权API数据
        }

    except Exception as e:
        logger.error(f"从market_state提取价格数据失败: {e}")
        # 直接抛出异常，不使用任何模拟数据
        raise Exception(f"无法从market_state提取有效的价格数据: {e}")

def extract_news_sentiment(market_state):
    """提取新闻情绪分析"""
    try:
        individual_analysis = market_state.get("individual_analyses", {})
        if individual_analysis:
            first_stock = list(individual_analysis.values())[0]
            sentiment_analysis = first_stock.get("sentiment_analysis", {})

            return {
                "sentiment": sentiment_analysis.get("sentiment", ""),
                "sentiment_score": sentiment_analysis.get("sentiment_score", 0.0),
                "news_count": sentiment_analysis.get("news_count", 0),
                "confidence": sentiment_analysis.get("confidence", 0.0)
            }
    except:
        pass

    # 如果没有个股分析，尝试从市场级别获取
    sentiment_analysis = market_state.get("sentiment_analysis", {})
    return {
        "sentiment": sentiment_analysis.get("sentiment", ""),
        "sentiment_score": sentiment_analysis.get("score", 0.0),
        "news_count": 0,
        "confidence": sentiment_analysis.get("confidence", 0.0)
    }

def extract_agent_analysis_summary(market_state):
    """提取Agent各个环节的分析结论文字"""
    analysis_summary = {}

    try:
        # 技术分析结论
        tech_analysis = market_state.get("technical_analysis", {})
        tech_signal = tech_analysis.get("signal", "")
        tech_strength = tech_analysis.get("strength", 0.0)
        analysis_summary["技术分析结论"] = f"信号: {tech_signal}, 强度: {tech_strength:.3f}"

        # 情绪分析结论
        sentiment_analysis = market_state.get("sentiment_analysis", {})
        sentiment = sentiment_analysis.get("sentiment", "")
        sentiment_score = sentiment_analysis.get("score", 0.0)
        confidence = sentiment_analysis.get("confidence", 0.0)
        analysis_summary["情绪分析结论"] = f"情绪: {sentiment}, 得分: {sentiment_score:.3f}, 置信度: {confidence:.2f}"

        # 基本面分析结论
        fundamentals_analysis = market_state.get("fundamentals_analysis", {})
        fundamental_score = fundamentals_analysis.get("fundamental_score", 0.0)
        rating = fundamentals_analysis.get("rating", "")
        analysis_summary["基本面分析结论"] = f"评分: {fundamental_score:.3f}, 评级: {rating}"

        # 市场状态结论
        market_state_analysis = market_state.get("market_state", {})
        trend = market_state_analysis.get("trend", "")
        trend_confidence = market_state_analysis.get("confidence", 0.0)
        analysis_summary["市场状态结论"] = f"趋势: {trend}, 置信度: {trend_confidence:.2f}"

        # 综合分析结论
        overall_summary = market_state.get("analysis_summary", "")
        analysis_summary["综合分析结论"] = overall_summary

        # 个股详细分析
        individual_analysis = market_state.get("individual_analyses", {})
        if individual_analysis:
            for stock_code, analysis in individual_analysis.items():
                stock_summary = analysis.get("analysis_summary", "")
                recommendations = analysis.get("recommendations", [])
                analysis_summary[f"个股{stock_code}分析"] = f"{stock_summary}, 建议: {', '.join(recommendations[:2])}"

    except Exception as e:
        logger.warning(f"提取Agent分析结论失败: {e}")
        analysis_summary["分析结论"] = "提取失败"

    return analysis_summary

def extract_trading_decision_summary(decision):
    """提取交易决策分析"""
    decision_summary = {}

    try:
        decision_summary["目标仓位"] = f"{decision.get('target_position', 0.0) * 100:.1f}%"
        decision_summary["决策置信度"] = f"{decision.get('confidence', 0.0) * 100:.1f}%"
        decision_summary["风险等级"] = decision.get('risk_level', '')
        decision_summary["决策原因"] = decision.get('reason', '')[:200] + "..." if len(decision.get('reason', '')) > 200 else decision.get('reason', '')
    except Exception as e:
        logger.warning(f"提取交易决策失败: {e}")
        decision_summary["决策摘要"] = "提取失败"

    return decision_summary

def calculate_cumulative_stats(daily_df, current_index):
    """计算累计胜率和盈利率"""
    if current_index < 1:
        return {"win_rate": 0.0, "profit_rate": 0.0}

    # 计算到当前日期为止的统计数据
    trading_days = daily_df.iloc[:current_index + 1]

    # 计算胜率：有正收益的天数比例
    winning_days = (trading_days['daily_return'] > 0).sum()
    total_trading_days = len(trading_days)
    win_rate = winning_days / total_trading_days if total_trading_days > 0 else 0.0

    # 计算盈利率：累计收益率
    if total_trading_days > 0:
        start_value = trading_days.iloc[0]['portfolio_value']
        current_value = trading_days.iloc[-1]['portfolio_value']
        profit_rate = (current_value - start_value) / start_value if start_value > 0 else 0.0
    else:
        profit_rate = 0.0

    return {
        "win_rate": win_rate * 100,  # 转换为百分比
        "profit_rate": profit_rate * 100  # 转换为百分比
    }

def extract_trading_signal(decision, current_position, target_position):
    """提取交易信号"""
    if target_position > current_position + 0.05:
        return "BUY"
    elif target_position < current_position - 0.05:
        return "SELL"
    else:
        return "HOLD"

def create_enhanced_comprehensive_csv(daily_csv_path, trade_csv_path, report_json_path, output_dir="backtest_system/result"):
    """创建增强版综合数据CSV文件"""

    logger.info("开始创建增强版综合数据CSV...")

    # 读取数据
    daily_df = pd.read_csv(daily_csv_path)
    trade_df = pd.read_csv(trade_csv_path) if trade_csv_path and os.path.exists(trade_csv_path) else pd.DataFrame()

    with open(report_json_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    # 获取股票信息
    stock_code = report["meta"]["stock_codes"][0] if report["meta"]["stock_codes"] else "UNKNOWN"
    start_date = report["meta"]["backtest_period"]["start"]
    end_date = report["meta"]["backtest_period"]["end"]

    # 直接获取股票名称，失败则停止
    try:
        stock_name = get_stock_name_from_code(stock_code)
    except Exception as e:
        logger.error(f"获取股票名称失败: {e}")
        raise Exception(f"无法获取股票 {stock_code} 的名称，回测停止: {e}")

    # 创建综合数据列表
    comprehensive_data = []

    for i, (_, row) in enumerate(daily_df.iterrows()):
        date = row['date']

        # 解析决策和市场状态
        decision = clean_eval_string(row['decision'])
        market_state = clean_eval_string(row['market_state'])

        # 提取真实价格数据，包含历史价格数据，失败则直接停止
        try:
            # 先尝试标准的价格提取
            price_data = extract_real_price_data(market_state, row.get('daily_return', 0.0))

            # 如果只有一个固定价格（开高低收都相同），尝试从数据源管理器获取该日期的历史数据
            try:
                unique_prices = set([price_data.get('current_price', 0), price_data.get('open', 0),
                                   price_data.get('high', 0), price_data.get('low', 0)])
                need_real_data = price_data and len(unique_prices) <= 2
            except:
                need_real_data = False

            if need_real_data:
                logger.warning(f"检测到固定价格数据，尝试获取{date}的历史价格")
                try:
                    from tradingagents.dataflows.data_source_manager import get_data_source_manager
                    from tradingagents.dataflows.data_source_manager import ChinaDataSource

                    manager = get_data_source_manager()
                    original_source = manager.current_source
                    manager.current_source = ChinaDataSource.TUSHARE

                    # 获取该日期的数据
                    df = manager.get_stock_dataframe(stock_code, date, date, period="daily")

                    if df is not None and not df.empty and len(df) > 0:
                        # 使用当天的真实数据
                        row_data = df.iloc[0]
                        price_data = {
                            "current_price": float(row_data['close']),
                            "open": float(row_data['open']),
                            "high": float(row_data['high']),
                            "low": float(row_data['low']),
                            "volume": float(row_data.get('volume', 0)),
                            "rsi": price_data.get("rsi", 50.0),  # 保留原有技术指标
                            "ma5": price_data.get("ma5", float(row_data['close'])),
                            "ma20": price_data.get("ma20", float(row_data['close'])),
                            "price_source": "QFQ_API_DATA"
                        }
                        logger.info(f"成功获取{date}的真实价格: {price_data['current_price']:.2f}")
                    else:
                        raise Exception(f"无法获取{date}的历史价格数据")

                    # 恢复原始数据源
                    manager.current_source = original_source

                except Exception as e:
                    logger.error(f"获取{date}历史价格失败: {e}")
                    raise Exception(f"无法处理日期 {date} 的价格数据，回测停止: {e}")

        except Exception as e:
            logger.error(f"处理日期 {date} 的价格数据失败: {e}")
            raise Exception(f"无法处理日期 {date} 的价格数据，回测停止: {e}")

        # 提取新闻情绪
        news_data = extract_news_sentiment(market_state)

        # 获取交易信号和看多看空结论
        target_position = decision.get('target_position', 0.0)
        current_position = row['position_ratio']
        trading_signal = extract_trading_signal(decision, current_position, target_position)

        # 获取技术分析信号（看多看空）
        tech_signal = "看多" if market_state.get("technical_analysis", {}).get("signal") == "bullish" else "看空"

        # 计算累计胜率和盈利率
        cumulative_stats = calculate_cumulative_stats(daily_df, i)

        # 提取Agent分析结论
        agent_analysis = extract_agent_analysis_summary(market_state)

        # 提取交易决策分析
        decision_analysis = extract_trading_decision_summary(decision)

        # 构建综合记录
        record = {
            # 基础信息
            "日期": date,
            "股票代码": stock_code,
            "数据来源": price_data.get("price_source", "UNKNOWN"),

            # 真实价格数据
            "开盘价": round(price_data.get("open", 0.0), 2),
            "收盘价": round(price_data.get("current_price", 0.0), 2),
            "最高价": round(price_data.get("high", 0.0), 2),
            "最低价": round(price_data.get("low", 0.0), 2),
            "成交量": price_data.get("volume", 0),
            "价格变化": round(price_data.get("current_price", 0.0) - price_data.get("open", 0.0), 2),
            "价格变化率(%)": round((price_data.get("current_price", 0.0) / price_data.get("open", 0.0) - 1) * 100, 2) if price_data.get("open", 0) > 0 else 0.0,

            # 新闻信息
            "新闻数量": news_data.get("news_count", 0),
            "新闻情绪": news_data.get("sentiment", ""),
            "新闻情绪得分": round(news_data.get("sentiment_score", 0.0), 3),
            "新闻置信度": round(news_data.get("confidence", 0.0), 2),

            # 交易分析
            "看多看空结论": tech_signal,
            "交易信号": trading_signal,
            "当前持仓比例": round(current_position * 100, 1),  # 转换为百分比
            "目标持仓比例": round(target_position * 100, 1),   # 转换为百分比
            "仓位价值": round(row['portfolio_value'] - row['cash'], 2),
            "现金可用": round(row['cash'], 2),
            "投资组合总值": round(row['portfolio_value'], 2),
            "日收益率": round(row['daily_return'] * 100, 2),  # 转换为百分比

            # 累计统计
            "累计胜率": round(cumulative_stats["win_rate"], 1),
            "累计盈利率": round(cumulative_stats["profit_rate"], 2),
            "当日交易次数": row.get('trades_count', 0),

            # 技术指标
            "RSI指标": round(price_data.get("rsi", 0.0), 1),
            "MA5均线": round(price_data.get("ma5", 0.0), 2),
            "MA20均线": round(price_data.get("ma20", 0.0), 2),

            # Agent分析结论文字（新增字段）
            "技术分析结论": agent_analysis.get("技术分析结论", ""),
            "情绪分析结论": agent_analysis.get("情绪分析结论", ""),
            "基本面分析结论": agent_analysis.get("基本面分析结论", ""),
            "市场状态结论": agent_analysis.get("市场状态结论", ""),
            "综合分析结论": agent_analysis.get("综合分析结论", ""),
            "个股分析结论": agent_analysis.get(f"个股{stock_code}分析", ""),

            # 交易决策分析（新增字段）
            "决策目标仓位": decision_analysis.get("目标仓位", ""),
            "决策置信度": decision_analysis.get("决策置信度", ""),
            "风险等级": decision_analysis.get("风险等级", ""),
            "决策原因": decision_analysis.get("决策原因", "")
        }

        comprehensive_data.append(record)

    # 创建DataFrame并保存
    comprehensive_df = pd.DataFrame(comprehensive_data)

    # 生成文件名：股票名_日期范围
    filename = f"{stock_name}_{start_date}_to_{end_date}_增强综合数据.csv"
    filepath = os.path.join(output_dir, filename)

    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 保存CSV
    comprehensive_df.to_csv(filepath, index=False, encoding='utf-8-sig')

    logger.info(f"✅ 增强版综合数据CSV已生成: {filepath}")
    logger.info(f"📊 共 {len(comprehensive_df)} 条记录，{len(comprehensive_df.columns)} 个字段")

    # 显示数据源统计
    real_data_count = comprehensive_df[comprehensive_df['数据来源'] == 'REAL_DATA'].shape[0]
    simulated_data_count = comprehensive_df[comprehensive_df['数据来源'] == 'SIMULATED_DATA'].shape[0]
    logger.info(f"📈 数据源统计: 真实数据 {real_data_count} 条, 模拟数据 {simulated_data_count} 条")

    return filepath, comprehensive_df, stock_name, start_date, end_date

def create_enhanced_comprehensive_chart(df, stock_name, start_date, end_date, output_dir="backtest_system/result"):
    """创建增强版综合数据可视化图表"""

    logger.info("开始生成增强版综合数据图表...")

    # 设置中文字体
    setup_chinese_font()

    # 转换日期格式
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期')

    # 创建图表
    fig, axes = plt.subplots(4, 1, figsize=(18, 16))
    fig.suptitle(f'{stock_name} ({start_date} 至 {end_date}) 增强版回测数据分析', fontsize=18, fontweight='bold')

    # 1. 真实股价走势和投资组合价值
    ax1 = axes[0]
    ax1_twin = ax1.twinx()

    # 股价线（使用真实价格）
    price_line = ax1.plot(df['日期'], df['收盘价'], 'b-', linewidth=3, label='收盘价', marker='o', markersize=6)
    ax1.fill_between(df['日期'], df['最低价'], df['最高价'], alpha=0.2, color='blue', label='价格区间')

    ax1.set_ylabel('股价 (元)', color='b', fontsize=14)
    ax1.tick_params(axis='y', labelcolor='b', labelsize=12)
    ax1.grid(True, alpha=0.3)

    # 投资组合价值 (右轴)
    portfolio_line = ax1_twin.plot(df['日期'], df['投资组合总值'], 'r-', linewidth=2.5, label='投资组合价值', marker='s', markersize=5)
    ax1_twin.set_ylabel('投资组合价值 (元)', color='r', fontsize=14)
    ax1_twin.tick_params(axis='y', labelcolor='r', labelsize=12)

    # 合并图例
    lines = price_line + portfolio_line
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=12)
    ax1.set_title('真实股价走势与投资组合价值', fontsize=16)

    # 2. 仓位变化和交易信号
    ax2 = axes[1]

    current_pos_line = ax2.plot(df['日期'], df['当前持仓比例'], 'g-', linewidth=3, label='当前持仓比例', marker='o', markersize=6)
    target_pos_line = ax2.plot(df['日期'], df['目标持仓比例'], 'r--', linewidth=2.5, label='目标持仓比例', marker='s', markersize=5)

    # 标记交易信号
    buy_signals = df[df['交易信号'] == 'BUY']
    sell_signals = df[df['交易信号'] == 'SELL']

    if not buy_signals.empty:
        ax2.scatter(buy_signals['日期'], buy_signals['当前持仓比例'],
                   color='gold', s=200, marker='^', label='买入信号', zorder=5, edgecolors='black', linewidth=2)
    if not sell_signals.empty:
        ax2.scatter(sell_signals['日期'], sell_signals['当前持仓比例'],
                   color='red', s=200, marker='v', label='卖出信号', zorder=5, edgecolors='black', linewidth=2)

    ax2.set_ylabel('仓位比例 (%)', fontsize=14)
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left', fontsize=12)
    ax2.set_title('仓位变化与交易信号', fontsize=16)

    # 3. 累计胜率和盈利率
    ax3 = axes[2]

    win_rate_line = ax3.plot(df['日期'], df['累计胜率'], 'purple', linewidth=3, label='累计胜率', marker='o', markersize=6)
    profit_rate_line = ax3.plot(df['日期'], df['累计盈利率'], 'orange', linewidth=3, label='累计盈利率', marker='s', markersize=6)

    # 标记零线
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    ax3.axhline(y=50, color='purple', linestyle='--', alpha=0.3, label='50%胜率线')

    ax3.set_ylabel('百分比 (%)', fontsize=14)
    ax3.set_ylim(min(df['累计胜率'].min(), df['累计盈利率'].min()) - 5,
                 max(df['累计胜率'].max(), df['累计盈利率'].max()) + 5)
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper left', fontsize=12)
    ax3.set_title('累计胜率与盈利率变化', fontsize=16)

    # 4. 技术指标和市场情绪
    ax4 = axes[3]
    ax4_twin = ax4.twinx()

    # RSI指标
    if df['RSI指标'].sum() > 0:
        rsi_line = ax4.plot(df['日期'], df['RSI指标'], 'navy', linewidth=3, label='RSI指标', marker='o', markersize=6)
        ax4.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='超买线(70)')
        ax4.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='超卖线(30)')
        ax4.set_ylabel('RSI指标', fontsize=14)
        ax4.set_ylim(0, 100)
    else:
        # 显示日收益率
        rsi_line = ax4.plot(df['日期'], df['日收益率'], 'navy', linewidth=3, label='日收益率', marker='o', markersize=6)
        ax4.set_ylabel('日收益率 (%)', fontsize=14)

    # 新闻情绪得分（如果有变化）
    if df['新闻情绪得分'].sum() != 0:
        sentiment_line = ax4_twin.plot(df['日期'], df['新闻情绪得分'], 'brown', linewidth=2.5, label='新闻情绪得分', marker='s', markersize=5)
        ax4_twin.set_ylabel('新闻情绪得分', fontsize=14)
        ax4_twin.tick_params(axis='y', labelcolor='brown')

    # 标记价格变化率
    ax4_twin2 = ax4.twinx()
    ax4_twin2.spines['right'].set_position(('outward', 60))
    price_change_line = ax4_twin2.plot(df['日期'], df['价格变化率(%)'], 'green', linewidth=2, alpha=0.7, label='价格变化率')
    ax4_twin2.set_ylabel('价格变化率 (%)', fontsize=14, color='green')
    ax4_twin2.tick_params(axis='y', labelcolor='green')

    ax4.grid(True, alpha=0.3)
    ax4.set_title('技术指标与市场情绪', fontsize=16)

    # 合并所有图例
    all_lines = ax4.get_lines() + ax4_twin.get_lines() + ax4_twin2.get_lines()
    all_labels = [line.get_label() for line in all_lines]
    ax4.legend(all_lines, all_labels, loc='upper left', fontsize=10, ncol=2)

    # 格式化x轴日期
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=12)

    plt.tight_layout()

    # 保存图表
    chart_filename = f"{stock_name}_{start_date}_to_{end_date}_增强分析图.png"
    chart_path = os.path.join(output_dir, chart_filename)

    plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    logger.info(f"✅ 增强版综合分析图表已生成: {chart_path}")
    return chart_path

def main():
    """主函数"""

    # 查找最新的回测文件
    import glob

    daily_files = glob.glob("backtest_system/result/daily_records_*.csv")
    trade_files = glob.glob("backtest_system/result/trade_records_*.csv")
    report_files = glob.glob("backtest_system/result/backtest_report_*.json")

    if not daily_files or not report_files:
        logger.error("未找到回测文件，请先运行回测")
        return

    # 获取最新文件
    latest_daily = max(daily_files, key=os.path.getctime)
    latest_report = max(report_files, key=os.path.getctime)
    latest_trade = max(trade_files, key=os.path.getctime) if trade_files else None

    logger.info(f"使用文件: {latest_daily}")
    logger.info(f"使用报告: {latest_report}")
    if latest_trade:
        logger.info(f"使用交易记录: {latest_trade}")

    # 创建增强版综合CSV
    csv_path, df, stock_name, start_date, end_date = create_enhanced_comprehensive_csv(
        latest_daily, latest_trade, latest_report
    )

    # 创建增强版综合图表
    chart_path = create_enhanced_comprehensive_chart(df, stock_name, start_date, end_date)

    logger.info("🎉 增强版综合分析完成!")
    logger.info(f"📁 输出文件:")
    logger.info(f"   CSV: {csv_path}")
    logger.info(f"   图表: {chart_path}")

    # 显示详细数据摘要
    print(f"\n📊 详细数据摘要:")
    print(f"   股票: {stock_name}")
    print(f"   日期范围: {start_date} 至 {end_date}")
    print(f"   记录天数: {len(df)}")

    # 数据源分析 - 现在只使用前复权API数据
    qfq_data_count = df[df['数据来源'] == 'QFQ_API_DATA'].shape[0]
    print(f"   数据来源: 前复权接口数据 {qfq_data_count} 天")

    print(f"   平均仓位: {df['当前持仓比例'].mean():.1f}%")
    print(f"   最终累计胜率: {df['累计胜率'].iloc[-1]:.1f}%")
    print(f"   最终累计盈利率: {df['累计盈利率'].iloc[-1]:.1f}%")
    print(f"   总收益率: {((df['投资组合总值'].iloc[-1] / df['投资组合总值'].iloc[0]) - 1) * 100:.2f}%")

    # 价格分析
    if qfq_data_count > 0:
        qfq_price_data = df[df['数据来源'] == 'QFQ_API_DATA']
        print(f"   前复权价格范围: {qfq_price_data['最低价'].min():.2f} - {qfq_price_data['最高价'].max():.2f} 元")
        print(f"   平均价格: {qfq_price_data['收盘价'].mean():.2f} 元")

    # 清理中间基础文件，只保留最终的股票命名CSV和PNG文件
    print("\n🧹 清理中间文件...")
    try:
        # 删除使用过的基础文件
        if os.path.exists(latest_daily):
            os.remove(latest_daily)
            print(f"   已删除: {os.path.basename(latest_daily)}")

        if latest_trade and os.path.exists(latest_trade):
            os.remove(latest_trade)
            print(f"   已删除: {os.path.basename(latest_trade)}")

        if os.path.exists(latest_report):
            os.remove(latest_report)
            print(f"   已删除: {os.path.basename(latest_report)}")

        print("   ✅ 清理完成，仅保留股票命名的最终文件")

    except Exception as e:
        print(f"   ⚠️ 清理文件时出错: {e}")

if __name__ == "__main__":
    main()