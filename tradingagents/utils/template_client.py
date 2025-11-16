"""
提示词模板客户端 - 用于Agent从模板系统获取提示词
"""

import os
import requests
from typing import Optional, Dict, Any
from tradingagents.utils.logging_init import get_logger

logger = get_logger("template_client")


class TemplateClient:
    """提示词模板客户端"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        初始化模板客户端
        
        Args:
            base_url: API基础URL，默认从环境变量TEMPLATE_API_URL读取，或使用http://localhost:8000
        """
        self.base_url = base_url or os.getenv("TEMPLATE_API_URL", "http://localhost:8000")
        self.timeout = 10  # 请求超时时间（秒）
        
    def get_effective_template(
        self,
        agent_type: str,
        agent_name: str,
        user_id: Optional[str] = None,
        preference_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取有效模板（用户模板优先，系统模板兜底）
        
        Args:
            agent_type: Agent类型（analysts, researchers, debators, managers, trader）
            agent_name: Agent名称
            user_id: 用户ID（可选）
            preference_id: 偏好ID（可选）
            
        Returns:
            模板内容字典，包含system_prompt、tool_guidance、analysis_requirements等字段
            如果获取失败返回None
        """
        try:
            # 构建请求参数
            params = {
                "agent_type": agent_type,
                "agent_name": agent_name
            }
            if user_id:
                params["user_id"] = user_id
            if preference_id:
                params["preference_id"] = preference_id
            
            # 发送请求
            url = f"{self.base_url}/api/v1/user-template-configs/effective-template"
            logger.debug(f"[TemplateClient] 请求URL: {url}")
            logger.debug(f"[TemplateClient] 请求参数: {params}")
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[TemplateClient] 成功获取模板: {agent_type}/{agent_name}")
                return data
            else:
                logger.warning(
                    f"[TemplateClient] 获取模板失败: {response.status_code} - {response.text}"
                )
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"[TemplateClient] 请求超时: {self.timeout}秒")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"[TemplateClient] 连接失败: {self.base_url}")
            return None
        except Exception as e:
            logger.error(f"[TemplateClient] 获取模板异常: {e}")
            return None
    
    def format_template(
        self,
        template: Dict[str, Any],
        variables: Dict[str, str]
    ) -> Dict[str, str]:
        """
        格式化模板，替换变量
        
        Args:
            template: 模板内容字典
            variables: 变量字典，如 {"ticker": "AAPL", "company_name": "Apple Inc."}
            
        Returns:
            格式化后的模板内容字典
        """
        try:
            content = template.get("content", {})
            formatted = {}
            
            for key, value in content.items():
                if isinstance(value, str):
                    # 替换所有变量
                    formatted_value = value
                    for var_name, var_value in variables.items():
                        placeholder = "{" + var_name + "}"
                        formatted_value = formatted_value.replace(placeholder, str(var_value))
                    formatted[key] = formatted_value
                else:
                    formatted[key] = value
            
            return formatted
            
        except Exception as e:
            logger.error(f"[TemplateClient] 格式化模板异常: {e}")
            return {}


# 全局单例
_template_client = None


def get_template_client() -> TemplateClient:
    """获取全局模板客户端单例"""
    global _template_client
    if _template_client is None:
        _template_client = TemplateClient()
    return _template_client


def get_agent_prompt(
    agent_type: str,
    agent_name: str,
    variables: Dict[str, str],
    user_id: Optional[str] = None,
    preference_id: Optional[str] = None,
    fallback_prompt: Optional[str] = None
) -> str:
    """
    获取Agent提示词（便捷函数）
    
    Args:
        agent_type: Agent类型
        agent_name: Agent名称
        variables: 模板变量字典
        user_id: 用户ID（可选）
        preference_id: 偏好ID（可选）
        fallback_prompt: 降级提示词（当API不可用时使用）
        
    Returns:
        完整的提示词字符串
    """
    client = get_template_client()
    
    # 尝试从API获取模板
    template = client.get_effective_template(agent_type, agent_name, user_id, preference_id)
    
    if template:
        # 格式化模板
        formatted = client.format_template(template, variables)
        
        # 组合完整提示词
        parts = []
        if formatted.get("system_prompt"):
            parts.append(formatted["system_prompt"])
        if formatted.get("tool_guidance"):
            parts.append("\n\n" + formatted["tool_guidance"])
        if formatted.get("analysis_requirements"):
            parts.append("\n\n" + formatted["analysis_requirements"])
        
        return "\n".join(parts)
    else:
        # 降级：使用硬编码提示词
        logger.warning(
            f"[TemplateClient] 无法获取模板，使用降级提示词: {agent_type}/{agent_name}"
        )
        return fallback_prompt or "请进行分析。"

