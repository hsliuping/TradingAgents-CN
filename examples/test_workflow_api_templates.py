"""
测试工作流 API 的 get_templates() 方法

验证空白工作流模板是否正确返回
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from core.api import WorkflowAPI


def test_get_templates():
    """测试获取工作流模板"""
    print("=" * 80)
    print("测试工作流 API - get_templates()")
    print("=" * 80)
    print()
    
    # 创建 API 实例
    api = WorkflowAPI()
    
    # 获取模板列表
    templates = api.get_templates()
    
    print(f"✅ 成功获取 {len(templates)} 个工作流模板")
    print()
    
    # 列出所有模板
    print("📋 模板列表:")
    for i, template in enumerate(templates, 1):
        print(f"\n{i}. {template['name']}")
        print(f"   ID: {template['id']}")
        print(f"   描述: {template['description'][:80]}...")
        print(f"   节点数: {len(template.get('nodes', []))}")
        print(f"   标签: {', '.join(template.get('tags', []))}")
    
    print()
    print("=" * 80)
    
    # 检查空白工作流是否存在
    blank_workflow = None
    for template in templates:
        if template['id'] == 'blank_workflow':
            blank_workflow = template
            break
    
    if blank_workflow:
        print("✅ 找到空白工作流模板!")
        print()
        print("📋 空白工作流详情:")
        print(f"   ID: {blank_workflow['id']}")
        print(f"   名称: {blank_workflow['name']}")
        print(f"   描述: {blank_workflow['description']}")
        print(f"   版本: {blank_workflow['version']}")
        print(f"   节点数: {len(blank_workflow.get('nodes', []))}")
        print(f"   边数: {len(blank_workflow.get('edges', []))}")
        print(f"   标签: {', '.join(blank_workflow.get('tags', []))}")
        print(f"   是否为模板: {blank_workflow.get('is_template')}")
        print()
        
        # 列出节点
        print("   节点:")
        for node in blank_workflow.get('nodes', []):
            print(f"     - {node['id']}: {node['label']} [{node['type']}]")
        
        print()
        print("   边:")
        for edge in blank_workflow.get('edges', []):
            print(f"     - {edge['source']} -> {edge['target']}")
        
        print()
        print("=" * 80)
        print("✅ 测试通过！空白工作流模板已正确添加到 API 返回列表中")
        print("=" * 80)
    else:
        print("❌ 错误：未找到空白工作流模板!")
        print("   请检查 core/api/workflow_api.py 中的 get_templates() 方法")
        print("=" * 80)
        return False
    
    return True


if __name__ == "__main__":
    success = test_get_templates()
    sys.exit(0 if success else 1)

