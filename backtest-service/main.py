"""
Backtrader 回测服务 - FastAPI 包装
POST /run        接收策略 DSL，返回回测结果
POST /run_python 接收 Python 代码 + config，动态加载策略执行
GET  /health     健康检查
"""
import json
import logging
import datetime as dt_module
from typing import Any, Dict, List, Type

import backtrader as bt
from fastapi import FastAPI
from pydantic import BaseModel

from config import MONGO_URI, MONGO_DB, PORT
from data_feed import make_backtrader_feed
from translator import DSLStrategy, dsl_to_strategy_params
from universe import get_universe_symbols
from analyzers import attach_analyzers, run_analyzers
from schemas import StrategyConfig
from sizers import CNAllInSizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Backtrader Backtest Service", version="1.0.0")

STRATEGY_CLASS_NAME = "GeneratedStrategy"


class RunRequest(BaseModel):
    """回测请求体（DSL）"""
    strategy: Dict[str, Any]


class RunPythonRequest(BaseModel):
    """Python 策略回测请求体"""
    code: str
    config: Dict[str, Any]


class RunResponse(BaseModel):
    """回测响应"""
    success: bool = True
    summary: Dict[str, Any]
    error: str | None = None
    logs: List[str] = []      # 运行日志（关键事件）
    warnings: List[str] = []  # 警告信息（可能的问题）


def _build_cerebro(dsl: Dict[str, Any]) -> bt.Cerebro:
    """根据 DSL 构建 Cerebro 实例"""
    cfg = dsl.get("config", {})
    start_year = cfg.get("start_year", 2016)
    end_year = cfg.get("end_year", 2025)
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"

    # 传递回测开始日期，用于获取历史成分股（避免生存者偏差）
    symbols = get_universe_symbols(dsl, backtest_start_date=start_date)
    if not symbols:
        raise ValueError("股票池为空，请配置 universe.symbols (type=static) 或 universe.index_code (type=index)")
    initial_cash = float(cfg.get("initial_capital", 1_000_000))
    market = cfg.get("market", "CN")
    data_source = cfg.get("data_source", "tushare")  # 避免多数据源重复

    feeds = make_backtrader_feed(
        symbols, start_date, end_date, market, data_source
    )
    if not feeds:
        raise ValueError(f"无可用数据: symbols={symbols}, range={start_date}~{end_date}")

    cerebro = bt.Cerebro()
    for fd in feeds:
        cerebro.adddata(fd)
    cerebro.broker.setcash(initial_cash)
    if market == "CN":
        cerebro.addsizer(CNAllInSizer)
    # 暂用默认 broker，CN 规则（T+1/涨跌停）后续在 cn_broker 中实现

    params = dsl_to_strategy_params(dsl)
    cerebro.addstrategy(DSLStrategy, **params)
    attach_analyzers(cerebro)

    return cerebro


def _load_strategy_class(code: str) -> Type[bt.Strategy]:
    """exec(code) 获取 GeneratedStrategy 类，注入 datetime/date/timedelta 供策略使用"""
    local_ns: Dict[str, Any] = {}
    exec_globals = {
        "bt": bt,
        "__builtins__": __builtins__,
        "datetime": dt_module.datetime,
        "date": dt_module.date,
        "timedelta": dt_module.timedelta,
    }
    exec(code, exec_globals, local_ns)
    cls = local_ns.get(STRATEGY_CLASS_NAME)
    if cls is None:
        raise ValueError(f"代码中未定义类 {STRATEGY_CLASS_NAME}，请确保策略类名为 {STRATEGY_CLASS_NAME}")
    if not issubclass(cls, bt.Strategy):
        raise ValueError(f"{STRATEGY_CLASS_NAME} 必须继承 bt.Strategy")
    return cls


def _build_cerebro_from_python(code: str, config: Dict[str, Any]) -> bt.Cerebro:
    """根据 Python 代码和 config 构建 Cerebro"""
    strategy_cls = _load_strategy_class(code)

    start_year = config.get("start_year", 2016)
    end_year = config.get("end_year", 2025)
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"

    # 传递回测开始日期，用于获取历史成分股（避免生存者偏差）
    symbols = get_universe_symbols(config, backtest_start_date=start_date)
    if not symbols:
        raise ValueError("股票池为空，请配置 config.universe.symbols 或 config.universe.index_code")
    initial_cash = float(config.get("initial_capital", 1_000_000))
    market = config.get("market", "CN")
    data_source = config.get("data_source", "tushare")

    feeds = make_backtrader_feed(symbols, start_date, end_date, market, data_source)
    if not feeds:
        raise ValueError(f"无可用数据: symbols={symbols}, range={start_date}~{end_date}")

    cerebro = bt.Cerebro()
    for fd in feeds:
        cerebro.adddata(fd)
    cerebro.broker.setcash(initial_cash)
    # 中国 A 股：全仓，按 100 股（1手）取整
    if market == "CN":
        cerebro.addsizer(CNAllInSizer)
    cerebro.addstrategy(strategy_cls)
    attach_analyzers(cerebro)
    return cerebro


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok", "service": "backtrader-backtest"}


