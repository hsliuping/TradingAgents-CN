"""
综合数据记录器
Comprehensive Data Recorder

负责将回测过程中的所有核心数据整合到一个CSV文件中
"""

import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class ComprehensiveDataRecorder:
    """综合数据记录器"""

    def __init__(self, output_dir: str = "backtest_system"):
        """
        初始化综合数据记录器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.comprehensive_data = []

    def add_daily_record(
        self,
        date: str,
        stock_code: str,
        stock_data: Dict,
        market_state: Dict,
        decision: Dict,
        portfolio_data: Dict,
        news_data: Optional[Dict] = None
    ):
        """
        添加每日记录

        Args:
            date: 日期
            stock_code: 股票代码
            stock_data: 股票数据 (开盘价、收盘价等)
            market_state: 市场状态分析
            decision: 交易决策
            portfolio_data: 投资组合数据
            news_data: 新闻数据
        """
        try:
            # 提取股票价格信息
            stock_price_data = self._extract_stock_price_data(stock_data)

            # 提取技术指标
            technical_indicators = self._extract_technical_indicators(market_state)

            # 提取情绪分析
            sentiment_data = self._extract_sentiment_data(market_state)

            # 提取交易信号
            trading_signal = self._extract_trading_signal(decision, market_state)

            # 提取新闻信息
            news_info = self._extract_news_info(news_data or {})

            # 计算累计胜率和盈利率
            cumulative_stats = self._calculate_cumulative_stats(portfolio_data, date)

            # 构建综合记录
            record = {
                # 基础信息
                "date": date,
                "stock_code": stock_code,

                # 股票价格数据
                "open_price": stock_price_data.get("open", 0.0),
                "close_price": stock_price_data.get("close", 0.0),
                "high_price": stock_price_data.get("high", 0.0),
                "low_price": stock_price_data.get("low", 0.0),
                "volume": stock_price_data.get("volume", 0),
                "price_change": stock_price_data.get("price_change", 0.0),
                "price_change_pct": stock_price_data.get("price_change_pct", 0.0),

                # 技术指标
                "rsi": technical_indicators.get("rsi", 0.0),
                "ma5": technical_indicators.get("ma5", 0.0),
                "ma20": technical_indicators.get("ma20", 0.0),
                "technical_signal": technical_indicators.get("signal", ""),
                "technical_strength": technical_indicators.get("strength", 0.0),
                "trend_direction": technical_indicators.get("trend", ""),
                "trend_strength": technical_indicators.get("trend_strength", 0.0),

                # 新闻信息
                "news_count": news_info.get("news_count", 0),
                "news_sentiment": news_info.get("sentiment", ""),
                "news_sentiment_score": news_info.get("sentiment_score", 0.0),
                "news_confidence": news_info.get("confidence", 0.0),

                # 交易信号和决策
                "trading_signal": trading_signal.get("action", ""),
                "target_position": trading_signal.get("target_position", 0.0),
                "decision_confidence": trading_signal.get("confidence", 0.0),
                "risk_level": trading_signal.get("risk_level", ""),
                "decision_reason": trading_signal.get("reason", ""),

                # 持仓和仓位
                "current_position": portfolio_data.get("position_ratio", 0.0),
                "position_value": portfolio_data.get("stock_value", 0.0),
                "cash_available": portfolio_data.get("cash", 0.0),
                "portfolio_value": portfolio_data.get("total_value", 0.0),
                "daily_return": portfolio_data.get("daily_return", 0.0),

                # 累计统计
                "cumulative_win_rate": cumulative_stats.get("win_rate", 0.0),
                "cumulative_profit_rate": cumulative_stats.get("profit_rate", 0.0),
                "total_trades": cumulative_stats.get("total_trades", 0),
                "winning_trades": cumulative_stats.get("winning_trades", 0),
                "max_drawdown": cumulative_stats.get("max_drawdown", 0.0),
                "sharpe_ratio": cumulative_stats.get("sharpe_ratio", 0.0),

                # 分析过程摘要
                "technical_summary": f"技术面: {technical_indicators.get('signal', '')}",
                "sentiment_summary": f"情绪面: {sentiment_data.get('sentiment', '')}",
                "fundamental_summary": f"基本面: {market_state.get('fundamentals_analysis', {}).get('rating', '')}",
                "overall_summary": market_state.get("analysis_summary", "")
            }

            self.comprehensive_data.append(record)
            logger.debug(f"添加综合数据记录: {date} - {stock_code}")

        except Exception as e:
            logger.error(f"添加每日记录失败: {e}")

    def _extract_stock_price_data(self, stock_data: Dict) -> Dict:
        """提取股票价格数据"""
        return {
            "open": stock_data.get("open", 0.0),
            "close": stock_data.get("close", 0.0),
            "high": stock_data.get("high", 0.0),
            "low": stock_data.get("low", 0.0),
            "volume": stock_data.get("volume", 0),
            "price_change": stock_data.get("price_change", 0.0),
            "price_change_pct": stock_data.get("price_change_pct", 0.0)
        }

    def _extract_technical_indicators(self, market_state: Dict) -> Dict:
        """提取技术指标"""
        individual_analysis = market_state.get("individual_analyses", {})

        # 获取第一只股票的技术分析数据
        if individual_analysis:
            first_stock = list(individual_analysis.values())[0]
            tech_analysis = first_stock.get("technical_analysis", {})
            indicators = tech_analysis.get("indicators", {})

            return {
                "rsi": indicators.get("rsi", 0.0),
                "ma5": indicators.get("ma5", 0.0),
                "ma20": indicators.get("ma20", 0.0),
                "signal": tech_analysis.get("signal", ""),
                "strength": tech_analysis.get("strength", 0.0),
                "trend": market_state.get("market_state", {}).get("trend", ""),
                "trend_strength": market_state.get("market_state", {}).get("strength", 0.0)
            }

        return {
            "rsi": 0.0, "ma5": 0.0, "ma20": 0.0, "signal": "",
            "strength": 0.0, "trend": "", "trend_strength": 0.0
        }

    def _extract_sentiment_data(self, market_state: Dict) -> Dict:
        """提取情绪分析数据"""
        sentiment_analysis = market_state.get("sentiment_analysis", {})
        return {
            "sentiment": sentiment_analysis.get("sentiment", ""),
            "score": sentiment_analysis.get("score", 0.0),
            "confidence": sentiment_analysis.get("confidence", 0.0)
        }

    def _extract_trading_signal(self, decision: Dict, market_state: Dict) -> Dict:
        """提取交易信号"""
        # 根据目标仓位变化决定交易信号
        target_position = decision.get("target_position", 0.0)
        current_position = 0.0  # 这里需要从上下文获取，暂时用0

        if target_position > current_position + 0.01:
            action = "BUY"
        elif target_position < current_position - 0.01:
            action = "SELL"
        else:
            action = "HOLD"

        return {
            "action": action,
            "target_position": target_position,
            "confidence": decision.get("confidence", 0.0),
            "risk_level": decision.get("risk_level", ""),
            "reason": decision.get("reason", "")
        }

    def _extract_news_info(self, news_data: Dict) -> Dict:
        """提取新闻信息"""
        return {
            "news_count": news_data.get("news_count", 0),
            "sentiment": news_data.get("sentiment", ""),
            "sentiment_score": news_data.get("sentiment_score", 0.0),
            "confidence": news_data.get("confidence", 0.0)
        }

    def _calculate_cumulative_stats(self, portfolio_data: Dict, date: str) -> Dict:
        """计算累计统计"""
        # 这里需要根据历史数据计算累计胜率和盈利率
        # 简化版本，实际应该基于交易记录计算
        return {
            "win_rate": 0.0,
            "profit_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0
        }

    def save_to_csv(self, stock_code: str, start_date: str, end_date: str) -> str:
        """
        保存综合数据到CSV - 已禁用自动生成

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            str: 保存的文件路径
        """
        # 注意：此方法已被禁用，我们只使用增强综合分析来生成股票命名的CSV和PNG文件
        logger.info("综合数据记录器CSV保存已禁用，仅使用增强综合分析生成股票命名文件")
        return ""

    def load_from_existing_files(
        self,
        daily_records_path: str,
        trade_records_path: str,
        backtest_report_path: str
    ):
        """
        从现有文件加载数据并生成综合记录

        Args:
            daily_records_path: 每日记录文件路径
            trade_records_path: 交易记录文件路径
            backtest_report_path: 回测报告文件路径
        """
        try:
            # 加载每日记录
            daily_df = pd.read_csv(daily_records_path)

            # 加载交易记录
            trade_df = pd.read_csv(trade_records_path) if os.path.exists(trade_records_path) else pd.DataFrame()

            # 加载回测报告
            with open(backtest_report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            # 处理每日记录
            for _, row in daily_df.iterrows():
                date = row['date']

                # 解析决策和市场状态
                decision = eval(row['decision']) if isinstance(row['decision'], str) else row['decision']
                market_state = eval(row['market_state']) if isinstance(row['market_state'], str) else row['market_state']

                # 构建股票数据
                stock_data = {
                    "close": 0.0,  # 需要从其他来源获取
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "volume": 0,
                    "price_change": 0.0,
                    "price_change_pct": row.get('daily_return', 0.0)
                }

                # 构建投资组合数据
                portfolio_data = {
                    "total_value": row['portfolio_value'],
                    "cash": row['cash'],
                    "stock_value": row['portfolio_value'] - row['cash'],
                    "position_ratio": row['position_ratio'],
                    "daily_return": row['daily_return']
                }

                # 从个股分析中提取新闻数据
                news_data = {}
                if 'individual_analyses' in market_state:
                    for stock_code, analysis in market_state['individual_analyses'].items():
                        if 'sentiment_analysis' in analysis:
                            news_data = analysis['sentiment_analysis']
                            break

                # 添加记录
                self.add_daily_record(
                    date=date,
                    stock_code=report['meta']['stock_codes'][0] if report['meta']['stock_codes'] else "UNKNOWN",
                    stock_data=stock_data,
                    market_state=market_state,
                    decision=decision,
                    portfolio_data=portfolio_data,
                    news_data=news_data
                )

            logger.info(f"从现有文件加载了 {len(self.comprehensive_data)} 条记录")

        except Exception as e:
            logger.error(f"从现有文件加载数据失败: {e}")

    def generate_summary_statistics(self) -> Dict:
        """生成摘要统计"""
        if not self.comprehensive_data:
            return {}

        df = pd.DataFrame(self.comprehensive_data)

        summary = {
            "total_records": len(df),
            "date_range": {
                "start": df['date'].min(),
                "end": df['date'].max()
            },
            "trading_signals": df['trading_signal'].value_counts().to_dict(),
            "technical_signals": df['technical_signal'].value_counts().to_dict(),
            "news_sentiments": df['news_sentiment'].value_counts().to_dict(),
            "risk_levels": df['risk_level'].value_counts().to_dict(),
            "average_position": df['current_position'].mean(),
            "max_position": df['current_position'].max(),
            "min_position": df['current_position'].min(),
            "total_portfolio_return": (df['portfolio_value'].iloc[-1] - df['portfolio_value'].iloc[0]) / df['portfolio_value'].iloc[0] if len(df) > 1 else 0
        }

        return summary