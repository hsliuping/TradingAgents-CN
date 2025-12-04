"""
API密钥检查工具
"""

import os

def check_api_keys():
    """检查所有必要的API密钥是否已配置"""

    # 检查各个API密钥
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    qianfan_key = os.getenv("QIANFAN_API_KEY")

    
    # 构建详细状态
    details = {
        "DASHSCOPE_API_KEY": {
            "configured": bool(dashscope_key),
            "display": f"{dashscope_key[:12]}..." if dashscope_key else "未配置",
            "required": True,
            "description": "阿里百炼API密钥"
        },
        "FINNHUB_API_KEY": {
            "configured": bool(finnhub_key),
            "display": f"{finnhub_key[:12]}..." if finnhub_key else "未配置",
            "required": True,
            "description": "金融数据API密钥"
        },
        "OPENAI_API_KEY": {
            "configured": bool(openai_key),
            "display": f"{openai_key[:12]}..." if openai_key else "未配置",
            "required": False,
            "description": "OpenAI API密钥"
        },
        "ANTHROPIC_API_KEY": {
            "configured": bool(anthropic_key),
            "display": f"{anthropic_key[:12]}..." if anthropic_key else "未配置",
            "required": False,
            "description": "Anthropic API密钥"
        },
        "GOOGLE_API_KEY": {
            "configured": bool(google_key),
            "display": f"{google_key[:12]}..." if google_key else "未配置",
            "required": False,
            "description": "Google AI API密钥"
        },
        "QIANFAN_ACCESS_KEY": {
            "configured": bool(qianfan_key),
            "display": f"{qianfan_key[:16]}..." if qianfan_key else "未配置",
            "required": False,
            "description": "文心一言（千帆）API Key（OpenAI兼容），一般以 bce-v3/ 开头"
        },
        # QIANFAN_SECRET_KEY 不再用于OpenAI兼容路径，仅保留给脚本示例使用
        # "QIANFAN_SECRET_KEY": {
        #     "configured": bool(qianfan_sk),
        #     "display": f"{qianfan_sk[:12]}..." if qianfan_sk else "未配置",
        #     "required": False,
        #     "description": "文心一言（千帆）Secret Key (仅脚本示例)"
        # },
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
        return "✅ 所有必需的API密钥已配置完成"
    elif status["required_configured"]:
        return "✅ 必需的API密钥已配置，可选API密钥未配置"
    else:
        missing = ", ".join(status["missing_required"])
        return f"❌ 缺少必需的API密钥: {missing}"

def validate_api_key_format(key_type, api_key):
    """验证API密钥格式"""
    
    if not api_key:
        return False, "API密钥不能为空"
    
    # 基本长度检查
    if len(api_key) < 10:
        return False, "API密钥长度过短"
    
    # 特定格式检查
    if key_type == "DASHSCOPE_API_KEY":
        if not api_key.startswith("sk-"):
            return False, "阿里百炼API密钥应以'sk-'开头"
    elif key_type == "OPENAI_API_KEY":
        if not api_key.startswith("sk-"):
            return False, "OpenAI API密钥应以'sk-'开头"
    elif key_type == "QIANFAN_API_KEY":
        if not api_key.startswith("bce-v3/"):
            return False, "千帆 API Key（OpenAI兼容）应以 'bce-v3/' 开头"
    
    return True, "API密钥格式正确"

def test_api_connection(key_type, api_key):
    """测试API连接（简单验证）"""
    
    # 这里可以添加实际的API连接测试
    # 为了简化，现在只做格式验证
    
    is_valid, message = validate_api_key_format(key_type, api_key)
    
    if not is_valid:
        return False, message
    
    # 可以在这里添加实际的API调用测试
    # 例如：调用一个简单的API端点验证密钥有效性
    
    return True, "API密钥验证通过"
