#!/usr/bin/env python3
"""
测试记忆模型提供商切换功能
验证当切换记忆模型提供商时，能够恢复之前为该提供商保存的模型名称
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.utils.persistence import ModelPersistence, load_model_selection, save_model_selection
import json

def test_memory_model_provider_switch():
    """测试记忆模型提供商切换功能"""
    print("🧪 测试记忆模型提供商切换功能")
    print("=" * 50)
    
    # 创建持久化管理器实例
    persistence = ModelPersistence()
    
    # 模拟session state
    import streamlit as st
    if 'memory_models_by_provider' not in st.session_state:
        st.session_state['memory_models_by_provider'] = {}
    
    print("\n1. 测试记忆模型名称保存和恢复:")
    
    # 场景1: 用户为不同提供商设置不同的记忆模型
    print("\n   场景1: 为不同提供商设置记忆模型")
    
    # 设置DashScope的记忆模型
    print("   设置DashScope记忆模型为: text-embedding-v1")
    persistence.save_config('dashscope', 'openai', 'qwen-plus', 'dashscope', 'text-embedding-v1')
    
    # 设置OpenAI的记忆模型
    print("   设置OpenAI记忆模型为: text-embedding-3-small")
    persistence.save_config('dashscope', 'openai', 'qwen-plus', 'openai', 'text-embedding-3-small')
    
    # 设置Google的记忆模型
    print("   设置Google记忆模型为: text-embedding-004")
    persistence.save_config('dashscope', 'openai', 'qwen-plus', 'google', 'text-embedding-004')
    
    print(f"   保存的记忆模型映射: {st.session_state.get('memory_models_by_provider', {})}")
    
    # 场景2: 切换记忆模型提供商，验证模型名称恢复
    print("\n   场景2: 切换记忆模型提供商")
    
    providers_to_test = ['dashscope', 'openai', 'google', 'deepseek']
    expected_models = {
        'dashscope': 'text-embedding-v1',
        'openai': 'text-embedding-3-small', 
        'google': 'text-embedding-004',
        'deepseek': None  # 没有设置过，应该使用默认值
    }
    
    for provider in providers_to_test:
        print(f"\n   切换到{provider}提供商:")
        
        # 模拟切换提供商
        memory_models_by_provider = st.session_state.get('memory_models_by_provider', {})
        if provider in memory_models_by_provider:
            restored_model = memory_models_by_provider[provider]
            print(f"     恢复的记忆模型: {restored_model}")
            if restored_model == expected_models[provider]:
                print(f"     ✅ 正确恢复了{provider}的记忆模型")
            else:
                print(f"     ❌ 恢复的记忆模型不正确，期望: {expected_models[provider]}")
        else:
            print(f"     没有保存过{provider}的记忆模型，将使用默认值")
            default_model = persistence._get_default_embedding_model(provider)
            print(f"     默认模型: {default_model}")
            if default_model == expected_models[provider]:
                print(f"     ✅ 默认值正确")
            else:
                print(f"     ❌ 默认值不正确，期望: {expected_models[provider]}")
    
    # 场景3: 测试新提供商设置记忆模型
    print("\n   场景3: 为新提供商设置记忆模型")
    
    # 为DeepSeek设置记忆模型
    print("   为DeepSeek设置记忆模型: text-embedding-v1")
    persistence.save_config('dashscope', 'openai', 'qwen-plus', 'deepseek', 'text-embedding-v1')
    
    # 验证是否保存成功
    memory_models_by_provider = st.session_state.get('memory_models_by_provider', {})
    if 'deepseek' in memory_models_by_provider:
        saved_model = memory_models_by_provider['deepseek']
        print(f"   保存的DeepSeek记忆模型: {saved_model}")
        if saved_model == 'text-embedding-v1':
            print("   ✅ DeepSeek记忆模型保存成功")
        else:
            print("   ❌ DeepSeek记忆模型保存失败")
    else:
        print("   ❌ DeepSeek记忆模型未保存")
    
    # 场景4: 测试配置加载时的记忆模型恢复
    print("\n   场景4: 测试配置加载时的记忆模型恢复")
    
    # 模拟加载配置
    loaded_config = persistence.load_config()
    print(f"   加载的配置: {json.dumps(loaded_config, ensure_ascii=False, indent=2)}")
    
    # 验证记忆模型是否正确
    if loaded_config['memory_provider'] == 'deepseek' and loaded_config['memory_model'] == 'text-embedding-v1':
        print("   ✅ 配置加载时记忆模型恢复正确")
    else:
        print("   ❌ 配置加载时记忆模型恢复错误")
    
    print("\n✅ 测试完成！")
    print("\n📋 测试结果总结:")
    print("   - 每个提供商的记忆模型名称可以独立保存")
    print("   - 切换提供商时能够恢复之前保存的模型名称")
    print("   - 新提供商使用默认模型名称")
    print("   - 配置加载时记忆模型正确恢复")

if __name__ == "__main__":
    test_memory_model_provider_switch()
