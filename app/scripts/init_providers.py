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
from tradingagents.llm_clients.provider_keys import canonical_aliases

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
            "test_model": "gpt-3.5-turbo",
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
            "test_model": "claude-3-haiku-20240307",
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
            "test_model": "gemini-2.0-flash-exp",
            "supported_features": ["chat", "completion", "embedding", "vision", "function_calling", "streaming"]
        },
        {
            "name": "glm",
            "display_name": "智谱AI",
            "description": "智谱AI提供GLM系列中文大模型",
            "website": "https://zhipuai.cn",
            "api_doc_url": "https://open.bigmodel.cn/doc",
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "aliases": canonical_aliases("glm"),
            "is_active": True,
            "test_model": "glm-4",
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
            "test_model": "deepseek-chat",
            "supported_features": ["chat", "completion", "function_calling", "streaming"]
        },
        {
            "name": "qwen",
            "display_name": "阿里云百炼",
            "description": "阿里云百炼大模型服务平台，提供通义千问等模型",
            "website": "https://bailian.console.aliyun.com",
            "api_doc_url": "https://help.aliyun.com/zh/dashscope/",
            "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "aliases": canonical_aliases("qwen"),
            "is_active": True,
            "test_model": "qwen-turbo",
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
            "test_model": "Qwen/Qwen2.5-7B-Instruct",
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"]
        },
        {
            "name": "atlascloud",
            "display_name": "Atlas Cloud",
            "description": "Atlas Cloud 提供 OpenAI 兼容的统一模型接口，可接入多种文本模型。",
            "website": "https://www.atlascloud.ai",
            "api_doc_url": "https://www.atlascloud.ai/docs",
            "default_base_url": "https://api.atlascloud.ai/v1",
            "aliases": canonical_aliases("atlascloud"),
            "is_active": True,
            "supported_features": ["chat", "completion", "vision", "function_calling", "streaming"]
        },
        {
            "name": "302ai",
            "display_name": "302.AI",
            "description": "302.AI是企业级AI聚合平台，提供多种主流大模型的统一接口",
            "website": "https://302.ai",
            "api_doc_url": "https://doc.302.ai",
            "default_base_url": "https://api.302.ai/v1",
            "is_active": True,
            "test_model": "gpt-3.5-turbo",
            "supported_features": ["chat", "completion", "embedding", "image", "vision", "function_calling", "streaming"]
        },
        {
            "name": "aihubmix",
            "display_name": "AIHubMix",
            "description": "AIHubMix 深度适配 OpenAI、Claude、Gemini、DeepSeek、智谱、千问 等全球顶级模型，多模型交叉验证，分析结论更可靠；无限并发永远在线，A股、港股、美股行情随时可分析，不卡顿不排队；内置 coding-glm-5.1-free 等多款免费模型，零成本体验 AI 分析；按量计费、价格透明，长期使用性价比远超单一厂商。",
            "website": "https://aihubmix.com/?aff=2rIi",
            "api_doc_url": "https://docs.aihubmix.com/cn/quick-start",
            "default_base_url": "https://aihubmix.com/v1",
            "is_active": True,
            "test_model": "gpt-3.5-turbo",
            "supported_features": ["chat", "completion", "embedding", "vision", "function_calling", "streaming"]
        },
        {
            "name": "volcengine",
            "display_name": "火山方舟",
            "description": "火山方舟集成了字节自研豆包模型+满血版开源 SOTA模型，覆盖文本、VLM、图像生成，全模态一站配齐：Seed-2.1、Seedream-5.0、GLM-5.2、DeepSeek等。不止编程、更能解决 Agent 复杂长程任务",
            "website": "https://www.volcengine.com/product/ark?utm_campaign=hw&utm_content=TradingAgents-CN&utm_medium=devrel-1&utm_source=OWO&utm_term=TradingAgents-CN",
            "api_doc_url": "https://docs.volcengine.com/docs/82379/2373738?lang=zh&utm_content=TradingAgents-CN&utm_medium=devrel-1&utm_source=OWO&utm_term=TradingAgents-CN",
            "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "is_active": True,
            "test_model": "Doubao-Seed-2.1-turbo",
            "supported_features": ["chat", "completion", "embedding", "image", "vision", "function_calling", "streaming"],
            "default_embedding_model": "doubao-seed-evolving"
        },
        {
            "name": "volcengine_coding",
            "display_name": "火山方舟编程",
            "description": "火山方舟 Coding Plan 是为开发者量身定制的 AI 编程订阅服务，支持 Doubao-Seed-Code、DeepSeek-V4 系列、GLM-5.2、Kimi-K2.7 等主流编程模型按需切换。兼容 Claude Code、Cursor、Cline、OpenCode、TRAE 等主流编程工具，套餐额度共享。提供 Lite（40元/月）和 Pro（200元/月）两档套餐，适配不同开发强度。注意：Coding Plan 仅限 AI 编程工具使用，Base URL 与 Agent Plan 不同。",
            "website": "https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=TradingAgents-CN",
            "api_doc_url": "https://www.volcengine.com/docs/82379/1925114",
            "default_base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "is_active": True,
            "test_model": "doubao-seed-2.0-code",
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"],
            "default_embedding_model": "doubao-embedding-vision"
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
