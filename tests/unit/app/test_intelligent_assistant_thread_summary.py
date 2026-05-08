import asyncio
from types import SimpleNamespace

from app.services import intelligent_assistant_service as service
from core.llm.models import LLMConfig, LLMProvider
from core.llm.models import LLMResponse


def test_build_thread_summary_with_llm_prefers_structured_output(monkeypatch):
    messages = [
        {"role": "user", "content": "宁德时代涨得太多了吧。"},
        {
            "role": "assistant",
            "content": (
                "数据回来了，咱们用数字说话。短期涨幅偏快，但 RSI 还没到超买，"
                "更像高位震荡而不是极端泡沫。"
            ),
        },
    ]

    class DummyClient:
        async def achat(self, messages):
            return LLMResponse(
                content=(
                    '{"abstract":"宁德时代短期涨幅偏快，但当前更接近高位强势震荡，尚未出现极端过热信号。",'
                    '"confirmed_facts":["最新一轮回复已比较价格偏离、RSI 与估值位置","结论偏向短期涨快了，但不是泡沫化极端状态"],'
                    '"open_questions":["是否要继续看行业景气和后续盈利兑现"],'
                    '"next_actions":["继续补充行业景气与盈利增速验证","观察后续动能是否继续走弱"],'
                    '"focus_score":0.86}'
                )
            )

    monkeypatch.setattr(service, "get_coding_llm_config", _async_return(_fake_llm_config()))
    monkeypatch.setattr(service.UnifiedLLMClient, "from_config", lambda config: DummyClient())

    summary = asyncio.run(service._build_thread_summary_with_llm(db=object(), messages=messages, title="宁德时代"))

    assert summary["abstract"] == "宁德时代短期涨幅偏快，但当前更接近高位强势震荡，尚未出现极端过热信号。"
    assert summary["confirmed_facts"][0] == "最新一轮回复已比较价格偏离、RSI 与估值位置"
    assert summary["open_questions"] == ["是否要继续看行业景气和后续盈利兑现"]
    assert summary["next_actions"][0] == "继续补充行业景气与盈利增速验证"
    assert summary["focus_score"] == 0.86


def test_build_thread_summary_with_llm_falls_back_when_llm_fails(monkeypatch):
    messages = [
        {"role": "user", "content": "宁德时代涨得太多了吧。"},
        {"role": "assistant", "content": "数据回来了，咱们用数字说话，不靠感觉。整理如下：\n\n## 当前状态\n价格偏离均线较多。"},
    ]

    class BrokenClient:
        async def achat(self, messages):
            raise RuntimeError("llm unavailable")

    monkeypatch.setattr(service, "get_coding_llm_config", _async_return(_fake_llm_config()))
    monkeypatch.setattr(service.UnifiedLLMClient, "from_config", lambda config: BrokenClient())

    summary = asyncio.run(service._build_thread_summary_with_llm(db=object(), messages=messages, title="宁德时代"))

    assert summary == service._build_thread_summary_from_messages(messages, "宁德时代")
    assert summary["abstract"].startswith("数据回来了")


def test_build_thread_summary_with_llm_falls_back_when_client_init_fails(monkeypatch):
    messages = [
        {"role": "user", "content": "宁德时代符合价值投资的概念吗"},
        {"role": "assistant", "content": "我从估值、盈利质量和现金流三层来拆。"},
    ]

    monkeypatch.setattr(service, "get_coding_llm_config", _async_return(_fake_llm_config()))

    def _raise_client_error(config):
        raise RuntimeError("client init failed")

    monkeypatch.setattr(service.UnifiedLLMClient, "from_config", _raise_client_error)

    summary = asyncio.run(service._build_thread_summary_with_llm(db=object(), messages=messages, title="宁德时代"))

    assert summary == service._build_thread_summary_from_messages(messages, "宁德时代")
    assert summary["focus_score"] > 0


def test_thread_doc_to_item_hides_legacy_raw_abstract_summary():
    item = service._thread_doc_to_item(
        {
            "thread_id": "thr_legacy",
            "title": "宁德时代",
            "topic_type": "general",
            "pinned": False,
            "archived": False,
            "message_count": 2,
            "last_user_message": "宁德时代符合价值投资的概念吗",
            "report_refs": [],
            "current_summary": {
                "abstract": "好啦，数据已经齐了。下面我用**价值投资的经典框架**来逐层拆解宁德时代。\n\n---\n\n## 🔍 宁德时代 × 价值投资体检",
                "confirmed_facts": [],
                "open_questions": [],
                "next_actions": [],
                "focus_score": 0.0,
            },
        }
    )

    assert item["current_summary"] is None


def test_store_thread_summary_memory_persists_confirmed_facts(monkeypatch):
    captured = {}

    class DummyMemoryService:
        async def store(self, messages, **kwargs):
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return SimpleNamespace(facts_extracted=len(messages), success=True, error="")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: DummyMemoryService())

    asyncio.run(
        service._store_thread_summary_memory(
            db=object(),
            user_id="user-1",
            thread_id="thr-1",
            title="宁德时代",
            summary={
                "abstract": "宁德时代当前更接近高位震荡而不是极端泡沫。",
                "confirmed_facts": ["最新一轮已比较价格偏离与 RSI 位置", "PEG 仍低于 1"],
                "open_questions": [],
                "next_actions": [],
                "focus_score": 0.82,
            },
            summary_type="auto",
        )
    )

    assert captured["kwargs"]["scope"] == "analysis_insight"
    assert captured["kwargs"]["infer"] is False
    assert captured["kwargs"]["metadata"]["source_agent"] == "assistant_summary"
    assert captured["messages"][0]["content"] == "宁德时代：最新一轮已比较价格偏离与 RSI 位置"
    assert captured["messages"][1]["content"] == "宁德时代：PEG 仍低于 1"


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


def _fake_llm_config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.DASHSCOPE,
        model="summary-test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        max_tokens=1024,
        timeout=60,
    )