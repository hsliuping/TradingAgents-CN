"""
投资组合管理器
Portfolio Manager

负责管理回测过程中的投资组合状态
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """持仓信息"""
    stock_code: str
    shares: int
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_ratio: float = 0.0

@dataclass
class Portfolio:
    """投资组合信息"""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    total_value: float = 0.0
    stock_value: float = 0.0
    total_cost: float = 0.0
    realized_pnl: float = 0.0
    max_portfolio_value: float = 0.0
    last_update: Optional[datetime] = None

class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, config):
        """
        初始化投资组合管理器

        Args:
            config: 回测配置
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 投资组合状态
        self.portfolio = Portfolio(cash=0.0)
        self.initial_capital = 0.0

        # 历史记录
        self.portfolio_value_history = []
        self.max_drawdown_history = []

        # 交易统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0

    def initialize(self, initial_capital: float):
        """
        初始化投资组合

        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.portfolio = Portfolio(cash=initial_capital, max_portfolio_value=initial_capital)
        self.portfolio_value_history = [initial_capital]
        self.max_drawdown_history = [0.0]

        # 重置统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0

        self.logger.info(f"投资组合初始化完成，初始资金: {initial_capital:,.2f}")

    def buy_stock(
        self,
        stock_code: str,
        shares: int,
        price: float,
        commission: float = 0.0
    ) -> bool:
        """
        买入股票

        Args:
            stock_code: 股票代码
            shares: 买入股数
            price: 买入价格
            commission: 手续费

        Returns:
            bool: 是否成功
        """
        try:
            total_cost = shares * price + commission

            # 检查资金是否充足
            if self.portfolio.cash < total_cost:
                self.logger.warning(f"资金不足，无法买入 {stock_code}。需要: {total_cost:,.2f}, 可用: {self.portfolio.cash:,.2f}")
                return False

            # 扣除资金
            self.portfolio.cash -= total_cost
            self.total_commission += commission

            # 更新持仓
            if stock_code in self.portfolio.positions:
                position = self.portfolio.positions[stock_code]
                # 计算新的平均成本
                total_shares = position.shares + shares
                total_cost_basis = position.shares * position.avg_cost + shares * price
                new_avg_cost = total_cost_basis / total_shares

                position.shares = total_shares
                position.avg_cost = new_avg_cost
                position.current_price = price
                position.market_value = total_shares * price
                position.unrealized_pnl = (price - new_avg_cost) * total_shares
                position.unrealized_pnl_ratio = (price - new_avg_cost) / new_avg_cost

                self.logger.debug(f"加仓 {stock_code}: {shares}股, 价格: {price:.2f}, 平均成本: {new_avg_cost:.2f}")
            else:
                # 新建持仓
                position = Position(
                    stock_code=stock_code,
                    shares=shares,
                    avg_cost=price,
                    current_price=price,
                    market_value=shares * price,
                    unrealized_pnl=0.0,
                    unrealized_pnl_ratio=0.0
                )
                self.portfolio.positions[stock_code] = position

                self.logger.debug(f"新建持仓 {stock_code}: {shares}股, 价格: {price:.2f}")

            # 更新统计
            self.portfolio.total_cost += shares * price
            self.total_trades += 1

            # 重新计算投资组合总值
            self._recalculate_portfolio_value()

            return True

        except Exception as e:
            self.logger.error(f"买入股票 {stock_code} 时出错: {e}")
            return False

    def sell_stock(
        self,
        stock_code: str,
        shares: int,
        price: float,
        commission: float = 0.0
    ) -> bool:
        """
        卖出股票

        Args:
            stock_code: 股票代码
            shares: 卖出股数
            price: 卖出价格
            commission: 手续费

        Returns:
            bool: 是否成功
        """
        try:
            if stock_code not in self.portfolio.positions:
                self.logger.warning(f"没有持仓 {stock_code}，无法卖出")
                return False

            position = self.portfolio.positions[stock_code]

            if position.shares < shares:
                self.logger.warning(f"持仓不足，无法卖出 {stock_code}。持有: {position.shares}, 尝试卖出: {shares}")
                return False

            # 计算收入
            total_proceeds = shares * price - commission

            # 增加现金
            self.portfolio.cash += total_proceeds
            self.total_commission += commission

            # 计算已实现盈亏
            cost_basis = shares * position.avg_cost
            realized_pnl = total_proceeds - cost_basis
            self.portfolio.realized_pnl += realized_pnl

            # 更新持仓
            if position.shares == shares:
                # 完全卖出
                del self.portfolio.positions[stock_code]
                self.logger.debug(f"完全卖出 {stock_code}: {shares}股, 价格: {price:.2f}, 已实现盈亏: {realized_pnl:.2f}")
            else:
                # 部分卖出
                position.shares -= shares
                position.market_value = position.shares * price
                position.unrealized_pnl = (price - position.avg_cost) * position.shares
                position.unrealized_pnl_ratio = (price - position.avg_cost) / position.avg_cost

                self.logger.debug(f"部分卖出 {stock_code}: {shares}股, 价格: {price:.2f}, 已实现盈亏: {realized_pnl:.2f}")

            # 更新统计
            self.portfolio.total_cost -= cost_basis
            self.total_trades += 1

            if realized_pnl > 0:
                self.winning_trades += 1
            elif realized_pnl < 0:
                self.losing_trades += 1

            # 重新计算投资组合总值
            self._recalculate_portfolio_value()

            return True

        except Exception as e:
            self.logger.error(f"卖出股票 {stock_code} 时出错: {e}")
            return False

    def update_portfolio_value(self, current_prices: Dict[str, float]):
        """
        更新投资组合价值

        Args:
            current_prices: 当前价格字典
        """
        total_stock_value = 0.0

        # 更新每个持仓的市值
        for stock_code, position in self.portfolio.positions.items():
            if stock_code in current_prices:
                price = current_prices[stock_code]
                position.current_price = price
                position.market_value = position.shares * price
                position.unrealized_pnl = (price - position.avg_cost) * position.shares
                position.unrealized_pnl_ratio = (price - position.avg_cost) / position.avg_cost if position.avg_cost > 0 else 0

                total_stock_value += position.market_value

        # 更新投资组合总值
        self.portfolio.stock_value = total_stock_value
        self.portfolio.total_value = self.portfolio.cash + total_stock_value
        self.portfolio.last_update = datetime.now()

        # 记录历史最大值
        if self.portfolio.total_value > self.portfolio.max_portfolio_value:
            self.portfolio.max_portfolio_value = self.portfolio.total_value

        # 返回投资组合总值
        return self.portfolio.total_value

        # 记录价值历史
        self.portfolio_value_history.append(self.portfolio.total_value)

        # 计算当前回撤
        current_drawdown = (self.portfolio.max_portfolio_value - self.portfolio.total_value) / self.portfolio.max_portfolio_value
        self.max_drawdown_history.append(current_drawdown)

    def _recalculate_portfolio_value(self):
        """重新计算投资组合价值"""
        total_stock_value = 0.0

        for position in self.portfolio.positions.values():
            total_stock_value += position.market_value

        self.portfolio.stock_value = total_stock_value
        self.portfolio.total_value = self.portfolio.cash + total_stock_value

    def get_current_positions(self) -> Dict[str, float]:
        """
        获取当前持仓（股数）

        Returns:
            Dict[str, float]: 股票代码 -> 持仓股数
        """
        return {
            stock_code: position.shares
            for stock_code, position in self.portfolio.positions.items()
        }

    def get_total_value(self) -> float:
        """获取投资组合总价值"""
        return self.portfolio.total_value

    def get_available_cash(self) -> float:
        """获取可用现金"""
        return self.portfolio.cash

    def get_stock_value(self) -> float:
        """获取股票市值"""
        return self.portfolio.stock_value

    def get_current_position_ratio(self) -> float:
        """获取当前仓位比例"""
        if self.portfolio.total_value <= 0:
            return 0.0
        return self.portfolio.stock_value / self.portfolio.total_value

    def get_average_cost(self) -> float:
        """获取平均持仓成本"""
        if not self.portfolio.positions:
            return 0.0

        total_shares = sum(position.shares for position in self.portfolio.positions.values())
        if total_shares == 0:
            return 0.0

        total_cost = sum(position.shares * position.avg_cost for position in self.portfolio.positions.values())
        return total_cost / total_shares

    def get_pnl_ratio(self) -> float:
        """获取总盈亏比例"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.portfolio.total_value - self.initial_capital) / self.initial_capital

    def get_max_drawdown(self) -> float:
        """获取最大回撤"""
        if not self.max_drawdown_history:
            return 0.0
        return max(self.max_drawdown_history)

    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """
        计算风险价值 (VaR)

        Args:
            confidence_level: 置信水平

        Returns:
            float: VaR值
        """
        if len(self.portfolio_value_history) < 30:
            return 0.0

        # 计算日收益率
        returns = []
        for i in range(1, len(self.portfolio_value_history)):
            daily_return = (self.portfolio_value_history[i] - self.portfolio_value_history[i-1]) / self.portfolio_value_history[i-1]
            returns.append(daily_return)

        if not returns:
            return 0.0

        # 计算VaR分位数
        var_percentile = (1 - confidence_level) * 100
        var_daily = np.percentile(returns, var_percentile)

        # 转换为绝对金额
        current_value = self.portfolio.total_value
        var_absolute = abs(var_daily * current_value)

        return var_absolute

    def get_portfolio_summary(self) -> Dict:
        """获取投资组合摘要"""

        # 持仓明细
        positions_detail = []
        for stock_code, position in self.portfolio.positions.items():
            positions_detail.append({
                'stock_code': stock_code,
                'shares': position.shares,
                'avg_cost': position.avg_cost,
                'current_price': position.current_price,
                'market_value': position.market_value,
                'unrealized_pnl': position.unrealized_pnl,
                'unrealized_pnl_ratio': position.unrealized_pnl_ratio,
                'weight': position.market_value / self.portfolio.total_value if self.portfolio.total_value > 0 else 0
            })

        # 盈亏统计
        total_unrealized_pnl = sum(position.unrealized_pnl for position in self.portfolio.positions.values())
        total_pnl = total_unrealized_pnl + self.portfolio.realized_pnl

        # 交易统计
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0

        summary = {
            'total_value': self.portfolio.total_value,
            'cash': self.portfolio.cash,
            'stock_value': self.portfolio.stock_value,
            'position_ratio': self.get_current_position_ratio(),
            'total_pnl': total_pnl,
            'realized_pnl': self.portfolio.realized_pnl,
            'unrealized_pnl': total_unrealized_pnl,
            'pnl_ratio': self.get_pnl_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'positions_count': len(self.portfolio.positions),
            'positions_detail': positions_detail,
            'trading_stats': {
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': win_rate,
                'total_commission': self.total_commission
            },
            'last_update': self.portfolio.last_update
        }

        return summary

    def reset(self):
        """重置投资组合"""
        self.portfolio = Portfolio(cash=self.initial_capital, max_portfolio_value=self.initial_capital)
        self.portfolio_value_history = [self.initial_capital]
        self.max_drawdown_history = [0.0]

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0

        self.logger.info("投资组合已重置")

# 需要导入numpy
try:
    import numpy as np
except ImportError:
    logger.warning("NumPy未安装，部分功能可能受限")
    np = None