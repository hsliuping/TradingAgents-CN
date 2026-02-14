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
TIMEOUT = float(os.getenv("BACKTEST_SERVICE_TIMEOUT", "120"))


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
        执行回测
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


def get_engine_client() -> BacktestEngineClient:
    """获取回测引擎客户端单例"""
    return BacktestEngineClient()
