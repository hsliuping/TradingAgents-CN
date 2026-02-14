"""
绩效分析：胜率、收益、回撤、Sharpe
Backtrader 分析器参考: https://www.backtrader.com/docu/analyzers-reference/
"""
from typing import Any, Dict

import backtrader as bt


def run_analyzers(cerebro: bt.Cerebro) -> Dict[str, Any]:
    """运行回测后收集分析器结果"""
    ret = {
        "final_value": cerebro.broker.getvalue(),
        "total_return": 0.0,
        "win_rate": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "trade_count": 0,
    }

    initial = cerebro.broker.startingcash or 1.0
    ret["total_return"] = (ret["final_value"] - initial) / initial * 100

    results = cerebro.run()
    if not results:
        return ret

    s = results[0]
    if not hasattr(s, "analyzers"):
        return ret

    # SharpeRatio: get_analysis() -> {"sharperatio": float}
    if "sharpe" in s.analyzers:
        a = s.analyzers.sharpe.get_analysis()
        ret["sharpe_ratio"] = float(a.get("sharperatio") or 0)

    # DrawDown: get_analysis() -> max.drawdown (0.xx 格式，如 0.123 表示 12.3%)
    if "drawdown" in s.analyzers:
        dd = s.analyzers.drawdown.get_analysis()
        max_dd = dd.get("max") or {}
        raw = max_dd.get("drawdown")
        ret["max_drawdown_pct"] = float(raw * 100) if raw is not None else 0.0

    # TradeAnalyzer: total.closed, won
    if "trades" in s.analyzers:
        ta = s.analyzers.trades.get_analysis()
        total = ta.get("total") or {}
        closed = total.get("closed", 0) or 0
        won = ta.get("won", 0) or 0
        ret["trade_count"] = int(closed)
        ret["win_rate"] = (won / closed * 100) if closed else 0.0

    return ret


def attach_analyzers(cerebro: bt.Cerebro) -> None:
    """附加绩效分析器"""
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
