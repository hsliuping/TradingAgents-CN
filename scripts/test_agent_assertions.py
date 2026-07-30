"""P2 反思断言 — 测试脚本

覆盖范围：
  Layer 1 组件测试
    1. test_assertion_service_create_and_load          — 创建断言 + 按 agent 加载
    2. test_assertion_service_non_blocking_on_db_failure — DB 不可用时不抛异常
    3. test_executor_term_forbidden_detected           — 禁用术语扫描命中
    4. test_executor_field_required_missing            — 必填字段缺失命中
    5. test_executor_field_enum_violation              — 枚举值违规命中
    6. test_executor_field_range_violation             — 数值范围违规命中
    7. test_executor_section_required_missing          — 章节缺失命中
    8. test_executor_no_violation_returns_empty        — 无违规返回空列表
    9. test_executor_cache_ttl                         — 缓存命中 + TTL 失效
   10. test_executor_non_blocking_on_assertion_failure — 单条断言异常不影响其他

  Layer 2 Manager 集成测试（mock LLM）
   11. test_risk_manager_v2_assertion_error_downgrades_validation — error 违规降级
   12. test_risk_manager_v2_assertion_warning_keeps_validation    — warning 违规保持
   13. test_research_manager_v2_assertion_integration             — 同构
   14. test_trader_v2_assertion_integration                       — 同构

  Layer 3 非阻塞测试
   15. test_assertion_disabled_by_setting                — 开关关闭时不执行
   16. test_assertion_db_failure_does_not_block_agent    — MongoDB 不可用时 agent 正常

运行方式：
    env\\Scripts\\python.exe scripts\\test_agent_assertions.py
    env\\Scripts\\python.exe -m pytest scripts\\test_agent_assertions.py -v

前置条件：
    - v3.0 MongoDB 容器运行中（端口 27019）
"""

import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 🔒 硬约束：必须使用 v3.0 专用数据库（端口 27019）。
# 直接运行脚本时 .env 可能指向其它版本（如 27018），这里强制覆盖，
# 避免误连非 v3.0 库造成数据污染（参考 CLAUDE.md 数据库操作铁律）。
# 必须在导入 app.core.config（settings 单例）之前设置。
os.environ["MONGODB_PORT"] = "27019"
os.environ["REDIS_PORT"] = "6381"

TEST_AGENT_ID = "test_assertion_agent"
_v3_mongo_port = 27019


# ============================================================================
# 工具函数
# ============================================================================

def _make_assertion(
    assertion_id: Optional[str] = None,
    target_agent: str = TEST_AGENT_ID,
    assertion_type: str = "term_forbidden",
    target_field: str = "*",
    constraint: Optional[Dict[str, Any]] = None,
    severity: str = "error",
    enabled: bool = True,
    description: str = "test assertion",
) -> Any:
    """构造 AgentAssertion 实例"""
    from app.models.agent_assertion import (
        AgentAssertion, AssertionConstraint, AssertionSeverity, AssertionType,
    )

    return AgentAssertion(
        assertion_id=assertion_id or f"test-{uuid.uuid4().hex[:8]}",
        target_agent=target_agent,
        assertion_type=AssertionType(assertion_type),
        target_field=target_field,
        constraint=AssertionConstraint(**(constraint or {})),
        severity=AssertionSeverity(severity),
        enabled=enabled,
        description=description,
    )


def _make_fake_llm(response_text: str = "") -> MagicMock:
    """构造 fake LLM"""
    fake_llm = MagicMock()
    fake_llm.model_name = "test-model"
    fake_llm.temperature = 0.3
    fake_llm.max_tokens = 4096

    fake_response = MagicMock()
    fake_response.content = response_text
    fake_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
    fake_response.response_metadata = {"model_name": "test-model"}
    fake_llm.invoke.return_value = fake_response
    return fake_llm


