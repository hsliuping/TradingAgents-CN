"""
错误信息格式化工具

将技术性错误转换为用户友好的错误提示，明确指出问题所在（数据源、大模型、配置等）
"""

import re
from typing import Dict, Optional, Tuple
from enum import Enum


class ErrorCategory(str, Enum):
    """错误类别"""
    LLM_API_KEY = "llm_api_key"  # 大模型 API Key 错误
    LLM_NETWORK = "llm_network"  # 大模型网络错误
    LLM_QUOTA = "llm_quota"  # 大模型配额/限流错误
    LLM_CONTENT_FILTER = "llm_content_filter"  # 大模型内容审核失败
    LLM_OTHER = "llm_other"  # 大模型其他错误

    DATA_SOURCE_API_KEY = "data_source_api_key"  # 数据源 API Key 错误
    DATA_SOURCE_NETWORK = "data_source_network"  # 数据源网络错误
    DATA_SOURCE_NOT_FOUND = "data_source_not_found"  # 数据源找不到数据
    DATA_SOURCE_OTHER = "data_source_other"  # 数据源其他错误

    STOCK_CODE_INVALID = "stock_code_invalid"  # 股票代码无效
    NETWORK = "network"  # 网络连接错误
    SYSTEM = "system"  # 系统错误
    UNKNOWN = "unknown"  # 未知错误


