"""
策略 DSL → Backtrader Strategy
支持: calendar_month 入场, holding_days 出场
"""
import logging
from datetime import date
from typing import Any, Dict, List

import backtrader as bt

from schemas import StrategyConfig

logger = logging.getLogger(__name__)


class DSLStrategy(bt.Strategy):
    """DSL 驱动的回测策略"""

    params = (
        ("entry_months", []),      # 可买入的月份
        ("holding_days", 0),       # 持仓天数
        ("max_positions", 10),     # 最大持仓数
    )

    def __init__(self):
        self.entry_months = self.p.entry_months or list(range(1, 13))
        self.holding_days = self.p.holding_days
        self.order = None
        self.entries = {}  # data_name -> (date, bars_held)
        self._data_by_name = {d._name: d for d in self.datas}

    def next(self):
        # 卖出：持仓天数到期
        for data_name, (entry_date, bars_held) in list(self.entries.items()):
            if self.holding_days > 0 and bars_held >= self.holding_days:
                data = self._data_by_name.get(data_name)
                if data and self.getposition(data).size > 0:
                    self.close(data=data)
                    del self.entries[data_name]
                    logger.debug(f"卖出 {data_name} 持仓{bars_held}天")

        # 更新持仓天数
        for data_name in list(self.entries.keys()):
            self.entries[data_name] = (self.entries[data_name][0], self.entries[data_name][1] + 1)

        # 买入：日历月份条件
        dt = self.datas[0].datetime.date(0)
        if dt.month not in self.entry_months:
            return

        # 已有持仓的不重复买
        for data in self.datas:
            if self.getposition(data).size > 0:
                continue
            if data._name in self.entries:
                continue

            if len(self.entries) >= self.p.max_positions:
                break

            self.buy(data=data)
            self.entries[data._name] = (dt, 0)

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                logger.debug(f"买入完成: {order.data._name} @ {order.executed.price}")
            else:
                logger.debug(f"卖出完成: {order.data._name} @ {order.executed.price}")

    def notify_trade(self, trade):
        if trade.isclosed:
            logger.debug(f"交易关闭: {trade.pnl:.2f}")


def dsl_to_strategy_params(dsl: Dict[str, Any]) -> Dict:
    """从 DSL 提取策略参数"""
    entry_months = list(range(1, 13))
    for r in dsl.get("entry_rules", []):
        if r.get("type") == "calendar_month" and r.get("months"):
            entry_months = r["months"]
            break

    holding_days = 0
    for r in dsl.get("exit_rules", []):
        if r.get("type") == "holding_days" and r.get("days"):
            holding_days = r["days"]
            break

    cfg = dsl.get("config", {})
    return {
        "entry_months": entry_months,
        "holding_days": holding_days,
        "max_positions": cfg.get("max_positions", 10),
    }


def get_universe_symbols(dsl: Dict[str, Any]) -> List[str]:
    """从 DSL 解析股票池"""
    uni = dsl.get("universe", {})
    t = uni.get("type", "static")
    if t == "static":
        return uni.get("symbols", []) or []
    # dividend_screen 暂不支持，返回空
    if t == "dividend_screen":
        logger.warning("dividend_screen 暂未实现，请使用 static")
    return []