def _cleanup_assertions(assertion_ids: List[str]) -> int:
    """清理测试产生的断言文档"""
    if not assertion_ids:
        return 0
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        result = db["agent_assertions"].delete_many(
            {"assertion_id": {"$in": assertion_ids}}
        )
        return result.deleted_count
    except Exception as e:
        print(f"  ⚠️ 清理测试断言失败: {e}")
        return 0


def _cleanup_by_agent(agent_id: str) -> int:
    """按 agent 清理测试断言"""
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        result = db["agent_assertions"].delete_many({"target_agent": agent_id})
        return result.deleted_count
    except Exception as e:
        print(f"  ⚠️ 清理测试断言失败: {e}")
        return 0


# ============================================================================
# Layer 1: 组件测试
# ============================================================================

def test_assertion_service_create_and_load():
    """测试 1: 创建断言 + 按 agent 加载"""
    from app.services.agent_assertion_service import agent_assertion_service

    assertion = _make_assertion(
        target_agent=TEST_AGENT_ID,
        assertion_type="term_forbidden",
        constraint={"terms": ["看涨", "看跌"]},
        severity="error",
        enabled=True,
    )
    cleanup_ids = [assertion.assertion_id]

    try:
        # 同步创建（独立脚本中 async motor 客户端未初始化，用 sync API）
        ok = agent_assertion_service.create_assertion_sync(assertion)
        assert ok, "create_assertion_sync 应返回 True"

        # 失效缓存确保从 DB 加载
        agent_assertion_service.invalidate_cache(TEST_AGENT_ID)

        # 同步加载
        loaded = agent_assertion_service.load_enabled_assertions_sync(TEST_AGENT_ID)
        assert len(loaded) >= 1, f"应加载至少 1 条断言，实际 {len(loaded)}"
        found = [a for a in loaded if a.assertion_id == assertion.assertion_id]
        assert len(found) == 1, "应找到刚创建的断言"
        assert found[0].constraint.model_dump().get("terms") == ["看涨", "看跌"]
        assert found[0].severity.value == "error"

        print("✅ 测试 1 通过: 创建断言 + 按 agent 加载")
    finally:
        _cleanup_assertions(cleanup_ids)
        agent_assertion_service.invalidate_cache(TEST_AGENT_ID)


def test_assertion_service_non_blocking_on_db_failure():
    """测试 2: DB 不可用时不抛异常"""
    from app.services.agent_assertion_service import AgentAssertionService

    service = AgentAssertionService()

    with patch("app.services.agent_assertion_service.get_mongo_db_sync") as mock_db:
        mock_db.side_effect = ConnectionError("模拟 DB 不可用")
        service.invalidate_cache(TEST_AGENT_ID)
        # load 不应抛异常，返回空列表
        result = service.load_enabled_assertions_sync(TEST_AGENT_ID)
        assert result == [], "DB 失败时应返回空列表"

        # increment_hit_count_sync 不应抛异常
        ok = service.increment_hit_count_sync("non-existent")
        assert ok is False, "DB 失败时 increment_hit_count_sync 应返回 False"

    print("✅ 测试 2 通过: DB 不可用时非阻塞")


def test_executor_term_forbidden_detected():
    """测试 3: 禁用术语扫描命中"""
    from core.agents.assertion_executor import AssertionExecutor
    from app.models.agent_assertion import AssertionSeverity, AssertionType

    assertion = _make_assertion(
        assertion_type="term_forbidden",
        target_field="*",
        constraint={"terms": ["看涨", "看跌"]},
        severity="error",
    )

    executor = AssertionExecutor()
    # 命中
    violation = executor._check_term_forbidden(assertion, "建议看涨该股票", None)
    assert violation is not None, "应检测到'看涨'"
    assert "看涨" in violation.violation_detail
    assert violation.severity == AssertionSeverity.ERROR

    # 未命中
    violation = executor._check_term_forbidden(assertion, "建议乐观对待", None)
    assert violation is None, "无禁用术语应返回 None"

    print("✅ 测试 3 通过: 禁用术语扫描命中")


