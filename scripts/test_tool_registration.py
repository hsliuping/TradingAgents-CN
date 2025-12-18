"""
测试工具注册情况

检查 index_market_tools 和 sector_market_tools 是否被正确注册到 ToolRegistry
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def test_tool_registration():
    """测试工具注册"""
    logger.info("=" * 80)
    logger.info("开始测试工具注册")
    logger.info("=" * 80)
    
    # 导入 ToolRegistry
    from core.tools.registry import ToolRegistry
    
    registry = ToolRegistry()
    
    # 需要检查的工具 ID
    required_tools = [
        "get_index_data",
        "get_market_breadth",
        "get_market_environment",
        "identify_market_cycle",
        "get_sector_data",
        "get_fund_flow_data",
        "get_peer_comparison",
        "analyze_sector",
    ]
    
    logger.info(f"\n检查 {len(required_tools)} 个必需工具...")
    
    # 检查每个工具
    results = {}
    for tool_id in required_tools:
        tool = registry.get_langchain_tool(tool_id)
        if tool:
            logger.info(f"✅ {tool_id:30s} - 已注册")
            results[tool_id] = True
        else:
            logger.error(f"❌ {tool_id:30s} - 未注册")
            results[tool_id] = False
    
    # 统计结果
    registered = sum(1 for v in results.values() if v)
    total = len(results)
    
    logger.info("\n" + "=" * 80)
    logger.info(f"测试结果: {registered}/{total} 个工具已注册")
    logger.info("=" * 80)
    
    if registered == total:
        logger.info("✅ 所有工具都已正确注册！")
        return True
    else:
        logger.error(f"❌ 有 {total - registered} 个工具未注册")
        return False


def test_agent_tool_loading():
    """测试 Agent 加载工具"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Agent 工具加载")
    logger.info("=" * 80)
    
    from core.agents.adapters import create_agent
    from core.llm.factory import create_llm
    
    # 创建一个测试 LLM
    llm = create_llm(provider="openai", model="gpt-4o-mini")
    
    # 测试 IndexAnalystV2
    logger.info("\n测试 IndexAnalystV2...")
    try:
        index_agent = create_agent("index_analyst_v2", llm)
        logger.info(f"✅ IndexAnalystV2 创建成功")
        logger.info(f"   工具数量: {len(index_agent._langchain_tools)}")
        logger.info(f"   工具列表: {[t.name for t in index_agent._langchain_tools]}")
    except Exception as e:
        logger.error(f"❌ IndexAnalystV2 创建失败: {e}")
    
    # 测试 SectorAnalystV2
    logger.info("\n测试 SectorAnalystV2...")
    try:
        sector_agent = create_agent("sector_analyst_v2", llm)
        logger.info(f"✅ SectorAnalystV2 创建成功")
        logger.info(f"   工具数量: {len(sector_agent._langchain_tools)}")
        logger.info(f"   工具列表: {[t.name for t in sector_agent._langchain_tools]}")
    except Exception as e:
        logger.error(f"❌ SectorAnalystV2 创建失败: {e}")


if __name__ == "__main__":
    try:
        # 测试工具注册
        success = test_tool_registration()
        
        # 测试 Agent 工具加载
        test_agent_tool_loading()
        
        # 退出码
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)

