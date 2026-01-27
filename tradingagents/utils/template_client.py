"""
提示词模板客户端 - 用于Agent从模板系统获取提示词

直接连接MongoDB获取模板，不通过HTTP API
"""

import os
import re
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
            mongo_uri: MongoDB连接字符串，默认从环境变量构建
            db_name: 数据库名称，默认从环境变量读取
        """
        from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

        self.mongo_uri = mongo_uri or build_mongodb_connection_string()
        self.db_name = db_name or get_mongodb_database_name()

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
        获取有效模板（调试模板优先，用户模板次之，系统模板兜底）

        Args:
            agent_type: Agent类型（analysts, researchers, debators, managers, trader）
            agent_name: Agent名称
            user_id: 用户ID（可选）
            preference_id: 偏好ID（可选，默认为neutral）
            context: AgentContext对象，包含调试模式信息

        Returns:
            模板内容字典，包含system_prompt、tool_guidance、analysis_requirements等字段
            如果获取失败返回None
        """
        try:
            # 兼容 context 为 dict 或 AgentContext 对象
            ctx_user = None
            ctx_pref = None
            is_debug_mode = False
            debug_template_id = None

            if context:
                if isinstance(context, dict):
                    ctx_user = context.get('user_id')
                    ctx_pref = context.get('preference_id')
                    is_debug_mode = context.get('is_debug_mode', False)
                    debug_template_id = context.get('debug_template_id') if is_debug_mode else None
                else:
                    ctx_user = getattr(context, 'user_id', None)
                    ctx_pref = getattr(context, 'preference_id', None)
                    is_debug_mode = getattr(context, 'is_debug_mode', False)
                    debug_template_id = getattr(context, 'debug_template_id', None) if is_debug_mode else None

            logger.info(
                f"[diagnose] input agent_type={agent_type} agent_name={agent_name} "
                f"user_id={user_id} pref={preference_id} ctx_user={ctx_user} ctx_pref={ctx_pref}"
            )

            if is_debug_mode and debug_template_id:
                logger.info(f"🔍 [调试模式] 使用调试模板ID: {debug_template_id}")
                try:
                    template_oid = debug_template_id if isinstance(debug_template_id, ObjectId) else ObjectId(str(debug_template_id))
                    debug_template = self.templates_collection.find_one({"_id": template_oid})

                    if debug_template:
                        logger.info(
                            f"✅ [调试模式] 成功获取调试模板: {agent_type}/{agent_name} "
                            f"(template_id={debug_template_id})"
                        )
                        content = debug_template.get("content") or {}
                        content["source"] = "debug"
                        content["template_id"] = str(debug_template.get("_id"))
                        content["version"] = debug_template.get("version", 1)
                        content["is_debug"] = True
                        return content
                    else:
                        logger.warning(f"⚠️ [调试模式] 调试模板不存在: {debug_template_id}，降级到正常流程")
                except Exception as e:
                    logger.error(f"❌ [调试模式] 获取调试模板失败: {e}，降级到正常流程")

            # 默认偏好为neutral
            # 兼容 context 为 dict 或 AgentContext 对象
            if context:
                if isinstance(context, dict):
                    # context 是字典
                    preference_id = context.get("preference_id") or preference_id
                    user_id = context.get("user_id") or user_id
                else:
                    # context 是 AgentContext 对象
                    preference_id = context.preference_id if context.preference_id else preference_id
                    user_id = context.user_id if context.user_id else user_id
            preference_id = preference_id or "neutral"

            # 1. 优先级1：如果指定了user_id，先检查用户在agent配置中是否设置了模板
            user_config_template = None
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

                        # 🔥 只使用已发布状态的模板
                        template = self.templates_collection.find_one({
                            "_id": template_oid,
                            "status": "active"
                        }) if template_oid else None

                        if template:
                            logger.info(
                                f"[diagnose] path=user_active_config config_id={config.get('_id')} "
                                f"template_id={template.get('_id')} version={template.get('version')} pref={config.get('preference_id')}"
                            )
                            logger.info(
                                f"✅ [优先级1] 获取用户在agent配置中设置的模板: {agent_type}/{agent_name} "
                                f"(user_id={user_id}, template_id={template_oid})"
                            )
                            content = template.get("content") or {}
                            content["source"] = "user_config"
                            content["template_id"] = str(template.get("_id"))
                            content["version"] = template.get("version", 1)
                            content["selected_preference"] = config.get("preference_id") or preference_id
                            return content
                        else:
                            # 如果用户配置的模板是草稿状态，记录警告并跳过
                            logger.warning(
                                f"⚠️ 用户配置的模板 {template_oid} 不是已发布状态或不存在，降级到用户偏好模板"
                            )
                            logger.info("[diagnose] user_config_found_but_template_lookup_failed_or_not_active")

            # 2. 优先级2：查找用户偏好对应的系统模板
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
                    f"✅ [优先级2] 获取用户偏好对应的系统模板: {agent_type}/{agent_name} (preference={preference_id})"
                )
                logger.info(f"[diagnose] path=system_fallback system_query={system_query}")
                content = system_template.get("content") or {}
                content["source"] = "system"
                content["template_id"] = str(system_template.get("_id"))
                content["version"] = system_template.get("version", 1)
                content["selected_preference"] = preference_id
                return content

            # 3. 优先级3：如果没有找到用户偏好对应的模板，降级到默认neutral模板
            if preference_id != "neutral":
                logger.info(
                    f"⚠️ 未找到偏好 {preference_id} 的系统模板，降级到默认neutral模板: {agent_type}/{agent_name}"
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
                    logger.info(f"✅ [优先级3] 获取默认neutral系统模板: {agent_type}/{agent_name}")
                    content = neutral_template.get("content") or {}
                    content["source"] = "system"
                    content["template_id"] = str(neutral_template.get("_id"))
                    content["version"] = neutral_template.get("version", 1)
                    content["selected_preference"] = "neutral"
                    return content

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
        variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        格式化模板，替换变量

        支持两种语法：
        1. 单层花括号：{variable_name}
        2. 双层花括号（Jinja2风格）：{{variable.nested_key}}

        Args:
            template_content: 模板内容字典（从get_effective_template返回）
            variables: 变量字典，支持嵌套，如 {"trade": {"code": "300274"}}

        Returns:
            格式化后的模板内容字典
        """
        try:
            # 打印输入的变量（调试用）
            logger.info(f"🔧 [format_template] 输入变量 (共 {len(variables)} 个):")
            if not variables:
                logger.warning(f"⚠️ [format_template] 变量字典为空！")
            else:
                for k, v in variables.items():
                    if isinstance(v, str) and len(v) > 100:
                        logger.info(f"  - {k}: {v[:100]}...")
                    else:
                        logger.info(f"  - {k}: {v}")

            def get_nested_value(data: Dict[str, Any], path: str) -> Any:
                """获取嵌套字典的值，支持点号路径如 'trade.code'"""
                keys = path.split('.')
                value = data
                for key in keys:
                    if isinstance(value, dict):
                        value = value.get(key, '')
                    else:
                        return ''
                return value

            def replace_variable(match):
                """替换变量占位符"""
                var_path = match.group(1).strip()
                value = get_nested_value(variables, var_path)
                # logger.info(f"  替换 {{{{{var_path}}}}} -> {value}")  # 太多了，注释掉
                return str(value) if value is not None else ''

            formatted = {}

            # 🔧 支持两种语法：
            # 1. 双层花括号 {{variable.path}}（Jinja2风格，优先级高）
            # 2. 单层花括号 {variable}（简单变量，避免与内容冲突）
            # 先处理双层花括号，再处理单层花括号（避免冲突）
            double_brace_pattern = re.compile(r'\{\{([^}]+)\}\}')
            # 单层花括号：只匹配 {变量名}，变量名只能是字母、数字、下划线的组合
            single_brace_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')

            for key, value in template_content.items():
                if isinstance(value, str):
                    formatted_value = value
                    
                    # 第一步：替换双层花括号变量 {{variable.path}}
                    def replacer_double(match):
                        var_path = match.group(1).strip()
                        val = get_nested_value(variables, var_path)
                        return str(val) if val is not None else ''
                    
                    formatted_value = double_brace_pattern.sub(replacer_double, formatted_value)
                    
                    # 第二步：替换单层花括号变量 {variable}（仅匹配简单变量名）
                    def replacer_single(match):
                        var_name = match.group(1).strip()
                        # 直接从variables字典中获取（不支持嵌套路径）
                        val = variables.get(var_name)
                        return str(val) if val is not None else ''
                    
                    formatted_value = single_brace_pattern.sub(replacer_single, formatted_value)
                    formatted[key] = formatted_value

                    # 检查是否还有未替换的变量（只针对system_prompt和user_prompt）
                    if key in ['system_prompt', 'user_prompt']:
                        # 检查双层花括号
                        unmatched_double = re.findall(r'\{\{([^}]+)\}\}', formatted_value)
                        # 检查单层花括号（简单变量名）
                        unmatched_single = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', formatted_value)
                        if unmatched_double or unmatched_single:
                            total_unmatched = len(unmatched_double) + len(unmatched_single)
                            logger.warning(f"⚠️ [模板渲染] {key} 中可能有 {total_unmatched} 个未渲染的变量")
                            # 显示前200字符
                            logger.warning(f"⚠️ [模板渲染] {key} 前200字符: {formatted_value[:200]}")
                            if unmatched_double:
                                for var_name in unmatched_double:
                                    logger.warning(f"  - 未替换(双层): {var_name}")
                            if unmatched_single:
                                for var_name in unmatched_single:
                                    logger.warning(f"  - 未替换(单层): {var_name}")
                else:
                    formatted[key] = value

            return formatted

        except Exception as e:
            logger.error(f"[TemplateClient] 格式化模板异常: {e}")
            import traceback
            traceback.print_exc()
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
            logger.info(f"📝 [模板渲染] 开始格式化模板，变量数量: {len(variables)}")
            logger.info(f"📝 [模板渲染] 模板字段: {list(template_content.keys())}")

            # 格式化模板
            formatted = client.format_template(template_content, variables)

            logger.info(f"📝 [模板渲染] 格式化完成，检查渲染结果...")
            # 检查是否还有未渲染的变量
            for key, value in formatted.items():
                if isinstance(value, str) and ('{{' in value or '{' in value):
                    # 检查双层花括号
                    unmatched_double = re.findall(r'\{\{([^}]+)\}\}', value)
                    # 检查单层花括号（简单变量名）
                    unmatched_single = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', value)

                    if unmatched_double or unmatched_single:
                        total_unmatched = len(unmatched_double) + len(unmatched_single)
                        logger.warning(f"⚠️ [模板渲染] {key} 中可能有 {total_unmatched} 个未渲染的变量")
                        # 显示前200字符
                        logger.warning(f"⚠️ [模板渲染] {key} 前200字符: {value[:200]}")
                        # 打印具体的未渲染变量名
                        if unmatched_double:
                            logger.warning(f"  📌 未渲染变量(双层花括号): {', '.join(unmatched_double)}")
                        if unmatched_single:
                            logger.warning(f"  📌 未渲染变量(单层花括号): {', '.join(unmatched_single)}")

            # 组合完整提示词
            parts = []
            if formatted.get("system_prompt"):
                parts.append(formatted["system_prompt"])
            if formatted.get("tool_guidance"):
                parts.append("\n\n" + formatted["tool_guidance"])
            if formatted.get("analysis_requirements"):
                parts.append("\n\n" + formatted["analysis_requirements"])
            if formatted.get("output_format"):
                parts.append("\n\n" + formatted["output_format"])
            if formatted.get("constraints"):
                parts.append("\n\n" + formatted["constraints"])

            prompt = "\n".join(parts)
            logger.info(f"✅ 成功生成提示词: {agent_type}/{agent_name} (长度: {len(prompt)})")
            logger.info(f"📝 [模板渲染] 提示词: {prompt}")
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


def get_user_prompt(
    agent_type: str,
    agent_name: str,
    variables: Dict[str, Any],
    user_id: Optional[str] = None,
    preference_id: Optional[str] = None,
    fallback_prompt: Optional[str] = None,
    context: Optional[AgentContext] = None
) -> str:
    """
    获取Agent用户提示词（便捷函数）

    Args:
        agent_type: Agent类型
        agent_name: Agent名称
        variables: 模板变量字典（包含所有需要替换的数据）
        user_id: 用户ID（可选）
        preference_id: 偏好ID（可选）
        fallback_prompt: 降级提示词（当API不可用时使用）

    Returns:
        渲染后的用户提示词字符串
    """
    try:
        # 🔍 调试：打印接收到的变量
        logger.info(f"🔍 [get_user_prompt] 接收到的变量 (共 {len(variables)} 个):")
        if not variables:
            logger.warning(f"⚠️ [get_user_prompt] 变量字典为空！")
        else:
            for k, v in variables.items():
                if isinstance(v, str) and len(v) > 100:
                    logger.info(f"  - {k}: {v[:100]}...")
                else:
                    logger.info(f"  - {k}: {v}")
        
        client = get_template_client()

        # 从MongoDB获取模板
        template_content = client.get_effective_template(agent_type, agent_name, user_id, preference_id, context)

        if template_content:
            # 格式化模板
            formatted = client.format_template(template_content, variables)

            # 返回用户提示词
            user_prompt = formatted.get("user_prompt", "")
            if user_prompt:
                # 检查是否还有未渲染的变量
                unmatched_double = re.findall(r'\{\{([^}]+)\}\}', user_prompt)
                unmatched_single = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', user_prompt)

                if unmatched_double or unmatched_single:
                    total_unmatched = len(unmatched_double) + len(unmatched_single)
                    logger.warning(f"⚠️ [get_user_prompt] user_prompt 中可能有 {total_unmatched} 个未渲染的变量")
                    logger.warning(f"⚠️ [get_user_prompt] user_prompt 前200字符: {user_prompt[:200]}")
                    if unmatched_double:
                        logger.warning(f"  📌 未渲染变量(双层花括号): {', '.join(unmatched_double)}")
                    if unmatched_single:
                        logger.warning(f"  📌 未渲染变量(单层花括号): {', '.join(unmatched_single)}")

                logger.info(f"✅ 成功生成用户提示词: {agent_type}/{agent_name} (长度: {len(user_prompt)})")
                logger.info(f"📝 [get_user_prompt] 用户提示词: {user_prompt}")
                return user_prompt
            else:
                logger.warning(f"⚠️ 模板中没有 user_prompt 字段，使用降级提示词: {agent_type}/{agent_name}")
                return fallback_prompt or "请进行分析。"
        else:
            # 降级：使用硬编码提示词
            logger.warning(
                f"⚠️ 无法获取模板，使用降级提示词: {agent_type}/{agent_name}"
            )
            return fallback_prompt or "请进行分析。"

    except Exception as e:
        logger.error(f"❌ 获取用户提示词异常: {e}")
        import traceback
        traceback.print_exc()
        return fallback_prompt or "请进行分析。"


def close_template_client():
    """关闭全局模板客户端连接"""
    global _template_client
    if _template_client is not None:
        _template_client.client.close()
        _template_client = None
        logger.info("✅ 模板客户端连接已关闭")