@app.post("/run", response_model=RunResponse)
def run_backtest(req: RunRequest) -> RunResponse:
    """执行回测（DSL）"""
    logs: List[str] = []
    warnings: List[str] = []

    try:
        dsl = req.strategy
        # 校验
        StrategyConfig.model_validate(dsl)
        cerebro = _build_cerebro(dsl)
        symbols = get_universe_symbols(dsl)
        initial = cerebro.broker.getcash()

        cfg = dsl.get("config", {})
        logs.append(f"股票池: {symbols}")
        logs.append(f"初始资金: {initial:,.0f}")
        logs.append(f"回测区间: {cfg.get('start_year', 2016)}-{cfg.get('end_year', 2025)}")

        # 检查数据完整性
        data_count = len(cerebro.datas)
        logs.append(f"加载数据源数量: {data_count}")
        if data_count < len(symbols):
            warnings.append(f"数据缺失: 请求{len(symbols)}只股票，实际加载{data_count}只")

        logger.info("[run] 开始回测 symbols=%s initial_cash=%.2f", symbols, initial)
        results = cerebro.run()

        final_value = cerebro.broker.getvalue()
        logger.info("[run] 回测执行完毕 broker_value=%.2f", final_value)
        summary = run_analyzers(cerebro, results)

        # 收集关键运行指标
        logs.append(f"最终资产: {final_value:,.2f}")
        logs.append(f"总收益率: {summary.get('total_return', 0):.2f}%")
        logs.append(f"交易次数: {summary.get('trade_count', 0)}")

        # 检测潜在问题
        trade_count = summary.get("trade_count", 0)
        if trade_count == 0:
            warnings.append("无任何交易发生，策略可能未触发买入条件")

        return RunResponse(success=True, summary=summary, logs=logs, warnings=warnings)
    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        warnings.append(f"参数错误: {e}")
        return RunResponse(success=False, summary={}, error=str(e), logs=logs, warnings=warnings)
    except Exception as e:
        logger.exception("回测失败")
        warnings.append(f"执行异常: {type(e).__name__}: {e}")
        return RunResponse(success=False, summary={}, error=str(e), logs=logs, warnings=warnings)


@app.post("/run_python", response_model=RunResponse)
def run_python_backtest(req: RunPythonRequest) -> RunResponse:
    """执行回测（Python 代码 + config）"""
    logs: List[str] = []
    warnings: List[str] = []

    try:
        logger.info("[run_python] ========== 收到策略 ==========")
        logger.info("[run_python] --- code ---\n%s", req.code)
        logger.info("[run_python] --- config ---\n%s", json.dumps(req.config, ensure_ascii=False, indent=2))
        logger.info("[run_python] ============================")

        logs.append(f"策略代码长度: {len(req.code)} 字符")

        cerebro = _build_cerebro_from_python(req.code, req.config)
        symbols = get_universe_symbols(req.config)
        initial = cerebro.broker.getcash()

        logs.append(f"股票池: {symbols}")
        logs.append(f"初始资金: {initial:,.0f}")
        logs.append(f"数据源: {req.config.get('data_source', 'tushare')}")
        logs.append(f"回测区间: {req.config.get('start_year', 2016)}-{req.config.get('end_year', 2025)}")

        # 检查数据完整性
        data_count = len(cerebro.datas)
        logs.append(f"加载数据源数量: {data_count}")
        if data_count < len(symbols):
            warnings.append(f"数据缺失: 请求{len(symbols)}只股票，实际加载{data_count}只")

        logger.info("[run_python] 开始回测 symbols=%s initial_cash=%.2f", symbols, initial)
        results = cerebro.run()

        final_value = cerebro.broker.getvalue()
        logger.info("[run_python] 回测执行完毕 broker_value=%.2f", final_value)

        summary = run_analyzers(cerebro, results)

        # 收集关键运行指标作为日志
        logs.append(f"最终资产: {final_value:,.2f}")
        logs.append(f"总收益率: {summary.get('total_return', 0):.2f}%")
        logs.append(f"交易次数: {summary.get('trade_count', 0)}")

        # 检测潜在问题并生成警告
        trade_count = summary.get("trade_count", 0)
        transactions = summary.get("transactions", [])
        positions = summary.get("positions", [])
        total_return = summary.get("total_return", 0)

        if trade_count == 0 and len(transactions) == 0:
            warnings.append("无任何交易发生，策略可能未触发买入条件")
            if positions:
                warnings.append(f"存在未平仓持仓: {positions}")

        if trade_count > 0 and summary.get("win_rate", 0) == 0:
            warnings.append("所有交易均为亏损，策略逻辑可能存在问题")

        if abs(total_return) < 0.01 and trade_count == 0:
            warnings.append("收益为0且无交易，请检查买入/卖出条件是否正确")

        if summary.get("max_drawdown_pct", 0) > 50:
            warnings.append(f"最大回撤过大: {summary.get('max_drawdown_pct', 0):.1f}%，风险控制可能不足")

        # 检查异常收益（无交易却有收益）
        if trade_count == 0 and len(transactions) == 0 and abs(total_return) > 0.01:
            if positions:
                logs.append(f"收益来源于未平仓持仓浮盈: {positions}")
            else:
                warnings.append(f"异常: 无交易无持仓却有收益 {total_return:.2f}%")

        logger.info("[run_python] ========== 返回数据 ==========")
        logger.info("[run_python] summary: total_return=%.2f%% max_drawdown=%.2f%% sharpe=%.2f win_rate=%.1f%% trade_count=%d",
                   summary.get("total_return", 0), summary.get("max_drawdown_pct", 0),
                   summary.get("sharpe_ratio", 0), summary.get("win_rate", 0), summary.get("trade_count", 0))
        logger.info("[run_python] logs=%s warnings=%s", logs, warnings)
        logger.info("[run_python] ============================")

        return RunResponse(success=True, summary=summary, logs=logs, warnings=warnings)
    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        warnings.append(f"参数错误: {e}")
        return RunResponse(success=False, summary={}, error=str(e), logs=logs, warnings=warnings)
    except Exception as e:
        logger.exception("Python 回测失败")
        warnings.append(f"执行异常: {type(e).__name__}: {e}")
        return RunResponse(success=False, summary={}, error=str(e), logs=logs, warnings=warnings)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
