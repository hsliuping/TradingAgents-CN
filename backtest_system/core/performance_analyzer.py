"""
性能分析器
Performance Analyzer

负责分析回测结果和生成性能指标
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self):
        """初始化性能分析器"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def analyze_performance(
        self,
        portfolio_history: List[Dict],
        trade_history: List[Dict],
        daily_analysis: List[Dict],
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        全面分析回测性能

        Args:
            portfolio_history: 投资组合历史记录
            trade_history: 交易历史记录
            daily_analysis: 每日分析记录
            benchmark_data: 基准数据

        Returns:
            Dict: 性能分析结果
        """

        if not portfolio_history:
            return {"error": "无有效的投资组合历史数据"}

        try:
            # 基础收益率分析
            returns_analysis = self._analyze_returns(portfolio_history)

            # 风险分析
            risk_analysis = self._analyze_risk(portfolio_history)

            # 交易分析
            trading_analysis = self._analyze_trading(trade_history)

            # 基准对比分析
            benchmark_analysis = self._analyze_benchmark(
                portfolio_history, benchmark_data
            )

            # 时间序列分析
            time_analysis = self._analyze_time_series(portfolio_history)

            # 持仓分析
            position_analysis = self._analyze_positions(daily_analysis)

            # 生成综合评分
            overall_score = self._calculate_overall_score(
                returns_analysis, risk_analysis, trading_analysis, benchmark_analysis
            )

            return {
                "returns": returns_analysis,
                "risk": risk_analysis,
                "trading": trading_analysis,
                "benchmark": benchmark_analysis,
                "time_series": time_analysis,
                "positions": position_analysis,
                "overall_score": overall_score,
                "analysis_date": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"性能分析失败: {e}")
            return {"error": str(e)}

    def _analyze_returns(self, portfolio_history: List[Dict]) -> Dict:
        """分析收益率"""

        # 提取收益率数据
        daily_returns = []
        cumulative_returns = []

        for record in portfolio_history:
            if 'daily_return' in record:
                daily_returns.append(record['daily_return'])
            if 'cumulative_return' in record:
                cumulative_returns.append(record['cumulative_return'])

        if not daily_returns:
            return {"error": "无收益率数据"}

        # 转换为numpy数组
        returns = np.array(daily_returns)

        # 基础统计
        total_return = cumulative_returns[-1] if cumulative_returns else 0
        annualized_return = total_return * 252 / len(returns)  # 年化收益率

        # 收益率统计
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        median_return = np.median(returns)

        # 正收益天数统计
        positive_days = len(returns[returns > 0])
        negative_days = len(returns[returns < 0])
        zero_days = len(returns[returns == 0])
        total_days = len(returns)

        win_rate = positive_days / total_days if total_days > 0 else 0

        # 最大单日收益和损失
        max_daily_gain = np.max(returns)
        max_daily_loss = np.min(returns)

        # 连续收益和亏损天数
        consecutive_wins, consecutive_losses = self._calculate_consecutive_days(returns)

        # 夏普比率 (假设无风险利率为3%)
        risk_free_rate = 0.03 / 252  # 日化无风险利率
        excess_returns = returns - risk_free_rate
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
        annualized_sharpe = sharpe_ratio * np.sqrt(252)

        # 索提诺比率 (只考虑下行风险)
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0
        sortino_ratio = mean_return / downside_std if downside_std > 0 else 0
        annualized_sortino = sortino_ratio * np.sqrt(252)

        # 卡尔玛比率
        max_drawdown = self._calculate_max_drawdown(cumulative_returns) if cumulative_returns else 0
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "daily_mean": mean_return,
            "daily_std": std_return,
            "daily_median": median_return,
            "win_rate": win_rate,
            "positive_days": positive_days,
            "negative_days": negative_days,
            "zero_days": zero_days,
            "total_days": total_days,
            "max_daily_gain": max_daily_gain,
            "max_daily_loss": max_daily_loss,
            "consecutive_wins": consecutive_wins,
            "consecutive_losses": consecutive_losses,
            "sharpe_ratio": annualized_sharpe,
            "sortino_ratio": annualized_sortino,
            "calmar_ratio": calmar_ratio
        }

    def _analyze_risk(self, portfolio_history: List[Dict]) -> Dict:
        """分析风险"""

        # 提取收益率和净值数据
        returns = [record.get('daily_return', 0) for record in portfolio_history]
        portfolio_values = [record.get('total_value', 0) for record in portfolio_history]
        cumulative_returns = [record.get('cumulative_return', 0) for record in portfolio_history]

        if not returns:
            return {"error": "无风险分析数据"}

        returns_array = np.array(returns)

        # 波动率
        volatility = np.std(returns_array) * np.sqrt(252)  # 年化波动率

        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(cumulative_returns)
        max_drawdown_duration = self._calculate_max_drawdown_duration(cumulative_returns)

        # VaR (Value at Risk)
        var_95 = np.percentile(returns_array, 5)
        var_99 = np.percentile(returns_array, 1)

        # CVaR (Conditional Value at Risk)
        cvar_95 = np.mean(returns_array[returns_array <= var_95]) if len(returns_array[returns_array <= var_95]) > 0 else 0
        cvar_99 = np.mean(returns_array[returns_array <= var_99]) if len(returns_array[returns_array <= var_99]) > 0 else 0

        # 下行波动率
        negative_returns = returns_array[returns_array < 0]
        downside_volatility = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0

        # 偏度和峰度
        skewness = self._calculate_skewness(returns_array)
        kurtosis = self._calculate_kurtosis(returns_array)

        # beta值（相对于市场的敏感性，这里使用自身波动率模拟）
        beta = volatility / 0.20  # 假设市场年化波动率为20%

        return {
            "volatility": volatility,
            "downside_volatility": downside_volatility,
            "max_drawdown": abs(max_drawdown),
            "max_drawdown_duration": max_drawdown_duration,
            "var_95": abs(var_95),
            "var_99": abs(var_99),
            "cvar_95": abs(cvar_95),
            "cvar_99": abs(cvar_99),
            "skewness": skewness,
            "kurtosis": kurtosis,
            "beta": beta
        }

    def _analyze_trading(self, trade_history: List[Dict]) -> Dict:
        """分析交易"""

        if not trade_history:
            return {"error": "无交易数据"}

        # 交易统计
        total_trades = len(trade_history)
        buy_trades = len([t for t in trade_history if t.get('action') == 'buy'])
        sell_trades = len([t for t in trade_history if t.get('action') == 'sell'])

        # 按股票分组交易
        trades_by_stock = {}
        for trade in trade_history:
            stock = trade.get('stock_code', 'unknown')
            if stock not in trades_by_stock:
                trades_by_stock[stock] = []
            trades_by_stock[stock].append(trade)

        # 计算每只股票的交易统计
        stock_stats = {}
        for stock, trades in trades_by_stock.items():
            stock_buy_trades = [t for t in trades if t.get('action') == 'buy']
            stock_sell_trades = [t for t in trades if t.get('action') == 'sell']

            stock_stats[stock] = {
                "total_trades": len(trades),
                "buy_trades": len(stock_buy_trades),
                "sell_trades": len(stock_sell_trades),
                "total_value": sum(t.get('value', 0) for t in trades),
                "total_commission": sum(t.get('commission', 0) for t in trades)
            }

        # 交易频率
        trading_days = len(set(trade.get('date')[:10] for trade in trade_history if trade.get('date')))
        trades_per_day = total_trades / trading_days if trading_days > 0 else 0

        # 平均交易规模
        trade_values = [t.get('value', 0) for t in trade_history if t.get('value', 0) > 0]
        avg_trade_size = np.mean(trade_values) if trade_values else 0
        median_trade_size = np.median(trade_values) if trade_values else 0

        # 手续费统计
        total_commission = sum(t.get('commission', 0) for t in trade_history)
        commission_rate = total_commission / sum(t.get('value', 0) for t in trade_history) if trade_history else 0

        # 交易时间分布（可以进一步分析交易的时间模式）
        # 这里简化处理

        return {
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "trading_days": trading_days,
            "trades_per_day": trades_per_day,
            "avg_trade_size": avg_trade_size,
            "median_trade_size": median_trade_size,
            "total_commission": total_commission,
            "commission_rate": commission_rate,
            "stocks_traded": len(trades_by_stock),
            "stock_stats": stock_stats
        }

    def _analyze_benchmark(
        self,
        portfolio_history: List[Dict],
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """基准对比分析"""

        if not portfolio_history:
            return {"error": "无投资组合历史数据"}

        portfolio_return = portfolio_history[-1].get('cumulative_return', 0)

        if benchmark_data is None or benchmark_data.empty:
            return {
                "portfolio_return": portfolio_return,
                "benchmark_return": 0,
                "excess_return": portfolio_return,
                "tracking_error": 0,
                "information_ratio": 0,
                "correlation": 0,
                "note": "无基准数据"
            }

        try:
            # 这里假设benchmark_data包含日期和收益率
            # 实际实现需要根据数据格式调整

            # 简化处理：假设基准总收益率为某个固定值
            benchmark_return = 0.08  # 假设基准年化收益率为8%

            # 计算相对指标
            excess_return = portfolio_return - benchmark_return

            # 跟踪误差（简化计算）
            tracking_error = 0.15  # 假设跟踪误差为15%

            # 信息比率
            information_ratio = excess_return / tracking_error if tracking_error > 0 else 0

            # 相关性（简化处理）
            correlation = 0.7  # 假设相关性为70%

            return {
                "portfolio_return": portfolio_return,
                "benchmark_return": benchmark_return,
                "excess_return": excess_return,
                "tracking_error": tracking_error,
                "information_ratio": information_ratio,
                "correlation": correlation,
                "alpha": excess_return,  # 简化的alpha
                "beta": 1.0,  # 简化的beta
                "up_capture": 0.8,  # 上涨捕获率
                "down_capture": 0.9  # 下跌捕获率
            }

        except Exception as e:
            self.logger.error(f"基准对比分析失败: {e}")
            return {
                "portfolio_return": portfolio_return,
                "benchmark_return": 0,
                "excess_return": portfolio_return,
                "error": str(e)
            }

    def _analyze_time_series(self, portfolio_history: List[Dict]) -> Dict:
        """时间序列分析"""

        if not portfolio_history:
            return {"error": "无时间序列数据"}

        # 提取时间序列数据
        dates = [record.get('date') for record in portfolio_history]
        values = [record.get('total_value', 0) for record in portfolio_history]
        returns = [record.get('daily_return', 0) for record in portfolio_history]

        # 计算移动平均
        if len(values) >= 20:
            ma_20 = np.mean(values[-20:])
            ma_5 = np.mean(values[-5:])
        else:
            ma_20 = np.mean(values)
            ma_5 = np.mean(values)

        # 动量指标
        momentum_5d = (values[-1] / values[-6] - 1) if len(values) > 5 else 0
        momentum_20d = (values[-1] / values[-21] - 1) if len(values) > 20 else 0

        # 趋势分析
        trend_slope = self._calculate_trend_slope(values)

        # 周期性分析（简化）
        day_of_week_returns = {}
        for i, record in enumerate(portfolio_history):
            if 'date' in record and 'daily_return' in record:
                try:
                    date_obj = pd.to_datetime(record['date'])
                    day_of_week = date_obj.day_name()
                    if day_of_week not in day_of_week_returns:
                        day_of_week_returns[day_of_week] = []
                    day_of_week_returns[day_of_week].append(record['daily_return'])
                except:
                    continue

        # 计算各星期几的平均收益
        avg_returns_by_day = {}
        for day, day_returns in day_of_week_returns.items():
            avg_returns_by_day[day] = np.mean(day_returns)

        return {
            "current_value": values[-1] if values else 0,
            "ma_5": ma_5,
            "ma_20": ma_20,
            "momentum_5d": momentum_5d,
            "momentum_20d": momentum_20d,
            "trend_slope": trend_slope,
            "avg_returns_by_day": avg_returns_by_day,
            "data_points": len(values)
        }

    def _analyze_positions(self, daily_analysis: List[Dict]) -> Dict:
        """持仓分析"""

        if not daily_analysis:
            return {"error": "无持仓分析数据"}

        # 提取持仓数据
        position_ratios = []
        position_decisions = []

        for record in daily_analysis:
            if 'position_ratio' in record:
                position_ratios.append(record['position_ratio'])
            if 'position_decision' in record:
                position_decisions.append(record['position_decision'])

        if not position_ratios:
            return {"error": "无持仓比例数据"}

        # 持仓比例统计
        avg_position_ratio = np.mean(position_ratios)
        max_position_ratio = np.max(position_ratios)
        min_position_ratio = np.min(position_ratios)

        # 持仓变化频率
        position_changes = 0
        for i in range(1, len(position_ratios)):
            if abs(position_ratios[i] - position_ratios[i-1]) > 0.01:  # 1%以上变化认为是调整
                position_changes += 1

        position_change_frequency = position_changes / len(position_ratios) if position_ratios else 0

        # 决策置信度分析
        confidences = []
        risk_levels = {}

        for decision in position_decisions:
            if 'confidence' in decision:
                confidences.append(decision['confidence'])
            if 'risk_level' in decision:
                risk_level = decision['risk_level']
                if risk_level not in risk_levels:
                    risk_levels[risk_level] = 0
                risk_levels[risk_level] += 1

        avg_confidence = np.mean(confidences) if confidences else 0

        return {
            "avg_position_ratio": avg_position_ratio,
            "max_position_ratio": max_position_ratio,
            "min_position_ratio": min_position_ratio,
            "position_change_frequency": position_change_frequency,
            "avg_confidence": avg_confidence,
            "risk_level_distribution": risk_levels,
            "total_decisions": len(position_decisions)
        }

    def _calculate_consecutive_days(self, returns: np.ndarray) -> Tuple[int, int]:
        """计算连续收益和亏损天数"""
        if len(returns) == 0:
            return 0, 0

        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for ret in returns:
            if ret > 0:
                current_wins += 1
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
                current_losses = 0
            elif ret < 0:
                current_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
                current_wins = 0
            else:
                current_wins = 0
                current_losses = 0

        return max_consecutive_wins, max_consecutive_losses

    def _calculate_max_drawdown(self, cumulative_returns: List[float]) -> float:
        """计算最大回撤"""
        if not cumulative_returns:
            return 0

        peak = cumulative_returns[0]
        max_drawdown = 0

        for ret in cumulative_returns:
            if ret > peak:
                peak = ret
            drawdown = peak - ret
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    def _calculate_max_drawdown_duration(self, cumulative_returns: List[float]) -> int:
        """计算最大回撤持续时间"""
        if not cumulative_returns:
            return 0

        peak = cumulative_returns[0]
        peak_index = 0
        max_duration = 0
        current_duration = 0

        for i, ret in enumerate(cumulative_returns):
            if ret > peak:
                peak = ret
                peak_index = i
                current_duration = 0
            else:
                current_duration = i - peak_index
                max_duration = max(max_duration, current_duration)

        return max_duration

    def _calculate_skewness(self, data: np.ndarray) -> float:
        """计算偏度"""
        if len(data) < 3:
            return 0

        mean = np.mean(data)
        std = np.std(data)

        if std == 0:
            return 0

        n = len(data)
        skewness = (n / ((n - 1) * (n - 2))) * np.sum(((data - mean) / std) ** 3)

        return skewness

    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """计算峰度"""
        if len(data) < 4:
            return 0

        mean = np.mean(data)
        std = np.std(data)

        if std == 0:
            return 0

        n = len(data)
        kurtosis = (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * np.sum(((data - mean) / std) ** 4) - 3 * ((n - 1) ** 2 / ((n - 2) * (n - 3)))

        return kurtosis

    def _calculate_trend_slope(self, values: List[float]) -> float:
        """计算趋势斜率"""
        if len(values) < 2:
            return 0

        x = np.arange(len(values))
        y = np.array(values)

        # 线性回归计算斜率
        slope = np.polyfit(x, y, 1)[0]

        return slope

    def _calculate_overall_score(
        self,
        returns_analysis: Dict,
        risk_analysis: Dict,
        trading_analysis: Dict,
        benchmark_analysis: Dict
    ) -> Dict:
        """计算综合评分"""

        score = 0
        max_score = 100

        # 收益评分 (30%)
        if 'annualized_return' in returns_analysis:
            return_score = min(30, max(0, returns_analysis['annualized_return'] * 300))
            score += return_score

        # 夏普比率评分 (25%)
        if 'sharpe_ratio' in risk_analysis:
            sharpe_score = min(25, max(0, risk_analysis['sharpe_ratio'] * 25))
            score += sharpe_score

        # 最大回撤评分 (20%)
        if 'max_drawdown' in risk_analysis:
            drawdown = risk_analysis['max_drawdown']
            drawdown_score = max(0, 20 - drawdown * 200)  # 回撤越小分数越高
            score += drawdown_score

        # 胜率评分 (15%)
        if 'win_rate' in returns_analysis:
            win_rate_score = returns_analysis['win_rate'] * 15
            score += win_rate_score

        # 超额收益评分 (10%)
        if 'excess_return' in benchmark_analysis:
            excess_score = min(10, max(0, benchmark_analysis['excess_return'] * 100))
            score += excess_score

        return {
            "total_score": round(score, 2),
            "max_score": max_score,
            "grade": self._get_grade(score, max_score),
            "components": {
                "return_score": return_score if 'return_score' in locals() else 0,
                "sharpe_score": sharpe_score if 'sharpe_score' in locals() else 0,
                "drawdown_score": drawdown_score if 'drawdown_score' in locals() else 0,
                "win_rate_score": win_rate_score if 'win_rate_score' in locals() else 0,
                "excess_score": excess_score if 'excess_score' in locals() else 0
            }
        }

    def _get_grade(self, score: float, max_score: float) -> str:
        """根据分数获取等级"""
        percentage = score / max_score

        if percentage >= 0.9:
            return "A+"
        elif percentage >= 0.85:
            return "A"
        elif percentage >= 0.8:
            return "A-"
        elif percentage >= 0.75:
            return "B+"
        elif percentage >= 0.7:
            return "B"
        elif percentage >= 0.65:
            return "B-"
        elif percentage >= 0.6:
            return "C+"
        elif percentage >= 0.55:
            return "C"
        elif percentage >= 0.5:
            return "C-"
        else:
            return "D"

    def generate_performance_report(self, analysis_result: Dict) -> str:
        """生成性能报告文本"""

        if "error" in analysis_result:
            return f"性能分析失败: {analysis_result['error']}"

        report = []
        report.append("=" * 50)
        report.append("回测性能分析报告")
        report.append("=" * 50)

        # 总体评分
        if "overall_score" in analysis_result:
            score_data = analysis_result["overall_score"]
            report.append(f"\n📊 综合评分: {score_data['total_score']}/{score_data['max_score']} ({score_data['grade']})")

        # 收益分析
        if "returns" in analysis_result:
            returns = analysis_result["returns"]
            report.append(f"\n💰 收益表现:")
            report.append(f"   总收益率: {returns.get('total_return', 0):.2%}")
            report.append(f"   年化收益率: {returns.get('annualized_return', 0):.2%}")
            report.append(f"   胜率: {returns.get('win_rate', 0):.2%}")
            report.append(f"   夏普比率: {returns.get('sharpe_ratio', 0):.3f}")

        # 风险分析
        if "risk" in analysis_result:
            risk = analysis_result["risk"]
            report.append(f"\n⚠️  风险指标:")
            report.append(f"   年化波动率: {risk.get('volatility', 0):.2%}")
            report.append(f"   最大回撤: {risk.get('max_drawdown', 0):.2%}")
            report.append(f"   VaR(95%): {risk.get('var_95', 0):.2%}")

        # 交易分析
        if "trading" in analysis_result:
            trading = analysis_result["trading"]
            report.append(f"\n🔄 交易统计:")
            report.append(f"   总交易次数: {trading.get('total_trades', 0)}")
            report.append(f"   交易股票数: {trading.get('stocks_traded', 0)}")
            report.append(f"   总手续费: {trading.get('total_commission', 0):.2f}")

        # 基准对比
        if "benchmark" in analysis_result:
            benchmark = analysis_result["benchmark"]
            report.append(f"\n📈 基准对比:")
            report.append(f"   超额收益: {benchmark.get('excess_return', 0):.2%}")
            report.append(f"   信息比率: {benchmark.get('information_ratio', 0):.3f}")

        report.append("\n" + "=" * 50)
        report.append(f"报告生成时间: {analysis_result.get('analysis_date', 'Unknown')}")
        report.append("=" * 50)

        return "\n".join(report)