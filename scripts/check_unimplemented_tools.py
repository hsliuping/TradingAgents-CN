"""
检查 core/tools/config.py 中定义但未实际实现的工具

目的：
1. 找出所有在 BUILTIN_TOOLS 中定义但没有实现的工具
2. 生成清理建议
"""

import logging
from core.tools.config import BUILTIN_TOOLS
from core.tools.registry import ToolRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_unimplemented_tools():
    """检查未实现的工具"""
    
    # 获取工具注册表
    registry = ToolRegistry()
    
    # 获取所有已注册的工具
    registered_tools = set(registry._tools.keys())
    
    # 获取 config.py 中定义的工具
    config_tools = set(BUILTIN_TOOLS.keys())
    
    # 找出未实现的工具
    unimplemented = config_tools - registered_tools
    
    # 找出已实现但未在 config.py 中定义的工具
    not_in_config = registered_tools - config_tools
    
    logger.info("=" * 80)
    logger.info("工具实现状态检查")
    logger.info("=" * 80)
    
    logger.info(f"\n📊 统计:")
    logger.info(f"  - config.py 中定义的工具: {len(config_tools)}")
    logger.info(f"  - 实际注册的工具: {len(registered_tools)}")
    logger.info(f"  - 未实现的工具: {len(unimplemented)}")
    logger.info(f"  - 未在 config.py 中定义的工具: {len(not_in_config)}")
    
    if unimplemented:
        logger.info("\n" + "=" * 80)
        logger.info("❌ 未实现的工具（在 config.py 中定义但未注册）:")
        logger.info("=" * 80)
        for tool_id in sorted(unimplemented):
            metadata = BUILTIN_TOOLS[tool_id]
            logger.info(f"\n  - {tool_id}")
            logger.info(f"    名称: {metadata.name}")
            logger.info(f"    描述: {metadata.description}")
            logger.info(f"    分类: {metadata.category}")
            logger.info(f"    数据源: {metadata.data_source}")
    
    if not_in_config:
        logger.info("\n" + "=" * 80)
        logger.info("⚠️ 已实现但未在 config.py 中定义的工具:")
        logger.info("=" * 80)
        for tool_id in sorted(not_in_config):
            logger.info(f"  - {tool_id}")
    
    # 生成清理建议
    logger.info("\n" + "=" * 80)
    logger.info("🔧 清理建议:")
    logger.info("=" * 80)
    
    if unimplemented:
        logger.info("\n1. 从 core/tools/config.py 的 BUILTIN_TOOLS 中删除以下工具:")
        for tool_id in sorted(unimplemented):
            logger.info(f'   - "{tool_id}"')
    
    if not_in_config:
        logger.info("\n2. 考虑将以下已实现的工具添加到 config.py:")
        for tool_id in sorted(not_in_config):
            logger.info(f'   - "{tool_id}"')
    
    # 生成删除代码
    if unimplemented:
        logger.info("\n" + "=" * 80)
        logger.info("📝 删除代码（复制到 config.py）:")
        logger.info("=" * 80)
        logger.info("\n# 删除以下未实现的工具:")
        for tool_id in sorted(unimplemented):
            logger.info(f'# del BUILTIN_TOOLS["{tool_id}"]')
    
    return {
        "config_tools": config_tools,
        "registered_tools": registered_tools,
        "unimplemented": unimplemented,
        "not_in_config": not_in_config
    }


if __name__ == "__main__":
    result = check_unimplemented_tools()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ 检查完成！")
    logger.info("=" * 80)

