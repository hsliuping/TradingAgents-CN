"""
回测引擎核心
Backtest Engine Core

负责整个回测流程的协调和执行
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import traceback

from .portfolio_manager import PortfolioManager
from .performance_analyzer import PerformanceAnalyzer
from ..agents.position_manager import PositionManager
from ..agents.real_agent_integrator import RealAgentIntegrator
from ..data.data_loader import DataLoader

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission_rate: float = 0.0003  # 手续费率
    slippage_rate: float = 0.0001    # 滑点率
    min_trade_amount: float = 100.0 # 最小交易金额
    max_position_ratio: float = 0.95 # 最大仓位比例
    benchmark: str = "399300"        # 对比基准

@dataclass
class BacktestResult:
    """回测结果"""
    config: BacktestConfig
    portfolio_history: List[Dict]
    trade_history: List[Dict]
    daily_analysis: List[Dict]
    performance_metrics: Dict
    success: bool = True
    error_message: Optional[str] = None

class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: BacktestConfig):
        """
        初始化回测引擎

        Args:
            config: 回测配置
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 初始化组件
        self.data_loader = DataLoader()
        self.portfolio_manager = PortfolioManager(config)
        self.position_manager = PositionManager(config.__dict__ if hasattr(config, '__dict__') else {})
        self.agent_integrator = RealAgentIntegrator(config.__dict__ if hasattr(config, '__dict__') else {})
        self.performance_analyzer = PerformanceAnalyzer()

        # 回测状态
        self.current_date = None
        self.is_running = False

        # 结果存储
        self.portfolio_history = []
        self.trade_history = []
        self.daily_analysis = []

    def run_backtest(
        self,
        stock_codes: List[str],
        progress_callback: Optional[callable] = None
    ) -> BacktestResult:
        """
        执行回测

        Args:
            stock_codes: 股票代码列表
            progress_callback: 进度回调函数

        Returns:
            BacktestResult: 回测结果
        """

        try:
            self.logger.info(f"开始回测: {stock_codes}, 时间范围: {self.config.start_date} - {self.config.end_date}")
            self.is_running = True

            # 加载数据
            stock_data = self._load_stock_data(stock_codes)
            if not stock_data:
                raise ValueError("无法加载股票数据")

            # 加载基准数据
            try:
                benchmark_data = self.data_loader.load_market_data(
                    self.config.benchmark,
                    self.config.start_date,
                    self.config.end_date
                )
                if benchmark_data is None or benchmark_data.empty:
                    self.logger.warning(f"⚠️ 基准数据 {self.config.benchmark} 为空，将继续运行但不进行基准对比")
                    benchmark_data = None
            except Exception as e:
                self.logger.warning(f"⚠️ 基准数据 {self.config.benchmark} 加载失败: {e}，将继续运行但不进行基准对比")
                benchmark_data = None

            # 生成交易日期列表
            trading_dates = self._generate_trading_dates(stock_data, benchmark_data)

            # 初始化投资组合
            self.portfolio_manager.initialize(self.config.initial_capital)

            # 逐日回测循环
            total_days = len(trading_dates)
            for i, date in enumerate(trading_dates):
                try:
                    self.current_date = date
                    self.logger.debug(f"处理日期: {date} ({i+1}/{total_days})")

                    # 执行单日回测
                    self._process_daily_trading(date, stock_data, stock_codes)

                    # 进度回调
                    if progress_callback:
                        progress = (i + 1) / total_days
                        progress_callback(progress, date, i + 1, total_days)

                except Exception as e:
                    self.logger.error(f"处理日期 {date} 时出错: {e}")
                    self.logger.debug(traceback.format_exc())
                    continue

            # 计算最终性能指标
            performance_metrics = self._calculate_final_performance(
                self.portfolio_history, benchmark_data
            )

            # 构建结果
            result = BacktestResult(
                config=self.config,
                portfolio_history=self.portfolio_history,
                trade_history=self.trade_history,
                daily_analysis=self.daily_analysis,
                performance_metrics=performance_metrics,
                success=True
            )

            self.logger.info("回测完成")
            return result

        except Exception as e:
            error_msg = f"回测执行失败: {e}"
            self.logger.error(error_msg)
            self.logger.debug(traceback.format_exc())

            return BacktestResult(
                config=self.config,
                portfolio_history=[],
                trade_history=[],
                daily_analysis=[],
                performance_metrics={},
                success=False,
                error_message=error_msg
            )

        finally:
            self.is_running = False

    def _load_stock_data(self, stock_codes: List[str]) -> Dict[str, pd.DataFrame]:
        """加载股票数据"""

        stock_data = {}
        for code in stock_codes:
            try:
                data = self.data_loader.load_market_data(
                    code, self.config.start_date, self.config.end_date
                )
                if data is not None and not data.empty:
                    stock_data[code] = data
                    self.logger.info(f"成功加载股票 {code} 数据: {len(data)} 条记录")
                else:
                    self.logger.warning(f"股票 {code} 数据为空")
            except Exception as e:
                self.logger.error(f"加载股票 {code} 数据失败: {e}")
                continue

        return stock_data

    def _generate_trading_dates(
        self,
        stock_data: Dict[str, pd.DataFrame],
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> List[str]:
        """生成交易日期列表"""

        all_dates = set()

        # 从股票数据中收集日期
        for code, data in stock_data.items():
            if 'date' in data.columns:
                dates = data['date'].dt.strftime('%Y-%m-%d').tolist()
                all_dates.update(dates)

        # 从基准数据中收集日期
        if benchmark_data is not None and 'date' in benchmark_data.columns:
            dates = benchmark_data['date'].dt.strftime('%Y-%m-%d').tolist()
            all_dates.update(dates)

        # 转换为列表并排序
        trading_dates = sorted(list(all_dates))

        # 过滤日期范围
        start_dt = pd.to_datetime(self.config.start_date)
        end_dt = pd.to_datetime(self.config.end_date)

        filtered_dates = []
        for date_str in trading_dates:
            date_dt = pd.to_datetime(date_str)
            if start_dt <= date_dt <= end_dt:
                filtered_dates.append(date_str)

        self.logger.info(f"生成交易日期 {len(filtered_dates)} 个")
        return filtered_dates

    def _process_daily_trading(
        self,
        date: str,
        stock_data: Dict[str, pd.DataFrame],
        stock_codes: List[str]
    ):
        """处理单日交易"""

        # 获取当日股票价格
        current_prices = {}
        for code in stock_codes:
            if code in stock_data:
                daily_data = stock_data[code]
                daily_row = daily_data[daily_data['date'].dt.strftime('%Y-%m-%d') == date]
                if not daily_row.empty:
                    current_prices[code] = daily_row.iloc[0]['close']

        if not current_prices:
            self.logger.warning(f"日期 {date} 无有效价格数据")
            return

        # 更新投资组合当前价值
        portfolio_value = self.portfolio_manager.update_portfolio_value(current_prices)

        # 确保portfolio_value不为None
        if portfolio_value is None:
            portfolio_value = self.portfolio_manager.get_total_value()

        # 获取当前持仓
        current_positions = self.portfolio_manager.get_current_positions()

        # 使用真实Agent进行市场分析
        market_analysis = self._perform_real_agent_analysis(
            date, stock_codes, stock_data, current_prices
        )

        # 生成风险指标
        risk_indicators = self._generate_risk_indicators(market_analysis)

        # 仓位决策（使用LLM）
        position_decision = self.position_manager.make_position_decision(
            current_position=self.portfolio_manager.get_current_position_ratio(),
            available_capital=self.portfolio_manager.get_available_cash(),
            market_analysis=market_analysis,
            risk_indicators=risk_indicators,
            historical_performance=self._get_historical_performance(),
            use_llm=True  # 启用LLM决策
        )

        # 执行交易
        trades_executed = self._execute_trades(
            date, current_prices, position_decision, current_positions
        )

        # 记录当日状态
        daily_record = {
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': self.portfolio_manager.get_available_cash(),
            'positions': current_positions.copy(),
            'prices': current_prices.copy(),
            'position_decision': {
                'target_position': position_decision.target_position,
                'confidence': position_decision.confidence,
                'reason': position_decision.reason,
                'risk_level': position_decision.risk_level
            },
            'market_analysis': market_analysis,
            'risk_indicators': risk_indicators,
            'trades': trades_executed
        }

        self.daily_analysis.append(daily_record)

        # 记录投资组合历史
        portfolio_record = {
            'date': date,
            'total_value': portfolio_value,
            'cash': self.portfolio_manager.get_available_cash() or 0.0,
            'stock_value': portfolio_value - (self.portfolio_manager.get_available_cash() or 0.0),
            'position_ratio': self.portfolio_manager.get_current_position_ratio(),
            'daily_return': 0.0,  # 将在后续计算
            'cumulative_return': 0.0  # 将在后续计算
        }

        # 计算日收益率
        if len(self.portfolio_history) > 0:
            prev_value = self.portfolio_history[-1]['total_value']
            if prev_value and prev_value > 0:
                portfolio_record['daily_return'] = (portfolio_value - prev_value) / prev_value
            else:
                portfolio_record['daily_return'] = 0.0

        self.portfolio_history.append(portfolio_record)

    def _generate_market_analysis(
        self,
        date: str,
        stock_data: Dict[str, pd.DataFrame],
        current_prices: Dict[str, float]
    ) -> Dict:
        """生成市场分析数据（模拟）"""

        # 这里应该调用实际的Agent分析结果
        # 目前使用简化逻辑模拟

        # 计算技术指标
        technical_signals = {}
        for code, price in current_prices.items():
            if code in stock_data:
                data = stock_data[code]
                # 简单的移动平均线信号
                recent_data = data[data['date'].dt.strftime('%Y-%m-%d') <= date].tail(20)
                if len(recent_data) >= 5:
                    ma5 = recent_data['close'].tail(5).mean()
                    ma20 = recent_data['close'].mean()
                    current_price = price

                    if current_price > ma5 > ma20:
                        signal_strength = 0.8
                    elif current_price < ma5 < ma20:
                        signal_strength = -0.8
                    else:
                        signal_strength = 0.0

                    technical_signals[code] = signal_strength
                else:
                    technical_signals[code] = 0.0

        # 综合技术强度
        avg_technical_strength = np.mean(list(technical_signals.values())) if technical_signals else 0

        # 基本面评分（模拟）
        fundamental_score = 0.5 + np.random.normal(0, 0.1)
        fundamental_score = max(0, min(1, fundamental_score))

        # 新闻情绪（模拟）
        sentiment_options = ['very_negative', 'negative', 'neutral', 'positive', 'very_positive']
        news_sentiment = np.random.choice(sentiment_options, p=[0.1, 0.15, 0.4, 0.25, 0.1])

        # 价格趋势（模拟）
        trend_options = ['strong_downtrend', 'downtrend', 'sideways', 'uptrend', 'strong_uptrend']
        price_trend = np.random.choice(trend_options)

        return {
            'technical_strength': avg_technical_strength,
            'fundamental_score': fundamental_score,
            'news_sentiment': news_sentiment,
            'price_trend': price_trend,
            'technical_signals': technical_signals,
            'institutional_consensus': 0.5 + np.random.normal(0, 0.15),
            'volume_change': np.random.normal(0, 0.2),
            'support_level': min(current_prices.values()) * 0.95,
            'resistance_level': max(current_prices.values()) * 1.05,
            'cost_basis': self.portfolio_manager.get_average_cost(),
            'pnl_ratio': self.portfolio_manager.get_pnl_ratio()
        }

    def _generate_risk_indicators(
        self,
        market_analysis: Dict
    ) -> Dict:
        """生成风险指标"""

        try:
            # 从市场分析中提取风险信息
            market_state = market_analysis.get("market_state", {})
            risk_assessment = market_analysis.get("risk_assessment", {})

            if risk_assessment:
                return {
                    "volatility": 0.2 + np.random.uniform(-0.05, 0.05),  # 模拟波动率
                    "market_sentiment": 0.5 + np.random.uniform(-0.2, 0.2),
                    "systemic_risk": risk_assessment.get("risk_level", "medium"),
                    "liquidity_risk": np.random.choice(["low", "medium", "high"]),
                    "max_drawdown": self.portfolio_manager.get_max_drawdown(),
                    "var_95": self.portfolio_manager.calculate_var(0.95),
                    "risk_score": risk_assessment.get("risk_score", 0.5),
                    "volatility_risk": risk_assessment.get("volatility_risk", 0.3),
                    "sentiment_risk": risk_assessment.get("sentiment_risk", 0.3),
                    "uncertainty_risk": risk_assessment.get("uncertainty_risk", 0.3)
                }
            else:
                # 回退到模拟风险指标
                return self._generate_mock_risk_indicators()

        except Exception as e:
            self.logger.error(f"生成风险指标失败: {e}")
            return self._generate_mock_risk_indicators()

    def _generate_mock_risk_indicators(self) -> Dict:
        """生成模拟风险指标"""
        return {
            "volatility": 0.2 + np.random.uniform(-0.05, 0.05),
            "market_sentiment": 0.5 + np.random.uniform(-0.2, 0.2),
            "systemic_risk": np.random.choice(["low", "medium", "high", "very_high"], p=[0.3, 0.4, 0.2, 0.1]),
            "liquidity_risk": np.random.choice(["low", "medium", "high"], p=[0.6, 0.3, 0.1]),
            "max_drawdown": self.portfolio_manager.get_max_drawdown(),
            "var_95": self.portfolio_manager.calculate_var(0.95),
            "risk_score": np.random.uniform(0.2, 0.8),
            "volatility_risk": np.random.uniform(0.1, 0.5),
            "sentiment_risk": np.random.uniform(0.1, 0.5),
            "uncertainty_risk": np.random.uniform(0.1, 0.5)
        }
        volatilities = []
        for code, data in stock_data.items():
            recent_data = data[data['date'].dt.strftime('%Y-%m-%d') <= date].tail(20)
            if len(recent_data) >= 5:
                returns = recent_data['close'].pct_change().dropna()
                if not returns.empty:
                    vol = returns.std() * np.sqrt(252)  # 年化波动率
                    volatilities.append(vol)

        avg_volatility = np.mean(volatilities) if volatilities else 0.2

        # 市场情绪指数（模拟）
        market_sentiment = 0.5 + np.random.normal(0, 0.15)
        market_sentiment = max(0, min(1, market_sentiment))

        # 系统性风险（模拟）
        risk_levels = ['low', 'medium', 'high', 'very_high']
        systemic_risk = np.random.choice(risk_levels, p=[0.3, 0.4, 0.2, 0.1])

        # 流动性风险（模拟）
        liquidity_risk = np.random.choice(['low', 'medium', 'high'], p=[0.6, 0.3, 0.1])

        return {
            'volatility': avg_volatility,
            'market_sentiment': market_sentiment,
            'systemic_risk': systemic_risk,
            'liquidity_risk': liquidity_risk,
            'max_drawdown': self.portfolio_manager.get_max_drawdown(),
            'var_95': self.portfolio_manager.calculate_var(0.95)
        }

    def _execute_trades(
        self,
        date: str,
        current_prices: Dict[str, float],
        position_decision,
        current_positions: Dict[str, float]
    ) -> List[Dict]:
        """执行交易"""

        trades = []
        current_ratio = self.portfolio_manager.get_current_position_ratio()
        target_ratio = position_decision.target_position

        # 计算需要调整的总金额
        total_value = self.portfolio_manager.get_total_value()
        target_stock_value = total_value * target_ratio
        current_stock_value = total_value - self.portfolio_manager.get_available_cash()

        value_diff = target_stock_value - current_stock_value

        if abs(value_diff) < self.config.min_trade_amount:
            return trades  # 调整金额太小，不进行交易

        # 执行交易逻辑
        if value_diff > 0:  # 需要加仓
            trades = self._execute_buy_trades(
                date, current_prices, value_diff, current_positions
            )
        else:  # 需要减仓
            trades = self._execute_sell_trades(
                date, current_prices, abs(value_diff), current_positions
            )

        return trades

    def _execute_buy_trades(
        self,
        date: str,
        current_prices: Dict[str, float],
        buy_amount: float,
        current_positions: Dict[str, float]
    ) -> List[Dict]:
        """执行买入交易"""

        trades = []
        cash = self.portfolio_manager.get_available_cash()

        # 可用现金限制
        actual_buy_amount = min(buy_amount, cash * self.config.max_position_ratio)

        if actual_buy_amount < self.config.min_trade_amount:
            return trades

        # 简单策略：平均分配到所有股票
        stock_codes = list(current_prices.keys())
        if not stock_codes:
            return trades

        amount_per_stock = actual_buy_amount / len(stock_codes)

        for code in stock_codes:
            price = current_prices[code]
            if price <= 0:
                continue

            # 计算购买数量（按手，100股为单位）
            shares = int(amount_per_stock / price / 100) * 100
            if shares <= 0:
                continue

            trade_value = shares * price
            commission = trade_value * self.config.commission_rate
            slippage = trade_value * self.config.slippage_rate
            total_cost = trade_value + commission + slippage

            if total_cost > cash:
                continue

            # 执行交易
            success = self.portfolio_manager.buy_stock(code, shares, price, commission)
            if success:
                trade_record = {
                    'date': date,
                    'stock_code': code,
                    'action': 'buy',
                    'shares': shares,
                    'price': price,
                    'value': trade_value,
                    'commission': commission,
                    'slippage': slippage,
                    'total_cost': total_cost,
                    'reason': '仓位调整加仓'
                }
                trades.append(trade_record)
                self.trade_history.append(trade_record)

        return trades

    def _execute_sell_trades(
        self,
        date: str,
        current_prices: Dict[str, float],
        sell_amount: float,
        current_positions: Dict[str, float]
    ) -> List[Dict]:
        """执行卖出交易"""

        trades = []

        # 计算当前持仓总值
        total_stock_value = sum(
            current_positions.get(code, 0) * current_prices.get(code, 0)
            for code in current_positions
        )

        if total_stock_value <= 0:
            return trades

        # 计算需要卖出的比例
        sell_ratio = min(sell_amount / total_stock_value, 1.0)

        for code, shares in current_positions.items():
            if code not in current_prices or shares <= 0:
                continue

            price = current_prices[code]
            if price <= 0:
                continue

            # 计算卖出数量
            sell_shares = int(shares * sell_ratio / 100) * 100  # 按手卖出
            if sell_shares <= 0:
                continue

            trade_value = sell_shares * price
            commission = trade_value * self.config.commission_rate
            slippage = trade_value * self.config.slippage_rate
            total_proceeds = trade_value - commission - slippage

            # 执行交易
            success = self.portfolio_manager.sell_stock(code, sell_shares, price, commission)
            if success:
                trade_record = {
                    'date': date,
                    'stock_code': code,
                    'action': 'sell',
                    'shares': sell_shares,
                    'price': price,
                    'value': trade_value,
                    'commission': commission,
                    'slippage': slippage,
                    'total_proceeds': total_proceeds,
                    'reason': '仓位调整减仓'
                }
                trades.append(trade_record)
                self.trade_history.append(trade_record)

        return trades

    def _get_historical_performance(self) -> Dict:
        """获取历史表现数据"""

        if len(self.portfolio_history) < 2:
            return {
                'avg_daily_return': 0,
                'volatility': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0
            }

        # 计算历史收益率
        returns = [
            record['daily_return']
            for record in self.portfolio_history
            if record['daily_return'] != 0
        ]

        if not returns:
            return {
                'avg_daily_return': 0,
                'volatility': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0
            }

        avg_return = np.mean(returns)
        volatility = np.std(returns) * np.sqrt(252)
        sharpe_ratio = avg_return / volatility if volatility > 0 else 0
        win_rate = len([r for r in returns if r > 0]) / len(returns)

        return {
            'avg_daily_return': avg_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.portfolio_manager.get_max_drawdown(),
            'win_rate': win_rate
        }

    def _calculate_final_performance(
        self,
        portfolio_history: List[Dict],
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """计算最终性能指标"""

        if not portfolio_history:
            return {}

        final_value = portfolio_history[-1]['total_value']
        initial_value = self.config.initial_capital

        # 计算收益率
        total_return = (final_value - initial_value) / initial_value

        # 计算累计收益率
        cumulative_returns = []
        for record in portfolio_history:
            cum_return = (record['total_value'] - initial_value) / initial_value
            cumulative_returns.append(cum_return)
            record['cumulative_return'] = cum_return

        # 计算日收益率统计
        daily_returns = [r['daily_return'] for r in portfolio_history if 'daily_return' in r]
        if daily_returns:
            avg_daily_return = np.mean(daily_returns)
            volatility = np.std(daily_returns) * np.sqrt(252)
            sharpe_ratio = avg_daily_return / volatility if volatility > 0 else 0
            max_drawdown = min(cumulative_returns) if cumulative_returns else 0
        else:
            avg_daily_return = volatility = sharpe_ratio = max_drawdown = 0

        # 胜率计算
        win_rate = len([r for r in daily_returns if r > 0]) / len(daily_returns) if daily_returns else 0

        # 基准对比（如果提供了基准数据）
        benchmark_return = 0
        if benchmark_data is not None and not benchmark_data.empty:
            start_date_mask = benchmark_data['date'].dt.strftime('%Y-%m-%d') == self.config.start_date
            end_date_mask = benchmark_data['date'].dt.strftime('%Y-%m-%d') == self.config.end_date

            start_data = benchmark_data[start_date_mask]
            end_data = benchmark_data[end_date_mask]

            if not start_data.empty and not end_data.empty:
                start_price = start_data['close'].iloc[0]
                end_price = end_data['close'].iloc[0]
                benchmark_return = (end_price - start_price) / start_price
            else:
                # 如果无法找到精确日期，使用最接近的日期
                start_price = benchmark_data.iloc[0]['close'] if len(benchmark_data) > 0 else 0
                end_price = benchmark_data.iloc[-1]['close'] if len(benchmark_data) > 0 else start_price
                benchmark_return = (end_price - start_price) / start_price if start_price > 0 else 0

        return {
            'total_return': total_return,
            'annualized_return': total_return * 252 / len(portfolio_history),
            'avg_daily_return': avg_daily_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': abs(max_drawdown),
            'win_rate': win_rate,
            'benchmark_return': benchmark_return,
            'excess_return': total_return - benchmark_return,
            'final_value': final_value,
            'total_trades': len(self.trade_history),
            'trading_days': len(portfolio_history)
        }

    def stop_backtest(self):
        """停止回测"""
        self.is_running = False
        self.logger.info("回测已停止")

    def get_current_status(self) -> Dict:
        """获取当前回测状态"""
        return {
            'is_running': self.is_running,
            'current_date': self.current_date,
            'portfolio_value': self.portfolio_manager.get_total_value() if hasattr(self, 'portfolio_manager') else 0,
            'trades_executed': len(self.trade_history),
            'days_processed': len(self.portfolio_history)
        }

    def _perform_real_agent_analysis(
        self,
        date: str,
        stock_codes: List[str],
        stock_data: Dict[str, pd.DataFrame],
        current_prices: Dict[str, float]
    ) -> Dict:
        """
        使用真实Agent进行市场分析

        Args:
            date: 分析日期
            stock_codes: 股票代码列表
            stock_data: 股票数据
            current_prices: 当前价格

        Returns:
            Dict: 市场分析结果
        """

        try:
            self.logger.info(f"开始真实Agent分析: {date}")

            # 获取新闻数据
            news_data = {}
            for code in stock_codes:
                try:
                    news = self.data_loader.load_news_data(code, date, date)
                    if news is not None and not news.empty:
                        news_data[code] = news
                except Exception as e:
                    self.logger.warning(f"加载 {code} 新闻数据失败: {e}")

            # 分析每只股票
            stock_analyses = {}
            for code in stock_codes:
                if code in stock_data:
                    stock_df = stock_data[code]
                    stock_news = news_data.get(code)

                    analysis = self.agent_integrator.analyze_market(
                        stock_code=code,
                        date=date,
                        stock_data=stock_df,
                        news_data=stock_news
                    )
                    stock_analyses[code] = analysis

            # 综合所有股票的分析结果
            comprehensive_analysis = self._aggregate_stock_analyses(stock_analyses, current_prices)

            self.logger.info(f"真实Agent分析完成: {len(stock_analyses)} 只股票")
            return comprehensive_analysis

        except Exception as e:
            self.logger.error(f"真实Agent分析失败: {e}")
            # 回退到模拟分析
            return self._generate_market_analysis(date, stock_data, current_prices)

    def _aggregate_stock_analyses(
        self,
        stock_analyses: Dict[str, Dict],
        current_prices: Dict[str, float]
    ) -> Dict:
        """
        聚合多只股票的分析结果

        Args:
            stock_analyses: 各股票分析结果
            current_prices: 当前价格

        Returns:
            Dict: 综合分析结果
        """

        if not stock_analyses:
            return self._get_default_market_analysis()

        # 聚合技术分析
        technical_strengths = []
        technical_signals = []
        for code, analysis in stock_analyses.items():
            tech_analysis = analysis.get("technical_analysis", {})
            technical_strengths.append(tech_analysis.get("strength", 0.5))
            technical_signals.append(tech_analysis.get("signal", "neutral"))

        avg_technical_strength = np.mean(technical_strengths) if technical_strengths else 0.5

        # 聚合情绪分析
        sentiment_scores = []
        for code, analysis in stock_analyses.items():
            sentiment_analysis = analysis.get("sentiment_analysis", {})
            sentiment_scores.append(sentiment_analysis.get("score", 0))

        avg_sentiment_score = np.mean(sentiment_scores) if sentiment_scores else 0

        # 聚合基本面分析
        fundamental_scores = []
        for code, analysis in stock_analyses.items():
            fundamentals = analysis.get("fundamentals_analysis", {})
            fundamental_scores.append(fundamentals.get("fundamental_score", 0.5))

        avg_fundamental_score = np.mean(fundamental_scores) if fundamental_scores else 0.5

        # 确定新闻情绪
        if avg_sentiment_score > 0.2:
            news_sentiment = "positive"
        elif avg_sentiment_score < -0.2:
            news_sentiment = "negative"
        else:
            news_sentiment = "neutral"

        # 确定价格趋势
        bullish_count = technical_signals.count("bullish")
        bearish_count = technical_signals.count("bearish")

        if bullish_count > bearish_count:
            price_trend = "uptrend"
        elif bearish_count > bullish_count:
            price_trend = "downtrend"
        else:
            price_trend = "sideways"

        return {
            "technical_analysis": {
                "signal": technical_signals[0] if technical_signals else "neutral",
                "strength": avg_technical_strength,
                "indicators": {}
            },
            "sentiment_analysis": {
                "sentiment": news_sentiment,
                "score": avg_sentiment_score,
                "confidence": 0.7
            },
            "fundamentals_analysis": {
                "fundamental_score": avg_fundamental_score,
                "rating": "fair"
            },
            "market_state": {
                "trend": price_trend,
                "strength": avg_technical_strength,
                "confidence": 0.7
            },
            "individual_analyses": stock_analyses,
            "analysis_summary": f"综合分析完成，技术强度: {avg_technical_strength:.3f}, 情绪: {news_sentiment}"
        }

    def _get_default_market_analysis(self) -> Dict:
        """获取默认市场分析结果"""
        return {
            "technical_analysis": {"signal": "neutral", "strength": 0.5, "indicators": {}},
            "sentiment_analysis": {"sentiment": "neutral", "score": 0, "confidence": 0.5},
            "fundamentals_analysis": {"fundamental_score": 0.5, "rating": "fair"},
            "market_state": {"trend": "sideways", "strength": 0.5, "confidence": 0.5},
            "analysis_summary": "使用默认分析结果"
        }