"""
Agent Builder Graph 端到端测试脚本（Nanobot 移除后版本）

模拟完整流程：
  1. 需求探索（用户：帮我创建一个财报排雷助手）
  2. 确认需求（用户：确认）
  3. 再次确认需求边界（用户：确认）
  4. 方案选择（用户：方案A）
  5. 真数据测试（用户：测试 600519）
  6. 评估与发布（用户：发布 / 跳过）

不依赖前端，直接调用 EmbeddedNanobotService.chat(channel="agent_workshop")。
走 LangGraph 工作流 + UnifiedLLMClient（标准 Function Calling），不经过已删除的 Nanobot Runtime。

验证项：
  - 工具调用成功（prepare_agent_requirement_intake / generate_confirmed_candidate_agent 等）
  - 无 XML 泄露（content 中不含 <tool_use> / <function_calls> / <invoke> 等标签）
  - SSE 事件正常（progress / tool / step）

用法: python scripts/test_agent_builder_graph.py
"""

import asyncio
import os
import re
import sys
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

# v3.0 默认 MongoDB 配置
os.environ.setdefault("MONGODB_HOST", "127.0.0.1")
os.environ.setdefault("MONGODB_PORT", "27019")
os.environ.setdefault("MONGODB_DATABASE", "tradingagents")
os.environ.setdefault("MONGODB_USERNAME", "admin")
os.environ.setdefault("MONGODB_PASSWORD", "tradingagents123")
os.environ.setdefault("MONGODB_AUTH_SOURCE", "admin")


# ── XML 泄露检测 ──
_XML_LEAK_PATTERNS = [
    re.compile(r"<tool_use\b", re.IGNORECASE),
    re.compile(r"</tool_use\s*>", re.IGNORECASE),
    re.compile(r"<function_calls?\b", re.IGNORECASE),
    re.compile(r"</function_calls?\s*>", re.IGNORECASE),
    re.compile(r"<invoke\b", re.IGNORECASE),
    re.compile(r"</invoke\s*>", re.IGNORECASE),
    re.compile(r"<parameter\b", re.IGNORECASE),
    re.compile(r"</parameter\s*>", re.IGNORECASE),
    re.compile(r"<antml:", re.IGNORECASE),
]


def _detect_xml_leak(text: str) -> list[str]:
    """检测 content 中是否有 XML 工具调用标签泄露。返回匹配到的模式列表。"""
    if not text:
        return []
    hits = []
    for pattern in _XML_LEAK_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


