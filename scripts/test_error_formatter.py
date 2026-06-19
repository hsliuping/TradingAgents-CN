"""
测试错误格式化器

验证各种错误类型的格式化输出
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.error_formatter import ErrorFormatter


def print_formatted_error(title: str, error_message: str, context: dict = None):
    """打印格式化后的错误"""
    print(f"\n{'='*80}")
    print(f"测试: {title}")
    print(f"{'='*80}")
    print(f"原始错误: {error_message}")
    print(f"上下文: {context}")
    print(f"{'-'*80}")
    
    result = ErrorFormatter.format_error(error_message, context)
    
    print(f"类别: {result['category']}")
    print(f"\n{result['title']}")
    print(f"\n{result['message']}")
    print(f"\n{result['suggestion']}")
    print(f"\n技术细节: {result['technical_detail']}")
    print(f"{'='*80}\n")


def main():
    """测试各种错误类型"""
    
    print("🧪 错误格式化器测试\n")
    
    # 1. Google Gemini API Key 错误
    print_formatted_error(
        "Google Gemini API Key 错误",
        "Error code: 401 - {'error': {'message': 'Incorrect API key provided.', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}, 'request_id': 'cf6db712-0b54-4f4d-a21d-b60b255a38a9'}",
        {"llm_provider": "google"}
    )
    
    # 2. 阿里百炼配额不足
    print_formatted_error(
        "阿里百炼配额不足",
        "Error: Resource exhausted. Quota exceeded for model qwen-plus. Please check your billing.",
        {"llm_provider": "dashscope", "model": "qwen-plus"}
    )
    
    # 3. DeepSeek 网络错误
    print_formatted_error(
        "DeepSeek 网络错误",
        "Connection timeout: Failed to connect to api.deepseek.com after 30 seconds",
        {"llm_provider": "deepseek"}
    )
    
    # 4. Tushare Token 错误
    print_formatted_error(
        "Tushare Token 错误",
        "❌ [数据来源: Tushare失败] Token无效或未配置",
        {"data_source": "tushare"}
    )
    
    # 5. AKShare 数据未找到
    print_formatted_error(
        "AKShare 数据未找到",
        "❌ [数据来源: AKShare失败] 未找到股票代码 999999 的数据",
        {"data_source": "akshare"}
    )
    
    # 6. 股票代码无效
    print_formatted_error(
        "股票代码无效",
        "股票代码格式不正确: ABC123。A股代码应为6位数字。",
        {}
    )
    
    # 7. 网络连接错误
    print_formatted_error(
        "网络连接错误",
        "Network connection failed: Unable to reach server at localhost:8100",
        {}
    )
    
    # 8. 系统内部错误
    print_formatted_error(
        "系统内部错误",
        "Internal server error: Database connection pool exhausted",
        {}
    )
    
    # 9. 未知错误
    print_formatted_error(
        "未知错误",
        "Something went wrong during analysis",
        {}
    )
    
    # 10. OpenAI API Key 错误（从错误信息中自动识别）
    print_formatted_error(
        "OpenAI API Key 错误（自动识别）",
        "OpenAI API error: Invalid API key provided",
        {}
    )
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    main()