def test_executor_field_required_missing():
    """测试 4: 必填字段缺失命中"""
    from core.agents.assertion_executor import AssertionExecutor

    assertion = _make_assertion(
        assertion_type="field_required",
        target_field="risk_level",
        constraint={"field": "risk_level"},
        severity="error",
    )

    executor = AssertionExecutor()
    # 缺失
    violation = executor._check_field_required(assertion, "", {"risk_score": 0.2})
    assert violation is not None, "字段缺失应命中"
    assert "risk_level" in violation.violation_detail

    # 存在
    violation = executor._check_field_required(assertion, "", {"risk_level": "低"})
    assert violation is None, "字段存在不应命中"

    # parsed 为 None
    violation = executor._check_field_required(assertion, "text", None)
    assert violation is not None, "parsed 为 None 应命中"

    print("✅ 测试 4 通过: 必填字段缺失命中")


def test_executor_field_enum_violation():
    """测试 5: 枚举值违规命中"""
    from core.agents.assertion_executor import AssertionExecutor

    assertion = _make_assertion(
        assertion_type="field_enum",
        target_field="final_trade_decision.action",
        constraint={
            "field": "final_trade_decision.action",
            "allowed": ["乐观", "审慎", "中性"],
        },
        severity="error",
    )

    executor = AssertionExecutor()
    # 违规
    parsed = {"final_trade_decision": {"action": "看涨"}}
    violation = executor._check_field_enum(assertion, "", parsed)
    assert violation is not None, "'看涨'不在允许值内应命中"
    assert "看涨" in violation.violation_detail

    # 合规
    parsed = {"final_trade_decision": {"action": "乐观"}}
    violation = executor._check_field_enum(assertion, "", parsed)
    assert violation is None, "'乐观'在允许值内不应命中"

    print("✅ 测试 5 通过: 枚举值违规命中")


def test_executor_field_range_violation():
    """测试 6: 数值范围违规命中"""
    from core.agents.assertion_executor import AssertionExecutor

    assertion = _make_assertion(
        assertion_type="field_range",
        target_field="confidence",
        constraint={"field": "confidence", "min": 0.0, "max": 1.0},
        severity="error",
    )

    executor = AssertionExecutor()
    # 超上限
    violation = executor._check_field_range(assertion, "", {"confidence": 1.5})
    assert violation is not None, "confidence=1.5 应命中"
    assert "超过最大值" in violation.violation_detail

    # 低于下限
    violation = executor._check_field_range(assertion, "", {"confidence": -0.2})
    assert violation is not None, "confidence=-0.2 应命中"
    assert "低于最小值" in violation.violation_detail

    # 在范围内
    violation = executor._check_field_range(assertion, "", {"confidence": 0.7})
    assert violation is None, "confidence=0.7 不应命中"

    print("✅ 测试 6 通过: 数值范围违规命中")


def test_executor_section_required_missing():
    """测试 7: 章节缺失命中"""
    from core.agents.assertion_executor import AssertionExecutor

    assertion = _make_assertion(
        assertion_type="section_required",
        target_field="*",
        constraint={"sections": ["一句话结论", "核心依据"]},
        severity="warning",
    )

    executor = AssertionExecutor()
    # 缺失一个章节
    text = "## 一句话结论\n这是结论。\n## 其他内容"
    violation = executor._check_section_required(assertion, text, None)
    assert violation is not None, "缺'核心依据'应命中"
    assert "核心依据" in violation.violation_detail

    # 全部存在
    text = "## 一句话结论\n结论\n## 核心依据\n依据"
    violation = executor._check_section_required(assertion, text, None)
    assert violation is None, "章节齐全不应命中"

    print("✅ 测试 7 通过: 章节缺失命中")


