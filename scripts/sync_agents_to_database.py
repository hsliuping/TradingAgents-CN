"""
将AgentRegistry中的所有Agent同步到数据库

功能：
1. 从AgentRegistry获取所有已注册的Agent
2. 为每个Agent生成配置
3. 写入到MongoDB的agent_configs集合
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from app.core.config import settings
from core.agents.registry import AgentRegistry
from core.config.agent_config_manager import AgentConfigManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_agents_to_database():
    """同步Agent配置到数据库"""
    
    print("=" * 80)
    print("同步Agent配置到数据库")
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
    
    # 2. 获取所有已注册的Agent
    print("\n2. 获取已注册的Agent...")
    registry = AgentRegistry()
    registered_agents = registry.list_all()
    print(f"   [OK] 找到 {len(registered_agents)} 个已注册的Agent")
    
    # 3. 设置AgentConfigManager的数据库连接
    print("\n3. 初始化AgentConfigManager...")
    config_manager = AgentConfigManager()
    config_manager.set_database(db)
    print(f"   [OK] AgentConfigManager已初始化")
    
    # 4. 同步每个Agent的配置
    print("\n4. 同步Agent配置到数据库...")
    print("=" * 80)
    
    success_count = 0
    failed_count = 0
    
    for metadata in registered_agents:
        agent_id = metadata.id
        print(f"\n处理Agent: {agent_id}")
        print(f"   名称: {metadata.name}")
        print(f"   类别: {metadata.category}")
        print(f"   描述: {metadata.description[:50]}..." if len(metadata.description) > 50 else f"   描述: {metadata.description}")
        
        # 生成配置
        config = {
            "agent_id": agent_id,
            "name": metadata.name,
            "category": metadata.category.value if hasattr(metadata.category, 'value') else metadata.category,
            "description": metadata.description,
            "enabled": True,
            "license_tier": metadata.license_tier.value if hasattr(metadata.license_tier, 'value') else metadata.license_tier,
            
            # 执行配置
            "config": {
                "max_iterations": 3,
                "timeout": 300,
                "temperature": 0.7,
            },
            
            # 提示词配置
            "prompt_template_type": None,
            "prompt_template_name": None,
            
            # 工具配置
            "default_tools": metadata.default_tools if hasattr(metadata, 'default_tools') else [],
            "required_tools": metadata.required_tools if hasattr(metadata, 'required_tools') else [],
            
            # 输入输出配置
            "input_fields": metadata.input_fields if hasattr(metadata, 'input_fields') else [],
            "output_fields": metadata.output_fields if hasattr(metadata, 'output_fields') else [],
            
            # 标签
            "tags": metadata.tags if hasattr(metadata, 'tags') else [],
            
            # 时间戳
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # 保存到数据库
        try:
            result = config_manager.save_agent_config(config)
            if result:
                print(f"   [OK] 配置已保存")
                success_count += 1
            else:
                print(f"   [ERROR] 保存失败")
                failed_count += 1
        except Exception as e:
            print(f"   [ERROR] 保存失败: {e}")
            failed_count += 1
    
    # 5. 生成总结报告
    print("\n" + "=" * 80)
    print("同步完成")
    print("=" * 80)
    print(f"\n总Agent数: {len(registered_agents)}")
    print(f"成功同步: {success_count}")
    print(f"失败: {failed_count}")
    
    if success_count > 0:
        print(f"\n[SUCCESS] 已成功同步 {success_count} 个Agent配置到数据库！")
        print(f"\n你现在可以在Web界面的 '分析 / Agent配置' 页面查看这些Agent。")
    
    client.close()


if __name__ == "__main__":
    sync_agents_to_database()

