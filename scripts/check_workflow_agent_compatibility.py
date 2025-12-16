"""
检查数据库中的工作流模板与v2.0 Agent的兼容性

检查内容：
1. 数据库中的工作流模板列表
2. 每个工作流使用的agent_id
3. 这些agent_id是否已注册为v2.0 Agent
4. 给出兼容性报告和建议
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from app.core.config import settings
from core.agents.registry import AgentRegistry
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_workflow_compatibility():
    """检查工作流与Agent的兼容性"""
    
    print("=" * 80)
    print("工作流模板与v2.0 Agent兼容性检查")
    print("=" * 80)
    
    # 1. 连接数据库
    print("\n1. 连接数据库...")
    try:
        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
        print(f"   [OK] 已连接到数据库: {settings.MONGO_DB}")
    except Exception as e:
        print(f"   [ERROR] 连接数据库失败: {e}")
        return
    
    # 2. 获取所有工作流模板
    print("\n2. 获取工作流模板...")
    try:
        workflows = list(db.workflows.find())
        print(f"   [OK] 找到 {len(workflows)} 个工作流")
    except Exception as e:
        print(f"   [ERROR] 获取工作流失败: {e}")
        return
    
    # 3. 获取已注册的v2.0 Agent
    print("\n3. 获取已注册的v2.0 Agent...")
    registry = AgentRegistry()
    registered_agents = registry.list_all()
    registered_agent_ids = {agent.id for agent in registered_agents}
    print(f"   [OK] 已注册 {len(registered_agent_ids)} 个v2.0 Agent")
    print(f"   Agent列表: {sorted(registered_agent_ids)}")
    
    # 4. 检查每个工作流
    print("\n4. 检查工作流兼容性...")
    print("=" * 80)
    
    compatibility_report = []
    
    for workflow in workflows:
        workflow_id = workflow.get('id', 'unknown')
        workflow_name = workflow.get('name', 'Unknown')
        nodes = workflow.get('nodes', [])
        
        print(f"\n工作流: {workflow_id}")
        print(f"名称: {workflow_name}")
        print(f"节点数: {len(nodes)}")
        
        # 提取所有agent节点
        agent_nodes = [n for n in nodes if n.get('type') in ['analyst', 'researcher', 'manager', 'trader']]
        agent_ids = [n.get('agent_id') for n in agent_nodes if n.get('agent_id')]
        
        print(f"Agent节点数: {len(agent_nodes)}")
        print(f"使用的Agent: {agent_ids}")
        
        # 检查兼容性
        compatible_agents = []
        incompatible_agents = []
        
        for agent_id in agent_ids:
            if agent_id in registered_agent_ids:
                compatible_agents.append(agent_id)
            else:
                incompatible_agents.append(agent_id)
        
        # 生成报告
        if incompatible_agents:
            status = "[WARNING] 部分不兼容"
            print(f"   {status}")
            print(f"   兼容的Agent ({len(compatible_agents)}): {compatible_agents}")
            print(f"   不兼容的Agent ({len(incompatible_agents)}): {incompatible_agents}")
        else:
            status = "[OK] 完全兼容"
            print(f"   {status}")
        
        compatibility_report.append({
            'workflow_id': workflow_id,
            'workflow_name': workflow_name,
            'total_agents': len(agent_ids),
            'compatible': len(compatible_agents),
            'incompatible': len(incompatible_agents),
            'incompatible_agents': incompatible_agents,
            'status': status
        })
    
    # 5. 生成总结报告
    print("\n" + "=" * 80)
    print("兼容性总结报告")
    print("=" * 80)
    
    total_workflows = len(compatibility_report)
    fully_compatible = sum(1 for r in compatibility_report if r['incompatible'] == 0)
    partially_compatible = sum(1 for r in compatibility_report if r['incompatible'] > 0)
    
    print(f"\n总工作流数: {total_workflows}")
    print(f"完全兼容: {fully_compatible}")
    print(f"部分不兼容: {partially_compatible}")
    
    if partially_compatible > 0:
        print("\n需要处理的不兼容Agent:")
        all_incompatible = set()
        for report in compatibility_report:
            all_incompatible.update(report['incompatible_agents'])
        
        for agent_id in sorted(all_incompatible):
            print(f"   - {agent_id}")
        
        print("\n建议:")
        print("   1. 为这些Agent创建v2.0适配器")
        print("   2. 或者更新工作流模板使用已有的v2.0 Agent")
    else:
        print("\n[SUCCESS] 所有工作流模板都与v2.0 Agent完全兼容！")
    
    client.close()


if __name__ == "__main__":
    check_workflow_compatibility()