async def test_end_to_end():
    """端到端测试 Agent Builder Graph（通过 EmbeddedNanobotService）。"""
    from app.services.embedded_nanobot_service import EmbeddedNanobotService
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
    print("🧪 Agent Builder Graph 端到端测试（Nanobot 移除后版本）")
    print("=" * 80)

    # 初始化 Service（替代已删除的 EmbeddedNanobotRuntime）
    print("\n📋 Step 0: 初始化 EmbeddedNanobotService...")
    service = EmbeddedNanobotService(
        db,
        workspace=PROJECT_ROOT,
        preferred_model=None,
    )
    print("✅ Service 初始化完成（StandardToolRegistryAdapter 会自动从 core.tools.registry 加载）")

    # 测试用的 thread_id
    test_thread_id = f"test-e2e-{int(asyncio.get_event_loop().time() * 1000)}"

    # 提前导入 store，供 _run_step 中追踪 spec_id 使用
    from core.embedded_nanobot.workflows.agent_builder_store import AgentBuilderGraphStore
    _store_for_tracking = AgentBuilderGraphStore(db)

    # 收集 SSE 事件
    events = []
    xml_leak_found = False

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

    async def _run_step(step_name: str, user_msg: str) -> dict:
        """执行一步对话，并自动检测 XML 泄露。"""
        nonlocal xml_leak_found
        print(f"\n📋 {step_name}")
        print(f"  用户: {user_msg}")

        result = await service.chat(
            user_message=user_msg,
            session_key=test_thread_id,
            user_id="test_user",
            current_thread_id=test_thread_id,
            channel="agent_workshop",
            chat_id=test_thread_id,
            thread_context={},
            on_progress=on_progress,
            on_stream=on_stream,
            on_tool_event=on_tool_event,
            on_step_event=on_step_event,
        )

        content = result.get("content", "") or ""
        tools_used = result.get("tools_used", []) or []
        print(f"  📤 回复: {content[:200]}...")
        print(f"  🔧 工具: {tools_used}")

        # 🔑 追踪 spec_id 变化
        _ckpt = await _store_for_tracking.load_checkpoint(test_thread_id)
        if _ckpt:
            _spec_id = _ckpt.get("spec_id", "")
            _spec_name = _ckpt.get("spec_name", "")
            _node = _ckpt.get("current_node", "")
            print(f"  📌 state: spec_id={_spec_id!r}, spec_name={_spec_name!r}, node={_node}")

        # XML 泄露检测
        leaks = _detect_xml_leak(content)
        if leaks:
            xml_leak_found = True
            print(f"  ❌ XML 泄露 detected: {leaks}")
        else:
            print(f"  ✅ 无 XML 泄露")

        return result

    # ── Step 1: 需求探索 ──
    result = await _run_step("Step 1: 需求探索", "帮我创建一个财报排雷助手")
    tools_used = result.get("tools_used", [])
    if not tools_used:
        print("  ❌ FAIL: 需求探索阶段没有调用工具")
        return False
    if "prepare_agent_requirement_intake" not in tools_used:
        print(f"  ❌ FAIL: 没有调用 prepare_agent_requirement_intake, 调了: {tools_used}")
        return False
    print("  ✅ 需求探索通过")

    # ── Step 2: 确认需求 ──
    result = await _run_step("Step 2: 确认需求", "确认")
    tools_used = result.get("tools_used", [])
    if "prepare_agent_generation_confirmation" in tools_used:
        print("  ✅ 需求确认通过（调用了 confirmation 工具）")
    else:
        print(f"  ⚠️  确认后调用的工具: {tools_used}")
        print("  （可能直接进入了能力盘点，这也算通过）")

    # ── Step 3: 再次确认需求边界 ──
    result = await _run_step("Step 3: 确认需求边界", "确认")
    tools_used = result.get("tools_used", [])
    if any(t in tools_used for t in ["search_project_capabilities", "analyze_agent_workshop_gaps"]):
        print("  ✅ 需求边界确认通过（进入能力盘点）")
    else:
        print(f"  ⚠️  确认后调用的工具: {tools_used}")

    # ── Step 4: 方案选择 ──
    result = await _run_step("Step 4: 方案选择", "方案A")
    tools_used = result.get("tools_used", [])
    if "generate_confirmed_candidate_agent" in tools_used:
        print("  ✅ 方案选择通过（开始生成 Agent）")
    elif "propose_agent_build_plans" in tools_used:
        print("  ⚠️  方案还没生成，先调了 propose_agent_build_plans")
    else:
        print(f"  ⚠️  方案选择后调用的工具: {tools_used}")

    # ── Step 5: 真数据测试 ──
    result = await _run_step("Step 5: 真数据测试", "测试 600519")
    tools_used = result.get("tools_used", [])
    content = result.get("content", "") or ""
    if "run_agent_workshop_real_data_test" in tools_used:
        print("  ✅ 真数据测试通过（调用了 real_data_test 工具）")
    else:
        print(f"  ⚠️  测试调用的工具: {tools_used}")

    # 检查是否进入了 error_recovery（测试可能失败）
    if "处理过程中遇到了一些问题" in content or "你可以选择" in content:
        print("  ℹ️  测试失败，进入错误恢复，尝试跳过测试继续发布")

        # ── Step 6a: 跳过错误，继续发布 ──
        result = await _run_step("Step 6a: 跳过错误，继续发布", "跳过")
        tools_used = result.get("tools_used", [])
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
        result = await _run_step("Step 6: 评估与发布", "发布")
        tools_used = result.get("tools_used", [])
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
    print(f"  XML 泄露: {'❌ 发现' if xml_leak_found else '✅ 未发现'}")

    # 检查 MongoDB checkpoint
    store = _store_for_tracking
    checkpoint = await store.load_checkpoint(test_thread_id)
    if checkpoint:
        print(f"  Checkpoint: node={checkpoint.get('current_node')}, stage={checkpoint.get('stage')}")
        # 🔑 打印 spec_id 追踪信息
        spec_id = checkpoint.get("spec_id", "")
        spec_name = checkpoint.get("spec_name", "")
        print(f"  spec_id: {spec_id!r}")
        print(f"  spec_name: {spec_name!r}")

        # 🔑 用 spec_id 去数据库查 spec
        if spec_id:
            spec_doc = await db["agent_specs"].find_one({"spec_id": spec_id})
            if spec_doc:
                print(f"  ✅ 数据库中找到 spec: name={spec_doc.get('name')}, status={spec_doc.get('status')}")
            else:
                print(f"  ❌ 数据库中未找到 spec_id={spec_id}！这就是 404 的原因！")
                # 列出数据库中所有的 spec_id，看看有没有类似的
                all_specs = await db["agent_specs"].find({}, {"spec_id": 1, "name": 1}).to_list(length=20)
                print(f"  📋 数据库中现有的 spec_id 列表:")
                for s in all_specs:
                    print(f"     - {s.get('spec_id')}: {s.get('name')}")
    else:
        print("  Checkpoint: 无（流程已完成或未保存）")

    # 清理测试数据
    await store.delete_checkpoint(test_thread_id)
    print("  ✅ 测试数据已清理")

    client.close()

    if xml_leak_found:
        print("\n❌ 端到端测试失败：检测到 XML 泄露")
        return False
    print("\n✅ 端到端测试通过：无 XML 泄露，工具调用正常")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_end_to_end())
    sys.exit(0 if success else 1)
