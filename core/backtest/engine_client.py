"""
回测引擎 HTTP 客户端
调用独立部署的 Backtrader 服务 (避免 GPL 传染)
"""
import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

BACKTEST_SERVICE_URL = os.getenv("BACKTEST_SERVICE_URL", "http://localhost:8900")
# 回测可能需要较长时间（大量数据、多股票、长周期），默认 20 分钟
TIMEOUT = float(os.getenv("BACKTEST_SERVICE_TIMEOUT", "1200"))


class BacktestEngineClient:
    """Backtrader 服务 HTTP 客户端"""

    def __init__(self, base_url: str | None = None, timeout: float = TIMEOUT):
        self.base_url = (base_url or BACKTEST_SERVICE_URL).rstrip("/")
        self.timeout = timeout

    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()

    async def run(self, strategy_dsl: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行回测（DSL）
        Args:
            strategy_dsl: 策略 DSL (JSON)
        Returns:
            {"success": bool, "summary": {...}, "error": str|None}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/run",
                json={"strategy": strategy_dsl},
            )
            r.raise_for_status()
            return r.json()

    async def run_python(
        self, code: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行回测（Python 代码 + config）
        Args:
            code: Backtrader 策略类 Python 代码（类名 GeneratedStrategy）
            config: 回测配置（symbols/universe、start_year、end_year 等）
        Returns:
            {"success": bool, "summary": {...}, "error": str|None}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/run_python",
                json={"code": code, "config": config},
            )
            r.raise_for_status()
            return r.json()


def get_engine_client() -> BacktestEngineClient:
    """获取回测引擎客户端单例"""
    return BacktestEngineClient()
