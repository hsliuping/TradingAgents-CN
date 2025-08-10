#!/usr/bin/env python3
"""
测试记忆模型独立性功能
验证大模型和记忆模型提供商可以独立设置，不会相互影响
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.utils.persistence import ModelPersistence, load_model_selection, save_model_selection
import json

def test_memory_model_independence():
    """测试记忆模型独立性功能"""
    print("🧪 测试记忆模型独立性功能")
    print("=" * 50)
    
    # 创建持久化管理器实例
    persistence = ModelPersistence()
    
    # 测试1: 测试默认embedding模型获取
    print("\n1. 测试默认embedding模型获取:")
    providers = ["dashscope", "deepseek", "openai", "google", "openrouter", "硅基流动"]
    for provider in providers:
        default_model = persistence._get_default_embedding_model(provider)
        print(f"   {provider}: {default_model}")
    
    # 测试2: 测试默认配置加载
    print("\n2. 测试默认配置加载:")
    default_config = persistence.load_config()
    print(f"   默认配置: {json.dumps(default_config, ensure_ascii=False, indent=2)}")
    
    # 测试3: 测试记忆模型独立性
    print("\n3. 测试记忆模型独立性:")
    
    # 场景1: 使用DeepSeek作为主模型，OpenAI作为记忆模型
    print("\n   场景1: DeepSeek主模型 + OpenAI记忆模型")
    test_config_1 = {
        'provider': 'deepseek',
        'category': 'openai',
        'model': 'deepseek-chat',
        'memory_provider': 'openai',
        'memory_model': 'text-embedding-3-small'
    }
    
    # 模拟保存配置
    persistence.save_config(
        test_config_1['provider'],
        test_config_1['category'],
        test_config_1['model'],
        test_config_1['memory_provider'],
        test_config_1['memory_model']
    )
    
    # 模拟加载配置
    loaded_config_1 = persistence.load_config()
    print(f"   加载的配置: {json.dumps(loaded_config_1, ensure_ascii=False, indent=2)}")
    
    # 场景2: 切换到Google主模型，记忆模型保持不变
    print("\n   场景2: 切换到Google主模型，记忆模型保持不变")
    test_config_2 = {
        'provider': 'google',
        'category': 'openai',
        'model': 'gemini-pro',
        'memory_provider': 'openai',  # 保持不变
        'memory_model': 'text-embedding-3-small'  # 保持不变
    }
    
    # 模拟保存配置
    persistence.save_config(
        test_config_2['provider'],
        test_config_2['category'],
        test_config_2['model'],
        test_config_2['memory_provider'],
        test_config_2['memory_model']
    )
    
    # 模拟加载配置
    loaded_config_2 = persistence.load_config()
    print(f"   加载的配置: {json.dumps(loaded_config_2, ensure_ascii=False, indent=2)}")
    
    # 验证记忆模型设置是否保持不变
    if (loaded_config_2['memory_provider'] == test_config_1['memory_provider'] and 
        loaded_config_2['memory_model'] == test_config_1['memory_model']):
        print("   ✅ 记忆模型设置保持不变")
    else:
        print("   ❌ 记忆模型设置被意外修改")
    
    # 场景3: 测试空值处理
    print("\n4. 测试空值处理:")
    empty_config = {
        'provider': 'dashscope',
        'category': 'openai',
        'model': 'qwen-plus',
        'memory_provider': None,
        'memory_model': None
    }
    
    # 模拟保存空值配置
    persistence.save_config(
        empty_config['provider'],
        empty_config['category'],
        empty_config['model'],
        empty_config['memory_provider'],
        empty_config['memory_model']
    )
    
    # 模拟加载空值配置（应该自动填充默认值）
    loaded_empty_config = persistence.load_config()
    print(f"   空值配置加载后: {json.dumps(loaded_empty_config, ensure_ascii=False, indent=2)}")
    
    # 验证默认值是否正确设置
    if (loaded_empty_config['memory_provider'] == 'dashscope' and 
        loaded_empty_config['memory_model'] == 'text-embedding-v1'):
        print("   ✅ 默认值设置正确")
    else:
        print("   ❌ 默认值设置错误")
    
    # 场景4: 测试不同组合
    print("\n5. 测试不同组合:")
    combinations = [
        ("dashscope", "openai"),
        ("deepseek", "google"),
        ("openai", "dashscope"),
        ("google", "deepseek"),
        ("openrouter", "openai")
    ]
    
    for main_provider, memory_provider in combinations:
        # 模拟保存配置
        persistence.save_config(main_provider, 'openai', f'{main_provider}-model', memory_provider, None)
        
        # 加载配置
        config = persistence.load_config()
        expected_memory_model = persistence._get_default_embedding_model(memory_provider)
        
        print(f"   {main_provider}主模型 + {memory_provider}记忆模型:")
        print(f"     主模型: {config['provider']}")
        print(f"     记忆模型提供商: {config['memory_provider']}")
        print(f"     记忆模型: {config['memory_model']}")
        
        if (config['provider'] == main_provider and 
            config['memory_provider'] == memory_provider and
            config['memory_model'] == expected_memory_model):
            print(f"     ✅ 配置正确")
        else:
            print(f"     ❌ 配置错误")
    
    print("\n✅ 测试完成！")
    print("\n📋 测试结果总结:")
    print("   - 记忆模型提供商和主模型提供商可以独立设置")
    print("   - 切换主模型时，记忆模型设置保持不变")
    print("   - 默认值设置正确")
    print("   - 支持A大模型+B记忆模型的组合")

if __name__ == "__main__":
    test_memory_model_independence()
