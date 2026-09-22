"""Agent 断言执行器（P2: 反思 lesson 升级为可执行断言）

在 manager agent 校验时同步执行召回的断言，违规结果合并到 validation_status。

设计原则：
1. 非阻塞：所有异常内部捕获，不影响 agent 执行
2. 进程内缓存：enabled assertions 按 agent_id 缓存 60s（由 service 层管理）
3. 结果合并：返回 AssertionRunResult，由基类合并到 validation_status
4. 单条隔离：单条断言执行失败不影响其他断言

用法（在 ManagerAgent._run_assertions 中）：
    from core.agents.assertion_executor import assertion_executor
    result = assertion_executor.run_assertions_sync(
        agent_id=self.agent_id,
        raw_text=raw_text,
        parsed=parsed_dict,
    )
    if result.has_error_violation:
        # 降级 validation_status
"""

# 注解惰性化：社区版剔除 agent_assertion 模型后，类型注解（如 -> AssertionRunResult）
# 在 def 执行时不求值，避免 NameError；必须位于其他 import 之前
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional

# 后端依赖可选导入：社区版（Apache 2.0 开源版）已将 app/models/agent_assertion 与
# app/services/agent_assertion_service 随 Pro 开源分离剔除。import 失败时本模块降级：
# run_assertions_sync 直接 raise，由调用方（trader_v2 / manager，均在 try 内）捕获降级
try:
    from app.pro.models.agent_assertion import (
        AgentAssertion,
        AssertionRunResult,
        AssertionSeverity,
        AssertionType,
        AssertionViolation,
    )
    from app.pro.services.agent_assertion_service import agent_assertion_service
    _ASSERTION_BACKEND_AVAILABLE = True
except ImportError:  # 社区版路径：断言后端不可用
    _ASSERTION_BACKEND_AVAILABLE = False

logger = logging.getLogger(__name__)


