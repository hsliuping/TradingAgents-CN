"""执行模式（研究/执行双模式提示词）开关统一读取入口

设计文档：docs/05-design/v4.0/execution-advice-mode-design.md

约定：
- research（默认，发行态）：加载公用提示词，全部投顾拦截清洗生效
- execution（仅自用机器）：加载本地 execution 提示词，旁路指令过滤类清洗；
  库中无 execution 模板时由模板加载层自动回落 research

所有拦截点、模板加载、schema 选择统一 import 本模块，禁止各自读 settings。
本模块属于 core 层，延迟 import app.core.config（先例：action_advisor_v2 import app.utils.compliance）。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ADVICE_MODE_RESEARCH = "research"
ADVICE_MODE_EXECUTION = "execution"

# 执行模式输出统一免责声明（服务层兜底注入，模板内亦内置）
EXECUTION_MODE_DISCLAIMER = (
    "本内容为执行模式输出，仅供使用者个人决策参考，不构成任何投资建议；据此操作风险自担。"
)


def is_execution_advice_mode() -> bool:
    """是否开启执行模式（机器级开关，默认 False）"""
    try:
        from app.core.config import settings

        return bool(getattr(settings, "EXECUTION_ADVICE_MODE", False))
    except Exception as e:  # 设置不可用时一律按研究模式处理，绝不放大
        logger.warning(f"⚠️ [advice_mode] 读取执行模式开关失败，按研究模式处理: {e}")
        return False


def current_advice_mode() -> str:
    """当前提示词模式："research" | "execution" """
    return ADVICE_MODE_EXECUTION if is_execution_advice_mode() else ADVICE_MODE_RESEARCH


# ==================== 执行模板存在性检查（无效开关保证） ====================
# 发行版库中永无 execution 模板：开关打开 + 模板不存在 → 行为完全等同研究模式。
# 结果做进程级缓存；本地导入新执行模板后重启进程生效即可（个人使用可接受）。

_EXECUTION_TEMPLATE_CACHE: Dict[Any, bool] = {}


def execution_template_available(agent_type: str, agent_name: str) -> bool:
    """本地是否存在该 agent 的执行模板（advice_mode=execution 的系统模板）

    开关关闭时直接返回 False（不查库）。
    """
    if not is_execution_advice_mode():
        return False
    key = (agent_type, agent_name)
    cached = _EXECUTION_TEMPLATE_CACHE.get(key)
    if cached is not None:
        return cached
    available = False
    try:
        from tradingagents.utils.template_client import get_template_client

        available = bool(
            get_template_client().has_execution_template(agent_type, agent_name)
        )
    except Exception as e:
        logger.warning(f"⚠️ [advice_mode] 执行模板存在性检查失败，按不可用处理: {e}")
        available = False
    _EXECUTION_TEMPLATE_CACHE[key] = available
    if available:
        logger.info(f"✅ [advice_mode] 检测到本地执行模板: {agent_type}/{agent_name}")
    return available


def use_execution_output(agent_type: str, agent_name: str) -> bool:
    """agent 输出层是否走执行口径（开关开 + 本地执行模板存在，二者缺一不可）"""
    return is_execution_advice_mode() and execution_template_available(agent_type, agent_name)


# 全局执行模板存在性（服务层清洗旁路用，进程级缓存）
_ANY_EXECUTION_TEMPLATE_CACHE: Optional[bool] = None


def any_execution_template_exists() -> bool:
    """本地是否存在任意执行模板（开关开时才查库）

    服务层/路由层拦截点（设计文档 §5.3）用它做统一旁路判断：
    发行版库中永无执行模板 → False → 全部清洗照常（无效开关保证）。
    """
    global _ANY_EXECUTION_TEMPLATE_CACHE
    if not is_execution_advice_mode():
        return False
    if _ANY_EXECUTION_TEMPLATE_CACHE is not None:
        return _ANY_EXECUTION_TEMPLATE_CACHE
    exists = False
    try:
        from tradingagents.utils.template_client import get_template_client

        exists = bool(get_template_client().has_any_execution_template())
    except Exception as e:
        logger.warning(f"⚠️ [advice_mode] 全局执行模板检查失败，按不存在处理: {e}")
        exists = False
    _ANY_EXECUTION_TEMPLATE_CACHE = exists
    return exists


def context_with_advice_mode(context: Any) -> Any:
    """向模板加载 context 注入 advice_mode（走 context 通道，不改 template_client 签名）

    - dict：返回带 advice_mode 的副本（不污染原 dict）
    - None：返回 {"advice_mode": ...}
    - AgentContext 等对象：尝试 setattr；失败则原样返回（模板层缺省 research）
    """
    mode = current_advice_mode()
    if context is None:
        return {"advice_mode": mode}
    if isinstance(context, dict):
        if context.get("advice_mode") == mode:
            return context
        return {**context, "advice_mode": mode}
    try:
        setattr(context, "advice_mode", mode)
    except Exception:
        logger.debug("[advice_mode] context 对象不支持 setattr，模板层按研究模式处理")
    return context
