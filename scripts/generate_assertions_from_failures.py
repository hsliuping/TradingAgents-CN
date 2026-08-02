"""P2.1 断言生成器 — 从失败执行轨迹提炼可执行断言

借鉴桥水 Pat「把错误转化为可执行验证用例」思路：扫描 agent_execution_traces
中 validation_status="failed" 的轨迹，按 system_prompt_hash + 失败模式聚类，
对每个反复出现的失败模式调 LLM 提炼为机器可执行断言（AgentAssertion）。

默认 --dry-run 仅打印；--apply 写入 MongoDB agent_assertions 集合
（默认 enabled=false + severity=warning，需人工审核激活）。

LLM 客户端从系统配置解析（复用 reflection_helper 的解析逻辑），
不硬编码 provider —— 遵循"反思节点 LLM 客户端必须从系统配置解析"硬约束。

用法：
    # 干跑（默认）：仅分析打印，不写库
    env\\Scripts\\python.exe scripts\\generate_assertions_from_failures.py \\
        --agent-id risk_manager_v2 --days 30 --limit 50

    # 写入 MongoDB（仍默认 enabled=false，需人工激活）
    env\\Scripts\\python.exe scripts\\generate_assertions_from_failures.py \\
        --agent-id risk_manager_v2 --days 30 --limit 50 --apply

前置条件：
    - v3.0 MongoDB 容器运行中（端口 27019）
    - 系统配置中已配置可用 LLM（quick_analysis_model 优先）
    - 存在 validation_status=failed 的执行轨迹
"""

import argparse
import json
import logging
import os
import re
import sys
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 🔒 硬约束：必须使用 v3.0 专用数据库（端口 27019）。
# 必须在导入 app.core.config（settings 单例）之前设置，避免误连 .env 中其它版本库。
os.environ["MONGODB_PORT"] = "27019"
os.environ["REDIS_PORT"] = "6381"

from app.models.agent_assertion import (
    AgentAssertion, AssertionConstraint, AssertionSeverity, AssertionType,
)
from app.models.execution_trace import AgentExecutionTrace
from app.services.agent_assertion_service import agent_assertion_service
from app.services.execution_trace_service import execution_trace_service

logger = logging.getLogger("generate_assertions")

# LLM 调用超时（秒）—— 离线脚本，给足时间
_LLM_TIMEOUT_SECONDS = 60

# 每个聚类送给 LLM 的最大样本数（控制 prompt 长度）
_MAX_SAMPLES_PER_CLUSTER = 5


# ============================================================================
# 目标 agent 的 schema 描述（供 LLM 理解字段结构，生成精准断言）
# ============================================================================

SCHEMA_DESCRIPTIONS: Dict[str, str] = {
    "risk_manager_v2": (
        "RiskAssessmentOutput (JSON):\n"
        "  risk_level: \"低\"|\"中\"|\"高\" (必填)\n"
        "  risk_score: float 0.0-1.0 (必填)\n"
        "  reasoning: str (必填)\n"
        "  key_risks: List[str]\n"
        "  risk_control: str\n"
        "  investment_adjustment: \"乐观\"|\"审慎\"|\"中性\" (必填，合规枚举)\n"
        "  final_trade_decision: {\n"
        "    action: \"乐观\"|\"审慎\"|\"中性\" (必填，合规枚举)\n"
        "    confidence: float 0.0-1.0\n"
        "    reasoning/summary/risk_warning: str\n"
        "  }\n"
        "合规禁用术语：看涨/看跌/买入/卖出/加仓/减仓/持有/清仓"
    ),
    "research_manager_v2": (
        "ResearchManagerOutput (JSON):\n"
        "  analysis_view: \"乐观\"|\"审慎\"|\"中性\" (必填，合规枚举)\n"
        "  confidence: float 0.0-1.0\n"
        "  risk_score: float 0.0-1.0\n"
        "  summary/reasoning: str (必填)\n"
        "  core_evidence/uncertainties/invalidation_conditions/watch_items: List[str]\n"
        "  risk_warning: str\n"
        "合规禁用术语：看涨/看跌/买入/卖出/加仓/减仓/持有/清仓"
    ),
    "trader_v2": (
        "TraderV2 输出为 Markdown 用户版研究简报，必备章节：\n"
        "  ## 一句话结论 / ## 核心依据 / ## 当前判断的限制 / \n"
        "  ## 后续观察事项 / ## 资料边界说明 / ## 免责声明\n"
        "合规禁用术语：看涨/看跌/买入/卖出/加仓/减仓/清仓\n"
        "（『持有』在简报中可能为非交易语境，仅 prompt 约束不强制校验）"
    ),
}


# ============================================================================
# 失败轨迹聚类
# ============================================================================

