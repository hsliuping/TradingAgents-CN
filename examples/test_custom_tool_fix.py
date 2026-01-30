"""
测试自定义工具异步修复

验证工具调用时返回的是实际结果而不是协程对象
"""

import asyncio
from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig, register_custom_tool
from core.tools.config import ToolParameter
from core.tools.registry import get_tool_registry


async def test_tool_registration():
    """测试工具注册和调用"""
    
    print("=" * 80)
    print("测试自定义工具异步修复")
    print("=" * 80)
    
    # 1. 创建一个简单的测试工具（使用 httpbin.org 作为测试 API）
    tool_def = CustomToolDefinition(
        id="test_custom_tool",
        name="测试工具",
        description="测试自定义工具是否返回实际结果",
        category="test",
        parameters=[
            ToolParameter(
                name="test_param",
                type="string",
                description="测试参数",
                required=True
            )
        ],
        implementation=HttpToolConfig(
            url="https://httpbin.org/get",
            method="GET",
            headers={}
        ),
        is_online=True,
        timeout=10
    )
    
    # 2. 注册工具
    print("\n1. 注册工具...")
    await register_custom_tool(tool_def)
    print("✅ 工具注册成功")
    
    # 3. 获取工具
    print("\n2. 获取工具...")
    registry = get_tool_registry()
    tool_func = registry.get_function("test_custom_tool")
    
    if tool_func is None:
        print("❌ 工具函数未找到")
        return
    
    print(f"✅ 工具函数类型: {type(tool_func)}")
    print(f"   函数名: {tool_func.__name__}")
    
    # 4. 测试调用（同步调用）
    print("\n3. 测试工具调用...")
    try:
        # 直接调用函数（模拟 LangChain 工具调用）
        result = tool_func(test_param="test_value")
        
        print(f"✅ 工具调用成功")
        print(f"   返回类型: {type(result)}")
        print(f"   是否为协程对象: {asyncio.iscoroutine(result)}")
        
        if asyncio.iscoroutine(result):
            print("❌ 错误：返回的是协程对象！")
            print("   这表示修复未生效")
        else:
            print("✅ 正确：返回的是实际结果")
            print(f"   结果预览: {str(result)[:200]}...")
            
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试 LangChain 工具创建
    print("\n4. 测试 LangChain 工具创建...")
    try:
        lc_tool = registry.get_langchain_tool("test_custom_tool")
        if lc_tool is None:
            print("❌ LangChain 工具创建失败")
        else:
            print(f"✅ LangChain 工具创建成功")
            print(f"   工具类型: {type(lc_tool)}")
            print(f"   工具名称: {lc_tool.name}")
            
            # 测试 invoke 方法
            print("\n5. 测试 LangChain 工具 invoke...")
            invoke_result = lc_tool.invoke({"test_param": "test_value"})
            
            print(f"✅ LangChain invoke 成功")
            print(f"   返回类型: {type(invoke_result)}")
            print(f"   是否为协程对象: {asyncio.iscoroutine(invoke_result)}")
            
            if asyncio.iscoroutine(invoke_result):
                print("❌ 错误：返回的是协程对象！")
            else:
                print("✅ 正确：返回的是实际结果")
                print(f"   结果预览: {str(invoke_result)[:200]}...")
                
    except Exception as e:
        print(f"❌ LangChain 工具测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tool_registration())
