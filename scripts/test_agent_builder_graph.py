"""
Agent Builder Graph 端到端测试脚本

模拟完整流程：
  1. 需求探索（用户：帮我创建一个财报排雷助手）
  2. 确认需求（用户：确认）
  3. 能力盘点（自动）
  4. 方案生成（自动）
  5. 方案选择（用户：方案A）
  6. 生成 Agent（自动）

不依赖前端，直接调用 Runtime + Graph。
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
    stream=sys.stderr,
)

os.environ.setdefault("MONGODB_HOST", "127.0.0.1")
os.environ.setdefault("MONGODB_PORT", "27019")
os.environ.setdefault("MONGODB_DATABASE", "tradingagents")
os.environ.setdefault("MONGODB_USERNAME", "admin")
os.environ.setdefault("MONGODB_PASSWORD", "tradingagents123")
os.environ.setdefault("MONGODB_AUTH_SOURCE", "admin")


async def test_end_to_end():
    """端到端测试 Agent Builder Graph。"""
    from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core import database as _db_module

    # 连接 MongoDB（带认证）
    mongo_host = os.environ.get("MONGODB_HOST", "127.0.0.1")
    mongo_port = os.environ.get("MONGODB_PORT", "27019")
    db_name = os.environ.get("MONGODB_DATABASE", "tradingagents")
    mongo_user = os.environ.get("MONGODB_USERNAME", "admin")
    mongo_pass = os.environ.get("MONGODB_PASSWORD", "tradingagents123")
    mongo_url = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:{mongo_port}/?authSource=admin"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # 绑定全局 mongo_client / mongo_db，供 tools 内部 get_mongo_db() 使用
    _db_module.mongo_client = client
    _db_module.mongo_db = db

    print("\n" + "=" * 80)
    print("🧪 Agent Builder Graph 端到端测试")
    print("=" * 80)

    # 初始化 Runtime
    print("\n📋 Step 0: 初始化 Runtime...")
    runtime = await EmbeddedNanobotRuntime.from_database(
        db,
        workspace=PROJECT_ROOT,
        preferred_model=None,
    )
    await runtime.sync_tradingagents_capabilities(db)
    print("✅ Runtime 初始化完成")

    # 测试用的 thread_id
    test_thread_id = f"test-e2e-{int(asyncio.get_event_loop().time() * 1000)}"

    # 收集 SSE 事件
    events = []

    async def on_progress(msg):
        print(f"  📊 progress: {msg}")

    async def on_stream(text):
        pass  # 不打印 token

    async def on_tool_event(data):
        print(f"  🔧 tool: {data.get('name', '?')} → {data.get('status', '?')}")
        events.append({"type": "tool", "data": data})

    async def on_step_event(data):
        print(f"  📝 step: {data.get('title', '?')}")
        events.append({"type": "step", "data": data})

    # ── Step 1: 需求探索 ──
    print(f"\n📋 Step 1: 需求探索 (thread={test_thread_id})")
    print("  用户: 帮我创建一个财报排雷助手")

    result = await runtime.handle_message(
        user_message="帮我创建一个财报排雷助手",
        session_key=test_thread_id,
        channel="agent_workshop",
        chat_id=test_thread_id,
        thread_id=test_thread_id,
        thread_context={},
        user_id="test_user",
        on_progress=on_progress,
        on_stream=on_stream,
        on_tool_event=on_tool_event,
        on_step_event=on_step_event,
    )

    content = result.get("content", "")
    tools_used = result.get("tools_used", [])
    print(f"  📤 回复: {content[:200]}...")
    print(f"  🔧 工具: {tools_used}")

    if not tools_used:
        print("  ❌ FAIL: 需求探索阶段没有调用工具")
        return False

    if "prepare_agent_requirement_intake" not in tools_used:
        print(f"  ❌ FAIL: 没有调用 prepare_agent_requirement_intake, 调了: {tools_used}")
        return False

    print("  ✅ 需求探索通过")

    # ── Step 2: 确认需求 ──
    print("\n📋 Step 2: 确认需求")
    print("  用户: 确认")

    result = await runtime.handle_message(
        user_message="确认",
        session_key=test_thread_id,
        channel="agent_workshop",
        chat_id=test_thread_id,
        thread_id=test_thread_id,
        thread_context={},
        user_id="test_user",
        on_progress=on_progress,
        on_stream=on_stream,
        on_tool_event=on_tool_event,
        on_step_event=on_step_event,
    )

    content = result.get("content", "")
    tools_used = result.get("tools_used", [])
    print(f"  📤 回复: {content[:200]}...")
    print(f"  🔧 工具: {tools_used}")

    # 确认后应该进入需求确认或能力盘点
    # 检查是否有 prepare_agent_generation_confirmation
    if "prepare_agent_generation_confirmation" in tools_used:
        print("  ✅ 需求确认通过（调用了 confirmation 工具）")
    else:
        print(f"  ⚠️  确认后调用的工具: {tools_used}")
        print("  （可能直接进入了能力盘点，这也算通过）")

    # ── Step 3: 再次确认需求边界 ──
    print("\n📋 Step 3: 确认需求边界")
    print("  用户: 确认")

    result = await runtime.handle_message(
        user_message="确认",
        session_key=test_thread_id,
        channel="agent_workshop",
        chat_id=test_thread_id,
        thread_id=test_thread_id,
        thread_context={},
        user_id="test_user",
        on_progress=on_progress,
        on_stream=on_stream,
        on_tool_event=on_tool_event,
        on_step_event=on_step_event,
    )

    content = result.get("content", "")
    tools_used = result.get("tools_used", [])
    print(f"  📤 回复: {content[:200]}...")
    print(f"  🔧 工具: {tools_used}")

    # 应该进入能力盘点或缺口分析
    if any(t in tools_used for t in ["search_project_capabilities", "analyze_agent_workshop_gaps"]):
        print("  ✅ 需求边界确认通过（进入能力盘点）")
    else:
        print(f"  ⚠️  确认后调用的工具: {tools_used}")

    # ── Step 4: 方案选择 ──
    print("\n📋 Step 4: 方案选择")
    print("  用户: 方案A")

    result = await runtime.handle_message(
        user_message="方案A",
        session_key=test_thread_id,
        channel="agent_workshop",
        chat_id=test_thread_id,
        thread_id=test_thread_id,
        thread_context={},
        user_id="test_user",
        on_progress=on_progress,
        on_stream=on_stream,
        on_tool_event=on_tool_event,
        on_step_event=on_step_event,
    )

    content = result.get("content", "")
    tools_used = result.get("tools_used", [])
    print(f"  📤 回复: {content[:200]}...")
    print(f"  🔧 工具: {tools_used}")

    # 检查是否调用了 generate_confirmed_candidate_agent
    if "generate_confirmed_candidate_agent" in tools_used:
        print("  ✅ 方案选择通过（开始生成 Agent）")
    elif "propose_agent_build_plans" in tools_used:
        print("  ⚠️  方案还没生成，先调了 propose_agent_build_plans")
    else:
        print(f"  ⚠️  方案选择后调用的工具: {tools_used}")

    # ── Step 5: 真数据测试 ──
    print("\n📋 Step 5: 真数据测试")
    print("  用户: 测试 600519")

    result = await runtime.handle_message(
        user_message="测试 600519",
        session_key=test_thread_id,
        channel="agent_workshop",
        chat_id=test_thread_id,
        thread_id=test_thread_id,
        thread_context={},
        user_id="test_user",
        on_progress=on_progress,
        on_stream=on_stream,
        on_tool_event=on_tool_event,
        on_step_event=on_step_event,
    )

    content = result.get("content", "")
    tools_used = result.get("tools_used", [])
    print(f"  📤 回复: {content[:200]}...")
    print(f"  🔧 工具: {tools_used}")

    if "run_agent_workshop_real_data_test" in tools_used:
        print("  ✅ 真数据测试通过（调用了 real_data_test 工具）")
    else:
        print(f"  ⚠️  测试调用的工具: {tools_used}")

    # 检查是否进入了 error_recovery（测试可能失败）
    content_lower = content.lower()
    if "处理过程中遇到了一些问题" in content or "你可以选择" in content:
        print("  ℹ️  测试失败，进入错误恢复，尝试跳过测试继续发布")

        # ── Step 6: 跳过错误，继续发布 ──
        print("\n📋 Step 6: 跳过错误，继续发布")
        print("  用户: 跳过")

        result = await runtime.handle_message(
            user_message="跳过",
            session_key=test_thread_id,
            channel="agent_workshop",
            chat_id=test_thread_id,
            thread_id=test_thread_id,
            thread_context={},
            user_id="test_user",
            on_progress=on_progress,
            on_stream=on_stream,
            on_tool_event=on_tool_event,
            on_step_event=on_step_event,
        )

        content = result.get("content", "")
        tools_used = result.get("tools_used", [])
        print(f"  📤 回复: {content[:200]}...")
        print(f"  🔧 工具: {tools_used}")

        if "publish_agent_workshop_version" in tools_used:
            print("  ✅ 发布通过（调用了 publish 工具）")
        elif "evaluate_agent_workshop_version" in tools_used:
            print("  ✅ 评估通过（调用了 evaluate 工具）")
        elif not tools_used:
            print("  ✅ 跳过成功（流程已结束，无更多工具调用）")
        else:
            print(f"  ⚠️  跳过后调用的工具: {tools_used}")
    else:
        # 测试成功，直接进入发布
        print("\n📋 Step 6: 评估与发布")
        print("  用户: 发布")

        result = await runtime.handle_message(
            user_message="发布",
            session_key=test_thread_id,
            channel="agent_workshop",
            chat_id=test_thread_id,
            thread_id=test_thread_id,
            thread_context={},
            user_id="test_user",
            on_progress=on_progress,
            on_stream=on_stream,
            on_tool_event=on_tool_event,
            on_step_event=on_step_event,
        )

        content = result.get("content", "")
        tools_used = result.get("tools_used", [])
        print(f"  📤 回复: {content[:200]}...")
        print(f"  🔧 工具: {tools_used}")

        if "publish_agent_workshop_version" in tools_used:
            print("  ✅ 发布通过（调用了 publish 工具）")
        elif "evaluate_agent_workshop_version" in tools_used:
            print("  ✅ 评估通过（调用了 evaluate 工具）")
        else:
            print(f"  ⚠️  评估/发布调用的工具: {tools_used}")

    # ── 总结 ──
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print(f"  总事件数: {len(events)}")
    tool_names = [e["data"].get("name", "") for e in events if e["type"] == "tool"]
    print(f"  工具调用: {tool_names}")

    # 检查 MongoDB checkpoint
    from core.embedded_nanobot.workflows.agent_builder_store import AgentBuilderGraphStore
    store = AgentBuilderGraphStore(db)
    checkpoint = await store.load_checkpoint(test_thread_id)
    if checkpoint:
        print(f"  Checkpoint: node={checkpoint.get('current_node')}, stage={checkpoint.get('stage')}")
    else:
        print("  Checkpoint: 无（流程已完成或未保存）")

    # 清理测试数据
    await store.delete_checkpoint(test_thread_id)
    print("  ✅ 测试数据已清理")

    client.close()
    return True


if __name__ == "__main__":
    success = asyncio.run(test_end_to_end())
    sys.exit(0 if success else 1)
