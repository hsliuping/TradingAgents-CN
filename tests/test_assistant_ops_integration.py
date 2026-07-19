"""
Step 1.3.8 集成测试 - 验证 assistant_ops 工具模块
"""
import asyncio
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_1_context_module():
    """测试 contextvars 用户上下文传递"""
    print("=== 1. 测试 context 模块 ===")
    from core.tools.context import set_current_user_id, get_current_user_id, require_current_user_id

    set_current_user_id("test_user_123")
    assert get_current_user_id() == "test_user_123", "context 未正确设置"
    assert require_current_user_id() == "test_user_123", "require 未返回正确值"

    # 测试未设置时 require 抛异常
    set_current_user_id(None)
    try:
        require_current_user_id()
        assert False, "应该抛出 RuntimeError"
    except RuntimeError:
        pass

    print("  ✅ context 模块正常")


def test_2_module_imports():
    """测试 4 个子模块全部可导入"""
    print("\n=== 2. 测试 assistant_ops 工具导入 ===")
    from core.tools.implementations.assistant_ops import analysis_trigger  # noqa
    from core.tools.implementations.assistant_ops import report_query  # noqa
    from core.tools.implementations.assistant_ops import schedule_manager  # noqa
    from core.tools.implementations.assistant_ops import watchlist_manager  # noqa
    print("  ✅ 4 个子模块全部导入成功")


def test_3_tool_registration():
    """测试 ToolRegistry 中注册了 12 个 assistant_ops 工具"""
    print("\n=== 3. 测试 ToolRegistry 注册情况 ===")
    from core.tools import get_tool_registry

    registry = get_tool_registry()
    all_tools = registry.get_all_tools()
    ops_tools = [t for t in all_tools if t.category == "assistant_ops"]
    print(f"  注册的 assistant_ops 工具数: {len(ops_tools)}")
    for t in ops_tools:
        desc = t.description[:60] if t.description else "(无描述)"
        print(f"    - {t.id} ({t.name}): {desc}...")

    expected_ids = {
        "trigger_stock_analysis",
        "trigger_batch_analysis",
        "get_analysis_status",
        "search_reports",
        "get_report_detail",
        "get_latest_report",
        "list_scheduled_configs",
        "create_scheduled_analysis",
        "toggle_scheduled_config",
        "list_watchlist_groups",
        "add_stock_to_watchlist",
        "remove_stock_from_watchlist",
    }
    actual_ids = {t.id for t in ops_tools}
    missing = expected_ids - actual_ids
    extra = actual_ids - expected_ids

    if missing:
        print(f"  ❌ 缺少工具: {missing}")
    if extra:
        print(f"  ⚠️ 额外工具: {extra}")

    assert len(missing) == 0, f"缺少工具: {missing}"
    print("  ✅ 12 个 assistant_ops 工具全部注册")


def test_4_fc_conversion():
    """测试 OpenAI function calling 格式转换"""
    print("\n=== 4. 测试 FC 转换 (OpenAI function calling 格式) ===")
    from core.tools import get_tool_registry, tool_metadata_list_to_openai

    registry = get_tool_registry()
    all_tools = registry.get_all_tools()
    ops_tools = [t for t in all_tools if t.category == "assistant_ops"]

    fc_list = tool_metadata_list_to_openai(ops_tools)
    print(f"  转换后 function 数: {len(fc_list)}")
    for fc in fc_list:
        fn = fc.get("function", {})
        params = list(fn.get("parameters", {}).get("properties", {}).keys())
        print(f"    - {fn.get('name')}: params={params}")

    assert len(fc_list) == 12, f"期望 12 个 FC，实际 {len(fc_list)}"
    print("  ✅ FC 转换正常")


def test_5_system_prompt():
    """测试系统提示词包含操作员角色"""
    print("\n=== 5. 测试系统提示词 ===")
    # 直接导入内部函数
    from app.services.intelligent_assistant_service import _get_system_prompt

    prompt = _get_system_prompt()
    assert "操作员" in prompt or "操作能力" in prompt or "触发分析" in prompt, "提示词缺少操作员角色"
    assert "trigger_stock_analysis" in prompt, "提示词缺少工具名引用"
    assert "股票关注列表" in prompt, "提示词缺少股票关注列表管理说明"
    print(f"  提示词长度: {len(prompt)} 字符")
    print("  ✅ 系统提示词包含操作员角色和工具说明")


def test_6_tool_callable():
    """测试工具函数可以被调用（dry-run 级别）"""
    print("\n=== 6. 测试工具函数可调用性 ===")
    from core.tools import get_tool_registry

    registry = get_tool_registry()
    all_tools = registry.get_all_tools()
    ops_tools = [t for t in all_tools if t.category == "assistant_ops"]

    for t in ops_tools:
        func = registry.get_function(t.id)
        assert func is not None, f"工具 {t.id} 无法获取函数"
        assert callable(func), f"工具 {t.id} 不可调用"
        print(f"    ✅ {t.id} ({t.name}) — callable")

    print("  ✅ 所有工具函数均可获取且可调用")


if __name__ == "__main__":
    tests = [
        test_1_context_module,
        test_2_module_imports,
        test_3_tool_registration,
        test_4_fc_conversion,
        test_5_system_prompt,
        test_6_tool_callable,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"结果: {passed} 通过, {failed} 失败")
    sys.exit(1 if failed > 0 else 0)

