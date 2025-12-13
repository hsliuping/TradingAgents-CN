"""
测试工作流模板API
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.api.workflow_api import WorkflowAPI


async def test_workflow_templates():
    """测试工作流模板"""
    print("🚀 测试工作流模板...")
    
    api = WorkflowAPI()
    
    # 获取所有模板
    templates = api.get_templates()
    
    print(f"📋 找到 {len(templates)} 个工作流模板:")
    for template in templates:
        print(f"   - {template['id']}: {template['name']}")
        print(f"     描述: {template['description']}")
        print(f"     节点数: {len(template['nodes'])}")
        print()
    
    # 检查持仓分析工作流是否存在
    position_analysis = None
    for template in templates:
        if template['id'] == 'position_analysis':
            position_analysis = template
            break
    
    if position_analysis:
        print("✅ 持仓分析工作流模板已正确加载!")
        print(f"   节点列表:")
        for node in position_analysis['nodes']:
            print(f"     - {node['id']}: {node['label']} ({node['type']})")
    else:
        print("❌ 持仓分析工作流模板未找到!")


if __name__ == "__main__":
    asyncio.run(test_workflow_templates())
