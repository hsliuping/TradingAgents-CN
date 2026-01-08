#!/usr/bin/env python3
"""
初始化大模型厂家数据脚本
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.database import init_db, get_mongo_db
from app.models.config import LLMProvider

async def init_providers():
    """初始化大模型厂家数据"""
    print("🚀 开始初始化大模型厂家数据...")
    
    # 初始化数据库连接
    await init_db()
    db = get_mongo_db()
    providers_collection = db.llm_providers
    
    # 预设厂家数据
    providers_data = [
        {
            "name": "openai",
            "display_name": "OpenAI",
            "description": "OpenAI是人工智能领域的领先公司，提供GPT系列模型",
            "website": "https://openai.com",
            "api_doc_url": "https://platform.openai.com/docs",
            "default_base_url": "https://api.openai.com/v1",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "image", "vision", "function_calling", "streaming"]
        },
        {
            "name": "anthropic",
            "display_name": "Anthropic",
            "description": "Anthropic专注于AI安全研究，提供Claude系列模型",
            "website": "https://anthropic.com",
            "api_doc_url": "https://docs.anthropic.com",
            "default_base_url": "https://api.anthropic.com",
            "is_active": True,
            "supported_features": ["chat", "completion", "function_calling", "streaming"]
        },
        {
            "name": "google",
            "display_name": "Google AI",
            "description": "Google的人工智能平台，提供Gemini系列模型",
            "website": "https://ai.google.dev",
            "api_doc_url": "https://ai.google.dev/docs",
            "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "vision", "function_calling", "streaming"]
        },
        {
            "name": "zhipu",
            "display_name": "智谱AI",
            "description": "智谱AI提供GLM系列中文大模型",
            "website": "https://zhipuai.cn",
            "api_doc_url": "https://open.bigmodel.cn/doc",
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"]
        },
        {
            "name": "deepseek",
            "display_name": "DeepSeek",
            "description": "DeepSeek提供高性能的AI推理服务",
            "website": "https://www.deepseek.com",
            "api_doc_url": "https://platform.deepseek.com/api-docs",
            "default_base_url": "https://api.deepseek.com",
            "is_active": True,
            "supported_features": ["chat", "completion", "function_calling", "streaming"]
        },
        {
            "name": "dashscope",
            "display_name": "阿里云百炼",
            "description": "阿里云百炼大模型服务平台，提供通义千问等模型",
            "website": "https://bailian.console.aliyun.com",
            "api_doc_url": "https://help.aliyun.com/zh/dashscope/",
            "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"]
        },
        {
            "name": "siliconflow",
            "display_name": "硅基流动",
            "description": "硅基流动提供高性价比的AI推理服务，支持多种开源模型",
            "website": "https://siliconflow.cn",
            "api_doc_url": "https://docs.siliconflow.cn",
            "default_base_url": "https://api.siliconflow.cn/v1",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"]
        },
        {
            "name": "302ai",
            "display_name": "302.AI",
            "description": "302.AI是企业级AI聚合平台，提供多种主流大模型的统一接口",
            "website": "https://302.ai",
            "api_doc_url": "https://doc.302.ai",
            "default_base_url": "https://api.302.ai/v1",
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "image", "vision", "function_calling", "streaming"]
        }
    ]
    
    # 清除现有数据
    await providers_collection.delete_many({})
    print("🧹 清除现有厂家数据")
    
    # 插入新数据
    for provider_data in providers_data:
        provider_data["created_at"] = datetime.utcnow()
        provider_data["updated_at"] = datetime.utcnow()
        
        result = await providers_collection.insert_one(provider_data)
        print(f"✅ 添加厂家: {provider_data['display_name']} (ID: {result.inserted_id})")
    
    print(f"🎉 成功初始化 {len(providers_data)} 个厂家数据")

if __name__ == "__main__":
    asyncio.run(init_providers())