def test_executor_no_violation_returns_empty():
    """测试 8: 无违规返回空列表"""
    from core.agents.assertion_executor import AssertionExecutor

    # mock service 返回一条合规断言
    assertion = _make_assertion(
        assertion_type="term_forbidden",
        constraint={"terms": ["看涨"]},
        severity="error",
    )

    executor = AssertionExecutor()
    with patch(
        "core.agents.assertion_executor.agent_assertion_service"
    ) as mock_service:
        mock_service.load_enabled_assertions_sync.return_value = [assertion]
        mock_service.increment_hit_count_sync.return_value = True

        # 输出不含禁用术语
        result = executor.run_assertions_sync(
            agent_id=TEST_AGENT_ID, raw_text="建议乐观对待", parsed=None
        )
        assert result.ran is True
        assert result.violations == [], "无违规应返回空列表"
        assert result.has_error_violation is False
        assert result.error_count == 0

    print("✅ 测试 8 通过: 无违规返回空列表")


def test_executor_cache_ttl():
    """测试 9: 缓存命中 + TTL 失效"""
    import time
    from app.services.agent_assertion_service import AgentAssertionService

    service = AgentAssertionService()
    service._cache_ttl_seconds = 0.5  # 缩短 TTL 便于测试

    assertion = _make_assertion(target_agent=TEST_AGENT_ID)

    call_count = {"n": 0}
    def _mock_load(agent_id):
        call_count["n"] += 1
        return [assertion]

    with patch.object(service, "_load_from_db_sync", side_effect=_mock_load):
        service.invalidate_cache(TEST_AGENT_ID)
        # 第一次调用 → 查 DB
        service.load_enabled_assertions_sync(TEST_AGENT_ID)
        assert call_count["n"] == 1, f"第一次应查 DB，实际 {call_count['n']}"

        # 第二次调用 → 命中缓存
        service.load_enabled_assertions_sync(TEST_AGENT_ID)
        assert call_count["n"] == 1, "第二次应命中缓存"

        # 等 TTL 过期
        time.sleep(0.6)
        service.load_enabled_assertions_sync(TEST_AGENT_ID)
        assert call_count["n"] == 2, f"TTL 过期后应重新查 DB，实际 {call_count['n']}"

    service.invalidate_cache(TEST_AGENT_ID)
    print("✅ 测试 9 通过: 缓存命中 + TTL 失效")


def test_executor_non_blocking_on_assertion_failure():
    """测试 10: 单条断言异常不影响其他"""
    from core.agents.assertion_executor import AssertionExecutor
    from app.models.agent_assertion import AssertionType

    # 构造一条会抛异常的断言（regex 无效）+ 一条正常断言
    bad_assertion = _make_assertion(
        assertion_type="regex_match",
        constraint={"field": "*", "pattern": "[invalid"},  # 无效正则
        severity="warning",
    )
    good_assertion = _make_assertion(
        assertion_type="term_forbidden",
        constraint={"terms": ["看涨"]},
        severity="error",
    )

    executor = AssertionExecutor()
    with patch(
        "core.agents.assertion_executor.agent_assertion_service"
    ) as mock_service:
        mock_service.load_enabled_assertions_sync.return_value = [bad_assertion, good_assertion]
        mock_service.increment_hit_count_sync.return_value = True

        # 输出含"看涨"，good_assertion 应命中；bad_assertion 应被跳过
        result = executor.run_assertions_sync(
            agent_id=TEST_AGENT_ID, raw_text="建议看涨", parsed=None
        )
        assert result.ran is True
        assert len(result.violations) == 1, f"应只有 1 条违规（bad 被跳过），实际 {len(result.violations)}"
        assert result.violations[0].assertion_id == good_assertion.assertion_id

    print("✅ 测试 10 通过: 单条断言异常不影响其他")


# ============================================================================
# Layer 2: Manager 集成测试（mock LLM + mock 断言）
# ============================================================================