class ErrorFormatter:
    """错误信息格式化器"""
    
    # LLM 厂商名称映射
    LLM_PROVIDERS = {
        "google": "Google Gemini",
        "qwen": "阿里百炼（通义千问）",
        "dashscope": "阿里百炼（通义千问）",
        "qianfan": "百度千帆",
        "deepseek": "DeepSeek",
        "openai": "OpenAI",
        "openrouter": "OpenRouter",
        "aihubmix": "AiHubMix",
        "anthropic": "Anthropic Claude",
        "glm": "智谱AI",
        "zhipu": "智谱AI",
        "moonshot": "月之暗面（Kimi）",
    }
    
    # 数据源名称映射
    DATA_SOURCES = {
        "tushare": "Tushare",
        "akshare": "AKShare",
        "baostock": "BaoStock",
        "finnhub": "Finnhub",
        "mongodb": "MongoDB缓存",
    }
    
    @classmethod
    def format_error(cls, error_message: str, context: Optional[Dict] = None) -> Dict[str, str]:
        """
        格式化错误信息
        
        Args:
            error_message: 原始错误信息
            context: 上下文信息（可选），包含 llm_provider, model, data_source 等
            
        Returns:
            {
                "category": "错误类别",
                "title": "错误标题",
                "message": "用户友好的错误描述",
                "suggestion": "解决建议",
                "technical_detail": "技术细节（可选）"
            }
        """
        context = context or {}
        
        # 分类错误
        category, provider_or_source = cls._categorize_error(error_message, context)
        
        # 生成友好提示
        return cls._generate_friendly_message(category, provider_or_source, error_message, context)
    
    @classmethod
    def _categorize_error(cls, error_message: str, context: Dict) -> Tuple[ErrorCategory, Optional[str]]:
        """
        分类错误
        
        Returns:
            (错误类别, 相关厂商/数据源名称)
        """
        error_lower = error_message.lower()
        
        # 1. 检查是否是 LLM 相关错误
        llm_provider = context.get("llm_provider") or cls._extract_llm_provider(error_message)
        
        if llm_provider or any(keyword in error_lower for keyword in [
            "api key", "api_key", "apikey", "invalid_api_key", "authentication", 
            "unauthorized", "401", "403", "gemini", "openai", "dashscope", "qianfan", "qwen", "zhipu", "glm"
        ]):
            # LLM API Key 错误
            if any(keyword in error_lower for keyword in [
                "api key", "api_key", "apikey", "invalid", "authentication", 
                "unauthorized", "401", "invalid_api_key", "api key not valid"
            ]):
                return ErrorCategory.LLM_API_KEY, llm_provider
            
            # LLM 配额/限流错误
            if any(keyword in error_lower for keyword in [
                "quota", "rate limit", "too many requests", "429", "resource exhausted",
                "insufficient_quota", "billing"
            ]):
                return ErrorCategory.LLM_QUOTA, llm_provider

            # LLM 内容审核失败
            if any(keyword in error_lower for keyword in [
                "data_inspection_failed", "inappropriate content", "content filter",
                "内容审核", "敏感内容", "违规内容", "content policy"
            ]):
                return ErrorCategory.LLM_CONTENT_FILTER, llm_provider

            # LLM 网络错误
            if any(keyword in error_lower for keyword in [
                "connection", "network", "timeout", "unreachable", "dns", "ssl"
            ]):
                return ErrorCategory.LLM_NETWORK, llm_provider

            # LLM 其他错误
            return ErrorCategory.LLM_OTHER, llm_provider
        
        # 2. 检查是否是数据源相关错误
        data_source = context.get("data_source") or cls._extract_data_source(error_message)
        
        if data_source or any(keyword in error_lower for keyword in [
            "tushare", "akshare", "baostock", "finnhub", "数据源", "data source"
        ]):
            # 数据源 API Key 错误
            if any(keyword in error_lower for keyword in [
                "token", "api key", "authentication", "unauthorized"
            ]):
                return ErrorCategory.DATA_SOURCE_API_KEY, data_source
            
            # 数据源找不到数据
            if any(keyword in error_lower for keyword in [
                "not found", "no data", "empty", "无数据", "未找到"
            ]):
                return ErrorCategory.DATA_SOURCE_NOT_FOUND, data_source
            
            # 数据源网络错误
            if any(keyword in error_lower for keyword in [
                "connection", "network", "timeout"
            ]):
                return ErrorCategory.DATA_SOURCE_NETWORK, data_source
            
            # 数据源其他错误
            return ErrorCategory.DATA_SOURCE_OTHER, data_source
        
        # 3. 检查是否是股票代码错误
        if any(keyword in error_lower for keyword in [
            "股票代码", "stock code", "symbol", "invalid code", "代码无效"
        ]):
            return ErrorCategory.STOCK_CODE_INVALID, None
        
        # 4. 检查是否是网络错误
        if any(keyword in error_lower for keyword in [
            "connection", "network", "timeout", "unreachable", "dns"
        ]):
            return ErrorCategory.NETWORK, None
        
        # 5. 系统错误
        if any(keyword in error_lower for keyword in [
            "internal error", "server error", "500", "系统错误"
        ]):
            return ErrorCategory.SYSTEM, None
        
        # 6. 未知错误
        return ErrorCategory.UNKNOWN, None
    
    @classmethod
    def _extract_llm_provider(cls, error_message: str) -> Optional[str]:
        """从错误信息中提取 LLM 厂商"""
        error_lower = error_message.lower()
        for key, name in cls.LLM_PROVIDERS.items():
            if key in error_lower or name.lower() in error_lower:
                return key
        return None
    
    @classmethod
    def _extract_data_source(cls, error_message: str) -> Optional[str]:
        """从错误信息中提取数据源"""
        error_lower = error_message.lower()
        for key, name in cls.DATA_SOURCES.items():
            if key in error_lower or name.lower() in error_lower:
                return key
        return None
    
    @classmethod
    def _generate_friendly_message(
        cls, 
        category: ErrorCategory, 
        provider_or_source: Optional[str],
        original_error: str,
        context: Dict
    ) -> Dict[str, str]:
        """生成用户友好的错误信息"""
        
        # 获取友好的厂商/数据源名称
        friendly_name = None
        if provider_or_source:
            friendly_name = cls.LLM_PROVIDERS.get(provider_or_source) or \
                           cls.DATA_SOURCES.get(provider_or_source) or \
                           provider_or_source
        
        # 根据类别生成消息
        if category == ErrorCategory.LLM_API_KEY:
            return {
                "category": "大模型配置错误",
                "title": f"❌ {friendly_name or '大模型'} API Key 无效",
                "message": f"{friendly_name or '大模型'} 的 API Key 无效或未配置。",
                "suggestion": (
                    "请检查以下几点：\n"
                    f"1. 在「系统设置 → 大模型配置」中检查 {friendly_name or '该模型'} 的 API Key 是否正确\n"
                    "2. 确认 API Key 是否已激活且有效\n"
                    "3. 尝试重新生成 API Key 并更新配置\n"
                    "4. 或者切换到其他可用的大模型"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.LLM_QUOTA:
            return {
                "category": "大模型配额不足",
                "title": f"⚠️ {friendly_name or '大模型'} 配额不足或限流",
                "message": f"{friendly_name or '大模型'} 的调用配额已用完或触发了限流。",
                "suggestion": (
                    "请尝试以下解决方案：\n"
                    f"1. 检查 {friendly_name or '该模型'} 账户余额和配额\n"
                    "2. 等待一段时间后重试（可能是限流）\n"
                    "3. 升级账户套餐以获取更多配额\n"
                    "4. 切换到其他可用的大模型"
                ),
                "technical_detail": original_error
            }

        elif category == ErrorCategory.LLM_CONTENT_FILTER:
            return {
                "category": "内容审核失败",
                "title": f"🚫 {friendly_name or '大模型'} 内容审核未通过",
                "message": f"{friendly_name or '大模型'} 检测到输入内容可能包含不适当的内容，拒绝处理请求。",
                "suggestion": (
                    "这通常是由于分析内容中包含了敏感词汇或不当表述。建议：\n"
                    "1. 这可能是股票新闻或财报中包含了敏感词汇（如政治、暴力等）\n"
                    "2. 尝试切换到其他大模型（如 DeepSeek、Google Gemini）\n"
                    "3. 如果是阿里百炼，可以尝试使用 qwen-max 或 qwen-plus 模型\n"
                    "4. 联系技术支持报告此问题，我们会优化内容过滤逻辑\n"
                    "\n"
                    "💡 提示：不同大模型的内容审核策略不同，切换模型通常可以解决此问题。"
                ),
                "technical_detail": original_error
            }

        elif category == ErrorCategory.LLM_NETWORK:
            return {
                "category": "大模型网络错误",
                "title": f"🌐 无法连接到 {friendly_name or '大模型'}",
                "message": f"连接 {friendly_name or '大模型'} 服务时网络超时或连接失败。",
                "suggestion": (
                    "请检查以下几点：\n"
                    "1. 检查网络连接是否正常\n"
                    f"2. {friendly_name or '该服务'} 可能需要科学上网（如 Google Gemini）\n"
                    "3. 检查防火墙或代理设置\n"
                    "4. 稍后重试或切换到其他大模型"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.LLM_OTHER:
            return {
                "category": "大模型调用错误",
                "title": f"❌ {friendly_name or '大模型'} 调用失败",
                "message": f"调用 {friendly_name or '大模型'} 时发生错误。",
                "suggestion": (
                    "建议：\n"
                    "1. 检查模型配置是否正确\n"
                    "2. 查看技术细节了解具体错误\n"
                    "3. 尝试切换到其他大模型\n"
                    "4. 如问题持续，请联系技术支持"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.DATA_SOURCE_API_KEY:
            return {
                "category": "数据源配置错误",
                "title": f"❌ {friendly_name or '数据源'} Token/API Key 无效",
                "message": f"{friendly_name or '数据源'} 的 Token 或 API Key 无效或未配置。",
                "suggestion": (
                    "请检查以下几点：\n"
                    f"1. 在「系统设置 → 数据源配置」中检查 {friendly_name or '该数据源'} 的配置\n"
                    "2. 确认 Token/API Key 是否正确且有效\n"
                    "3. 检查账户是否已激活\n"
                    "4. 系统会自动尝试使用备用数据源"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.DATA_SOURCE_NOT_FOUND:
            return {
                "category": "数据获取失败",
                "title": f"📊 {friendly_name or '数据源'} 未找到数据",
                "message": f"从 {friendly_name or '数据源'} 获取股票数据失败，可能是股票代码不存在或数据暂未更新。",
                "suggestion": (
                    "建议：\n"
                    "1. 检查股票代码是否正确\n"
                    "2. 确认该股票是否已上市\n"
                    "3. 系统会自动尝试使用其他数据源\n"
                    "4. 如果是新股，可能需要等待数据更新"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.DATA_SOURCE_NETWORK:
            return {
                "category": "数据源网络错误",
                "title": f"🌐 无法连接到 {friendly_name or '数据源'}",
                "message": f"连接 {friendly_name or '数据源'} 时网络超时或连接失败。",
                "suggestion": (
                    "请检查：\n"
                    "1. 网络连接是否正常\n"
                    "2. 数据源服务是否可用\n"
                    "3. 系统会自动尝试使用备用数据源\n"
                    "4. 稍后重试"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.DATA_SOURCE_OTHER:
            return {
                "category": "数据源错误",
                "title": f"❌ {friendly_name or '数据源'} 调用失败",
                "message": f"从 {friendly_name or '数据源'} 获取数据时发生错误。",
                "suggestion": (
                    "建议：\n"
                    "1. 系统会自动尝试使用备用数据源\n"
                    "2. 查看技术细节了解具体错误\n"
                    "3. 稍后重试\n"
                    "4. 如问题持续，请联系技术支持"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.STOCK_CODE_INVALID:
            return {
                "category": "股票代码错误",
                "title": "❌ 股票代码无效",
                "message": "输入的股票代码格式不正确或不存在。",
                "suggestion": (
                    "请检查：\n"
                    "1. A股代码格式：6位数字（如 000001、600000）\n"
                    "2. 港股代码格式：5位数字（如 00700）\n"
                    "3. 美股代码格式：股票代码（如 AAPL、TSLA）\n"
                    "4. 确认股票是否已上市"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.NETWORK:
            return {
                "category": "网络连接错误",
                "title": "🌐 网络连接失败",
                "message": "网络连接超时或无法访问服务。",
                "suggestion": (
                    "请检查：\n"
                    "1. 网络连接是否正常\n"
                    "2. 服务器是否可访问\n"
                    "3. 防火墙或代理设置\n"
                    "4. 稍后重试"
                ),
                "technical_detail": original_error
            }
        
        elif category == ErrorCategory.SYSTEM:
            return {
                "category": "系统错误",
                "title": "⚠️ 系统内部错误",
                "message": "系统处理请求时发生内部错误。",
                "suggestion": (
                    "建议：\n"
                    "1. 稍后重试\n"
                    "2. 如问题持续，请联系技术支持\n"
                    "3. 提供技术细节以便排查问题"
                ),
                "technical_detail": original_error
            }
        
        else:  # UNKNOWN
            return {
                "category": "未知错误",
                "title": "❌ 分析失败",
                "message": "分析过程中发生错误。",
                "suggestion": (
                    "建议：\n"
                    "1. 检查输入参数是否正确\n"
                    "2. 查看技术细节了解具体错误\n"
                    "3. 稍后重试\n"
                    "4. 如问题持续，请联系技术支持"
                ),
                "technical_detail": original_error
            }