def _error_pattern_key(trace: AgentExecutionTrace) -> str:
    """提取失败模式键：system_prompt_hash + 校验错误前 80 字符。

    同一 prompt 版本下相同错误模式归为一类，便于识别反复出现的失败。
    """
    prompt_hash = (trace.prompts.system_prompt_hash or "no_hash") if trace.prompts else "no_hash"
    err = (trace.validation.validation_error or "") if trace.validation else ""
    # 归一化：去掉动态部分（如具体字段值），保留错误类型描述
    err_norm = re.sub(r"[\w\-]{8,}", "x", err)[:80] if err else "no_error"
    return f"{prompt_hash}::{err_norm}"


def cluster_failures(
    traces: List[AgentExecutionTrace],
    min_cluster_size: int = 2,
) -> List[Tuple[str, List[AgentExecutionTrace]]]:
    """按失败模式聚类，只保留 >= min_cluster_size 的聚类（反复出现的失败）。"""
    buckets: Dict[str, List[AgentExecutionTrace]] = defaultdict(list)
    for t in traces:
        buckets[_error_pattern_key(t)].append(t)

    clusters = []
    for key, items in buckets.items():
        if len(items) >= min_cluster_size:
            clusters.append((key, items))
    # 按聚类大小降序
    clusters.sort(key=lambda x: len(x[1]), reverse=True)
    return clusters


# ============================================================================
# LLM 断言生成
# ============================================================================

# 生成器 system prompt —— 格式契约前置（硬约束：system prompt 必须把格式要求放最前）
_GENERATOR_SYSTEM_PROMPT = """【输出格式契约·必须严格遵守】
你的输出必须是一个 JSON 对象，只输出 JSON，不要包裹在 markdown 代码块中，不要有任何额外文字。

{
  "failure_pattern_summary": "失败模式的简短描述（30-80字）",
  "assertions": [
    {
      "assertion_type": "term_forbidden | field_required | field_enum | field_range | schema_match | regex_match | section_required",
      "target_agent": "目标 agent_id",
      "target_field": "字段路径（如 final_trade_decision.action；作用于原始文本时填 *）",
      "constraint": { ... },
      "severity": "error | warning",
      "description": "人类可读的断言说明（30-80字）"
    }
  ]
}

【断言类型语义】
- term_forbidden: 原始文本中扫描禁用术语。constraint={"terms": ["看涨","看跌"]}
- field_required: parsed_dict 必须包含字段（点路径）。constraint={"field": "risk_level"}
- field_enum: 字段值必须在枚举内。constraint={"field": "final_trade_decision.action", "allowed": ["乐观","审慎","中性"]}
- field_range: 数值字段必须在范围内。constraint={"field": "confidence", "min": 0.0, "max": 1.0}
- schema_match: 整个 parsed_dict 必须匹配指定 schema。constraint={"schema_name": "RiskAssessmentOutput"}
- regex_match: 字段必须匹配正则。constraint={"field": "summary", "pattern": "\\\\d{4}-\\\\d{2}-\\\\d{2}"}
- section_required: 原始文本必须包含章节标题。constraint={"sections": ["一句话结论","核心依据"]}

【severity 语义】
- error: 必须满足的硬约束（如禁用术语、必填字段缺失），违规让 validation_status=failed
- warning: 建议满足的软约束（如章节齐全），违规只记录到 assertion_violations 字段

【你的任务】
分析下面给出的失败 LLM 输出案例，识别反复出现的失败模式，提炼为可执行断言。

【输出要求】
1. 只输出 JSON，不要其他文字
2. 断言必须机器可执行（不要模糊建议如"应当更注意合规"）
3. 优先识别反复出现的失败模式
4. 每条断言必须有 description
5. 不确定时 severity 用 warning（保守原则，避免误报阻塞主流程）
6. 如果失败模式无法转为可执行断言，返回空 assertions 数组，但在 failure_pattern_summary 中说明
7. constraint 字段必须符合上面的语义示例
"""


def _build_user_prompt(
    agent_id: str,
    cluster_key: str,
    samples: List[AgentExecutionTrace],
) -> str:
    """构建送给 LLM 的 user prompt（失败案例 + schema 描述）。"""
    schema_desc = SCHEMA_DESCRIPTIONS.get(agent_id, "（未知 agent，无 schema 描述）")

    cases = []
    for i, t in enumerate(samples[:_MAX_SAMPLES_PER_CLUSTER], 1):
        out_preview = (t.output.output_raw_preview or "") if t.output else ""
        val_err = (t.validation.validation_error or "") if t.validation else ""
        val_details = ""
        if t.validation and t.validation.validation_details:
            try:
                val_details = json.dumps(t.validation.validation_details, ensure_ascii=False)[:300]
            except Exception:
                val_details = str(t.validation.validation_details)[:300]
        cases.append(
            f"--- 案例 {i} ---\n"
            f"trace_id: {t.trace_id}\n"
            f"started_at: {t.started_at}\n"
            f"validation_error: {val_err}\n"
            f"validation_details: {val_details}\n"
            f"output_raw_preview:\n{out_preview}"
        )

    return (
        f"【目标 agent】{agent_id}\n"
        f"【失败模式聚类键】{cluster_key}\n"
        f"【聚类样本数】{len(samples)}\n\n"
        f"【目标 agent 的 schema 描述】\n{schema_desc}\n\n"
        f"【失败案例】\n" + "\n\n".join(cases)
    )


