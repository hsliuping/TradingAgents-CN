"""报告质量指标采集与查询服务（v3.6.0 项5）。

依赖阶段一项1（quality_gate）产出的 quality_flags 数据，自动统计：
- 报告长度（按 Agent 类型）
- 数据引用情况
- LLM 调用耗时和成本
- 兜底文案命中率
- low_quality 标记比例

写入 MongoDB analysis_quality_metrics 集合，供仪表盘 API 查询。

使用方式：
1. 分析完成后调用 record_analysis_metrics() 写入指标
2. 仪表盘调用 query_metrics() 按日期/股票/Agent 类型查询
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "analysis_quality_metrics"


class QualityMetricsService:
    """报告质量指标服务"""

    def __init__(self, db: Any):
        self._db = db
        self._collection = db[COLLECTION_NAME]

    async def record_analysis_metrics(
        self,
        *,
        user_id: str,
        ticker: str = "",
        agent_id: str = "",
        agent_type: str = "",
        report_content: str = "",
        report_length: int = 0,
        is_low_quality: bool = False,
        quality_flags: List[Dict[str, Any]] = None,
        hit_fallback: bool = False,
        fallback_pattern: str = "",
        llm_elapsed_seconds: float = 0.0,
        llm_tokens_used: int = 0,
        llm_cost_estimate: float = 0.0,
        retry_count: int = 0,
        analysis_date: str = "",
        workflow_id: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录一次分析的质量指标。

        Args:
            user_id: 用户 ID
            ticker: 股票代码
            agent_id: Agent ID
            agent_type: Agent 类型（analyst/researcher/manager 等）
            report_content: 报告内容（用于事后审计，可选）
            report_length: 报告字符数
            is_low_quality: 是否被标记为低质量
            quality_flags: 质量门禁标记列表
            hit_fallback: 是否命中兜底文案
            fallback_pattern: 命中的兜底文案
            llm_elapsed_seconds: LLM 调用耗时（秒）
            llm_tokens_used: LLM token 使用量
            llm_cost_estimate: LLM 成本估算（元）
            retry_count: 重试次数
            analysis_date: 分析日期
            workflow_id: 工作流 ID
            extra: 额外指标

        Returns:
            写入的记录 ID
        """
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user_id,
            "ticker": str(ticker).upper() if ticker else "",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "report_length": report_length or len(report_content or ""),
            "is_low_quality": is_low_quality,
            "quality_flags": quality_flags or [],
            "hit_fallback": hit_fallback,
            "fallback_pattern": fallback_pattern,
            "llm_elapsed_seconds": llm_elapsed_seconds,
            "llm_tokens_used": llm_tokens_used,
            "llm_cost_estimate": llm_cost_estimate,
            "retry_count": retry_count,
            "analysis_date": analysis_date or now[:10],
            "workflow_id": workflow_id,
            "recorded_at": now,
        }
        if extra:
            doc["extra"] = extra

        try:
            result = await self._collection.insert_one(doc)
            logger.info(
                "[QualityMetrics] 已记录指标: user=%s ticker=%s agent=%s low_quality=%s",
                user_id, ticker, agent_id, is_low_quality,
            )
            return str(result.inserted_id)
        except Exception as e:
            logger.warning("[QualityMetrics] 写入失败: %s", e)
            return ""

    def record_analysis_metrics_sync(self, **kwargs) -> str:
        """record_analysis_metrics 的同步包装器（供 LangGraph 节点调用）。

        在新线程中运行 async 版本，避免阻塞事件循环。
        失败时返回空字符串，不阻塞主流程。
        """
        import asyncio
        import threading

        try:
            try:
                asyncio.get_running_loop()
                running_loop = True
            except RuntimeError:
                running_loop = False

            if not running_loop:
                return asyncio.run(self.record_analysis_metrics(**kwargs))

            # 有运行中的事件循环，在新线程中运行
            result_holder: Dict[str, Any] = {"id": ""}

            def _run_in_thread() -> None:
                try:
                    result_holder["id"] = asyncio.run(self.record_analysis_metrics(**kwargs))
                except Exception as exc:
                    logger.warning("[QualityMetrics] sync 包装器线程异常: %s", exc)

            t = threading.Thread(target=_run_in_thread, daemon=True)
            t.start()
            t.join(timeout=10)
            return result_holder.get("id", "")
        except Exception as exc:
            logger.warning("[QualityMetrics] record_analysis_metrics_sync 异常: %s", exc)
            return ""

    async def query_metrics(
        self,
        *,
        user_id: Optional[str] = None,
        ticker: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        only_low_quality: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询质量指标（仪表盘用）。

        支持按用户/股票/Agent/日期范围筛选。
        """
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if ticker:
            query["ticker"] = str(ticker).upper()
        if agent_id:
            query["agent_id"] = agent_id
        if agent_type:
            query["agent_type"] = agent_type
        if only_low_quality:
            query["is_low_quality"] = True

        # 日期范围（按 analysis_date 字符串比较）
        date_range: Dict[str, Any] = {}
        if start_date:
            date_range["$gte"] = start_date
        if end_date:
            date_range["$lte"] = end_date
        if date_range:
            query["analysis_date"] = date_range

        cursor = self._collection.find(query).sort("recorded_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        # 过滤 _id（不可序列化）
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in docs]

    async def get_quality_summary(
        self,
        *,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取质量汇总统计（仪表盘顶部数字用）。

        Returns:
            {
                "total_reports": 总报告数,
                "low_quality_count": 低质量报告数,
                "low_quality_rate": 低质量比例,
                "fallback_hit_count": 兜底文案命中数,
                "fallback_hit_rate": 兜底命中率,
                "avg_report_length": 平均报告长度,
                "avg_llm_elapsed_seconds": 平均 LLM 耗时,
                "total_llm_cost": 总 LLM 成本,
                "by_agent_type": {agent_type: {count, low_quality_count, ...}},
            }
        """
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        date_range: Dict[str, Any] = {}
        if start_date:
            date_range["$gte"] = start_date
        if end_date:
            date_range["$lte"] = end_date
        if date_range:
            query["analysis_date"] = date_range

        cursor = self._collection.find(query)
        docs = await cursor.to_list(length=10000)

        total = len(docs)
        if total == 0:
            return {
                "total_reports": 0,
                "low_quality_count": 0,
                "low_quality_rate": 0.0,
                "fallback_hit_count": 0,
                "fallback_hit_rate": 0.0,
                "avg_report_length": 0,
                "avg_llm_elapsed_seconds": 0.0,
                "total_llm_cost": 0.0,
                "by_agent_type": {},
            }

        low_quality_count = sum(1 for d in docs if d.get("is_low_quality"))
        fallback_hit_count = sum(1 for d in docs if d.get("hit_fallback"))
        total_length = sum(d.get("report_length", 0) for d in docs)
        total_elapsed = sum(d.get("llm_elapsed_seconds", 0) for d in docs)
        total_cost = sum(d.get("llm_cost_estimate", 0) for d in docs)

        # 按 agent_type 聚合
        by_type: Dict[str, Dict[str, Any]] = {}
        for d in docs:
            at = d.get("agent_type", "unknown")
            if at not in by_type:
                by_type[at] = {
                    "count": 0,
                    "low_quality_count": 0,
                    "fallback_hit_count": 0,
                    "total_length": 0,
                }
            by_type[at]["count"] += 1
            if d.get("is_low_quality"):
                by_type[at]["low_quality_count"] += 1
            if d.get("hit_fallback"):
                by_type[at]["fallback_hit_count"] += 1
            by_type[at]["total_length"] += d.get("report_length", 0)

        # 计算每个类型的平均值
        for at, stats in by_type.items():
            count = stats["count"]
            stats["avg_length"] = stats["total_length"] / count if count > 0 else 0
            stats["low_quality_rate"] = stats["low_quality_count"] / count if count > 0 else 0

        return {
            "total_reports": total,
            "low_quality_count": low_quality_count,
            "low_quality_rate": low_quality_count / total,
            "fallback_hit_count": fallback_hit_count,
            "fallback_hit_rate": fallback_hit_count / total,
            "avg_report_length": total_length / total,
            "avg_llm_elapsed_seconds": total_elapsed / total,
            "total_llm_cost": total_cost,
            "by_agent_type": by_type,
        }


# 模块级工厂方法
def get_quality_metrics_service(db: Any) -> QualityMetricsService:
    """获取 QualityMetricsService 实例"""
    return QualityMetricsService(db)
