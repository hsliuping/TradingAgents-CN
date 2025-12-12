"""
交易执行器
Trade Executor

负责执行具体的交易操作
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TradeRequest:
    """交易请求"""
    stock_code: str
    action: str  # 'buy' or 'sell'
    quantity: int
    price: float
    reason: str = ""

@dataclass
class TradeResult:
    """交易结果"""
    success: bool
    stock_code: str
    action: str
    quantity: int
    price: float
    executed_quantity: int
    executed_price: float
    commission: float
    slippage: float
    total_cost: float
    timestamp: datetime
    error_message: Optional[str] = None

class TradeExecutor:
    """交易执行器"""

    def __init__(self, config: Dict = None):
        """
        初始化交易执行器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 默认配置
        self.default_config = {
            "commission_rate": 0.0003,    # 手续费率
            "slippage_rate": 0.0001,      # 滑点率
            "min_commission": 5.0,        # 最小手续费
            "max_quantity_per_trade": 10000,  # 单笔最大交易数量
        }

        # 合并配置
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value

        # 交易统计
        self.trade_count = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_commission = 0.0

    def execute_trade(self, request: TradeRequest, current_cash: float) -> TradeResult:
        """
        执行交易

        Args:
            request: 交易请求
            current_cash: 当前可用现金

        Returns:
            TradeResult: 交易结果
        """
        try:
            # 验证交易请求
            validation_result = self._validate_trade_request(request, current_cash)
            if not validation_result[0]:
                return TradeResult(
                    success=False,
                    stock_code=request.stock_code,
                    action=request.action,
                    quantity=request.quantity,
                    price=request.price,
                    executed_quantity=0,
                    executed_price=0.0,
                    commission=0.0,
                    slippage=0.0,
                    total_cost=0.0,
                    timestamp=datetime.now(),
                    error_message=validation_result[1]
                )

            # 计算执行价格（包含滑点）
            executed_price = self._calculate_executed_price(request)

            # 计算手续费
            commission = self._calculate_commission(
                request.action, request.quantity, executed_price
            )

            # 计算总成本
            total_cost = self._calculate_total_cost(
                request.action, request.quantity, executed_price, commission
            )

            # 检查资金充足性（仅对买入）
            if request.action == 'buy' and total_cost > current_cash:
                return TradeResult(
                    success=False,
                    stock_code=request.stock_code,
                    action=request.action,
                    quantity=request.quantity,
                    price=request.price,
                    executed_quantity=0,
                    executed_price=0.0,
                    commission=0.0,
                    slippage=0.0,
                    total_cost=0.0,
                    timestamp=datetime.now(),
                    error_message="资金不足"
                )

            # 计算滑点
            slippage = abs(executed_price - request.price) * request.quantity

            # 执行交易
            self.trade_count += 1
            self.successful_trades += 1
            self.total_commission += commission

            result = TradeResult(
                success=True,
                stock_code=request.stock_code,
                action=request.action,
                quantity=request.quantity,
                price=request.price,
                executed_quantity=request.quantity,
                executed_price=executed_price,
                commission=commission,
                slippage=slippage,
                total_cost=total_cost,
                timestamp=datetime.now()
            )

            self.logger.info(f"交易执行成功: {request.stock_code} {request.action} {request.quantity}股 @ {executed_price:.2f}")
            return result

        except Exception as e:
            self.trade_count += 1
            self.failed_trades += 1
            error_msg = f"交易执行失败: {e}"

            self.logger.error(error_msg)
            return TradeResult(
                success=False,
                stock_code=request.stock_code,
                action=request.action,
                quantity=request.quantity,
                price=request.price,
                executed_quantity=0,
                executed_price=0.0,
                commission=0.0,
                slippage=0.0,
                total_cost=0.0,
                timestamp=datetime.now(),
                error_message=error_msg
            )

    def execute_batch_trades(
        self,
        requests: List[TradeRequest],
        current_cash: float
    ) -> List[TradeResult]:
        """
        批量执行交易

        Args:
            requests: 交易请求列表
            current_cash: 当前可用现金

        Returns:
            List[TradeResult]: 交易结果列表
        """
        results = []
        remaining_cash = current_cash

        for request in requests:
            result = self.execute_trade(request, remaining_cash)
            results.append(result)

            # 更新可用现金
            if result.success:
                if result.action == 'buy':
                    remaining_cash -= result.total_cost
                elif result.action == 'sell':
                    remaining_cash += (result.executed_price * result.executed_quantity - result.commission)

        return results

    def _validate_trade_request(self, request: TradeRequest, current_cash: float) -> Tuple[bool, str]:
        """验证交易请求"""

        # 检查基本参数
        if not request.stock_code:
            return False, "股票代码不能为空"

        if request.action not in ['buy', 'sell']:
            return False, "交易动作必须是buy或sell"

        if request.quantity <= 0:
            return False, "交易数量必须大于0"

        if request.price <= 0:
            return False, "交易价格必须大于0"

        # 检查数量限制
        if request.quantity > self.config["max_quantity_per_trade"]:
            return False, f"单笔交易数量不能超过{self.config['max_quantity_per_trade']}"

        # 检查资金充足性（买入时）
        if request.action == 'buy':
            estimated_cost = request.quantity * request.price * (1 + self.config["commission_rate"])
            if estimated_cost > current_cash:
                return False, f"资金不足，需要{estimated_cost:.2f}，可用{current_cash:.2f}"

        return True, ""

    def _calculate_executed_price(self, request: TradeRequest) -> float:
        """计算执行价格（包含滑点）"""

        slippage_rate = self.config["slippage_rate"]

        if request.action == 'buy':
            # 买入时价格可能上浮
            executed_price = request.price * (1 + slippage_rate)
        else:
            # 卖出时价格可能下浮
            executed_price = request.price * (1 - slippage_rate)

        return round(executed_price, 2)

    def _calculate_commission(self, action: str, quantity: int, price: float) -> float:
        """计算手续费"""

        trade_value = quantity * price
        commission = trade_value * self.config["commission_rate"]

        # 最低手续费
        commission = max(commission, self.config["min_commission"])

        return round(commission, 2)

    def _calculate_total_cost(
        self,
        action: str,
        quantity: int,
        price: float,
        commission: float
    ) -> float:
        """计算总成本"""

        trade_value = quantity * price

        if action == 'buy':
            # 买入成本 = 交易金额 + 手续费
            total_cost = trade_value + commission
        else:
            # 卖出收入 = 交易金额 - 手续费
            total_cost = trade_value - commission

        return round(total_cost, 2)

    def get_trade_statistics(self) -> Dict:
        """获取交易统计"""

        success_rate = (self.successful_trades / self.trade_count * 100) if self.trade_count > 0 else 0

        return {
            "total_trades": self.trade_count,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": round(success_rate, 2),
            "total_commission": round(self.total_commission, 2)
        }

    def reset_statistics(self):
        """重置交易统计"""
        self.trade_count = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_commission = 0.0

    def estimate_trade_cost(self, action: str, quantity: int, price: float) -> Dict:
        """估算交易成本"""

        trade_value = quantity * price
        commission = self._calculate_commission(action, quantity, price)
        estimated_slippage = price * self.config["slippage_rate"] * quantity
        total_cost = self._calculate_total_cost(action, quantity, price, commission)

        return {
            "trade_value": trade_value,
            "commission": commission,
            "estimated_slippage": estimated_slippage,
            "total_cost": total_cost,
            "cost_rate": commission / trade_value if trade_value > 0 else 0
        }