def _strip_json_code_fence(text: str) -> str:
    """剥离 ```json ... ``` 代码块标记（LLM 常忽略"不要代码块"要求）。"""
    if not text:
        return text
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # 没有代码块标记，尝试直接提取第一个 {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0)
    return text


def _resolve_llm_client():
    """从系统配置解析 LLM 客户端（复用 reflection_helper 逻辑，不硬编码 provider）。"""
    try:
        from core.agents.reflection_helper import _resolve_reflection_llm_client
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        return _resolve_reflection_llm_client(db)
    except Exception as e:
        logger.warning(f"⚠️ 解析 LLM 客户端失败: {e}")
        return None


def generate_assertions_for_cluster(
    llm_client,
    agent_id: str,
    cluster_key: str,
    samples: List[AgentExecutionTrace],
) -> Tuple[str, List[AgentAssertion]]:
    """对一个失败聚类调 LLM 生成断言。返回 (failure_pattern_summary, assertions)。"""
    from core.llm.models import Message, MessageRole

    system_prompt = _GENERATOR_SYSTEM_PROMPT
    user_prompt = _build_user_prompt(agent_id, cluster_key, samples)

    try:
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]
        resp = llm_client.chat(messages)
        raw_content = resp.content or "" if hasattr(resp, "content") else str(resp)
    except Exception as e:
        logger.error(f"❌ LLM 调用失败（cluster={cluster_key}）: {e}")
        return f"LLM 调用失败: {e}", []

    # 解析 JSON
    cleaned = _strip_json_code_fence(raw_content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            f"⚠️ LLM 输出非合法 JSON（cluster={cluster_key}）: {e}\n原始输出前200字: {raw_content[:200]}"
        )
        return f"LLM 输出解析失败: {e}", []

    summary = str(data.get("failure_pattern_summary", ""))
    raw_assertions = data.get("assertions", [])
    if not isinstance(raw_assertions, list):
        raw_assertions = []

    assertions: List[AgentAssertion] = []
    source_trace_id = samples[0].trace_id if samples else None
    for item in raw_assertions:
        if not isinstance(item, dict):
            continue
        try:
            atype_str = str(item.get("assertion_type", "")).strip()
            atype = AssertionType(atype_str)
        except ValueError:
            logger.warning(f"⚠️ 跳过未知 assertion_type: {item.get('assertion_type')}")
            continue

        constraint_payload = item.get("constraint", {}) or {}
        target_agent = str(item.get("target_agent", agent_id)).strip() or agent_id
        target_field = str(item.get("target_field", "*")).strip() or "*"
        sev_str = str(item.get("severity", "warning")).strip().lower()
        severity = AssertionSeverity.ERROR if sev_str == "error" else AssertionSeverity.WARNING
        description = str(item.get("description", "")).strip()

        try:
            assertion = AgentAssertion(
                assertion_id=f"auto-{uuid.uuid4().hex[:12]}",
                target_agent=target_agent,
                assertion_type=atype,
                target_field=target_field,
                constraint=AssertionConstraint(**constraint_payload),
                severity=severity,
                enabled=False,  # 默认禁用，需人工激活
                description=description,
                source_trace_id=source_trace_id,
                source_failure_pattern=summary[:200] if summary else None,
                creator="auto_generator",
            )
            assertions.append(assertion)
        except Exception as construct_exc:
            logger.warning(f"⚠️ 构造 AgentAssertion 失败（跳过）: {construct_exc}")

    return summary, assertions


# ============================================================================
# 主流程
# ============================================================================

