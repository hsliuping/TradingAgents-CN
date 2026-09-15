"""智能助手流式对话持久化兜底回归测试。

历史 Bug：stream_chat_with_assistant 只在回复完整收集后才保存会话，
超时/异常/客户端中途断开时用户提问直接丢失——刷新页面后提问消失，
既丢上下文也无从排查。修复后无论哪条失败路径，用户消息与错误说明
都必须落库。
"""

import asyncio
import json

from app.services import intelligent_assistant_service as service


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _Recorder:
    """记录 save_assistant_message 调用参数。"""

    def __init__(self):
        self.saved = []

    async def save(self, db, user_id, user_content, assistant_content,
                   tools_used, conversation_id=None):
        self.saved.append({
            "user_content": user_content,
            "assistant_content": assistant_content,
            "tools_used": tools_used,
        })


def _install_common_stubs(monkeypatch, fake_service_cls, recorder):
    """替换 stream_chat_with_assistant 的全部外部依赖。"""

    async def _none(*args, **kwargs):
        return None

    async def _empty_list(*args, **kwargs):
        return []

    async def _empty_str(*args, **kwargs):
        return ""

    async def _thread(*args, **kwargs):
        return {"thread_id": "thr_test"}

    monkeypatch.setattr(service, "IntelligentAssistantService", fake_service_cls)
    monkeypatch.setattr(service, "_load_assistant_settings", _none)
    monkeypatch.setattr(service, "load_user_profile", _none)
    monkeypatch.setattr(service, "get_assistant_conversation", _empty_list)
    monkeypatch.setattr(service, "_recall_memory_block", _empty_str)
    monkeypatch.setattr(service, "get_or_create_assistant_thread", _thread)
    monkeypatch.setattr(service, "save_assistant_message", recorder.save)


def _collect(agen):
    async def _run():
        return [item async for item in agen]

    return asyncio.run(_run())


def _make_service_cls(events):
    class _FakeService:
        def __init__(self, *args, **kwargs):
            pass

        async def chat_stream(self, *args, **kwargs):
            for item in events:
                yield item

    return _FakeService


def test_stream_error_event_persists_user_message_with_error_note(monkeypatch):
    """内层超时/异常发 error 事件：用户提问 + 错误说明必须落库，done 带 error 标记。"""
    recorder = _Recorder()
    events = [
        _sse("error", {"message": "处理超时（已超过 180 秒），请尝试更简短的问题。"}),
        _sse("done", {"tools_used": [], "data_refs": [], "error": True}),
    ]
    _install_common_stubs(monkeypatch, _make_service_cls(events), recorder)

    items = _collect(service.stream_chat_with_assistant(
        db=object(),
        user_message="帮我查一下问界各车型最近半年的销量变化情况。",
        user_id="u1",
        conversation_id=None,
    ))

    assert recorder.saved, "失败路径也必须保存用户提问"
    saved = recorder.saved[0]
    assert "问界" in saved["user_content"]
    assert "处理超时" in saved["assistant_content"]
    # error 事件透传给前端，done 事件带 error 标记
    assert any(item.startswith("event: error\n") and "处理超时" in item for item in items)
    assert any(item.startswith("event: done\n") and '"error": true' in item for item in items)


def test_stream_client_disconnect_persists_partial_reply(monkeypatch):
    """客户端中途断开（aclose）：已收集的部分回复与用户提问必须落库。"""
    recorder = _Recorder()

    class _FakeService:
        def __init__(self, *args, **kwargs):
            pass

        async def chat_stream(self, *args, **kwargs):
            yield _sse("token", {"content": "部分回复"})
            # 第二个事件尚未被外层收集时客户端断开
            yield _sse("token", {"content": "不会被收到"})

    _install_common_stubs(monkeypatch, _FakeService, recorder)

    async def _run():
        gen = service.stream_chat_with_assistant(
            db=object(),
            user_message="生成一个预估测试的excel表格吧。",
            user_id="u1",
            conversation_id=None,
        )
        first = await gen.__anext__()
        await gen.aclose()  # 模拟前端断开/超时 abort
        return first

    first = asyncio.run(_run())

    assert "部分回复" in first
    assert recorder.saved, "客户端中途断开也必须保存已收集内容"
    saved = recorder.saved[0]
    assert "excel" in saved["user_content"]
    assert "部分回复" in saved["assistant_content"]
    assert "不会被收到" not in saved["assistant_content"]


def test_stream_success_persists_once(monkeypatch):
    """正常完成：只保存一次，且保存完整回复。"""
    recorder = _Recorder()
    events = [
        _sse("token", {"content": "正常回复"}),
        _sse("done", {"tools_used": ["t1"], "data_refs": []}),
    ]
    _install_common_stubs(monkeypatch, _make_service_cls(events), recorder)

    items = _collect(service.stream_chat_with_assistant(
        db=object(),
        user_message="正常问题",
        user_id="u1",
        conversation_id=None,
    ))

    assert len(recorder.saved) == 1
    saved = recorder.saved[0]
    assert saved["user_content"] == "正常问题"
    assert saved["assistant_content"] == "正常回复"
    assert saved["tools_used"] == ["t1"]
    # 正常路径 done 不带 error 标记
    assert not any(item.startswith("event: done\n") and '"error": true' in item for item in items)


def test_stream_outer_exception_sends_error_event_and_persists(monkeypatch):
    """内层生成器抛异常：外层发 error 事件（而非伪装成回复文本），并保存部分回复+错误说明。"""
    recorder = _Recorder()

    class _BrokenService:
        def __init__(self, *args, **kwargs):
            pass

        async def chat_stream(self, *args, **kwargs):
            yield _sse("token", {"content": "partial"})
            raise RuntimeError("boom")

    _install_common_stubs(monkeypatch, _BrokenService, recorder)

    items = _collect(service.stream_chat_with_assistant(
        db=object(),
        user_message="问一下",
        user_id="u1",
        conversation_id=None,
    ))

    assert recorder.saved, "外层异常也必须保存会话"
    saved = recorder.saved[0]
    assert saved["user_content"] == "问一下"
    assert "partial" in saved["assistant_content"]
    assert "boom" in saved["assistant_content"]
    # 前端收到明确的 error 事件
    assert any(item.startswith("event: error\n") and "boom" in item for item in items)
    assert any(item.startswith("event: done\n") and '"error": true' in item for item in items)


def test_stream_no_reply_no_error_persists_placeholder(monkeypatch):
    """既无回复也无错误（极端场景）：用户提问仍落库，assistant 内容为明确占位。"""
    recorder = _Recorder()
    events = [_sse("done", {"tools_used": [], "data_refs": []})]
    _install_common_stubs(monkeypatch, _make_service_cls(events), recorder)

    _collect(service.stream_chat_with_assistant(
        db=object(),
        user_message="空回复问题",
        user_id="u1",
        conversation_id=None,
    ))

    assert recorder.saved
    saved = recorder.saved[0]
    assert saved["user_content"] == "空回复问题"
    assert "未收到任何内容" in saved["assistant_content"]
