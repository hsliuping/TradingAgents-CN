"""
v2.0 Embedding 配置获取示例

演示如何在 v2.0 系统中获取配置的 embedding 模型和参数
"""

import logging
from core.workflow.builder import WorkflowBuilder
from core.llm import EmbeddingManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_get_embedding_config():
    """示例：获取 Embedding 配置信息"""
    
    # 方式1：通过 WorkflowBuilder 获取
    print("=" * 80)
    print("方式1：通过 WorkflowBuilder 获取 Embedding 配置")
    print("=" * 80)
    
    builder = WorkflowBuilder()
    
    if builder.embedding_manager:
        config = builder.embedding_manager.get_config()
        print(f"\n✅ Embedding 配置信息:")
        print(f"   - 是否有提供商: {config['has_provider']}")
        print(f"   - 提供商总数: {config['total_providers']}")
        
        if config['primary_provider']:
            primary = config['primary_provider']
            print(f"\n🎯 主提供商:")
            print(f"   - 名称: {primary['name']}")
            print(f"   - 显示名称: {primary['display_name']}")
            print(f"   - 模型: {primary['model']}")
            print(f"   - API地址: {primary['base_url']}")
        
        if config['fallback_providers']:
            print(f"\n💡 备用提供商 ({len(config['fallback_providers'])} 个):")
            for i, provider in enumerate(config['fallback_providers'], 1):
                print(f"   {i}. {provider['display_name']} ({provider['name']})")
                print(f"      - 模型: {provider['model']}")
                print(f"      - API地址: {provider['base_url']}")
    else:
        print("❌ EmbeddingManager 未初始化")
    
    # 方式2：直接创建 EmbeddingManager 实例
    print("\n" + "=" * 80)
    print("方式2：直接创建 EmbeddingManager 实例")
    print("=" * 80)
    
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        
        embedding_mgr = EmbeddingManager(db=db)
        config = embedding_mgr.get_config()
        
        print(f"\n✅ Embedding 配置信息:")
        print(f"   - 是否有提供商: {config['has_provider']}")
        print(f"   - 提供商总数: {config['total_providers']}")
        
        if config['primary_provider']:
            primary = config['primary_provider']
            print(f"\n🎯 主提供商:")
            print(f"   - 名称: {primary['name']}")
            print(f"   - 显示名称: {primary['display_name']}")
            print(f"   - 模型: {primary['model']}")
            print(f"   - API地址: {primary['base_url']}")
        
        # 测试获取 embedding
        if config['has_provider']:
            print(f"\n🧪 测试获取 Embedding:")
            embedding, provider_name = embedding_mgr.get_embedding("测试文本")
            if embedding:
                print(f"   ✅ 成功获取 Embedding，维度: {len(embedding)}")
                print(f"   ✅ 使用的提供商: {provider_name}")
            else:
                print(f"   ❌ 获取 Embedding 失败: {provider_name}")
        
    except Exception as e:
        print(f"❌ 创建 EmbeddingManager 失败: {e}")


def example_use_embedding_in_agent():
    """示例：在 Agent 中使用 Embedding"""
    
    print("\n" + "=" * 80)
    print("示例：在 Agent 中使用 Embedding")
    print("=" * 80)
    
    builder = WorkflowBuilder()
    
    if builder.embedding_manager:
        # 获取配置信息
        config = builder.embedding_manager.get_config()
        
        if config['has_provider']:
            primary = config['primary_provider']
            print(f"\n📋 当前使用的 Embedding 配置:")
            print(f"   - 提供商: {primary['display_name']} ({primary['name']})")
            print(f"   - 模型: {primary['model']}")
            print(f"   - API地址: {primary['base_url']}")
            
            # 在实际使用中，可以通过 builder.embedding_manager 获取 embedding
            # 例如在 Agent 的 execute 方法中：
            # embedding, provider = builder.embedding_manager.get_embedding(text)
            
            print(f"\n💡 使用方式:")
            print(f"   在 Agent 中可以通过以下方式获取 embedding:")
            print(f"   ```python")
            print(f"   # 假设在 Agent 的 execute 方法中")
            print(f"   embedding_manager = state.get('embedding_manager')")
            print(f"   if embedding_manager:")
            print(f"       embedding, provider = embedding_manager.get_embedding(text)")
            print(f"   ```")
        else:
            print("❌ 没有可用的 Embedding 提供商")
    else:
        print("❌ EmbeddingManager 未初始化")


if __name__ == "__main__":
    print("v2.0 Embedding 配置获取示例\n")
    
    try:
        example_get_embedding_config()
        example_use_embedding_in_agent()
    except Exception as e:
        logger.error(f"示例执行失败: {e}", exc_info=True)
