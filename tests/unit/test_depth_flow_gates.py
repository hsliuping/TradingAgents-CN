"""M3 流程门控单元测试（C6）：门控旗标 / 运行清单 / 模板条件分流 / 报告标注。"""

from core.workflow.builder import WorkflowBuilder
from core.workflow.depth_profiles import (
    GATE_FLAG_DEBATE,
    GATE_FLAG_RISK_REVIEW,
    GATE_FLAG_SCENARIO_SIM,
    STATUS_INCLUDED,
    STATUS_SKIPPED,
    build_depth_report_notice,
    build_gate_flags,
    build_run_manifest,
    get_profile,
)
from core.workflow.engine import WorkflowEngine
from core.workflow.models import NodeType
from core.workflow.templates.v2_stock_analysis_workflow import V2_STOCK_ANALYSIS_WORKFLOW


class TestBuildGateFlags:
    """profile.nodes → 门控旗标（True=跳过该段）。"""

    def test_quick_skips_scenario_and_risk(self):
        flags = build_gate_flags(get_profile("快速"))
        assert flags == {
            GATE_FLAG_DEBATE: False,
            GATE_FLAG_SCENARIO_SIM: True,
            GATE_FLAG_RISK_REVIEW: True,
        }

    def test_standard_and_above_run_all(self):
        for depth in ("标准", "深度"):
            assert build_gate_flags(get_profile(depth)) == {
                GATE_FLAG_DEBATE: False,
                GATE_FLAG_SCENARIO_SIM: False,
                GATE_FLAG_RISK_REVIEW: False,
            }


class TestBuildRunManifest:
    """环节运行清单：被跳过节点置 skipped 态留痕，不静默消失。"""

    def _status_map(self, depth):
        return {e["node_id"]: e["status"] for e in build_run_manifest(get_profile(depth))}

    def test_quick_skips_risk_segment_and_scenario(self):
        status = self._status_map("快速")
        for node_id in (
            "scenario_simulator_v2",
            "risk_debate",
            "risky_analyst_v2",
            "safe_analyst_v2",
            "neutral_analyst_v2",
            "risk_manager_v2",
        ):
            assert status[node_id] == STATUS_SKIPPED, node_id
        # 整合与辩论段照常执行
        for node_id in ("debate", "bull_researcher_v2", "bear_researcher_v2",
                        "research_manager_v2", "trader_v2"):
            assert status[node_id] == STATUS_INCLUDED, node_id

    def test_standard_manifest_all_included(self):
        status = self._status_map("标准")
        assert set(status.values()) == {STATUS_INCLUDED}

    def test_manifest_entries_shape(self):
        manifest = build_run_manifest(get_profile("快速"))
        assert len(manifest) == 17  # 6 分析师 + 3 辩论 + 1 试算 + 5 风险 + 2 整合
        for entry in manifest:
            assert set(entry) == {"node_id", "stage", "stage_label", "status"}


class TestTemplateGates:
    """v2 模板门控节点与条件边结构。"""

    def _gate(self, gate_id):
        node = V2_STOCK_ANALYSIS_WORKFLOW.get_node(gate_id)
        assert node is not None, gate_id
        assert node.type == NodeType.CONDITION, gate_id
        return node

    def test_gate_conditions_are_simple_flag_checks(self):
        assert self._gate("gate_debate").condition == "not state.get('_skip_debate')"
        assert self._gate("gate_scenario_sim").condition == "not state.get('_skip_scenario_sim')"
        assert self._gate("gate_risk_review").condition == "not state.get('_skip_risk_review')"

    def test_gate_targets(self):
        expected = {
            "gate_debate": {"true": "debate", "false": "risk_profile_v2"},
            "gate_scenario_sim": {"true": "scenario_simulator_v2", "false": "gate_risk_review"},
            "gate_risk_review": {"true": "risk_debate", "false": "trader_v2"},
        }
        for gate_id, targets in expected.items():
            edges = V2_STOCK_ANALYSIS_WORKFLOW.get_edges_from(gate_id)
            assert {e.condition: e.target for e in edges} == targets, gate_id

    def test_upstream_edges_enter_gates(self):
        edges = {e.id: e for e in V2_STOCK_ANALYSIS_WORKFLOW.edges}
        assert edges["e_debate"].source == "merge_analysts"
        assert edges["e_debate"].target == "gate_debate"
        assert edges["e_to_risk_debate"].source == "research_manager_v2"
        assert edges["e_to_risk_debate"].target == "gate_scenario_sim"
        assert edges["e_sim"].source == "scenario_simulator_v2"
        assert edges["e_sim"].target == "gate_risk_review"

    def test_no_direct_edge_bypassing_gates(self):
        # 门控上游不得残留直连边（merge→debate / 研究经理→试算 / 试算→风险辩论）
        pairs = {
            (e.source, e.target) for e in V2_STOCK_ANALYSIS_WORKFLOW.edges
        }
        assert ("merge_analysts", "debate") not in pairs
        assert ("research_manager_v2", "scenario_simulator_v2") not in pairs
        assert ("scenario_simulator_v2", "risk_debate") not in pairs


