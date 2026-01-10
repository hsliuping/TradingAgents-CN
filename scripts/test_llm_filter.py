"""
测试 LLM 模型过滤逻辑

验证：
1. GET /api/config/llm 接口只返回有有效 API Key 的模型
2. has_valid_api_key() 函数的过滤逻辑正确
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_llm_filter():
    """测试 LLM 模型过滤"""
    from app.services.config_service import config_service
    from app.utils.api_key_utils import has_valid_api_key
    
    print("=" * 80)
    print("测试 LLM 模型过滤逻辑")
    print("=" * 80)
    
    # 1. 获取系统配置
    print("\n📊 步骤 1: 获取系统配置")
    config = await config_service.get_system_config()
    if not config:
        print("❌ 系统配置为空")
        return
    
    print(f"✅ 系统配置存在，大模型配置数量: {len(config.llm_configs)}")
    
    # 2. 获取厂家配置
    print("\n📊 步骤 2: 获取厂家配置")
    providers = await config_service.get_llm_providers()
    print(f"✅ 厂家配置数量: {len(providers)}")
    
    # 构建厂家字典
    providers_dict = {p.name: p for p in providers}
    active_provider_names = {p.name for p in providers if p.is_active}
    
    print(f"   - 启用的厂家: {len(active_provider_names)}")
    print(f"   - 启用的厂家列表: {', '.join(active_provider_names)}")
    
    # 3. 检查每个厂家的 API Key 状态
    print("\n📊 步骤 3: 检查厂家 API Key 状态")
    for provider in providers:
        has_key = provider.extra_config.get('has_api_key', False) if provider.extra_config else False
        status = "✅ 有密钥" if has_key else "❌ 无密钥"
        active = "启用" if provider.is_active else "禁用"
        print(f"   - {provider.display_name:15s} ({provider.name:15s}): {status} | {active}")
    
    # 4. 测试模型过滤
    print("\n📊 步骤 4: 测试模型过滤")
    print(f"   原始模型数量: {len(config.llm_configs)}")
    
    # 统计各种状态的模型
    enabled_count = sum(1 for llm in config.llm_configs if llm.enabled)
    active_provider_count = sum(1 for llm in config.llm_configs if llm.provider in active_provider_names)
    has_key_count = sum(1 for llm in config.llm_configs if has_valid_api_key(llm, providers_dict))
    
    print(f"   - 启用的模型: {enabled_count}")
    print(f"   - 厂家启用的模型: {active_provider_count}")
    print(f"   - 有 API Key 的模型: {has_key_count}")
    
    # 应用过滤
    filtered_configs = [
        llm_config for llm_config in config.llm_configs
        if llm_config.enabled 
        and llm_config.provider in active_provider_names
        and has_valid_api_key(llm_config, providers_dict)
    ]
    
    print(f"   - 过滤后的模型: {len(filtered_configs)}")
    
    # 5. 显示过滤后的模型列表
    print("\n📊 步骤 5: 过滤后的模型列表")
    if filtered_configs:
        for llm in filtered_configs:
            print(f"   ✅ {llm.model_name:30s} ({llm.provider})")
    else:
        print("   ⚠️  没有可用的模型（所有模型都被过滤掉了）")
    
    # 6. 显示被过滤掉的模型
    print("\n📊 步骤 6: 被过滤掉的模型")
    filtered_out = [
        llm for llm in config.llm_configs
        if not (llm.enabled and llm.provider in active_provider_names and has_valid_api_key(llm, providers_dict))
    ]
    
    if filtered_out:
        for llm in filtered_out:
            reasons = []
            if not llm.enabled:
                reasons.append("模型未启用")
            if llm.provider not in active_provider_names:
                reasons.append("厂家未启用")
            if not has_valid_api_key(llm, providers_dict):
                reasons.append("无 API Key")
            
            reason_str = ", ".join(reasons)
            print(f"   ❌ {llm.model_name:30s} ({llm.provider:15s}) - {reason_str}")
    else:
        print("   ✅ 没有被过滤掉的模型")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


async def test_api_key_sanitization():
    """测试 API Key 脱敏逻辑"""
    from app.services.config_service import config_service
    from app.routers.config import _sanitize_llm_configs
    from app.utils.api_key_utils import has_valid_api_key

    print("=" * 80)
    print("测试 API Key 脱敏逻辑")
    print("=" * 80)

    # 1. 获取系统配置
    print("\n📊 步骤 1: 获取系统配置")
    config = await config_service.get_system_config()
    if not config:
        print("❌ 系统配置为空")
        return

    print(f"✅ 系统配置存在，大模型配置数量: {len(config.llm_configs)}")

    # 2. 获取厂家配置
    print("\n📊 步骤 2: 获取厂家配置")
    providers = await config_service.get_llm_providers()
    providers_dict = {p.name: p for p in providers}
    active_provider_names = {p.name for p in providers if p.is_active}

    print(f"✅ 厂家配置数量: {len(providers)}")

    # 3. 过滤模型
    print("\n📊 步骤 3: 过滤模型")
    filtered_configs = [
        llm_config for llm_config in config.llm_configs
        if llm_config.enabled
        and llm_config.provider in active_provider_names
        and has_valid_api_key(llm_config, providers_dict)
    ]

    print(f"   过滤后的模型数量: {len(filtered_configs)}")

    # 4. 脱敏 API Key
    print("\n📊 步骤 4: 脱敏 API Key")
    sanitized_configs = _sanitize_llm_configs(filtered_configs, providers_dict)

    print(f"   脱敏后的模型数量: {len(sanitized_configs)}")

    # 5. 显示脱敏后的 API Key
    print("\n📊 步骤 5: 脱敏后的 API Key")
    for llm in sanitized_configs:
        api_key_display = llm.api_key if llm.api_key else "(无)"
        print(f"   - {llm.model_name:30s} ({llm.provider:15s}): {api_key_display}")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sanitize":
        asyncio.run(test_api_key_sanitization())
    else:
        asyncio.run(test_llm_filter())

