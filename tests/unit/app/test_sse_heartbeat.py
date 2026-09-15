# -*- coding: utf-8 -*-
"""SSE 心跳包装器测试。

回归（真实缺陷）：旧实现 `wait_for(gen.__anext__(), timeout=15)` 在心跳超时
时会把 CancelledError 注入底层生成器，第一次 >15s 静默（长工具执行，如
估值 Excel 生成 30-180s）就杀死整条流。
"""

import asyncio

import pytest

from app.routers.intelligent_assistant import sse_stream_with_heartbeat


async def _collect(agen, max_items=100):
    items = []
    async for chunk in agen:
        items.append(chunk)
        if len(items) >= max_items:
            break
    return items


class TestSseHeartbeat:
    @pytest.mark.asyncio
    async def test_long_silence_survives_and_delivers_keepalives(self):
        """底层生成器静默超过多个心跳周期后仍存活，心跳之后正常产出到达。"""

        async def slow_gen():
            await asyncio.sleep(0.25)  # 约 5 个心跳周期（interval=0.05）
            yield "event: data\ndata: final\n\n"

        items = await _collect(sse_stream_with_heartbeat(slow_gen(), heartbeat_interval=0.05))

        assert "event: data\ndata: final\n\n" in items
        keepalives = [i for i in items if i == ": keepalive\n\n"]
        assert len(keepalives) >= 3, f"长静默期应持续发心跳，实际 {len(keepalives)} 条"

    @pytest.mark.asyncio
    async def test_normal_chunks_pass_through(self):
        async def gen():
            for i in range(3):
                yield f"chunk-{i}"

        items = await _collect(sse_stream_with_heartbeat(gen(), heartbeat_interval=5))
        assert items == ["chunk-0", "chunk-1", "chunk-2"]

    @pytest.mark.asyncio
    async def test_generator_exception_becomes_error_event(self):
        async def boom():
            yield "before"
            raise RuntimeError("工具爆炸了")
            yield "after"  # noqa: unreachable

        items = await _collect(sse_stream_with_heartbeat(boom(), heartbeat_interval=5))
        assert items[0] == "before"
        assert any(i.startswith("event: error") and "工具爆炸了" in i for i in items[1:])

    @pytest.mark.asyncio
    async def test_early_client_close_cancels_generator(self):
        """消费方提前关闭（模拟客户端断开）时，底层生成器被取消并完成清理。"""
        cancelled = asyncio.Event()

        async def gen():
            try:
                await asyncio.sleep(10)
                yield "never"
            except asyncio.CancelledError:
                cancelled.set()
                raise

        # 短心跳：第一次 __anext__ 拿到心跳时，底层生成器仍挂在 sleep 上
        wrapped = sse_stream_with_heartbeat(gen(), heartbeat_interval=0.05)
        first = await wrapped.__anext__()
        assert first == ": keepalive\n\n"
        await wrapped.aclose()
        # 给取消传播留一个循环周期
        await asyncio.sleep(0.05)
        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_old_antipattern_demonstration(self):
        """对照实验：旧模式（wait_for(__anext__)）确实会杀死生成器。
        本测试固化缺陷行为，防止有人把包装器改回旧模式。"""

        async def slow_gen():
            await asyncio.sleep(30)
            yield "late"

        g = slow_gen()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(g.__anext__(), timeout=0.05)
        # 旧模式：生成器已被取消杀死
        with pytest.raises(StopAsyncIteration):
            await g.__anext__()