class TestGateConditionEval:
    """门控表达式与 _create_condition_node 的 eval 契约一致。"""

    def _eval_gate(self, gate_id, state):
        node = V2_STOCK_ANALYSIS_WORKFLOW.get_node(gate_id)
        fn = WorkflowBuilder.__new__(WorkflowBuilder)._create_condition_node(node)
        return fn(state).get("_condition_result")

    def test_skip_flag_blocks_segment(self):
        assert self._eval_gate("gate_risk_review", {GATE_FLAG_RISK_REVIEW: True}) is False

    def test_clear_flag_runs_segment(self):
        assert self._eval_gate("gate_risk_review", {GATE_FLAG_RISK_REVIEW: False}) is True

    def test_missing_flag_defaults_run(self):
        # 旧链路/自定义流不带门控旗标 → 照常执行（默认不跳段，行为不变）
        for gate_id in ("gate_debate", "gate_scenario_sim", "gate_risk_review"):
            assert self._eval_gate(gate_id, {}) is True


class TestBooleanStateReducer:
    """布尔状态字段必须取最新值（回归 C10：门控路由依赖 False 覆盖 True）。"""

    def test_keep_latest_bool_accepts_false(self):
        from core.state.reducers import keep_latest_bool

        assert keep_latest_bool(True, False) is False
        assert keep_latest_bool(False, True) is True
        assert keep_latest_bool(True, None) is True

    def test_dynamic_state_boolean_uses_keep_latest_bool(self):
        from typing import get_args

        from core.state.builder import StateSchemaBuilder
        from core.state.models import FieldType, StateFieldDefinition, WorkflowStateSchema
        from core.state.reducers import keep_latest_bool

        schema = WorkflowStateSchema(workflow_id="gate_reducer_probe")
        schema.add_field(
            StateFieldDefinition(name="_condition_result", type=FieldType.BOOLEAN)
        )
        state_cls = StateSchemaBuilder().generate_typed_dict(schema)
        reducer = get_args(state_cls.__annotations__["_condition_result"])[1]
        assert reducer is keep_latest_bool
        # 先 True 后 False 必须落到 False，否则门控/路由恒走 true 分支
        assert reducer(True, False) is False


class TestDepthReportNotice:
    """M3.2 报告标注：skipped 显式声明 + 跳过风险会审时静态风险声明常驻。"""

    def test_quick_notice_has_skip_labels_and_static_risk(self):
        notice = build_depth_report_notice("快速", build_run_manifest(get_profile("快速")))
        assert "快速模式" in notice
        assert "本档不含" in notice
        assert "风险会审" in notice and "情景试算" in notice
        assert "静态风险声明" in notice
        assert "不构成投资建议" in notice

    def test_standard_notice_empty(self):
        assert build_depth_report_notice("标准", build_run_manifest(get_profile("标准"))) == ""

    def test_deep_notice_empty(self):
        # 深度档全环节执行：无标注段
        assert build_depth_report_notice("深度", build_run_manifest(get_profile("深度"))) == ""

    def test_empty_manifest_notice_empty(self):
        assert build_depth_report_notice("快速", []) == ""
        assert build_depth_report_notice("快速", None) == ""


class TestEngineDepthNoticeAppend:
    """engine 把标注段追加到 final_trade_decision 末尾。"""

    def _engine(self):
        return WorkflowEngine.__new__(WorkflowEngine)

    def test_quick_report_appended(self):
        result = {
            "research_depth": "快速",
            "depth_run_manifest": build_run_manifest(get_profile("快速")),
            "final_trade_decision": "# 研究结论正文",
        }
        self._engine()._append_depth_notices(result)
        ftd = result["final_trade_decision"]
        assert ftd.startswith("# 研究结论正文")
        assert "本档不含" in ftd and "静态风险声明" in ftd

    def test_dict_report_appended_to_content(self):
        result = {
            "research_depth": "快速",
            "depth_run_manifest": build_run_manifest(get_profile("快速")),
            "final_trade_decision": {"content": "正文", "action": "hold"},
        }
        self._engine()._append_depth_notices(result)
        assert result["final_trade_decision"]["content"].startswith("正文")
        assert "静态风险声明" in result["final_trade_decision"]["content"]

    def test_no_manifest_noop(self):
        result = {"research_depth": "快速", "final_trade_decision": "正文"}
        self._engine()._append_depth_notices(result)
        assert result["final_trade_decision"] == "正文"
        assert "depth_notice" not in result

    def test_standard_run_no_notice(self):
        result = {
            "research_depth": "标准",
            "depth_run_manifest": build_run_manifest(get_profile("标准")),
            "final_trade_decision": "正文",
        }
        self._engine()._append_depth_notices(result)
        assert result["final_trade_decision"] == "正文"
