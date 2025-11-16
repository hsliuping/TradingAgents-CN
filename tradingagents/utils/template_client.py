"""
提示词模板客户端 - 用于Agent从模板系统获取提示词

直接连接MongoDB获取模板，不通过HTTP API
"""

import os
from typing import Optional, Dict, Any
from tradingagents.agents.utils.agent_context import AgentContext
from pymongo import MongoClient
from bson import ObjectId
from tradingagents.utils.logging_init import get_logger

logger = get_logger("template_client")


class TemplateClient:
    """提示词模板客户端 - 直接连接MongoDB"""

    def __init__(self, mongo_uri: Optional[str] = None, db_name: Optional[str] = None):
        """
        初始化模板客户端

        Args:
            mongo_uri: MongoDB连接字符串，默认从环境变量MONGODB_CONNECTION_STRING读取
            db_name: 数据库名称，默认从环境变量MONGODB_DATABASE_NAME读取
        """
        self.mongo_uri = mongo_uri or os.getenv(
            "MONGODB_CONNECTION_STRING",
            "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
        )
        self.db_name = db_name or os.getenv("MONGODB_DATABASE_NAME", "tradingagents")

        # 创建MongoDB连接
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        self.templates_collection = self.db.prompt_templates
        self.configs_collection = self.db.user_template_configs

        logger.info(f"✅ 模板客户端初始化成功: {self.db_name}")

    def get_effective_template(
        self,
        agent_type: str,
        agent_name: str,
        user_id: Optional[str] = None,
        preference_id: Optional[str] = None,
        context: Optional[AgentContext] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取有效模板（用户模板优先，系统模板兜底）

        Args:
            agent_type: Agent类型（analysts, researchers, debators, managers, trader）
            agent_name: Agent名称
            user_id: 用户ID（可选）
            preference_id: 偏好ID（可选，默认为neutral）

        Returns:
            模板内容字典，包含system_prompt、tool_guidance、analysis_requirements等字段
            如果获取失败返回None
        """
        try:
            logger.info(
                f"[diagnose] input agent_type={agent_type} agent_name={agent_name} "
                f"user_id={user_id} pref={preference_id} ctx_user={getattr(context,'user_id',None)} ctx_pref={getattr(context,'preference_id',None)}"
            )
            # 默认偏好为neutral
            preference_id = (context.preference_id if context and context.preference_id else preference_id) or "neutral"
            user_id = (context.user_id if context and context.user_id else user_id)

            # 1. 如果指定了user_id，按活跃配置选择（不以偏好为筛选条件）
            if user_id:
                user_oid = None
                try:
                    user_oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
                except Exception:
                    user_oid = None

                if user_oid:
                    config_query = {
                        "user_id": user_oid,
                        "agent_type": agent_type,
                        "agent_name": agent_name,
                        "is_active": True
                    }
                    logger.info(f"[diagnose] config_query={config_query}")
                    config = self.configs_collection.find_one(config_query)

                    if config and config.get("template_id"):
                        template_oid = None
                        try:
                            tid = config["template_id"]
                            template_oid = tid if isinstance(tid, ObjectId) else ObjectId(str(tid))
                        except Exception:
                            template_oid = None
                            logger.info(f"[diagnose] template_id_convert_failed raw={config.get('template_id')}")

                        template = self.templates_collection.find_one({"_id": template_oid}) if template_oid else None
                        if template:
                            logger.info(
                                f"[diagnose] path=user_active_config config_id={config.get('_id')} "
                                f"template_id={template.get('_id')} version={template.get('version')} pref={config.get('preference_id')}"
                            )
                            logger.info(
                                f"✅ 获取用户模板: {agent_type}/{agent_name} "
                                f"(user_id={user_id}, preference={preference_id})"
                            )
                            content = template.get("content") or {}
                            content["source"] = "user"
                            content["template_id"] = str(template.get("_id"))
                            content["version"] = template.get("version", 1)
                            content["selected_preference"] = config.get("preference_id") or preference_id
                            return content
                        else:
                            logger.info("[diagnose] user_config_found_but_template_lookup_failed")

            # 2. 查找系统默认模板
            system_query = {
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": preference_id,
                "is_system": True,
                "status": "active"
            }

            system_template = self.templates_collection.find_one(system_query)

            if system_template:
                logger.info(
                    f"✅ 获取系统模板: {agent_type}/{agent_name} (preference={preference_id})"
                )
                logger.info(f"[diagnose] path=system_fallback system_query={system_query}")
                content = system_template.get("content") or {}
                content["source"] = "system"
                content["template_id"] = str(system_template.get("_id"))
                content["version"] = system_template.get("version", 1)
                content["selected_preference"] = preference_id
                return content

            # 3. 如果没有找到指定偏好的模板，尝试获取neutral偏好的模板
            if preference_id != "neutral":
                logger.warning(
                    f"⚠️ 未找到{preference_id}偏好的模板，尝试获取neutral偏好"
                )
                neutral_query = {
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "preference_type": "neutral",
                    "is_system": True,
                    "status": "active"
                }
                neutral_template = self.templates_collection.find_one(neutral_query)
                if neutral_template:
                    logger.info(f"✅ 获取neutral系统模板: {agent_type}/{agent_name}")
                    return neutral_template.get("content")

            logger.error(
                f"❌ 未找到任何可用模板: {agent_type}/{agent_name} (preference={preference_id})"
            )
            return None

        except Exception as e:
            logger.error(f"❌ 获取模板异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def format_template(
        self,
        template_content: Dict[str, Any],
        variables: Dict[str, str]
    ) -> Dict[str, str]:
        """
        格式化模板，替换变量

        Args:
            template_content: 模板内容字典（从get_effective_template返回）
            variables: 变量字典，如 {"ticker": "AAPL", "company_name": "Apple Inc."}

        Returns:
            格式化后的模板内容字典
        """
        try:
            formatted = {}

            for key, value in template_content.items():
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
    fallback_prompt: Optional[str] = None,
    context: Optional[AgentContext] = None
) -> str:
    """
    获取Agent提示词（便捷函数）

    Args:
        agent_type: Agent类型
        agent_name: Agent名称
        variables: 模板变量字典（如ticker、company_name、current_date等）
        user_id: 用户ID（可选）
        preference_id: 偏好ID（可选）
        fallback_prompt: 降级提示词（当API不可用时使用）
        
    Returns:
        完整的提示词字符串
    """
    try:
        client = get_template_client()

        # 从MongoDB获取模板
        template_content = client.get_effective_template(agent_type, agent_name, user_id, preference_id, context)

        if template_content:
            # 格式化模板
            formatted = client.format_template(template_content, variables)

            # 组合完整提示词
            parts = []
            if formatted.get("system_prompt"):
                parts.append(formatted["system_prompt"])
            if formatted.get("tool_guidance"):
                parts.append("\n\n" + formatted["tool_guidance"])
            if formatted.get("analysis_requirements"):
                parts.append("\n\n" + formatted["analysis_requirements"])

            prompt = "\n".join(parts)
            logger.info(f"✅ 成功生成提示词: {agent_type}/{agent_name} (长度: {len(prompt)})")
            return prompt
        else:
            # 降级：使用硬编码提示词
            logger.warning(
                f"⚠️ 无法获取模板，使用降级提示词: {agent_type}/{agent_name}"
            )
            return fallback_prompt or "请进行分析。"

    except Exception as e:
        logger.error(f"❌ 获取提示词异常: {e}")
        return fallback_prompt or "请进行分析。"


def close_template_client():
    """关闭全局模板客户端连接"""
    global _template_client
    if _template_client is not None:
        _template_client.client.close()
        _template_client = None
        logger.info("✅ 模板客户端连接已关闭")

