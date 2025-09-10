#!/usr/bin/env python3
"""
API配置快速修复脚本
解决OpenAI API密钥认证失败问题
"""

import os
import sys
from pathlib import Path

def main():
    """主修复函数"""
    print("🔧 TradingAgents-CN API配置修复工具")
    print("=" * 50)
    
    # 检查.env文件
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ 未找到.env文件")
        print("💡 请先复制.env.example为.env: cp .env.example .env")
        return
    
    print("📋 当前可用的LLM提供商选项:")
    print("1. 🇨🇳 DeepSeek V3 (推荐) - 性价比极高，中文优化")
    print("2. 🇨🇳 阿里百炼 - 国产稳定，中文优化") 
    print("3. 🌍 Google AI - 免费额度大，性能优秀")
    print("4. 🌐 OpenRouter - 聚合多模型，包含免费选项")
    print("5. 🔧 手动配置OpenAI")
    print()
    
    choice = input("请选择要配置的LLM提供商 (1-5): ").strip()
    
    if choice == "1":
        configure_deepseek()
    elif choice == "2":
        configure_dashscope()
    elif choice == "3":
        configure_google_ai()
    elif choice == "4":
        configure_openrouter()
    elif choice == "5":
        configure_openai()
    else:
        print("❌ 无效选择")
        return
    
    print("\n🎉 配置完成！请重新启动Web应用测试")

def configure_deepseek():
    """配置DeepSeek API"""
    print("\n🚀 配置DeepSeek V3 API")
    print("-" * 30)
    print("📝 获取API密钥步骤:")
    print("1. 访问: https://platform.deepseek.com/")
    print("2. 注册并登录账号")
    print("3. 进入API Keys页面")
    print("4. 创建新的API Key")
    print()
    
    api_key = input("请输入DeepSeek API密钥 (sk-开头): ").strip()
    if not api_key.startswith("sk-"):
        print("❌ API密钥格式错误，应以sk-开头")
        return
    
    # 更新.env文件
    update_env_file({
        "DEEPSEEK_API_KEY": api_key,
        "DEEPSEEK_ENABLED": "true"
    })
    
    # 更新默认配置
    update_default_config("deepseek", "deepseek-chat", "deepseek-chat")
    print("✅ DeepSeek配置完成")

def configure_dashscope():
    """配置阿里百炼API"""
    print("\n🇨🇳 配置阿里百炼 API")
    print("-" * 30)
    print("📝 获取API密钥步骤:")
    print("1. 访问: https://dashscope.aliyun.com/")
    print("2. 注册阿里云账号并开通百炼服务")
    print("3. 获取API密钥")
    print()
    
    api_key = input("请输入阿里百炼API密钥 (sk-开头): ").strip()
    if not api_key.startswith("sk-"):
        print("❌ API密钥格式错误，应以sk-开头")
        return
    
    # 更新.env文件
    update_env_file({
        "DASHSCOPE_API_KEY": api_key
    })
    
    # 更新默认配置
    update_default_config("dashscope", "qwen-plus", "qwen-turbo")
    print("✅ 阿里百炼配置完成")

def configure_google_ai():
    """配置Google AI API"""
    print("\n🌍 配置Google AI API")
    print("-" * 30)
    print("📝 获取API密钥步骤:")
    print("1. 访问: https://ai.google.dev/")
    print("2. 获取免费API密钥")
    print()
    
    api_key = input("请输入Google AI API密钥: ").strip()
    if not api_key:
        print("❌ API密钥不能为空")
        return
    
    # 更新.env文件
    update_env_file({
        "GOOGLE_API_KEY": api_key
    })
    
    # 更新默认配置
    update_default_config("google", "gemini-2.0-flash", "gemini-2.0-flash")
    print("✅ Google AI配置完成")

def configure_openrouter():
    """配置OpenRouter API"""
    print("\n🌐 配置OpenRouter API")
    print("-" * 30)
    print("📝 获取API密钥步骤:")
    print("1. 访问: https://openrouter.ai/")
    print("2. 注册账号获取API密钥")
    print("3. 可以使用免费模型")
    print()
    
    api_key = input("请输入OpenRouter API密钥 (sk-or-开头): ").strip()
    if not api_key.startswith("sk-or-"):
        print("❌ API密钥格式错误，应以sk-or-开头")
        return
    
    # 更新.env文件
    update_env_file({
        "OPENROUTER_API_KEY": api_key
    })
    
    # 更新默认配置
    update_default_config("openrouter", "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free")
    print("✅ OpenRouter配置完成")

def configure_openai():
    """配置OpenAI API"""
    print("\n🔧 配置OpenAI API")
    print("-" * 30)
    print("📝 获取API密钥步骤:")
    print("1. 访问: https://platform.openai.com/")
    print("2. 注册账号并获取API密钥")
    print("⚠️ 注意：需要国外网络访问")
    print()
    
    api_key = input("请输入OpenAI API密钥 (sk-开头): ").strip()
    if not api_key.startswith("sk-"):
        print("❌ API密钥格式错误，应以sk-开头")
        return
    
    # 更新.env文件
    update_env_file({
        "OPENAI_API_KEY": api_key
    })
    
    # 更新默认配置
    update_default_config("openai", "gpt-4o", "gpt-4o-mini")
    print("✅ OpenAI配置完成")

def update_env_file(updates):
    """更新.env文件"""
    env_file = Path(".env")
    content = env_file.read_text(encoding='utf-8')
    
    for key, value in updates.items():
        # 查找并替换现有配置
        import re
        pattern = rf'^{key}=.*$'
        replacement = f'{key}={value}'
        
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # 如果不存在，添加到文件末尾
            content += f'\n{key}={value}\n'
    
    env_file.write_text(content, encoding='utf-8')

def update_default_config(provider, deep_model, quick_model):
    """更新默认配置文件"""
    config_file = Path("tradingagents/default_config.py")
    if not config_file.exists():
        print("⚠️ 默认配置文件不存在，跳过更新")
        return
    
    content = config_file.read_text(encoding='utf-8')
    
    # 替换LLM提供商配置
    import re
    content = re.sub(r'"llm_provider":\s*"[^"]*"', f'"llm_provider": "{provider}"', content)
    content = re.sub(r'"deep_think_llm":\s*"[^"]*"', f'"deep_think_llm": "{deep_model}"', content)
    content = re.sub(r'"quick_think_llm":\s*"[^"]*"', f'"quick_think_llm": "{quick_model}"', content)
    
    config_file.write_text(content, encoding='utf-8')

if __name__ == "__main__":
    main()