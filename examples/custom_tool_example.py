"""
自定义工具使用示例

演示如何创建、注册和使用自定义工具
"""

import asyncio
from typing import Dict, Any
from langchain_openai import ChatOpenAI

from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig, register_custom_tool
from core.tools.config import ToolParameter
from core.agents import create_agent


async def example_create_and_register_tool():
    """示例：创建并注册自定义工具"""
    
    # 1. 定义工具参数
    parameters = [
        ToolParameter(
            name="ticker",
            type="string",
            description="股票代码，如 000001（A股）、00700（港股）、AAPL（美股）",
            required=True
        ),
        ToolParameter(
            name="date",
            type="string",
            description="查询日期，格式：YYYY-MM-DD，默认为今天",
            required=False
        )
    ]
    
    # 2. 定义 HTTP 配置
    http_config = HttpToolConfig(
        url="https://api.example.com/v1/stock/{ticker}",
        method="GET",
        headers={
            "Authorization": "Bearer YOUR_API_KEY",
            "Content-Type": "application/json"
        }
    )
    
    # 3. 创建工具定义
    tool_definition = CustomToolDefinition(
        id="get_stock_info_custom",
        name="获取股票信息",
        description="通过自定义API获取股票的基本信息，包括价格、成交量、市值等",
        category="market",
        parameters=parameters,
        implementation=http_config,
        is_online=True,
        timeout=30
    )
    
    # 4. 注册工具
    # 🔥 注意：register_custom_tool 会自动创建同步包装函数
    # 即使工具内部使用异步 HTTP 请求，也会被包装成同步函数供 LangChain 使用
    await register_custom_tool(tool_definition)
    print("✅ 工具注册成功: get_stock_info_custom")
    print("   - 工具会自动处理异步到同步的转换")
    print("   - LangChain 调用时会返回实际结果，而不是协程对象")


async def example_use_tool_in_agent():
    """示例：在 Agent 中使用自定义工具"""
    
    # 1. 创建 LLM 实例
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7
    )
    
    # 2. 创建 Agent（工具会自动从数据库配置加载）
    # 注意：需要先在数据库中配置 tool_agent_bindings
    agent = create_agent(
        agent_id="market_analyst",
        llm=llm,
        tool_ids=["get_stock_info_custom"]  # 指定要使用的工具
    )
    
    # 3. 执行分析任务
    state = {
        "ticker": "000001",
        "analysis_date": "2025-01-30",
        "market_type": "A股"
    }
    
    # 4. Agent 会自动：
    #    - 调用 LLM（绑定工具）
    #    - LLM 决定调用 get_stock_info_custom
    #    - 执行工具调用
    #    - 将工具结果添加到消息历史
    #    - 再次调用 LLM 生成报告
    result = agent.execute(state)
    
    print("✅ 分析完成")
    print(f"报告: {result.get('market_report', '')[:200]}...")


def example_prompt_with_tool():
    """示例：提示词中如何提及工具"""
    
    # ✅ 好的提示词写法
    good_system_prompt = """你是一位专业的市场分析师。

你的任务是分析股票的市场表现。

你可以使用以下工具获取数据：
- get_stock_info_custom: 获取股票基本信息（价格、成交量等）
- get_market_data: 获取市场整体数据

请根据用户的需求，调用合适的工具获取数据，然后基于真实数据进行分析。"""

    good_user_prompt = """请分析股票 000001 在 2025-01-30 的市场表现。

请先调用工具获取数据，然后基于数据生成详细的分析报告。"""
    
    # ❌ 不好的提示词写法（过于详细，LLM 会自动理解）
    bad_system_prompt = """你必须使用 get_stock_info_custom 工具。
调用格式：get_stock_info_custom(ticker="000001", date="2025-01-30")
工具返回的数据格式是 JSON，包含 price、volume 等字段..."""
    
    print("✅ 好的提示词：简洁明了，让 LLM 自主决定")
    print("❌ 不好的提示词：过于详细，限制了 LLM 的灵活性")


def example_tool_return_format():
    """示例：工具返回数据的格式"""
    
    # ✅ 推荐：返回结构化的 JSON 数据
    good_return = {
        "ticker": "000001",
        "name": "平安银行",
        "price": 10.50,
        "volume": 1000000,
        "market_cap": 20000000000,
        "currency": "CNY",
        "date": "2025-01-30"
    }
    
    # ✅ 也可以返回字符串（会被 LLM 解析）
    good_string_return = """股票代码: 000001
股票名称: 平安银行
当前价格: 10.50 元
成交量: 1,000,000 股
市值: 200 亿元
日期: 2025-01-30"""
    
    # ❌ 不推荐：返回过于复杂或难以理解的数据
    bad_return = {
        "data": {
            "nested": {
                "deep": {
                    "value": "很难理解的结构"
                }
            }
        }
    }
    
    print("✅ 推荐：返回结构清晰、易于理解的 JSON 数据")
    print("✅ 也可以：返回格式化的字符串")
    print("❌ 不推荐：返回过于复杂的嵌套结构")


def example_message_history_structure():
    """示例：工具调用后的消息历史结构"""
    
    # 这是 Agent.invoke_with_tools() 内部的消息历史结构
    messages = [
        # 1. 系统提示词
        {
            "type": "system",
            "content": "你是市场分析师，可以使用工具获取数据..."
        },
        
        # 2. 用户请求
        {
            "type": "human",
            "content": "请分析股票 000001 的价格"
        },
        
        # 3. LLM 决定调用工具
        {
            "type": "ai",
            "content": "",
            "tool_calls": [
                {
                    "name": "get_stock_info_custom",
                    "args": {"ticker": "000001"},
                    "id": "call_abc123"
                }
            ]
        },
        
        # 4. 工具执行结果（自动添加）
        {
            "type": "tool",
            "content": '{"ticker": "000001", "price": 10.50, "volume": 1000000}',
            "tool_call_id": "call_abc123"
        },
        
        # 5. 分析提示词（自动添加）
        {
            "type": "human",
            "content": "工具调用已完成，请基于上述数据生成分析报告..."
        },
        
        # 6. LLM 生成最终报告
        {
            "type": "ai",
            "content": "根据工具返回的数据，股票 000001 的当前价格为 10.50 元..."
        }
    ]
    
    print("消息历史结构：")
    for i, msg in enumerate(messages, 1):
        print(f"{i}. {msg['type']}: {str(msg)[:100]}...")


async def main():
    """主函数：运行所有示例"""
    
    print("=" * 80)
    print("自定义工具使用示例")
    print("=" * 80)
    
    print("\n1. 创建并注册工具")
    print("-" * 80)
    await example_create_and_register_tool()
    
    print("\n2. 提示词写法示例")
    print("-" * 80)
    example_prompt_with_tool()
    
    print("\n3. 工具返回数据格式示例")
    print("-" * 80)
    example_tool_return_format()
    
    print("\n4. 消息历史结构示例")
    print("-" * 80)
    example_message_history_structure()
    
    print("\n5. 在 Agent 中使用工具")
    print("-" * 80)
    print("（需要先配置数据库绑定关系）")
    # await example_use_tool_in_agent()
    
    print("\n" + "=" * 80)
    print("示例完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
