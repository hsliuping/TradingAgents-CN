# -*- coding: utf-8 -*-
"""
测试删除 LLM 配置功能
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

from app.core.database import init_database, get_mongo_db
from app.services.config_service import ConfigService


async def test_delete_llm_config():
    """测试删除 LLM 配置"""
    print("=" * 80)
    print("🧪 测试删除 LLM 配置功能")
    print("=" * 80)
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 创建配置服务
    config_service = ConfigService(db)
    
    # 获取当前配置
    print("\n📊 获取当前系统配置...")
    config = await config_service.get_system_config()
    
    if not config:
        print("❌ 系统配置为空")
        return
    
    print(f"✅ 当前大模型配置数量: {len(config.llm_configs)}")
    print("\n📋 当前所有 LLM 配置:")
    for i, llm in enumerate(config.llm_configs, 1):
        # 测试 provider 字段类型
        provider_str = llm.provider if isinstance(llm.provider, str) else llm.provider.value
        print(f"   {i}. provider: {provider_str} ({type(llm.provider).__name__}), model: {llm.model_name}")
    
    # 测试删除一个不存在的配置
    print("\n" + "=" * 80)
    print("🧪 测试 1: 删除不存在的配置")
    print("=" * 80)
    result = await config_service.delete_llm_config("nonexistent", "test-model")
    print(f"结果: {result} (预期: False)")
    
    # 测试删除一个存在的配置（如果有的话）
    if config.llm_configs:
        first_llm = config.llm_configs[0]
        provider_str = first_llm.provider if isinstance(first_llm.provider, str) else first_llm.provider.value
        
        print("\n" + "=" * 80)
        print(f"🧪 测试 2: 删除存在的配置 ({provider_str}/{first_llm.model_name})")
        print("=" * 80)
        print(f"⚠️ 这将真实删除配置，请确认！")
        print(f"如果不想删除，请按 Ctrl+C 退出")
        
        # 注释掉实际删除操作，避免误删
        # result = await config_service.delete_llm_config(provider_str, first_llm.model_name)
        # print(f"结果: {result} (预期: True)")
        print("⏭️ 跳过实际删除操作（已注释）")
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(test_delete_llm_config())

