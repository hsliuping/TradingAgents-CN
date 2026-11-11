#!/usr/bin/env python3
"""
测试模型配置功能
验证模型能力字段的保存和读取
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8001"

# 全局访问令牌
access_token: Optional[str] = None

async def login():
    """登录获取访问令牌"""
    global access_token
    print("🔐 正在登录...")
    
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        access_token = result["data"]["access_token"]
                        print(f"✅ 登录成功，获取访问令牌")
                        return True
                    else:
                        print(f"❌ 登录失败: {result.get('message', '未知错误')}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"❌ 登录失败 ({response.status}): {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 登录请求异常: {e}")
            return False

def get_auth_headers():
    """获取认证头"""
    if access_token:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    return {"Content-Type": "application/json"}

async def test_add_llm_config():
    """测试添加LLM配置"""
    print("🧪 测试添加LLM配置...")
    
    # 测试配置数据
    config_data = {
        "provider": "qwen",
        "model_name": "qwen-test-model",
        "model_display_name": "Qwen测试模型",
        "api_key": "",
        "max_tokens": 4000,
        "temperature": 0.7,
        "enabled": True,
        "description": "用于测试的模型配置",
        
        # 模型能力字段
        "capability_level": 3,
        "suitable_roles": ["both"],
        "features": ["tool_calling", "reasoning"],
        "recommended_depths": ["标准", "深度"],
        "performance_metrics": {
            "speed": 4,
            "cost": 3,
            "quality": 4
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 添加配置
            async with session.post(
                f"{BASE_URL}/api/config/llm",
                json=config_data,
                headers=get_auth_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 添加配置成功: {result}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 添加配置失败 ({response.status}): {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

async def test_get_llm_configs():
    """测试获取LLM配置"""
    print("🧪 测试获取LLM配置...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{BASE_URL}/api/config/llm",
                headers=get_auth_headers()
            ) as response:
                if response.status == 200:
                    configs = await response.json()
                    print(f"✅ 获取配置成功，共 {len(configs)} 个配置")
                    
                    # 查找测试模型
                    test_model = None
                    for config in configs:
                        if config.get("model_name") == "qwen-test-model":
                            test_model = config
                            break
                    
                    if test_model:
                        print("✅ 找到测试模型配置:")
                        print(f"   - 模型名称: {test_model.get('model_name')}")
                        print(f"   - 显示名称: {test_model.get('model_display_name')}")
                        print(f"   - 能力等级: {test_model.get('capability_level')}")
                        print(f"   - 适用角色: {test_model.get('suitable_roles')}")
                        print(f"   - 特性: {test_model.get('features')}")
                        print(f"   - 推荐深度: {test_model.get('recommended_depths')}")
                        print(f"   - 性能指标: {test_model.get('performance_metrics')}")
                        return True
                    else:
                        print("❌ 未找到测试模型配置")
                        return False
                else:
                    error_text = await response.text()
                    print(f"❌ 获取配置失败 ({response.status}): {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

async def test_model_capability_service():
    """测试模型能力服务"""
    print("🧪 测试模型能力服务...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 测试推荐模型
            async with session.post(
                f"{BASE_URL}/api/model-capabilities/recommend",
                json={"research_depth": "标准"},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 模型推荐成功:")
                    print(f"   - 快速模型: {result.get('data', {}).get('quick_model')}")
                    print(f"   - 深度模型: {result.get('data', {}).get('deep_model')}")
                    print(f"   - 推荐理由: {result.get('data', {}).get('reason')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 模型推荐失败 ({response.status}): {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

async def test_delete_test_config():
    """删除测试配置"""
    print("🧪 清理测试配置...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(
                f"{BASE_URL}/api/config/llm/qwen/qwen-test-model",
                headers=get_auth_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 删除测试配置成功: {result}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"⚠️ 删除测试配置失败 ({response.status}): {error_text}")
                    return False
        except Exception as e:
            print(f"⚠️ 删除请求异常: {e}")
            return False

async def main():
    """主测试函数"""
    print("🚀 开始测试模型配置功能...")
    print("=" * 50)
    
    # 首先登录
    if not await login():
        print("❌ 登录失败，无法继续测试")
        return
    
    # 测试步骤
    tests = [
        ("添加LLM配置", test_add_llm_config),
        ("获取LLM配置", test_get_llm_configs),
        ("模型能力服务", test_model_capability_service),
        ("清理测试配置", test_delete_test_config),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        success = await test_func()
        results.append((test_name, success))
        print()
    
    # 总结
    print("=" * 50)
    print("📊 测试结果总结:")
    passed = 0
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n🎯 总计: {passed}/{len(results)} 个测试通过")
    
    if passed == len(results):
        print("🎉 所有测试通过！配置功能正常工作。")
    else:
        print("⚠️ 部分测试失败，请检查配置。")

if __name__ == "__main__":
    asyncio.run(main())