def run_generation_sync(
    agent_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
    min_cluster_size: int = 2,
    apply: bool = False,
) -> Dict[str, Any]:
    """断言生成核心流程（同步，供 CLI 与管理 API 复用）。

    返回结构化结果：
      {
        "total_traces": int, "total_clusters": int,
        "generated_count": int, "written_count": int, "applied": bool,
        "clusters": [{"cluster_key","agent_id","summary","sample_count","generated"}],
        "assertions": [断言 dict 列表],
        "llm_available": bool,
      }
    """
    target_agents = [agent_id] if agent_id else _discover_target_agents()
    all_assertions: List[AgentAssertion] = []
    cluster_reports: List[Dict[str, Any]] = []
    total_clusters = 0
    total_traces = 0
    llm_available = True

    for aid in target_agents:
        traces = execution_trace_service.get_failure_patterns_sync(
            agent_id=aid, days=days, limit=limit
        )
        total_traces += len(traces)
        if not traces:
            continue

        clusters = cluster_failures(traces, min_cluster_size=min_cluster_size)
        if not clusters:
            continue

        llm_client = _resolve_llm_client()
        if llm_client is None:
            llm_available = False
            logger.warning(f"系统配置未解析到可用 LLM，跳过 agent={aid} 的 LLM 提炼")
            continue

        for cluster_key, samples in clusters:
            total_clusters += 1
            summary, assertions = generate_assertions_for_cluster(
                llm_client, aid, cluster_key, samples
            )
            all_assertions.extend(assertions)
            cluster_reports.append({
                "cluster_key": cluster_key,
                "agent_id": aid,
                "summary": summary,
                "sample_count": len(samples),
                "generated": len(assertions),
            })

    written_count = 0
    if apply and all_assertions:
        written_count = agent_assertion_service.bulk_create_assertions_sync(all_assertions)
        for aid in {a.target_agent for a in all_assertions}:
            agent_assertion_service.invalidate_cache(aid)

    return {
        "total_traces": total_traces,
        "total_clusters": total_clusters,
        "generated_count": len(all_assertions),
        "written_count": written_count,
        "applied": apply,
        "llm_available": llm_available,
        "clusters": cluster_reports,
        "assertions": [a.model_dump(mode="json") for a in all_assertions],
    }


def main():
    parser = argparse.ArgumentParser(
        description="从失败执行轨迹提炼可执行断言（P2.1 断言生成器）"
    )
    parser.add_argument("--agent-id", default=None, help="目标 agent_id（不指定则覆盖所有）")
    parser.add_argument("--days", type=int, default=30, help="回溯天数（默认 30）")
    parser.add_argument("--limit", type=int, default=100, help="最多扫描的失败轨迹数（默认 100）")
    parser.add_argument("--min-cluster-size", type=int, default=2, help="聚类最小样本数（默认 2）")
    parser.add_argument("--apply", action="store_true", help="写入 MongoDB（默认 dry-run 仅打印）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
    )

    print("=" * 80)
    print("🔧 P2.1 断言生成器 — 从失败轨迹提炼可执行断言")
    print(f"   MongoDB: v3.0 (端口 27019)")
    print(f"   agent_id: {args.agent_id or '(全部)'}")
    print(f"   回溯: {args.days} 天 | 上限: {args.limit} 条 | 最小聚类: {args.min_cluster_size}")
    print(f"   模式: {'--apply (写库, enabled=false)' if args.apply else '--dry-run (仅打印)'}")
    print("=" * 80)

    result = run_generation_sync(
        agent_id=args.agent_id, days=args.days, limit=args.limit,
        min_cluster_size=args.min_cluster_size, apply=args.apply,
    )

    for c in result["clusters"]:
        print(f"\n📦 聚类: {c['cluster_key']} ({c['sample_count']} 样本)")
        print(f"   失败模式: {c['summary']}")
        print(f"   生成断言: {c['generated']} 条")

    print("\n" + "=" * 80)
    print(f"📊 汇总: 扫描 {result['total_traces']} 条轨迹 | 处理 {result['total_clusters']} 个聚类 | "
          f"生成 {result['generated_count']} 条断言")
    print("=" * 80)

    if not result["llm_available"]:
        print("⚠️ 系统配置未解析到可用 LLM，已跳过 LLM 提炼。请在系统设置中配置 LLM 后重试。")

    if not result["assertions"]:
        print("\nℹ️ 未生成任何断言（可能失败模式不适合转断言，或无反复失败模式）。")
        return 0

    if args.apply:
        print(f"\n✅ 已写入 MongoDB agent_assertions 集合: {result['written_count']} 条")
        print("   所有断言 enabled=false，需通过管理 API 人工审核激活。")
    else:
        print("\n💤 dry-run 模式：未写库。添加 --apply 参数写入 MongoDB。")
        print("\n📝 断言 JSON 预览（供审核）:")
        print(json.dumps(result["assertions"], ensure_ascii=False, indent=2, default=str))

    return 0


def _discover_target_agents() -> List[str]:
    """未指定 --agent-id 时，扫描存在失败轨迹的 agent 列表。"""
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        # distinct agent_id from failed traces
        agents = db["agent_execution_traces"].distinct(
            "agent_id", {"validation.validation_status": "failed"}
        )
        return sorted([a for a in agents if a])
    except Exception as e:
        logger.warning(f"⚠️ 发现有失败轨迹的 agent 列表失败: {e}")
        return ["risk_manager_v2", "research_manager_v2", "trader_v2"]


if __name__ == "__main__":
    sys.exit(main())
