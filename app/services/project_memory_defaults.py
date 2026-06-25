"""L4 项目长期记忆默认种子。"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models.project_memory import DEFAULT_PROJECT_MEMORY_PROJECT_ID, ProjectMemoryCategory


PROJECT_MEMORY_DEFAULT_VERSION = "v1"


def get_default_project_memory_items() -> List[Dict[str, Any]]:
    seed_meta = {
        "source": "system_seed",
        "seed_name": "project_memory_defaults",
        "seed_version": PROJECT_MEMORY_DEFAULT_VERSION,
    }
    return [
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "global-no-trading-advice",
            "title": "禁止直接投资建议",
            "content": "所有分析只提供研究与学习参考，不给买入、卖出、持有、目标价、仓位或具体时点等直接交易建议。",
            "category": ProjectMemoryCategory.PROJECT_RULE.value,
            "priority": 10,
            "tags": ["compliance", "assistant", "global"],
            "metadata": dict(seed_meta),
        },
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "financial-domain-boundary",
            "title": "服务边界限定在金融领域",
            "content": "非金融话题只做简短拒绝，并引导回股票、基金、宏观、行业、持仓、复盘或交易计划等金融场景。",
            "category": ProjectMemoryCategory.PROJECT_RULE.value,
            "priority": 20,
            "tags": ["assistant", "boundary"],
            "metadata": dict(seed_meta),
        },
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "confirm-side-effect-operations",
            "title": "复杂副作用操作先确认",
            "content": "创建定时分析、删除或移除对象、复杂多步任务以及意图不明确的分析请求，必须先说明方案或确认参数，再执行。",
            "category": ProjectMemoryCategory.GOVERNANCE_CONSTRAINT.value,
            "priority": 30,
            "tags": ["governance", "assistant_ops"],
            "metadata": dict(seed_meta),
        },
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "realtime-data-first",
            "title": "实时数据问题必须先取数",
            "content": "涉及行情、指数点位、财报数字、技术指标、近期公告或最新进展的问题，必须先调用工具获取数据，不能用训练记忆补答案。",
            "category": ProjectMemoryCategory.GOVERNANCE_CONSTRAINT.value,
            "priority": 40,
            "tags": ["data", "realtime", "governance"],
            "metadata": dict(seed_meta),
        },
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "answer-structure-conclusion-first",
            "title": "回答结构先结论后展开",
            "content": "默认先给结论，再给证据、风险和不确定性；如果工具数据不是当前口径，必须明确标注数据日期。",
            "category": ProjectMemoryCategory.ANALYSIS_OUTPUT_CONSTRAINT.value,
            "priority": 50,
            "tags": ["output", "assistant", "analysis"],
            "metadata": dict(seed_meta),
        },
        {
            "project_id": DEFAULT_PROJECT_MEMORY_PROJECT_ID,
            "memory_key": "stock-analysis-template",
            "title": "个股分析默认结构",
            "content": "个股分析默认按结论、核心驱动、关键风险、待验证点组织；缺少实时数据时先说明信息缺口，再继续分析。",
            "category": ProjectMemoryCategory.RESEARCH_TEMPLATE.value,
            "priority": 60,
            "tags": ["template", "stock_analysis"],
            "metadata": dict(seed_meta),
        },
    ]