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


def test_store_thread_summary_memory_is_noop(monkeypatch):
    """契约：主题摘要只保留在 Mongo 线程集合，不再写入 mem0 长期记忆。

    （旧测试断言写入 mem0，但该函数已改为 no-op；保留测试防止行为被意外改回。）
    """
    called = {"count": 0}

    class DummyMemoryService:
        async def store(self, messages, **kwargs):
            called["count"] += 1
            return SimpleNamespace(facts_extracted=0, success=True, error="")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: DummyMemoryService())

    asyncio.run(
        service._store_thread_summary_memory(
            db=object(),
            user_id="user-1",
            thread_id="thr-1",
            title="宁德时代",
            summary={
                "abstract": "宁德时代当前更接近高位震荡而不是极端泡沫。",
                "confirmed_facts": ["PEG 仍低于 1"],
                "open_questions": [],
                "next_actions": [],
                "focus_score": 0.82,
            },
            summary_type="auto",
        )
    )

    assert called["count"] == 0


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


class TestSummaryTranscriptBudget:
    def test_total_budget_caps_length_and_keeps_latest(self):
        """总量封顶 6000 字符，超预算时保留最新消息（旧消息被舍弃）"""
        messages = (
            [{"role": "user", "content": "老问题" + "甲" * 700}]
            + [
                {"role": "assistant", "content": f"第{i}条回复" + "乙" * 700}
                for i in range(9)
            ]
            + [{"role": "user", "content": "最新问题" + "丙" * 700}]
        )  # 共 11 条，每条约 700+ 字符，总计远超 6000

        text = service._format_messages_for_summary(messages)

        assert len(text) <= 6100  # 允许编号/角色前缀的少量开销
        assert "最新问题" in text
        assert "老问题" not in text  # 最老的消息被预算挤出

    def test_short_conversation_kept_intact(self):
        messages = [
            {"role": "user", "content": "问界最近销量"},
            {"role": "assistant", "content": "M9 月销过万"},
        ]
        text = service._format_messages_for_summary(messages)
        assert "问界最近销量" in text
        assert "M9 月销过万" in text
        # 编号按时间顺序
        assert text.index("1. [user]") < text.index("2. [assistant]")

    def test_empty_content_skipped(self):
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "有内容"},
        ]
        text = service._format_messages_for_summary(messages)
        assert "有内容" in text


class TestSaveAssistantMessageSummaryScheduling:
    def test_summary_runs_in_background_without_blocking_save(self, monkeypatch):
        """消息同步落库，摘要 fire-and-forget：save 返回时摘要尚未执行，
        让出事件循环后后台执行。"""
        appended = []

        async def fake_append(db, *, user_id, role, content, conversation_id=None, **kw):
            appended.append(role)
            return "thr-bg-1"

        summary_started = asyncio.Event()
        summary_done = asyncio.Event()

        async def fake_summarize(db, user_id, conversation_id=None, summary_type="manual"):
            summary_started.set()
            # 模拟 LLM 摘要耗时；关键路径不应等待它
            await asyncio.sleep(0.05)
            summary_done.set()

        monkeypatch.setattr(service, "append_assistant_message", fake_append)
        monkeypatch.setattr(service, "summarize_assistant_thread", fake_summarize)

        async def scenario():
            await service.save_assistant_message(
                db=object(),
                user_id="u1",
                user_content="问界销量",
                assistant_content="M9 过万",
                tools_used=["dongchedi_x"],
                conversation_id=None,
            )
            # save 已返回：两条消息同步落库……
            assert appended == ["user", "assistant"]
            # ……但摘要仍在后台排队/执行中（未阻塞 save）
            assert not summary_done.is_set()
            # 等待后台任务跑完
            await asyncio.wait_for(summary_done.wait(), timeout=2)
            assert summary_started.is_set()

        asyncio.run(scenario())


def _fake_llm_config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.DASHSCOPE,
        model="summary-test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        max_tokens=1024,
        timeout=60,
    )