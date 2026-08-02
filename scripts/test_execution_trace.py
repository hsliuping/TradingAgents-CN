"""P1 机器可读执行轨迹 — 测试脚本

覆盖范围：
  Layer 1 组件测试
    1. test_recorder_methods_record_correctly   — Recorder 各 record_* 方法正确填充 trace
    2. test_is_trace_enabled_follows_settings   — 开关跟随 settings.AGENT_EXECUTION_TRACE_ENABLED
    3. test_service_save_and_update             — Service 写入 + 回填（连真实 MongoDB 27019）
    4. test_service_non_blocking_on_db_failure  — DB 不可用时不抛异常（非阻塞保障）
    5. test_record_trace_validation_skips_when_disabled — 开关关闭时回填跳过

  Layer 2 Manager 校验逻辑测试（mock LLM，不调真实 LLM）
    6. test_risk_manager_v2_validate_passed     — 合规 JSON → passed
    7. test_risk_manager_v2_validate_failed     — 不合规 JSON → failed
    8. test_research_manager_v2_validate_passed — 合规 JSON → passed
    9. test_research_manager_v2_validate_failed — 不合规 JSON → failed
   10. test_trader_v2_validate_passed           — 合规简报 → passed
   11. test_trader_v2_validate_failed           — 含禁用术语 → failed

运行方式：
    env\\Scripts\\python.exe scripts\\test_execution_trace.py
    env\\Scripts\\python.exe -m pytest scripts\\test_execution_trace.py -v

前置条件：
    - v3.0 MongoDB 容器运行中（端口 27019）
    - env/ 虚拟环境已安装项目依赖
"""

import json
import os
import sys
import uuid
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 测试用常量
TEST_AGENT_ID = "test_agent_v2"
TEST_TRACE_PREFIX = "test-trace-"
_v3_mongo_port = 27019  # v3.0 专用数据库端口


# ============================================================================
# 工具函数
# ============================================================================

