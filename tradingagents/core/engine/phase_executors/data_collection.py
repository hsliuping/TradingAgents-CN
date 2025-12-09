# tradingagents/core/engine/phase_executors/data_collection.py
"""
数据收集阶段执行器（初始化阶段）

职责：
- 初始化分析上下文的基本信息
- 验证输入参数的有效性
- 可选：预加载公共基础数据（如公司基本信息）

注意：
- 此阶段不替代 Agent 的 tools 数据获取能力
- Agent 仍通过各自的 tools 从 dataflows 获取所需数据
- Agent 将分析结果写入 Context 供其他 Agent 读取
"""

from typing import Any, Dict, Optional

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import DataLayer
from .base import PhaseExecutor

logger = get_logger("default")


class DataCollectionPhase(PhaseExecutor):
    """
    数据收集阶段执行器（实际为初始化阶段）

    主要职责：
    1. 验证和规范化输入参数（ticker, trade_date 等）
    2. 初始化 Context 的基本信息
    3. 可选：预加载公司基本信息等公共数据

    注意：原始数据获取由各 Agent 通过 tools 自行完成
    """

    phase_name = "DataCollectionPhase"

    def __init__(
        self,
        llm_provider: Any = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化数据收集阶段

        Args:
            llm_provider: LLM 提供者（此阶段不需要）
            config: 阶段配置
        """
        super().__init__(llm_provider, config)

    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行初始化阶段

        Args:
            context: 分析上下文
            data_manager: 数据访问管理器

        Returns:
            初始化结果摘要
        """
        self.log_start()

        # 获取并验证上下文信息
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        trade_date = context.get(DataLayer.CONTEXT, "trade_date")
        company_name = context.get(DataLayer.CONTEXT, "company_name")
        market_type = context.get(DataLayer.CONTEXT, "market_type") or self._detect_market_type(ticker)

        logger.info(f"📊 [{self.phase_name}] 初始化分析上下文: {ticker} ({trade_date})")

        # 验证必要参数
        if not ticker:
            raise ValueError("ticker 是必需参数")
        if not trade_date:
            raise ValueError("trade_date 是必需参数")

        # 规范化 ticker 格式
        normalized_ticker = self._normalize_ticker(ticker, market_type)
        if normalized_ticker != ticker:
            context.set(DataLayer.CONTEXT, "ticker", normalized_ticker, source=self.phase_name)
            logger.debug(f"📊 [{self.phase_name}] ticker 规范化: {ticker} -> {normalized_ticker}")

        # 设置市场类型（如果未设置）
        if not context.get(DataLayer.CONTEXT, "market_type"):
            context.set(DataLayer.CONTEXT, "market_type", market_type, source=self.phase_name)

        # 构建输出摘要
        outputs = {
            "ticker": normalized_ticker,
            "trade_date": trade_date,
            "company_name": company_name,
            "market_type": market_type,
            "initialized": True
        }

        self.log_end(outputs)
        return outputs

    def _detect_market_type(self, ticker: str) -> str:
        """
        根据 ticker 格式检测市场类型

        Args:
            ticker: 股票代码

        Returns:
            市场类型 ("cn", "us", "hk")
        """
        if not ticker:
            return "cn"

        ticker_upper = ticker.upper()

        # 中国 A 股格式
        if ticker_upper.endswith((".SZ", ".SH", ".BJ")):
            return "cn"
        if ticker.isdigit() and len(ticker) == 6:
            return "cn"

        # 港股格式
        if ticker_upper.endswith(".HK"):
            return "hk"

        # 默认为美股
        return "us"

    def _normalize_ticker(self, ticker: str, market_type: str) -> str:
        """
        规范化 ticker 格式

        Args:
            ticker: 原始股票代码
            market_type: 市场类型

        Returns:
            规范化后的股票代码
        """
        if not ticker:
            return ticker

        ticker = ticker.strip().upper()

        if market_type == "cn":
            # 中国 A 股：确保有后缀
            if ticker.isdigit() and len(ticker) == 6:
                if ticker.startswith(("60", "68")):
                    return f"{ticker}.SH"
                elif ticker.startswith(("00", "30")):
                    return f"{ticker}.SZ"
                elif ticker.startswith(("4", "8")):
                    return f"{ticker}.BJ"
            return ticker

        # 其他市场保持原样
        return ticker

