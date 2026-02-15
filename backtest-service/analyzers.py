"""
绩效分析：胜率、收益、回撤、Sharpe、成交明细
Backtrader 分析器参考: https://www.backtrader.com/docu/analyzers-reference/
"""
import logging
from typing import Any, Dict, List

import backtrader as bt

logger = logging.getLogger(__name__)


class OrderExecutionLogger(bt.Analyzer):
    """记录每笔订单和成交，便于调试，并收集 transactions 供 API 返回"""

    def __init__(self):
        super().__init__()
        self._transactions: List[Dict[str, Any]] = []

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        # 使用 order.data 的 datetime，确保多数据源时日期正确
        data_dt = getattr(order.data, "datetime", None)
        dt_str = data_dt.datetime(0).strftime("%Y-%m-%d") if (data_dt and len(self)) else ""
        name = getattr(order.data, "_name", str(order.data))
        if order.status == order.Completed:
            side = "买" if order.isbuy() else "卖"
            size = abs(int(order.executed.size))
            price = float(order.executed.price)
            execution_amount = round(size * price, 2)
            # 买入：持仓成本=成交金额；卖出：持仓成本在匹配 trade 时填充
            cost_basis = execution_amount if order.isbuy() else None
            self._transactions.append({
                "date": dt_str,
                "symbol": name,
                "side": "buy" if order.isbuy() else "sell",
                "size": size,
                "price": round(price, 2),
                "cost_basis": cost_basis,
                "execution_amount": execution_amount,
            })
            logger.info(
                "[OrderExecution] %s 成交 %s %s 数量=%d 价格=%.2f 成交额=%.2f",
                dt_str, side, name, order.executed.size, order.executed.price, execution_amount
            )
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            logger.info("[OrderExecution] %s 订单 %s %s 状态=%s", dt_str, name, order.getstatusname(), order.status)

    def notify_trade(self, trade):
        if trade.isclosed:
            name = getattr(trade.data, "_name", str(trade.data))
            logger.info(
                "[OrderExecution] 平仓 %s 盈亏=%.2f 净盈亏=%.2f",
                name, trade.pnl, trade.pnlcomm
            )

    def get_analysis(self):
        return {"transactions": self._transactions}


class TradeRecorder(bt.Analyzer):
    """记录每笔已平仓交易的明细（开仓日、平仓日、标的、盈亏等）"""

    def __init__(self):
        super().__init__()
        self._trades: List[Dict[str, Any]] = []

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        try:
            # 使用 trade.data 的 datetime；close 时当前 bar 即为平仓 bar
            data_dt = getattr(trade.data, "datetime", None)
            dt_open = data_dt.datetime(trade.baropen) if (data_dt and trade.baropen is not None) else None
            dt_close = data_dt.datetime(0) if data_dt else None
            symbol = getattr(trade.data, "_name", None) or str(trade.data)
            # 平仓时 size 为 0，从 history 取开仓数量（若有）
            size = 0
            if hasattr(trade, "history") and trade.history:
                for h in trade.history:
                    if hasattr(h, "status") and hasattr(h, "size") and h.size:
                        size = abs(int(h.size))
                        break
        except Exception:
            dt_open = dt_close = None
            symbol = str(trade.data)
            size = 0
        self._trades.append({
            "symbol": symbol,
            "open_date": dt_open.strftime("%Y-%m-%d") if dt_open else "",
            "close_date": dt_close.strftime("%Y-%m-%d") if dt_close else "",
            "size": size,
            "pnl": round(float(trade.pnl), 2),
            "pnl_net": round(float(trade.pnlcomm), 2),
            "commission": round(float(trade.commission), 4),
        })

    def get_analysis(self):
        return {"trades": self._trades}


class ValueDrawDown(bt.Analyzer):
    """在 next 中跟踪 broker value，计算最大回撤（不依赖 notify_fund）"""

    def __init__(self):
        super().__init__()
        self._peak = float("-inf")
        self._max_drawdown_pct = 0.0

    def next(self):
        val = self.strategy.broker.getvalue()
        if val > self._peak:
            self._peak = val
        if self._peak > 0:
            dd = 100.0 * (self._peak - val) / self._peak
            self._max_drawdown_pct = max(self._max_drawdown_pct, dd)

    def get_analysis(self):
        return {"max": {"drawdown": self._max_drawdown_pct / 100.0}}


