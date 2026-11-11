"""执行模式（研究/执行双模式提示词）PR1 单测：开关 + 模板加载双向隔离与回落

设计文档：docs/05-design/v4.0/execution-advice-mode-design.md §4
"""

import types

import pytest

from tradingagents.utils.template_client import TemplateClient


# ==================== 测试基建：内存版 Mongo 查询语义 ====================

def _matches(doc, query):
    """极简 Mongo 查询匹配：支持等值 / $ne / $exists / $or（覆盖 template_client 用到的算子）"""
    for key, cond in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in cond):
                return False
            continue
        val = doc.get(key)
        if isinstance(cond, dict):
            for op, arg in cond.items():
                if op == "$ne":
                    if val == arg:
                        return False
                elif op == "$exists":
                    if arg and key not in doc:
                        return False
                    if not arg and key in doc:
                        return False
                else:  # pragma: no cover - 未用到的算子显式失败
                    raise NotImplementedError(f"unsupported op: {op}")
        elif val != cond:
            return False
    return True


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find_one(self, query):
        self.queries.append(query)
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None


def _make_client(template_docs):
    """跳过 Mongo 连接构造 TemplateClient（get_effective_template 仅用两个集合）"""
    client = TemplateClient.__new__(TemplateClient)
    client.templates_collection = _FakeCollection(template_docs)
    client.configs_collection = _FakeCollection([])
    return client


_RESEARCH_DOC = {
    "_id": "research-1",
    "agent_type": "managers_v2",
    "agent_name": "research_manager_v2",
    "preference_type": "neutral",
    "is_system": True,
    "status": "active",
    "content": {"system_prompt": "RESEARCH_PROMPT", "user_prompt": "RESEARCH_USER"},
    # 无 workflow_id 键（默认系统模板），无 advice_mode 键（≡ research）
}

_EXECUTION_DOC = {
    "_id": "execution-1",
    "agent_type": "managers_v2",
    "agent_name": "research_manager_v2",
    "preference_type": "neutral",
    "is_system": True,
    "status": "active",
    "advice_mode": "execution",
    "content": {"system_prompt": "EXECUTION_PROMPT", "user_prompt": "EXECUTION_USER"},
}

_WORKFLOW_RESEARCH_DOC = {
    "_id": "wf-research-1",
    "agent_type": "managers_v2",
    "agent_name": "research_manager_v2",
    "preference_type": "neutral",
    "workflow_id": "stock_analysis_v2",
    "status": "active",
    "content": {"system_prompt": "WORKFLOW_RESEARCH_PROMPT"},
}


# ==================== 开关 helper ====================

class TestAdviceModeSwitch:
    def test_default_off(self, monkeypatch):
        from core.agents import advice_mode

        class _Settings:
            EXECUTION_ADVICE_MODE = False

        monkeypatch.setattr("app.core.config.settings", _Settings())
        assert advice_mode.is_execution_advice_mode() is False
        assert advice_mode.current_advice_mode() == "research"

    def test_switch_on(self, monkeypatch):
        from core.agents import advice_mode

        class _Settings:
            EXECUTION_ADVICE_MODE = True

        monkeypatch.setattr("app.core.config.settings", _Settings())
        assert advice_mode.is_execution_advice_mode() is True
        assert advice_mode.current_advice_mode() == "execution"

    def test_settings_unavailable_falls_back_to_research(self, monkeypatch):
        from core.agents import advice_mode

        def _raise():
            raise RuntimeError("no settings")

        monkeypatch.setattr("app.core.config", types.SimpleNamespace(settings=None), raising=False)
        # settings 为 None 时 getattr 链路应安全返回 False
        assert advice_mode.is_execution_advice_mode() is False


class TestContextInjection:
    def test_none_context_returns_dict(self, monkeypatch):
        from core.agents import advice_mode

        monkeypatch.setattr(advice_mode, "is_execution_advice_mode", lambda: True)
        ctx = advice_mode.context_with_advice_mode(None)
        assert ctx == {"advice_mode": "execution"}

    def test_dict_context_copy_not_mutated(self, monkeypatch):
        from core.agents import advice_mode

        monkeypatch.setattr(advice_mode, "is_execution_advice_mode", lambda: False)
        original = {"user_id": "u1", "preference_id": "neutral"}
        ctx = advice_mode.context_with_advice_mode(original)
        assert ctx["advice_mode"] == "research"
        assert ctx["user_id"] == "u1"
        assert "advice_mode" not in original  # 原 dict 不被污染

    def test_object_context_setattr(self, monkeypatch):
        from core.agents import advice_mode

        monkeypatch.setattr(advice_mode, "is_execution_advice_mode", lambda: True)
        obj = types.SimpleNamespace(user_id="u1")
        ctx = advice_mode.context_with_advice_mode(obj)
        assert ctx is obj
        assert ctx.advice_mode == "execution"


