# API Key Checker Tool

"""Check if all required API keys are configured"""

import os

def check_api_keys():
    """检查所有必要的API密钥是否已配置"""

    # 检查各个API密钥
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    
    # 构建详细状态
    details = {
        "DASHSCOPE_API_KEY": {
            "configured": bool(dashscope_key),
            "display": f"{dashscope_key[:12]}..." if dashscope_key else "Not configured",
            "required": True,
            "description": "Alibaba Qwen API Key"
        },
        "FINNHUB_API_KEY": {
            "configured": bool(finnhub_key),
            "display": f"{finnhub_key[:12]}..." if finnhub_key else "Not configured",
            "required": True,
            "description": "Financial Data API Key"
        },
        "OPENAI_API_KEY": {
            "configured": bool(openai_key),
            "display": f"{openai_key[:12]}..." if openai_key else "Not configured",
            "required": False,
            "description": "OpenAI API Key"
        },
        "ANTHROPIC_API_KEY": {
            "configured": bool(anthropic_key),
            "display": f"{anthropic_key[:12]}..." if anthropic_key else "Not configured",
            "required": False,
            "description": "Anthropic API Key"
        },
        "GOOGLE_API_KEY": {
            "configured": bool(google_key),
            "display": f"{google_key[:12]}..." if google_key else "Not configured",
            "required": False,
            "description": "Google AI API Key"
        }
    }
    
    # 检查必需的API密钥
    required_keys = [key for key, info in details.items() if info["required"]]
    missing_required = [key for key in required_keys if not details[key]["configured"]]
    
    return {
        "all_configured": len(missing_required) == 0,
        "required_configured": len(missing_required) == 0,
        "missing_required": missing_required,
        "details": details,
        "summary": {
            "total": len(details),
            "configured": sum(1 for info in details.values() if info["configured"]),
            "required": len(required_keys),
            "required_configured": len(required_keys) - len(missing_required)
        }
    }

def get_api_key_status_message():
    """获取API密钥状态消息"""
    
    status = check_api_keys()
    
    if status["all_configured"]:
        return "✅ All required API keys are configured"
    elif status["required_configured"]:
        return "✅ Required API keys are configured, optional API keys are not configured"
    else:
        missing = ", ".join(status["missing_required"])
        return f"❌ Missing required API keys: {missing}"

def validate_api_key_format(key_type, api_key):
    """验证API密钥格式"""
    
    if not api_key:
        return False, "API key cannot be empty"
    
    # 基本长度检查
    if len(api_key) < 10:
        return False, "API key is too short"
    
    # 特定格式检查
    if key_type == "DASHSCOPE_API_KEY":
        if not api_key.startswith("sk-"):
            return False, "Alibaba Qwen API key must start with 'sk-'"
    elif key_type == "OPENAI_API_KEY":
        if not api_key.startswith("sk-"):
            return False, "OpenAI API key must start with 'sk-'"
    
    return True, "API key format is correct"

def test_api_connection(key_type, api_key):
    """测试API连接（简单验证）"""
    
    # 这里可以添加实际的API连接测试
    # 为了简化，现在只做格式验证
    
    is_valid, message = validate_api_key_format(key_type, api_key)
    
    if not is_valid:
        return False, message
    
    # 可以在这里添加实际的API调用测试
    # 例如：调用一个简单的API端点验证密钥有效性
    
    return True, "API key validation passed"