def run_analyzers(cerebro: bt.Cerebro, results: List[bt.Strategy] | None = None) -> Dict[str, Any]:
    """运行回测后收集分析器结果"""
    broker = cerebro.broker
    initial = broker.startingcash or 1.0
    final_value = broker.getvalue()
    cash = broker.getcash()

    # 调试：无成交却有收益时，打印 broker 明细
    ret = {
        "final_value": final_value,
        "total_return": 0.0,
        "win_rate": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "trade_count": 0,
        "trades": [],
        "transactions": [],
        "positions": [],
    }
    ret["total_return"] = (final_value - initial) / initial * 100

    # 收集持仓明细（用于排查「无成交却有收益」）
    positions_info = []
    try:
        for data in cerebro.datas:
            pos = broker.getposition(data)
            if pos.size != 0:
                positions_info.append({
                    "name": getattr(data, "_name", str(data)),
                    "size": pos.size,
                    "price": pos.price,
                    "value": pos.size * pos.price if pos.price else 0,
                })
    except Exception as e:
        logger.warning("[analyzers] 获取持仓失败: %s", e)

    ret["positions"] = positions_info

    if results is None:
        results = cerebro.run()
    if not results:
        return ret

    s = results[0]
    if not hasattr(s, "analyzers"):
        return ret

    # SharpeRatio: get_analysis() -> {"sharperatio": float}
    if hasattr(s.analyzers, "sharpe"):
        a = s.analyzers.sharpe.get_analysis()
        ret["sharpe_ratio"] = float(a.get("sharperatio") or 0)

    # DrawDown: get_analysis() -> max.drawdown (0.xx 格式，如 0.123 表示 12.3%)
    if hasattr(s.analyzers, "drawdown"):
        dd = s.analyzers.drawdown.get_analysis()
        max_dd = dd.get("max") or {}
        raw = max_dd.get("drawdown")
        ret["max_drawdown_pct"] = float(raw * 100) if raw is not None else 0.0

    # TradeAnalyzer: total.closed, won.total（won 是子 dict，含 total 键）
    if hasattr(s.analyzers, "trades"):
        ta = s.analyzers.trades.get_analysis()
        total = ta.get("total") or {}
        closed = total.get("closed", 0) or 0
        won_obj = ta.get("won")
        won = (won_obj.get("total", 0) if hasattr(won_obj, "get") else getattr(won_obj, "total", 0)) or 0
        ret["trade_count"] = int(closed)
        ret["win_rate"] = (won / closed * 100) if closed else 0.0

    # TradeRecorder: 已平仓交易明细（含盈亏）
    if hasattr(s.analyzers, "trade_recorder"):
        rec = s.analyzers.trade_recorder.get_analysis()
        ret["trades"] = rec.get("trades", [])
        if ret["trade_count"] == 0 and ret["trades"]:
            ret["trade_count"] = len(ret["trades"])
            ret["win_rate"] = sum(1 for t in ret["trades"] if (t.get("pnl_net") or 0) > 0) / len(ret["trades"]) * 100

    # 成交明细：优先从 OrderExecutionLogger 获取（可靠），否则从 Transactions 分析器
    analyzer_names = [a for a in dir(s.analyzers) if not a.startswith("_")]
    logger.info("[analyzers] 可用分析器=%s | sharpe=%.2f max_dd=%.2f%% win_rate=%.1f%%",
               analyzer_names, ret.get("sharpe_ratio", 0), ret.get("max_drawdown_pct", 0), ret.get("win_rate", 0))
    if hasattr(s.analyzers, "order_logger"):
        rec = s.analyzers.order_logger.get_analysis()
        ret["transactions"] = rec.get("transactions", [])
        logger.info("[analyzers] order_logger 返回 transactions len=%d", len(ret["transactions"]))
        # 为卖出记录附加盈亏、持仓成本
        # 优先按 symbol 顺序匹配 trade；若无 trade 则按 FIFO 用买入配对计算
        if ret["transactions"]:
            from collections import defaultdict
            # 1) 从 trades 匹配
            if ret["trades"]:
                trades_by_symbol: Dict[str, List[Dict]] = defaultdict(list)
                for t in ret["trades"]:
                    trades_by_symbol[t.get("symbol", "")].append(t)
                sell_idx: Dict[str, int] = defaultdict(int)
                for tx in ret["transactions"]:
                    if tx.get("side") == "sell":
                        sym = tx.get("symbol", "")
                        trades = trades_by_symbol.get(sym, [])
                        idx = sell_idx[sym]
                        if idx < len(trades):
                            match = trades[idx]
                            tx["pnl_net"] = match.get("pnl_net")
                            pnl = match.get("pnl") or 0
                            exec_amt = tx.get("execution_amount") or 0
                            tx["cost_basis"] = round(exec_amt - pnl, 2)
                            sell_idx[sym] = idx + 1
            # 2) 未匹配到的 sell：用 FIFO 买入配对计算
            buy_queue: Dict[str, List[tuple]] = defaultdict(list)  # (remaining_size, cost_per_unit)
            for tx in ret["transactions"]:
                sym = tx.get("symbol", "")
                if tx.get("side") == "buy":
                    sz = tx.get("size") or 0
                    amt = tx.get("execution_amount") or 0
                    if sz > 0:
                        buy_queue[sym].append((sz, amt / sz))
                elif tx.get("side") == "sell":
                    if tx.get("cost_basis") is not None and tx.get("pnl_net") is not None:
                        continue
                    sell_size = tx.get("size") or 0
                    sell_amt = tx.get("execution_amount") or 0
                    remaining = sell_size
                    cost_total = 0.0
                    while remaining > 0 and buy_queue[sym]:
                        b_size, b_price = buy_queue[sym][0]
                        if b_size <= 0:
                            buy_queue[sym].pop(0)
                            continue
                        close_size = min(remaining, b_size)
                        cost_total += close_size * b_price
                        remaining -= close_size
                        if close_size >= b_size:
                            buy_queue[sym].pop(0)
                        else:
                            buy_queue[sym][0] = (b_size - close_size, b_price)
                    if cost_total > 0:
                        tx["cost_basis"] = round(cost_total, 2)
                        tx["pnl_net"] = round(sell_amt - cost_total, 2)
        if ret["trade_count"] == 0 and ret["transactions"]:
            buy_count = sum(1 for t in ret["transactions"] if t.get("side") == "buy")
            ret["trade_count"] = buy_count
            if buy_count and ret["trades"]:
                win_count = sum(1 for t in ret["trades"] if (t.get("pnl_net") or 0) > 0)
                ret["win_rate"] = win_count / buy_count * 100
    elif hasattr(s.analyzers, "transactions"):
        tx_analysis = s.analyzers.transactions.get_analysis()
        tx_list = []
        for dt_key, entries in tx_analysis.items():
            if isinstance(dt_key, str) and dt_key in ("date", "amount", "price", "sid", "symbol", "value"):
                continue
            dt_str = str(dt_key)[:10] if dt_key else ""
            for ent in entries if isinstance(entries, list) else []:
                if len(ent) >= 5:
                    size, price, sid, symbol, value = ent[0], ent[1], ent[2], ent[3], ent[4]
                    exec_amt = round(abs(float(value)), 2)
                    tx_list.append({
                        "date": dt_str,
                        "symbol": symbol,
                        "side": "buy" if size > 0 else "sell",
                        "size": abs(int(size)),
                        "price": round(float(price), 2),
                        "cost_basis": exec_amt if size > 0 else None,
                        "execution_amount": exec_amt,
                    })
        ret["transactions"] = sorted(tx_list, key=lambda x: (x["date"], x["symbol"]))

    # 调试日志
    if ret["trade_count"] == 0 and len(ret["transactions"]) == 0 and abs(ret["total_return"]) > 0.001:
        if positions_info:
            logger.info(
                "[analyzers] 回测完成（有持仓未平仓）| initial=%.2f final=%.2f cash=%.2f return=%.4f%% 持仓=%s",
                initial, final_value, cash, ret["total_return"], positions_info
            )
        else:
            logger.warning(
                "[analyzers] 异常：无成交无持仓却有收益 | initial=%.2f final=%.2f cash=%.2f return=%.4f%%",
                initial, final_value, cash, ret["total_return"]
            )
    else:
        logger.info(
            "[analyzers] 回测完成 | initial=%.2f final=%.2f cash=%.2f return=%.4f%% trades=%d tx=%d 持仓=%s",
            initial, final_value, cash, ret["total_return"], ret["trade_count"], len(ret["transactions"]), positions_info
        )

    return ret


def attach_analyzers(cerebro: bt.Cerebro) -> None:
    """附加绩效分析器"""
    # SharpeRatio: 用日收益，样本多；年化输出
    cerebro.addanalyzer(
        bt.analyzers.SharpeRatio,
        _name="sharpe",
        timeframe=bt.TimeFrame.Days,
        annualize=True,
    )
    # DrawDown: 内置需 notify_fund，改用自定义 ValueDrawDown（在 next 中取 broker value）
    cerebro.addanalyzer(ValueDrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(OrderExecutionLogger, _name="order_logger")
    cerebro.addanalyzer(TradeRecorder, _name="trade_recorder")
    cerebro.addanalyzer(bt.analyzers.Transactions, _name="transactions")