# ==================== 模板加载双向隔离与回落 ====================

class TestTemplateLoadingIsolation:
    def test_research_mode_excludes_execution_template(self):
        """研究模式：库中只有 execution 模板时不得返回（双向隔离）"""
        client = _make_client([_EXECUTION_DOC])
        result = client.get_effective_template("managers_v2", "research_manager_v2")
        assert result is None  # execution 模板被 $ne 排除，无可用研究模板
        # 所有查询都带排除条件
        assert client.templates_collection.queries
        for q in client.templates_collection.queries:
            assert q.get("advice_mode") == {"$ne": "execution"}

    def test_research_mode_returns_research_template(self):
        """研究模式（默认）：正常返回研究模板，查询含排除条件"""
        client = _make_client([_RESEARCH_DOC, _EXECUTION_DOC])
        result = client.get_effective_template("managers_v2", "research_manager_v2")
        assert result is not None
        assert result["system_prompt"] == "RESEARCH_PROMPT"
        assert result["source"] == "system"
        for q in client.templates_collection.queries:
            assert q.get("advice_mode") == {"$ne": "execution"}

    def test_execution_mode_prefers_execution_template(self):
        """执行模式：优先返回 execution 模板，首个查询即 advice_mode=execution"""
        client = _make_client([_RESEARCH_DOC, _EXECUTION_DOC])
        result = client.get_effective_template(
            "managers_v2", "research_manager_v2",
            context={"advice_mode": "execution"},
        )
        assert result is not None
        assert result["system_prompt"] == "EXECUTION_PROMPT"
        assert result["source"] == "system_execution"
        assert result["advice_mode"] == "execution"
        first_query = client.templates_collection.queries[0]
        assert first_query.get("advice_mode") == "execution"

    def test_execution_mode_falls_back_to_research(self):
        """执行模式回落保证：库中无 execution 模板 → 回落研究模板"""
        client = _make_client([_RESEARCH_DOC])
        result = client.get_effective_template(
            "managers_v2", "research_manager_v2",
            context={"advice_mode": "execution"},
        )
        assert result is not None
        assert result["system_prompt"] == "RESEARCH_PROMPT"
        # 先查 execution（miss），再回落研究查询（带 $ne）
        queries = client.templates_collection.queries
        assert queries[0].get("advice_mode") == "execution"
        assert any(q.get("advice_mode") == {"$ne": "execution"} for q in queries[1:])

    def test_execution_mode_beats_workflow_specific_template(self):
        """执行模式优先级：execution 系统模板高于流程专属研究模板"""
        docs = [_WORKFLOW_RESEARCH_DOC, dict(_EXECUTION_DOC)]
        client = _make_client(docs)
        result = client.get_effective_template(
            "managers_v2", "research_manager_v2",
            context={"advice_mode": "execution", "workflow_id": "stock_analysis_v2"},
        )
        assert result is not None
        assert result["system_prompt"] == "EXECUTION_PROMPT"

    def test_execution_mode_pref_preference_then_neutral(self):
        """执行模式偏好降级：preference=aggressive 无 execution 模板时降级 neutral 命中"""
        client = _make_client([_RESEARCH_DOC, _EXECUTION_DOC])
        result = client.get_effective_template(
            "managers_v2", "research_manager_v2",
            preference_id="aggressive",
            context={"advice_mode": "execution"},
        )
        assert result is not None
        assert result["system_prompt"] == "EXECUTION_PROMPT"
        assert result["selected_preference"] == "neutral"

    def test_workflow_channel_excludes_execution(self):
        """流程专属通道双向隔离：execution 模板即使带 workflow_id 也不被流程查询命中"""
        wf_execution = dict(_EXECUTION_DOC)
        wf_execution["workflow_id"] = "stock_analysis_v2"
        client = _make_client([_WORKFLOW_RESEARCH_DOC, wf_execution])
        result = client.get_effective_template(
            "managers_v2", "research_manager_v2",
            context={"workflow_id": "stock_analysis_v2"},  # 研究模式
        )
        assert result is not None
        assert result["system_prompt"] == "WORKFLOW_RESEARCH_PROMPT"