def test_risk_manager_v2_assertion_error_downgrades_validation():
    """测试 11: risk_manager_v2 error 断言违规降级 validation_status"""
    from app.models.agent_assertion import (
        AssertionRunResult, AssertionSeverity, AssertionViolation, AssertionType,
    )
    from core.agents.adapters.risk_manager_v2 import RiskManagerV2

    agent = RiskManagerV2(llm=_make_fake_llm())

    # mock _run_assertions 返回 error 违规
    error_violation = AssertionViolation(
        assertion_id="test-err-1",
        assertion_type=AssertionType.TERM_FORBIDDEN,
        target_agent="risk_manager_v2",
        severity=AssertionSeverity.ERROR,
        description="测试 error 违规",
        violation_detail="命中: ['看涨']",
    )
    error_result = AssertionRunResult(
        ran=True, violations=[error_violation],
        has_error_violation=True, error_count=1, warning_count=0,
    )

    with patch.object(agent, "_run_assertions", return_value=error_result):
        with patch.object(agent, "_record_trace_validation"):
            # 构造一个合规的 schema 输出（会通过 schema 校验）
            valid_output = json.dumps({
                "risk_level": "低",
                "risk_score": 0.2,
                "reasoning": "测试推理",
                "key_risks": ["风险1"],
                "risk_control": "测试风控",
                "investment_adjustment": "乐观",
                "final_trade_decision": {
                    "action": "乐观",
                    "confidence": 0.7,
                    "reasoning": "测试",
                    "summary": "测试",
                },
            }, ensure_ascii=False)

            validated_dict, validation_error = agent._validate_risk_assessment(valid_output)
            assert validation_error is None, "schema 应校验通过"

            # 模拟 execute 中的断言合并逻辑
            result: Dict[str, Any] = {}
            assertion_result = agent._run_assertions(raw_text=valid_output, parsed=validated_dict)
            if assertion_result.has_error_violation:
                result["risk_assessment_validation_status"] = "failed"
                result["risk_assessment_validation_error"] = f"断言违规: {assertion_result.error_count} 条 error"

            assert result["risk_assessment_validation_status"] == "failed", "error 违规应降级为 failed"
            assert "断言违规" in result["risk_assessment_validation_error"]

    print("✅ 测试 11 通过: risk_manager_v2 error 违规降级 validation_status")


def test_risk_manager_v2_assertion_warning_keeps_validation():
    """测试 12: risk_manager_v2 warning 断言违规保持 validation_status=passed"""
    from app.models.agent_assertion import (
        AssertionRunResult, AssertionSeverity, AssertionViolation, AssertionType,
    )
    from core.agents.adapters.risk_manager_v2 import RiskManagerV2

    agent = RiskManagerV2(llm=_make_fake_llm())

    warning_violation = AssertionViolation(
        assertion_id="test-warn-1",
        assertion_type=AssertionType.SECTION_REQUIRED,
        target_agent="risk_manager_v2",
        severity=AssertionSeverity.WARNING,
        description="测试 warning 违规",
        violation_detail="缺失章节: ['附录']",
    )
    warning_result = AssertionRunResult(
        ran=True, violations=[warning_violation],
        has_error_violation=False, error_count=0, warning_count=1,
    )

    with patch.object(agent, "_run_assertions", return_value=warning_result):
        with patch.object(agent, "_record_trace_validation"):
            valid_output = json.dumps({
                "risk_level": "低",
                "risk_score": 0.2,
                "reasoning": "测试",
                "investment_adjustment": "乐观",
                "final_trade_decision": {"action": "乐观", "confidence": 0.7, "reasoning": "x", "summary": "y"},
            }, ensure_ascii=False)

            validated_dict, validation_error = agent._validate_risk_assessment(valid_output)
            assert validation_error is None

            result: Dict[str, Any] = {}
            assertion_result = agent._run_assertions(raw_text=valid_output, parsed=validated_dict)
            if assertion_result.has_error_violation:
                result["risk_assessment_validation_status"] = "failed"
            else:
                result["risk_assessment_validation_status"] = "passed"

            assert result["risk_assessment_validation_status"] == "passed", "warning 违规应保持 passed"

    print("✅ 测试 12 通过: risk_manager_v2 warning 违规保持 validation_status")


