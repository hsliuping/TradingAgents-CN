#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试调试接口实际调用的URL
"""

import sys
import os
import json
import logging

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

def test_dashscope_url():
    """测试 DashScope 实际调用的 URL"""
    print("\n" + "=" * 80)
    print("🧪 测试：DashScope 实际调用的 URL")
    print("=" * 80)
    
    from tradingagents.llm_adapters.dashscope_openai_adapter import ChatDashScopeOpenAI
    
    # 测试1：使用默认 URL
    print("\n📝 测试1：使用默认 URL")
    print("-" * 80)
    
    try:
        llm1 = ChatDashScopeOpenAI(
            model="qwen-plus",
            api_key="test_key_12345",
            temperature=0.7,
            max_tokens=2000
        )
        
        base_url = getattr(llm1, 'base_url', None) or getattr(llm1, 'openai_api_base', None)
        print(f"✅ LLM 创建成功")
        print(f"   模型: {llm1.model_name}")
        print(f"   Base URL: {base_url}")
        print(f"   预期: https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        if base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1":
            print(f"   ✅ URL 正确")
        else:
            print(f"   ❌ URL 不正确")
    except Exception as e:
        print(f"❌ 创建失败: {e}")
    
    # 测试2：使用自定义 URL
    print("\n📝 测试2：使用自定义 URL")
    print("-" * 80)
    
    try:
        custom_url = "https://dashscope.aliyuncs.com/api/v2"
        llm2 = ChatDashScopeOpenAI(
            model="qwen-plus",
            api_key="test_key_12345",
            base_url=custom_url,
            temperature=0.7,
            max_tokens=2000
        )
        
        base_url = getattr(llm2, 'base_url', None) or getattr(llm2, 'openai_api_base', None)
        print(f"✅ LLM 创建成功")
        print(f"   模型: {llm2.model_name}")
        print(f"   Base URL: {base_url}")
        print(f"   预期: {custom_url}")
        
        if base_url == custom_url:
            print(f"   ✅ URL 正确")
        else:
            print(f"   ❌ URL 不正确")
    except Exception as e:
        print(f"❌ 创建失败: {e}")
    
    # 测试3：使用 None 作为 base_url
    print("\n📝 测试3：使用 None 作为 base_url")
    print("-" * 80)
    
    try:
        llm3 = ChatDashScopeOpenAI(
            model="qwen-plus",
            api_key="test_key_12345",
            base_url=None,
            temperature=0.7,
            max_tokens=2000
        )
        
        base_url = getattr(llm3, 'base_url', None) or getattr(llm3, 'openai_api_base', None)
        print(f"✅ LLM 创建成功")
        print(f"   模型: {llm3.model_name}")
        print(f"   Base URL: {base_url}")
        print(f"   预期: https://dashscope.aliyuncs.com/compatible-mode/v1 (默认)")
        
        if base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1":
            print(f"   ✅ URL 正确")
        else:
            print(f"   ❌ URL 不正确")
    except Exception as e:
        print(f"❌ 创建失败: {e}")

if __name__ == "__main__":
    test_dashscope_url()
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)

