"""
Backtrader 回测服务 - FastAPI 包装
POST /run  接收策略 DSL，返回回测结果
GET  /health 健康检查
"""
import logging
from typing import Any, Dict, List

import backtrader as bt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import MONGO_URI, MONGO_DB, PORT
from data_feed import make_backtrader_feed
from translator import DSLStrategy, dsl_to_strategy_params, get_universe_symbols
from analyzers import attach_analyzers, run_analyzers
from schemas import StrategyConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Backtrader Backtest Service", version="1.0.0")


class RunRequest(BaseModel):
    """回测请求体"""
    strategy: Dict[str, Any]


class RunResponse(BaseModel):
    """回测响应"""
    success: bool = True
    summary: Dict[str, Any]
    error: str | None = None


def _build_cerebro(dsl: Dict[str, Any]) -> bt.Cerebro:
    """根据 DSL 构建 Cerebro 实例"""
    symbols = get_universe_symbols(dsl)
    if not symbols:
        raise ValueError("股票池为空，请配置 universe.symbols (type=static)")

    cfg = dsl.get("config", {})
    start_year = cfg.get("start_year", 2016)
    end_year = cfg.get("end_year", 2025)
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    initial_cash = float(cfg.get("initial_capital", 1_000_000))
    market = cfg.get("market", "CN")

    feeds = make_backtrader_feed(symbols, start_date, end_date, market)
    if not feeds:
        raise ValueError(f"无可用数据: symbols={symbols}, range={start_date}~{end_date}")

    cerebro = bt.Cerebro()
    for fd in feeds:
        cerebro.adddata(fd)
    cerebro.broker.setcash(initial_cash)
    # 暂用默认 broker，CN 规则（T+1/涨跌停）后续在 cn_broker 中实现

    params = dsl_to_strategy_params(dsl)
    cerebro.addstrategy(DSLStrategy, **params)
    attach_analyzers(cerebro)

    return cerebro


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok", "service": "backtrader-backtest"}


@app.post("/run", response_model=RunResponse)
def run_backtest(req: RunRequest) -> RunResponse:
    """执行回测"""
    try:
        dsl = req.strategy
        # 校验
        StrategyConfig.model_validate(dsl)
        cerebro = _build_cerebro(dsl)
        cerebro.run()
        summary = run_analyzers(cerebro)
        return RunResponse(success=True, summary=summary)
    except ValueError as e:
        logger.warning(f"参数错误: {e}")
        return RunResponse(success=False, summary={}, error=str(e))
    except Exception as e:
        logger.exception("回测失败")
        return RunResponse(success=False, summary={}, error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