def _get_field_by_path(parsed: Dict[str, Any], field_path: str) -> Any:
    """按点路径从 parsed dict 中取值。

    例如 field_path="final_trade_decision.action" 从 {"final_trade_decision": {"action": "乐观"}} 取出 "乐观"。
    返回 None 表示路径不存在或值为 None。
    """
    if not parsed or not field_path or field_path == "*":
        return None
    current: Any = parsed
    for part in field_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class AssertionExecutor:
    """断言执行器"""

    def __init__(self):
        # 命中计数异步触发用的线程锁（避免并发写日志）
        self._hit_lock = threading.Lock()

    def run_assertions_sync(
        self,
        agent_id: str,
        raw_text: str,
        parsed: Optional[Dict[str, Any]] = None,
    ) -> AssertionRunResult:
        """同步执行断言（在 manager agent execute 上下文调用）。

        全程 try/except，失败返回 AssertionRunResult(ran=False)。
        """
        # 后端不可用（社区版已剔除断言体系）→ 抛出，调用方 try/except 降级
        if not _ASSERTION_BACKEND_AVAILABLE:
            raise ImportError("断言后端不可用（社区版无 agent_assertion 体系）")
        try:
            # 1. 加载启用断言（带缓存，由 service 层管理）
            assertions = agent_assertion_service.load_enabled_assertions_sync(agent_id)
            if not assertions:
                return AssertionRunResult(ran=False)

            # 2. 按 assertion_type 分发执行
            violations: List[AssertionViolation] = []
            hit_assertion_ids: List[str] = []

            for assertion in assertions:
                violation = self._run_single_assertion(assertion, raw_text, parsed)
                if violation is not None:
                    violations.append(violation)
                    hit_assertion_ids.append(assertion.assertion_id)

            # 3. 异步触发 hit_count 自增（fire-and-forget，不阻塞）
            if hit_assertion_ids:
                self._fire_and_forget_hit_count(hit_assertion_ids)

            # 4. 统计
            error_count = sum(1 for v in violations if v.severity == AssertionSeverity.ERROR)
            warning_count = sum(1 for v in violations if v.severity == AssertionSeverity.WARNING)

            return AssertionRunResult(
                ran=True,
                violations=violations,
                has_error_violation=error_count > 0,
                error_count=error_count,
                warning_count=warning_count,
            )
        except Exception as e:
            logger.warning(f"⚠️ [AssertionExecutor] 断言执行失败（不影响 agent）: {e}")
            return AssertionRunResult(ran=False)

    def _run_single_assertion(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """执行单条断言，返回 violation 或 None（未违规）。

        单条断言执行失败不影响其他断言。
        """
        try:
            handler = self._HANDLERS.get(assertion.assertion_type)
            if handler is None:
                logger.warning(
                    f"⚠️ [AssertionExecutor] 未知断言类型: {assertion.assertion_type}（跳过）"
                )
                return None
            return handler(self, assertion, raw_text, parsed)
        except Exception as e:
            logger.warning(
                f"⚠️ [AssertionExecutor] 单条断言执行失败（跳过）: assertion_id={assertion.assertion_id}, error={e}"
            )
            return None

    @staticmethod
    def _constraint_get(assertion: AgentAssertion, key: str, default: Any = None) -> Any:
        """从 constraint 中取值（兼容 pydantic extra 字段）。

        AssertionConstraint 用 extra="allow"，extra 字段存在 __pydantic_extra__ 中，
        __dict__ 取不到，必须用 model_dump()。
        """
        try:
            return assertion.constraint.model_dump().get(key, default)
        except Exception:
            return default

    # ==================== 7 种断言类型实现 ====================

    def _check_term_forbidden(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """禁用术语扫描（作用于原始文本）"""
        terms = self._constraint_get(assertion, "terms") or []
        if not terms or not raw_text:
            return None

        hit_terms = [t for t in terms if t and t in raw_text]
        if hit_terms:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "禁用术语扫描",
                violation_detail=f"命中禁用术语: {hit_terms}",
            )
        return None

    def _check_field_required(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """必填字段检查（作用于 parsed dict）"""
        field = self._constraint_get(assertion, "field") or assertion.target_field
        if not field or field == "*":
            return None
        if parsed is None:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "必填字段检查",
                violation_detail=f"parsed 为空，无法检查字段 {field}",
            )
        value = _get_field_by_path(parsed, field)
        if value is None:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "必填字段检查",
                violation_detail=f"字段缺失: {field}",
            )
        return None

    def _check_field_enum(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """字段枚举约束"""
        field = self._constraint_get(assertion, "field") or assertion.target_field
        allowed = self._constraint_get(assertion, "allowed") or []
        if not field or field == "*" or not allowed:
            return None
        if parsed is None:
            return None  # parsed 为空时不报枚举违规（由 field_required 报）

        value = _get_field_by_path(parsed, field)
        if value is None:
            return None  # 字段缺失由 field_required 负责

        if value not in allowed:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "字段枚举约束",
                violation_detail=f"字段 {field}={value!r} 不在允许值 {allowed} 内",
            )
        return None

    def _check_field_range(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """数值字段范围约束"""
        field = self._constraint_get(assertion, "field") or assertion.target_field
        min_val = self._constraint_get(assertion, "min")
        max_val = self._constraint_get(assertion, "max")
        if not field or field == "*" or parsed is None:
            return None

        value = _get_field_by_path(parsed, field)
        if value is None:
            return None

        try:
            num_value = float(value)
        except (TypeError, ValueError):
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "数值范围约束",
                violation_detail=f"字段 {field}={value!r} 不是数值",
            )

        if min_val is not None and num_value < float(min_val):
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "数值范围约束",
                violation_detail=f"字段 {field}={num_value} 低于最小值 {min_val}",
            )
        if max_val is not None and num_value > float(max_val):
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "数值范围约束",
                violation_detail=f"字段 {field}={num_value} 超过最大值 {max_val}",
            )
        return None

    def _check_schema_match(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """整个 parsed_dict 匹配指定 schema。

        P2.0 实现简化版：只检查 schema_name 是否在已知 schema 注册表中，
        并尝试用对应 pydantic 模型校验。schema 校验本身已由 manager 的 _validate_* 完成，
        此断言主要用于"显式记录某次执行违反了哪个 schema"的统计目的。
        """
        schema_name = self._constraint_get(assertion, "schema_name")
        if not schema_name or parsed is None:
            return None

        # 延迟导入避免循环依赖
        try:
            schema_model = self._get_schema_model(schema_name)
        except Exception as e:
            logger.warning(f"⚠️ [AssertionExecutor] schema {schema_name} 不可用: {e}")
            return None

        if schema_model is None:
            logger.warning(f"⚠️ [AssertionExecutor] 未知 schema: {schema_name}")
            return None

        try:
            schema_model(**parsed)
            return None  # 校验通过
        except Exception as e:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "schema 匹配检查",
                violation_detail=f"不匹配 schema {schema_name}: {e}",
            )

    def _check_regex_match(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """字段正则匹配"""
        field = self._constraint_get(assertion, "field") or assertion.target_field
        pattern = self._constraint_get(assertion, "pattern")
        if not pattern:
            return None

        # 取值：field="*" 作用于 raw_text，否则作用于 parsed 字段
        if field == "*" or not field:
            value = raw_text
        elif parsed is not None:
            value = _get_field_by_path(parsed, field)
        else:
            value = None

        if value is None:
            return None

        try:
            if not re.search(pattern, str(value)):
                return AssertionViolation(
                    assertion_id=assertion.assertion_id,
                    assertion_type=assertion.assertion_type,
                    target_agent=assertion.target_agent,
                    severity=assertion.severity,
                    description=assertion.description or "正则匹配检查",
                    violation_detail=f"字段 {field} 值不匹配正则 {pattern!r}",
                )
        except re.error as e:
            logger.warning(f"⚠️ [AssertionExecutor] 正则无效 {pattern!r}: {e}")
            return None
        return None

    def _check_section_required(
        self,
        assertion: AgentAssertion,
        raw_text: str,
        parsed: Optional[Dict[str, Any]],
    ) -> Optional[AssertionViolation]:
        """必备章节检查（作用于原始文本）"""
        sections = self._constraint_get(assertion, "sections") or []
        if not sections or not raw_text:
            return None

        missing = [s for s in sections if s and s not in raw_text]
        if missing:
            return AssertionViolation(
                assertion_id=assertion.assertion_id,
                assertion_type=assertion.assertion_type,
                target_agent=assertion.target_agent,
                severity=assertion.severity,
                description=assertion.description or "必备章节检查",
                violation_detail=f"缺失章节: {missing}",
            )
        return None

    # ==================== 辅助方法 ====================

    def _get_schema_model(self, schema_name: str):
        """按名称获取 pydantic schema 模型（延迟导入避免循环依赖）。

        返回 None 表示未知 schema。
        """
        if schema_name == "RiskAssessmentOutput":
            from core.agents.adapters.risk_manager_v2 import RiskAssessmentOutput
            return RiskAssessmentOutput
        if schema_name == "ResearchManagerOutput":
            from core.agents.adapters.research_manager_v2 import ResearchManagerOutput
            return ResearchManagerOutput
        return None

    def _fire_and_forget_hit_count(self, assertion_ids: List[str]) -> None:
        """异步触发命中计数（fire-and-forget，不阻塞主流程）"""
        try:
            for assertion_id in assertion_ids:
                try:
                    agent_assertion_service.increment_hit_count_sync(assertion_id)
                except Exception as e:
                    logger.debug(f"hit_count 自增失败（不影响主流程）: assertion_id={assertion_id}, error={e}")
        except Exception as e:
            logger.debug(f"fire-and-forget hit_count 异常: {e}")

    # 断言类型 -> handler 映射（在类定义后填充）
    _HANDLERS: Dict[AssertionType, Any] = {}


# 填充 handler 映射（社区版无 agent_assertion 模型，AssertionType 不可用 → 跳过填充；
# run_assertions_sync 在后端不可用时已提前 raise，不会访问 _HANDLERS）
try:
    AssertionExecutor._HANDLERS = {
        AssertionType.TERM_FORBIDDEN: AssertionExecutor._check_term_forbidden,
        AssertionType.FIELD_REQUIRED: AssertionExecutor._check_field_required,
        AssertionType.FIELD_ENUM: AssertionExecutor._check_field_enum,
        AssertionType.FIELD_RANGE: AssertionExecutor._check_field_range,
        AssertionType.SCHEMA_MATCH: AssertionExecutor._check_schema_match,
        AssertionType.REGEX_MATCH: AssertionExecutor._check_regex_match,
        AssertionType.SECTION_REQUIRED: AssertionExecutor._check_section_required,
    }
except NameError:  # 社区版路径：AssertionType 未定义
    pass


# 全局单例
assertion_executor = AssertionExecutor()