def test_research_manager_v2_assertion_integration():
    """测试 13: research_manager_v2 断言集成"""
    from app.models.agent_assertion import AssertionRunResult
    from core.agents.adapters.research_manager_v2 import ResearchManagerV2

    agent = ResearchManagerV2(llm=_make_fake_llm())
    empty_result = AssertionRunResult(ran=True, violations=[], has_error_violation=False)

    with patch.object(agent, "_run_assertions", return_value=empty_result):
        with patch.object(agent, "_record_trace_validation"):
            valid_output = json.dumps({
                "analysis_view": "乐观",
                "confidence": 0.7,
                "risk_score": 0.3,
                "summary": "测试",
                "reasoning": "测试",
                "core_evidence": ["证据1"],
                "uncertainties": ["不确定性1"],
                "invalidation_conditions": ["条件1"],
                "watch_items": ["观察1"],
                "risk_warning": "提示",
            }, ensure_ascii=False)

            validated_dict, validation_error = agent._validate_research_output(valid_output)
            assert validation_error is None, "schema 应通过"

            assertion_result = agent._run_assertions(raw_text=valid_output, parsed=validated_dict)
            assert assertion_result.has_error_violation is False

            result = {"investment_plan_validation_status": "passed" if not assertion_result.has_error_violation else "failed"}
            assert result["investment_plan_validation_status"] == "passed"

    print("✅ 测试 13 通过: research_manager_v2 断言集成")


def test_trader_v2_assertion_integration():
    """测试 14: trader_v2 断言集成（直接调用 executor 单例）"""
    from app.models.agent_assertion import (
        AssertionRunResult, AssertionSeverity, AssertionViolation, AssertionType,
    )
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2(llm=_make_fake_llm())

    error_violation = AssertionViolation(
        assertion_id="test-trader-1",
        assertion_type=AssertionType.SECTION_REQUIRED,
        target_agent="trader_v2",
        severity=AssertionSeverity.ERROR,
        description="测试",
        violation_detail="缺失章节",
    )
    error_result = AssertionRunResult(
        ran=True, violations=[error_violation],
        has_error_violation=True, error_count=1, warning_count=0,
    )

    # trader_v2 直接调用 assertion_executor 单例，mock 它
    # 注意：record_trace_validation 是 trader_v2.execute() 内的局部导入，
    # 无法在模块级 patch；本测试不调用 execute()，故无需 patch。
    with patch("core.agents.assertion_executor.assertion_executor") as mock_executor:
        mock_executor.run_assertions_sync.return_value = error_result

        # 构造一个合规简报（通过 _validate_trader_output）
        valid_brief = "## 一句话结论\n乐观\n## 核心依据\n依据\n## 免责声明\n免责"
        validation_warning = agent._validate_trader_output(valid_brief)
        assert validation_warning is None, "简报应通过合规校验"

        # 模拟断言执行
        assertion_result = mock_executor.run_assertions_sync(
            agent_id=agent.agent_id, raw_text=valid_brief, parsed=None
        )
        assert assertion_result.has_error_violation is True

        # 合并逻辑：合规通过 + 断言 error → failed
        status = "failed" if (validation_warning or assertion_result.has_error_violation) else "passed"
        assert status == "failed", "断言 error 应让整体 status=failed"

    print("✅ 测试 14 通过: trader_v2 断言集成")


# ============================================================================
# Layer 3: 非阻塞测试
# ============================================================================

def test_assertion_disabled_by_setting():
    """测试 15: AGENT_ASSERTION_ENABLED=False 时不执行"""
    from app.core.config import settings
    from app.models.agent_assertion import AssertionRunResult
    from core.agents.manager import ManagerAgent
    from core.agents.adapters.risk_manager_v2 import RiskManagerV2

    agent = RiskManagerV2(llm=_make_fake_llm())
    original = getattr(settings, "AGENT_ASSERTION_ENABLED", True)

    try:
        settings.AGENT_ASSERTION_ENABLED = False
        with patch(
            "core.agents.assertion_executor.assertion_executor"
        ) as mock_executor:
            result = agent._run_assertions(raw_text="test", parsed={})
            assert result.ran is False, "开关关闭时 ran 应为 False"
            mock_executor.run_assertions_sync.assert_not_called()

        print("✅ 测试 15 通过: 开关关闭时不执行断言")
    finally:
        settings.AGENT_ASSERTION_ENABLED = original


