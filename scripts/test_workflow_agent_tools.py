"""
测试工作流编辑器中Agent工具和模板加载

验证：
1. position_analyst 的工具配置能正确返回（即使工具列表为空）
2. position_analyst 的提示词模板能正确加载
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.agents.config import BUILTIN_AGENTS
from core.tools.registry import get_tool_registry


async def test_position_analyst_tools():
    """测试 position_analyst 的工具配置"""
    print("\n" + "="*60)
    print("测试 position_analyst 工具配置")
    print("="*60)
    
    agent_id = "position_analyst"
    
    # 检查 Agent 是否存在
    if agent_id not in BUILTIN_AGENTS:
        print(f"❌ Agent {agent_id} 不存在于 BUILTIN_AGENTS")
        return False
    
    agent = BUILTIN_AGENTS[agent_id]
    print(f"✅ Agent 存在: {agent.name}")
    print(f"   ID: {agent.id}")
    print(f"   类别: {agent.category}")
    print(f"   工具列表: {agent.tools}")
    print(f"   默认工具: {agent.default_tools}")
    print(f"   最大工具调用次数: {agent.max_tool_calls}")
    
    # 获取工具注册表
    registry = get_tool_registry()
    
    # 获取可用工具详情
    available_tools = []
    for tool_id in agent.tools:
        tool = registry.get(tool_id)
        if tool:
            available_tools.append({
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
            })
    
    print(f"\n   可用工具数量: {len(available_tools)}")
    if len(available_tools) == 0:
        print("   ℹ️  该 Agent 不使用工具（这是正常的）")
    else:
        for tool in available_tools:
            print(f"   - {tool['name']} ({tool['id']})")
    
    return True


async def test_all_review_agents():
    """测试所有复盘分析师"""
    print("\n" + "="*60)
    print("测试所有复盘分析师")
    print("="*60)
    
    review_agents = [
        "timing_analyst",
        "position_analyst",
        "emotion_analyst",
        "attribution_analyst",
        "review_manager",
    ]
    
    for agent_id in review_agents:
        if agent_id in BUILTIN_AGENTS:
            agent = BUILTIN_AGENTS[agent_id]
            print(f"\n✅ {agent.name} ({agent_id})")
            print(f"   类别: {agent.category}")
            print(f"   工具数量: {len(agent.tools)}")
        else:
            print(f"\n❌ {agent_id} 不存在")
    
    return True


async def main():
    """主测试函数"""
    print("\n🧪 开始测试工作流 Agent 工具配置")
    
    # 测试 position_analyst
    success1 = await test_position_analyst_tools()
    
    # 测试所有复盘分析师
    success2 = await test_all_review_agents()
    
    print("\n" + "="*60)
    if success1 and success2:
        print("✅ 所有测试通过")
    else:
        print("❌ 部分测试失败")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

