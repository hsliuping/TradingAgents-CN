#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 API Key 配置优先级逻辑

测试场景：
1. 数据库有有效的 Key → 使用数据库的 Key
2. 数据库有无效的 Key（占位符） → 使用环境变量的 Key
3. 数据库有无效的 Key（长度不够） → 使用环境变量的 Key
4. 数据库和环境变量都没有 → 报错
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def test_api_key_validation():
    """测试 API Key 验证逻辑"""
    from app.services.config_service import ConfigService
    
    config_service = ConfigService()
    
    print("=" * 80)
    print("🧪 测试 API Key 验证逻辑")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        ("sk-test-placeholder-valid-001234", True, "有效格式占位 Key"),
        ("your_api_key_here", False, "占位符 (your_)"),
        ("your-api-key-here", False, "占位符 (your-)"),
        ("short", False, "长度不够"),
        ("", False, "空字符串"),
        (None, False, "None"),
        ("  sk-test-placeholder-valid-001234  ", True, "有空格但有效"),
    ]
    
    print("\n📋 测试用例：")
    for api_key, expected, description in test_cases:
        result = config_service._is_valid_api_key(api_key)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description:30s} | Key: {repr(api_key):30s} | 结果: {result} | 期望: {expected}")
    
    print("\n" + "=" * 80)


async def test_provider_key_priority():
    """测试厂家 API Key 优先级"""
    from app.services.config_service import ConfigService
    from app.core.database import init_db
    
    # 初始化数据库
    await init_db()
    
    config_service = ConfigService()
    
    print("\n" + "=" * 80)
    print("🧪 测试厂家 API Key 优先级")
    print("=" * 80)
    
    # 获取所有厂家配置
    providers = await config_service.get_llm_providers()
    
    print(f"\n📊 找到 {len(providers)} 个厂家配置：\n")
    
    for provider in providers:
        print(f"厂家: {provider.display_name} ({provider.name})")
        
        # 检查数据库中的 Key
        db_key = provider.api_key
        db_key_valid = config_service._is_valid_api_key(db_key)
        
        # 检查环境变量中的 Key
        env_key = config_service._get_env_api_key(provider.name)
        
        # 显示配置来源
        source = provider.extra_config.get("source", "unknown") if provider.extra_config else "unknown"
        
        print(f"  数据库 Key: {_mask_key(db_key):30s} | 有效: {db_key_valid}")
        print(f"  环境变量 Key: {_mask_key(env_key):30s} | 有效: {bool(env_key)}")
        print(f"  实际使用: {_mask_key(provider.api_key):30s} | 来源: {source}")
        print()
    
    print("=" * 80)


def _mask_key(key: str) -> str:
    """脱敏显示 API Key"""
    if not key:
        return "未配置"
    if len(key) <= 10:
        return "***"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


async def main():
    """主函数"""
    try:
        # 测试 1: API Key 验证逻辑
        await test_api_key_validation()
        
        # 测试 2: 厂家 API Key 优先级
        await test_provider_key_priority()
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