def _make_fake_llm(model_name: str = "test-model", response_text: str = "") -> MagicMock:
    """构造一个 fake LLM，invoke 返回带 content 的 response"""
    fake_llm = MagicMock()
    fake_llm.model_name = model_name
    fake_llm.temperature = 0.3
    fake_llm.max_tokens = 4096

    fake_response = MagicMock()
    fake_response.content = response_text
    fake_response.usage_metadata = {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    fake_response.response_metadata = {"model_name": model_name}
    fake_llm.invoke.return_value = fake_response
    return fake_llm


def _make_fake_agent(agent_id: str = TEST_AGENT_ID, manager_type: Optional[str] = "risk") -> MagicMock:
    """构造一个 fake agent 供 start_execution_trace 使用"""
    agent = MagicMock()
    agent.agent_id = agent_id

    metadata = MagicMock()
    metadata.version = "2.0.0"
    agent.get_metadata.return_value = metadata
    agent.manager_type = manager_type
    agent._llm = _make_fake_llm()
    return agent


def _cleanup_test_traces(trace_ids: list) -> int:
    """清理测试产生的 trace 文档"""
    if not trace_ids:
        return 0
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        result = db["agent_execution_traces"].delete_many(
            {"trace_id": {"$in": trace_ids}}
        )
        return result.deleted_count
    except Exception as e:
        print(f"  ⚠️ 清理测试 trace 失败: {e}")
        return 0


# ============================================================================
# Layer 1: 组件测试
# ============================================================================

def test_recorder_methods_record_correctly():
    """测试 1: Recorder 各 record_* 方法能正确填充 trace 对象"""
    from core.agents.execution_trace_recorder import ExecutionTraceRecorder

    state = {
        "ticker": "600519",
        "analysis_date": "2026-07-28",
        "_workflow_runtime": {
            "workflow_id": "wf-test-001",
            "execution_id": "exec-test-001",
            "user_id": "test-user",
        },
    }

    recorder = ExecutionTraceRecorder(
        agent_id=TEST_AGENT_ID,
        agent_version="2.0.0",
        agent_type="manager",
        manager_type="risk",
        state=state,
    )

    # 初始状态
    assert recorder.trace.agent_id == TEST_AGENT_ID
    assert recorder.trace.ticker == "600519"
    assert recorder.trace.analysis_date == "2026-07-28"
    assert recorder.trace.workflow_id == "wf-test-001"
    assert recorder.trace.execution_id == "exec-test-001"
    assert recorder.trace.user_id == "test-user"

    # record_inputs
    recorder.record_inputs({"bull_report": "x" * 100, "bear_report": "y" * 50})
    assert recorder.trace.inputs.input_keys == ["bull_report", "bear_report"]
    assert recorder.trace.inputs.input_lengths["bull_report"] == 100
    assert recorder.trace.inputs.input_lengths["bear_report"] == 50

    # record_prompts
    recorder.record_prompts("system prompt", "user prompt")
    assert recorder.trace.prompts.system_prompt_length == 13
    assert recorder.trace.prompts.user_prompt_length == 11
    assert recorder.trace.prompts.system_prompt_hash is not None
    assert len(recorder.trace.prompts.system_prompt_hash) == 16

    # record_llm_response
    fake_resp = MagicMock()
    fake_resp.content = "hello world"
    fake_resp.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    fake_resp.response_metadata = {"model_name": "qwen-test"}
    recorder.record_llm_response(fake_resp, llm_duration_ms=250)
    assert recorder.trace.output.output_raw_length == 11
    assert recorder.trace.output.output_raw_preview == "hello world"
    assert recorder.trace.token_usage.input_tokens == 10
    assert recorder.trace.token_usage.total_tokens == 15
    assert recorder.trace.llm_config.model_name == "qwen-test"

    # record_parsed_output
    recorder.record_parsed_output({"content": "...", "success": True})
    assert recorder.trace.output.output_parsed_type == "dict"
    assert recorder.trace.output.output_parsed_keys == ["content", "success"]
    assert recorder.trace.output.output_parsed_success is True

    # record_error
    recorder.record_error(ValueError("test error"))
    assert recorder.trace.success is False
    assert recorder.trace.error_type == "ValueError"
    assert "test error" in recorder.trace.error_message

    print("✅ 测试 1 通过: Recorder 各 record_* 方法正确填充 trace")


def test_is_trace_enabled_follows_settings():
    """测试 2: is_trace_enabled 跟随 settings.AGENT_EXECUTION_TRACE_ENABLED"""
    from app.core.config import settings
    from core.agents.execution_trace_recorder import is_trace_enabled

    original = getattr(settings, "AGENT_EXECUTION_TRACE_ENABLED", True)

    try:
        settings.AGENT_EXECUTION_TRACE_ENABLED = True
        assert is_trace_enabled() is True

        settings.AGENT_EXECUTION_TRACE_ENABLED = False
        assert is_trace_enabled() is False
        print("✅ 测试 2 通过: is_trace_enabled 跟随 settings 开关")
    finally:
        settings.AGENT_EXECUTION_TRACE_ENABLED = original


def test_service_save_and_update():
    """测试 3: Service 写入 + 回填（连真实 MongoDB 27019）"""
    from app.core.database import get_mongo_db_sync
    from app.models.execution_trace import AgentExecutionTrace
    from app.services.execution_trace_service import execution_trace_service
    from app.utils.timezone import now_tz

    trace_id = f"{TEST_TRACE_PREFIX}{uuid.uuid4().hex[:12]}"
    cleanup_ids = [trace_id]

    try:
        # 构造一个完整的 trace
        trace = AgentExecutionTrace(
            trace_id=trace_id,
            agent_id=TEST_AGENT_ID,
            agent_version="2.0.0",
            agent_type="manager",
            manager_type="risk",
            started_at=now_tz(),
            ticker="600519",
            analysis_date="2026-07-28",
            workflow_id="wf-test-002",
        )

        # 写入
        ok = execution_trace_service.save_trace_sync(trace)
        assert ok is True, "save_trace_sync 应返回 True"

        # 验证写入
        db = get_mongo_db_sync()
        doc = db["agent_execution_traces"].find_one({"trace_id": trace_id})
        assert doc is not None, "文档应已写入"
        assert doc["agent_id"] == TEST_AGENT_ID
        assert doc["ticker"] == "600519"
        assert doc["workflow_id"] == "wf-test-002"

        # 回填校验结果
        ok = execution_trace_service.update_validation_sync(
            trace_id=trace_id,
            validation_status="passed",
            validation_details={"risk_level": "低", "risk_score": 0.2},
        )
        assert ok is True, "update_validation_sync 应返回 True"

        # 验证回填
        doc = db["agent_execution_traces"].find_one({"trace_id": trace_id})
        assert doc["validation"]["validation_status"] == "passed"
        assert doc["validation"]["validation_details"]["risk_level"] == "低"

        print("✅ 测试 3 通过: Service 写入 + 回填正常（连真实 MongoDB 27019）")
    finally:
        _cleanup_test_traces(cleanup_ids)


def test_service_non_blocking_on_db_failure():
    """测试 4: DB 不可用时不抛异常（非阻塞保障）"""
    from app.models.execution_trace import AgentExecutionTrace
    from app.services.execution_trace_service import ExecutionTraceService
    from app.utils.timezone import now_tz

    trace = AgentExecutionTrace(
        trace_id=f"{TEST_TRACE_PREFIX}{uuid.uuid4().hex[:12]}",
        agent_id=TEST_AGENT_ID,
        agent_version="2.0.0",
        agent_type="manager",
        manager_type="risk",
        started_at=now_tz(),
    )

    service = ExecutionTraceService()

    # mock get_mongo_db_sync 抛异常，验证不外抛
    with patch("app.services.execution_trace_service.get_mongo_db_sync") as mock_db:
        mock_db.side_effect = ConnectionError("模拟 DB 不可用")

        # save_trace_sync 不应抛异常
        ok = service.save_trace_sync(trace)
        assert ok is False, "DB 失败时 save_trace_sync 应返回 False"

        # update_validation_sync 不应抛异常
        ok = service.update_validation_sync(
            trace_id="non-existent",
            validation_status="failed",
            validation_error="test error",
        )
        assert ok is False, "DB 失败时 update_validation_sync 应返回 False"

    print("✅ 测试 4 通过: DB 不可用时非阻塞，不抛异常")


def test_record_trace_validation_skips_when_disabled():
    """测试 5: 开关关闭时 record_trace_validation 跳过"""
    from app.core.config import settings
    from core.agents.execution_trace_recorder import record_trace_validation

    original = getattr(settings, "AGENT_EXECUTION_TRACE_ENABLED", True)

    try:
        settings.AGENT_EXECUTION_TRACE_ENABLED = False

        with patch(
            "app.services.execution_trace_service.execution_trace_service.update_validation_sync"
        ) as mock_update:
            record_trace_validation(
                trace_id="some-trace-id",
                validation_status="passed",
            )
            # 开关关闭时不应调用 service
            mock_update.assert_not_called()

        print("✅ 测试 5 通过: 开关关闭时 record_trace_validation 跳过")
    finally:
        settings.AGENT_EXECUTION_TRACE_ENABLED = original


# ============================================================================
# Layer 2: Manager 校验逻辑测试（直接测试 _validate_* 方法，不调 LLM）
# ============================================================================

def test_risk_manager_v2_validate_passed():
    """测试 6: risk_manager_v2 合规 JSON → passed"""
    from core.agents.adapters.risk_manager_v2 import RiskAssessmentOutput  # noqa: F401
    from core.agents.adapters.risk_manager_v2 import RiskManagerV2

    # _validate_* 方法不依赖 config/llm，用最小化实例即可
    agent = RiskManagerV2(llm=_make_fake_llm())

    valid_json = json.dumps({
        "risk_level": "低",
        "risk_score": 0.2,
        "reasoning": "测试推理",
        "key_risks": ["风险1"],
        "risk_control": "测试风控建议",
        "investment_adjustment": "乐观",
        "final_trade_decision": {
            "action": "乐观",
            "confidence": 0.7,
            "reasoning": "测试最终决策推理",
            "summary": "测试摘要",
        },
    }, ensure_ascii=False)

    validated, error = agent._validate_risk_assessment(valid_json)
    assert error is None, f"合规 JSON 不应报错，但得到: {error}"
    assert validated is not None
    assert validated["risk_level"] == "低"
    assert validated["final_trade_decision"]["action"] == "乐观"

    print("✅ 测试 6 通过: risk_manager_v2 合规 JSON → passed")


def test_risk_manager_v2_validate_failed():
    """测试 7: risk_manager_v2 不合规 JSON → failed（禁用术语 + 字段缺失）"""
    from core.agents.adapters.risk_manager_v2 import RiskManagerV2

    agent = RiskManagerV2(llm=_make_fake_llm())

    # 禁用术语 + 缺 final_trade_decision
    invalid_json = json.dumps({
        "risk_level": "低",
        "risk_score": 0.2,
        "investment_adjustment": "看涨",  # ❌ 禁用术语
        "summary": "测试",
    }, ensure_ascii=False)

    validated, error = agent._validate_risk_assessment(invalid_json)
    assert error is not None, "禁用术语应触发校验失败"
    assert validated is None
    assert "看涨" in error or "investment_adjustment" in error

    print(f"✅ 测试 7 通过: risk_manager_v2 不合规 JSON → failed ({error[:60]}...)")


def test_research_manager_v2_validate_passed():
    """测试 8: research_manager_v2 合规 JSON → passed"""
    from core.agents.adapters.research_manager_v2 import ResearchManagerV2

    agent = ResearchManagerV2(llm=_make_fake_llm())

    valid_json = json.dumps({
        "analysis_view": "乐观",
        "confidence": 0.7,
        "risk_score": 0.3,
        "summary": "测试摘要",
        "reasoning": "测试推理",
        "core_evidence": ["证据1", "证据2"],
        "uncertainties": ["不确定性1"],
        "invalidation_conditions": ["失效条件1"],
        "watch_items": ["观察事项1"],
        "risk_warning": "测试风险提示",
    }, ensure_ascii=False)

    validated, error = agent._validate_research_output(valid_json)
    assert error is None, f"合规 JSON 不应报错，但得到: {error}"
    assert validated is not None
    assert validated["analysis_view"] == "乐观"
    assert 0.0 <= validated["confidence"] <= 1.0

    print("✅ 测试 8 通过: research_manager_v2 合规 JSON → passed")


def test_research_manager_v2_validate_failed():
    """测试 9: research_manager_v2 不合规 JSON → failed（confidence 超范围 + 禁用术语）"""
    from core.agents.adapters.research_manager_v2 import ResearchManagerV2

    agent = ResearchManagerV2(llm=_make_fake_llm())

    invalid_json = json.dumps({
        "analysis_view": "看跌",  # ❌ 禁用术语
        "confidence": 95,  # ❌ 应为 0-1
        "risk_score": 0.3,
        "summary": "测试",
        "reasoning": "测试",
    }, ensure_ascii=False)

    validated, error = agent._validate_research_output(invalid_json)
    assert error is not None, "禁用术语 + confidence 超范围应触发校验失败"
    assert validated is None

    print(f"✅ 测试 9 通过: research_manager_v2 不合规 JSON → failed ({error[:60]}...)")


def test_trader_v2_validate_passed():
    """测试 10: trader_v2 合规简报 → passed"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2(llm=_make_fake_llm())

    valid_brief = """## 一句话结论
当前研究倾向为乐观，但需关注后续信号。

## 核心依据
- 基本面稳健
- 行业景气度上行

## 当前判断的限制
数据存在缺口。

## 后续观察事项
- 关注季报披露

## 资料边界说明
部分数据未提供。

## 免责声明
本研究简报仅供信息参考，不构成投资建议。
"""

    warning = agent._validate_trader_output(valid_brief)
    assert warning is None, f"合规简报不应报警告，但得到: {warning}"

    print("✅ 测试 10 通过: trader_v2 合规简报 → passed")


def test_trader_v2_validate_failed():
    """测试 11: trader_v2 含禁用术语 → failed"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2(llm=_make_fake_llm())

    invalid_brief = """## 一句话结论
建议买入该股票，预计看涨。

## 核心依据
- 基本面稳健

## 免责声明
本研究简报仅供信息参考。
"""

    warning = agent._validate_trader_output(invalid_brief)
    assert warning is not None, "含'买入'/'看涨'应触发警告"
    assert "买入" in warning or "看涨" in warning

    print(f"✅ 测试 11 通过: trader_v2 含禁用术语 → failed ({warning[:60]}...)")


# ============================================================================
# 主入口
# ============================================================================

ALL_TESTS = [
    ("Layer 1 - Recorder 各 record_* 方法", test_recorder_methods_record_correctly),
    ("Layer 1 - is_trace_enabled 跟随 settings", test_is_trace_enabled_follows_settings),
    ("Layer 1 - Service 写入 + 回填（真实 MongoDB）", test_service_save_and_update),
    ("Layer 1 - DB 不可用时非阻塞", test_service_non_blocking_on_db_failure),
    ("Layer 1 - 开关关闭时回填跳过", test_record_trace_validation_skips_when_disabled),
    ("Layer 2 - risk_manager_v2 合规 JSON → passed", test_risk_manager_v2_validate_passed),
    ("Layer 2 - risk_manager_v2 不合规 JSON → failed", test_risk_manager_v2_validate_failed),
    ("Layer 2 - research_manager_v2 合规 JSON → passed", test_research_manager_v2_validate_passed),
    ("Layer 2 - research_manager_v2 不合规 JSON → failed", test_research_manager_v2_validate_failed),
    ("Layer 2 - trader_v2 合规简报 → passed", test_trader_v2_validate_passed),
    ("Layer 2 - trader_v2 含禁用术语 → failed", test_trader_v2_validate_failed),
]


def main():
    """主入口：按顺序执行所有测试"""
    print("=" * 80)
    print("🧪 P1 机器可读执行轨迹 — 测试脚本")
    print(f"   MongoDB 端口: {_v3_mongo_port} (v3.0)")
    print(f"   测试用例数: {len(ALL_TESTS)}")
    print("=" * 80)

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

    print("\n" + "=" * 80)
    print(f"📊 测试结果: {passed} 通过 / {failed} 失败 / {len(ALL_TESTS)} 总计")
    print("=" * 80)

    if failures:
        print("\n❌ 失败用例:")
        for name, e in failures:
            print(f"  - {name}: {e}")
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！P1 执行轨迹采集功能就绪。")
        sys.exit(0)


if __name__ == "__main__":
    main()