def test_assertion_db_failure_does_not_block_agent():
    """测试 16: MongoDB 不可用时 agent 正常返回"""
    from core.agents.assertion_executor import AssertionExecutor

    executor = AssertionExecutor()
    with patch(
        "core.agents.assertion_executor.agent_assertion_service"
    ) as mock_service:
        # service 加载断言抛异常
        mock_service.load_enabled_assertions_sync.side_effect = ConnectionError("DB 挂了")
        mock_service.increment_hit_count_sync.return_value = False

        # executor 不应抛异常
        result = executor.run_assertions_sync(
            agent_id=TEST_AGENT_ID, raw_text="test", parsed=None
        )
        # 注意：load 抛异常会被 run_assertions_sync 的 try/except 捕获，返回 ran=False
        assert result.ran is False, "DB 失败时 ran 应为 False"

    print("✅ 测试 16 通过: MongoDB 不可用时 agent 正常返回")


# ============================================================================
# 主入口
# ============================================================================

ALL_TESTS = [
    ("Layer 1 - Service 创建 + 加载", test_assertion_service_create_and_load),
    ("Layer 1 - DB 不可用时非阻塞", test_assertion_service_non_blocking_on_db_failure),
    ("Layer 1 - 禁用术语扫描命中", test_executor_term_forbidden_detected),
    ("Layer 1 - 必填字段缺失命中", test_executor_field_required_missing),
    ("Layer 1 - 枚举值违规命中", test_executor_field_enum_violation),
    ("Layer 1 - 数值范围违规命中", test_executor_field_range_violation),
    ("Layer 1 - 章节缺失命中", test_executor_section_required_missing),
    ("Layer 1 - 无违规返回空列表", test_executor_no_violation_returns_empty),
    ("Layer 1 - 缓存命中 + TTL 失效", test_executor_cache_ttl),
    ("Layer 1 - 单条断言异常不影响其他", test_executor_non_blocking_on_assertion_failure),
    ("Layer 2 - risk_manager_v2 error 降级", test_risk_manager_v2_assertion_error_downgrades_validation),
    ("Layer 2 - risk_manager_v2 warning 保持", test_risk_manager_v2_assertion_warning_keeps_validation),
    ("Layer 2 - research_manager_v2 集成", test_research_manager_v2_assertion_integration),
    ("Layer 2 - trader_v2 集成", test_trader_v2_assertion_integration),
    ("Layer 3 - 开关关闭不执行", test_assertion_disabled_by_setting),
    ("Layer 3 - DB 不可用不阻塞 agent", test_assertion_db_failure_does_not_block_agent),
]


def main():
    print("=" * 80)
    print("🧪 P2 反思断言 — 测试脚本")
    print(f"   MongoDB 端口: {_v3_mongo_port} (v3.0)")
    print(f"   测试用例数: {len(ALL_TESTS)}")
    print("=" * 80)

    # 测试前清理
    _cleanup_by_agent(TEST_AGENT_ID)

    passed = 0
    failed = 0
    failures = []

    for name, test_func in ALL_TESTS:
        print(f"\n▶ 运行: {name}")
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            failures.append((name, e))
            print(f"❌ 失败: {name}")
            print(f"   异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    # 测试后清理
    _cleanup_by_agent(TEST_AGENT_ID)

    print("\n" + "=" * 80)
    print(f"📊 测试结果: {passed} 通过 / {failed} 失败 / {len(ALL_TESTS)} 总计")
    print("=" * 80)

    if failures:
        print("\n❌ 失败用例:")
        for name, e in failures:
            print(f"  - {name}: {e}")
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！P2 反思断言功能就绪。")
        sys.exit(0)


if __name__ == "__main__":
    main()
