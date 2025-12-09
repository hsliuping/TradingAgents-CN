#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Embedding 服务提供者

验证：
1. 从数据库获取支持 embedding 的厂商
2. 按优先级尝试各个服务
3. 降级机制
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-5s | %(message)s'
)


def test_embedding_provider():
    """测试 EmbeddingProviderManager"""
    print("\n" + "=" * 60)
    print("测试 EmbeddingProviderManager")
    print("=" * 60 + "\n")
    
    from tradingagents.agents.utils.embedding_provider import (
        EmbeddingProviderManager,
        get_embedding_manager,
        get_embedding_with_fallback
    )
    
    # 1. 测试获取可用提供者
    print("📋 1. 获取可用的 Embedding 提供者")
    print("-" * 40)
    
    manager = get_embedding_manager()
    providers = manager.get_available_providers(force_refresh=True)
    
    if not providers:
        print("⚠️ 没有找到可用的 embedding 提供者")
        print("   请检查：")
        print("   - 数据库中是否有 is_active=true 且 supported_features 包含 'embedding' 的厂商")
        print("   - 是否配置了有效的 API Key")
    else:
        print(f"✅ 找到 {len(providers)} 个可用的 embedding 提供者：")
        for i, p in enumerate(providers, 1):
            print(f"   {i}. {p.display_name} ({p.name})")
            print(f"      - 优先级: {p.priority}")
            print(f"      - 模型: {p.model}")
            print(f"      - Base URL: {p.base_url[:50]}...")
            print(f"      - API Key: {'已配置' if p.api_key else '未配置'}")
    
    print()
    
    # 2. 测试获取 embedding
    if providers:
        print("📝 2. 测试获取 Embedding")
        print("-" * 40)
        
        test_text = "这是一个测试文本，用于验证 embedding 服务是否正常工作。"
        print(f"   测试文本: {test_text}")
        print()
        
        embedding, provider_name = get_embedding_with_fallback(test_text)
        
        if embedding:
            print(f"✅ Embedding 获取成功！")
            print(f"   - 使用的提供者: {provider_name}")
            print(f"   - 向量维度: {len(embedding)}")
            print(f"   - 向量前5个值: {embedding[:5]}")
        else:
            print(f"❌ Embedding 获取失败: {provider_name}")
    
    print()
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


def test_memory_with_embedding():
    """测试 Memory 与新 Embedding 系统的集成"""
    print("\n" + "=" * 60)
    print("测试 Memory 与 Embedding 集成")
    print("=" * 60 + "\n")
    
    from tradingagents.agents.utils.memory import FinancialSituationMemory
    
    # 使用默认配置创建 Memory
    config = {
        "llm_provider": "dashscope",  # 使用 dashscope 作为主提供者
    }
    
    print("📋 创建 FinancialSituationMemory 实例...")
    memory = FinancialSituationMemory("test_memory", config)
    
    print(f"   - 配置状态: {memory.get_embedding_config_status()}")
    print()
    
    # 测试获取 embedding
    test_text = "五粮液股票在当前市场环境下表现如何？技术面显示..."
    print(f"📝 测试文本: {test_text[:50]}...")
    
    embedding = memory.get_embedding(test_text)
    
    if embedding and any(x != 0.0 for x in embedding):
        print(f"✅ Memory embedding 获取成功！")
        print(f"   - 向量维度: {len(embedding)}")
        print(f"   - 最后处理信息: {memory.get_last_text_info()}")
    else:
        print("⚠️ Memory embedding 返回空向量（可能是降级模式）")
        print(f"   - 最后处理信息: {memory.get_last_text_info()}")
    
    print()
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_embedding_provider()
    print("\n" * 2)
    test_memory_with_embedding()

