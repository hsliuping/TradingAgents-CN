"""
智能助手服务 - Agent 自主编排模式

支持 ReAct 模式的工具自主调用，用于事件驱动分析、探索性查询等场景。
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# 智能助手整体超时（LLM + 多轮工具调用），默认 120 秒
ASSISTANT_TIMEOUT_SECONDS = int(os.environ.get("ASSISTANT_TIMEOUT_SECONDS", "120"))

# 会话历史最大条数（每用户）
ASSISTANT_CONVERSATION_LIMIT = 100

from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_user_id
from core.llm import UnifiedLLMClient
from core.llm.models import LLMConfig, LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)


def _get_latest_trade_date() -> str:
    """获取 A 股最近交易日（周末回退到上周五）"""
    now = datetime.now()
    # 周六(5)、周日(6) 用上周五
    if now.weekday() == 5:
        now = now - timedelta(days=1)
    elif now.weekday() == 6:
        now = now - timedelta(days=2)
    return now.strftime("%Y-%m-%d")


def _build_profile_block(user_profile: Optional[dict]) -> str:
    """将用户画像格式化为系统提示词中的一个段落"""
    if not user_profile:
        return ""
    lines = ["【你对该用户的了解】"]
    recently = user_profile.get("recently_analyzed") or []
    if recently:
        latest = recently[-1]
        sym = latest.get("symbol", "")
        name = latest.get("name", "")
        date = latest.get("analyzed_at") or ""
        if hasattr(date, "strftime"):
            date = date.strftime("%Y-%m-%d")
        elif isinstance(date, str) and "T" in date:
            date = date[:10]
        conclusion = latest.get("conclusion", "")
        lines.append(f"- 最近分析：{name}({sym}) · {date} · 结论：{conclusion}")
        if len(recently) > 1:
            prev = [f"{r.get('name', r.get('symbol', ''))}({r.get('symbol', '')})" for r in recently[-4:-1]]
            lines.append(f"- 历史分析：{', '.join(prev)} 等共 {len(recently)} 条")
    watchlist = user_profile.get("watchlist_symbols") or []
    if watchlist:
        lines.append(f"- 自选股：{', '.join(watchlist[:5])}（共 {len(watchlist)} 只）")
    pref = user_profile.get("preference") or {}
    if pref:
        parts = []
        if pref.get("investment_style"):
            parts.append(pref["investment_style"])
        if pref.get("risk_level"):
            parts.append(pref["risk_level"] + "风格")
        sectors = pref.get("focus_sectors") or []
        if sectors:
            parts.append("/".join(sectors[:3]) + "板块")
        if parts:
            lines.append(f"- 偏好：{', '.join(parts)}")
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


def _get_system_prompt(knowledge_snippets: str = "", assistant_settings: dict = None, is_im: bool = False, user_profile: Optional[dict] = None) -> str:
    """生成包含当前日期的系统提示词

    Args:
        knowledge_snippets: RAG 检索到的动态知识片段（由 FinancialKnowledgeManager 提供）
        assistant_settings: 用户助理个性化设置 {"name", "tone", "custom_instructions"}
        is_im: 是否来自 IM 渠道（QQ Bot 等），为 True 时注入移动端格式规范
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    trade_date = _get_latest_trade_date()

    # 助理个性化
    ast = assistant_settings or {}
    assistant_name = ast.get("name", "分析助理")
    tone = ast.get("tone", "professional")
    custom_instructions = ast.get("custom_instructions", "")

    tone_map = {
        "professional": "专业严谨，用数据说话",
        "friendly": "轻松友好，善用类比和通俗语言",
        "concise": "简洁高效，只说重点，少用修饰",
    }
    tone_desc = tone_map.get(tone, tone_map["professional"])

    personalization_block = f"""【助理身份】
- 你的名字是「{assistant_name}」，用户可能直接叫你的名字
- 语气风格：{tone_desc}
"""
    if custom_instructions.strip():
        personalization_block += f"- 用户特别要求：{custom_instructions.strip()}\n"

    # IM 渠道格式规范
    im_block = ""
    if is_im:
        im_block = """
【IM 消息格式规范】（当前通过 QQ 等移动端 IM 渠道对话）
- 禁止使用 Markdown 表格，改用「字段名: 值」竖排格式，例如：
    PE市盈率: 35x
    PB市净率: 12x
- 禁止使用 Markdown 语法（**加粗**、### 标题、`代码` 等）
- 列表用"• 内容"格式，每条不超过20个汉字
- 回答总字数控制在400字以内，突出关键结论
- 数字分析结果直接给出，无需铺垫性语句
"""

    return f"""你是 TradingAgents-CN 平台的**{assistant_name}（操作员）**，同时具备投资教练能力。你既能帮用户执行操作（触发分析、查报告、管理定时任务、管理自选股），也能教用户投资分析方法。

{personalization_block}

【角色定位】
- **首要角色：操作员** —— 用户说"帮我分析贵州茅台"，你立即调用工具触发分析，而不是讲理论
- **附加角色：教练** —— 用户问"毛利率怎么看"，你获取数据后教方法、讲框架
- **判断原则**：如果用户的意图是"做某事"，执行操作；如果意图是"学某事"，进入教练模式

【操作能力 —— 你可以做这些事】
1. **触发分析**：用户说"分析XX股票"、"帮我分析XX"、"分析一下XX"，**必须**调用 `trigger_stock_analysis` 创建新的后台分析任务，**绝对不能**调用 `search_reports` 或 `get_latest_report` 来替代
2. **批量分析**：用户说"帮我分析这几只股票"，调用 `trigger_batch_analysis`
3. **查看进度**：用户说"任务进度怎样了"，调用 `get_analysis_status`
4. **搜索报告**：用户明确说"查一下/找一下之前的报告"、"上周分析过哪些"，才调用 `search_reports`
5. **查看/解读报告**：
   - 用户明确说"看看茅台的报告"、"上次分析结果"，调用 `get_latest_report` 或 `get_report_detail`
   - 用户说"解读这个报告"、"这份报告说什么"、"帮我分析一下这个报告"、"哪个角色得出了什么结论"等**未提供股票代码**的情况，**禁止向用户追问股票代码**，**立即**调用 `get_latest_report`（不传 symbol 参数）获取最近一份报告，然后进行解读
   - 若会话历史中提到了某只股票（如"茅台"、"600519"），优先用该股票调用 `get_latest_report`
6. **定时任务**：用户说"设个定时每天分析"，先用 `list_watchlist_groups` 确认分组，再调用 `create_scheduled_analysis`
7. **管理定时**：用户说"暂停/启用定时任务"，调用 `toggle_scheduled_config`
8. **查看自选股**：用户说"我的自选股有哪些"，调用 `list_watchlist_groups`
9. **管理自选股**：用户说"把XX加入自选"，调用 `add_stock_to_watchlist`

【工具选择核心规则 —— 非常重要】
- "分析XX" = 发起新任务 → `trigger_stock_analysis`（即使之前分析过，也要重新分析）
- "看XX报告/结果" = 查看已有报告 → `get_latest_report` 或 `get_report_detail`
- "查一下之前的报告/历史记录" = 搜索已有报告 → `search_reports`
- **绝不能**把"分析XX"意图路由到报告查询类工具

【操作确认原则】
- **创建定时任务** 前：确认名称、频率、分组等参数后再创建
- **删除/移除** 操作前：先告知用户将要做什么，得到确认后再执行
- **触发分析** 可直接执行，无需确认（代价低、可重复）

【教练能力 —— 保留原有教学风格】
- 教方法，不给答案：带用户走分析流程，而非直接下结论
- 用数据说话：所有分析必须基于工具获取的实时数据
- 解释为什么：教用户理解数据背后的含义
- 诚实表达不确定性

【当前日期】{today}（用于判断年份、财报披露周期等时间逻辑）
【当前/最近交易日】{trade_date}（用于调用工具获取行情数据）
- 调用所有需要 curr_date 或 trade_date 参数的工具时，**必须传入交易日**
- 回答涉及年份、季度等问题时，**必须基于当前日期推理**
- 严禁使用训练数据中的历史日期回答

【A股财报披露时间规则】
- 年报：1月1日～4月30日 | 一季报：4月30日前 | 半年报：8月31日前 | 三季报：10月31日前

{knowledge_snippets}
{_build_profile_block(user_profile)}
【合规原则】
- 你是助理+教练，不是投顾：**教分析方法，不给"买入/卖出/持有"的直接建议**
- 所有观点必须有工具返回的数据支撑，不做主观臆断
- 不提供目标价、仓位建议、具体买卖时点
- 每次回答结尾自然提醒：以上分析仅供学习参考，不构成投资建议

【工具使用原则】
- **严禁**根据训练数据回答行情、大盘、市场等需要实时数据的问题，**必须**通过调用工具获取
- 根据每个工具的描述，**自主选择**最合适的工具；若一次调用不足，可继续调用其他工具
- 所有需要 curr_date 或 trade_date 的工具，**必须**传入上述日期
- **板块/行业类问题**优先使用板块级别工具，无需股票代码
- **操作类请求**（分析、报告、定时、自选股）优先使用 assistant_ops 类工具
{im_block}"""


def _resolve_models(config_doc) -> tuple:
    """从配置文档解析模型名：优先 default_models，否则 system_settings"""
    default_models = config_doc.get("default_models") or {}
    system_settings = config_doc.get("system_settings") or {}
    return (
        default_models.get("quick_analysis_model") or system_settings.get("quick_analysis_model"),
        default_models.get("deep_analysis_model") or system_settings.get("deep_analysis_model"),
        default_models.get("deep_reasoning_model") or system_settings.get("deep_reasoning_model"),
        default_models.get("coding_model") or system_settings.get("coding_model"),
    )


async def _get_llm_config_for_model(db, target_model: str, purpose: str = "") -> Optional[LLMConfig]:
    """根据模型名获取 LLM 配置（内部复用逻辑）"""
    if not target_model:
        return None
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        return None
    llm_configs = config_doc.get("llm_configs", [])
    model_configs = [c for c in llm_configs if c.get("model_name") == target_model and c.get("enabled", True)]
    if not model_configs:
        return None
    model_config = model_configs[0]
    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
    provider_info = get_provider_and_url_by_model_sync(target_model)
    if not provider_info:
        return None
    provider_str = (provider_info.get("provider") or model_config.get("provider", "")).lower()
    provider_map = {
        "openai": LLMProvider.OPENAI, "deepseek": LLMProvider.DEEPSEEK,
        "dashscope": LLMProvider.DASHSCOPE, "qwen": LLMProvider.DASHSCOPE,
        "zhipu": LLMProvider.ZHIPU, "google": LLMProvider.GOOGLE,
        "anthropic": LLMProvider.ANTHROPIC, "siliconflow": LLMProvider.SILICONFLOW,
        "ollama": LLMProvider.OLLAMA, "openrouter": LLMProvider.OPENROUTER,
    }
    provider = provider_map.get(provider_str, LLMProvider.DEEPSEEK)
    return LLMConfig(
        provider=provider, model=target_model,
        api_key=provider_info.get("api_key"), base_url=provider_info.get("backend_url"),
        temperature=float(model_config.get("temperature", 0.2)),
        max_tokens=int(model_config.get("max_tokens", 4000)),
        timeout=int(model_config.get("timeout", 60)),
    )


async def _get_assistant_llm_config(db, use_reasoning_model: bool = False) -> Optional[LLMConfig]:
    """
    从数据库获取智能助手使用的 LLM 配置
    优先使用深度思考模型（deep_analysis_model），以保证时间逻辑、财报披露等推理准确
    use_reasoning_model=True 时，优先使用深度推理模型（deep_reasoning_model），适用于策略生成、规划等
    若未配置则回退到快速模型或默认模型
    """
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        logger.warning("[智能助手] 数据库中没有 LLM 配置")
        return None

    llm_configs = config_doc.get("llm_configs", [])
    default_llm = config_doc.get("default_llm")
    quick_model, deep_model, reasoning_model, _ = _resolve_models(config_doc)

    if use_reasoning_model and reasoning_model:
        target_model = reasoning_model
        logger.info(f"[智能助手] 使用深度推理模型: {target_model}")
    else:
        target_model = deep_model or quick_model or default_llm
        if deep_model:
            logger.info(f"[智能助手] 使用深度分析模型: {deep_model}")
        elif quick_model:
            logger.info(f"[智能助手] 深度模型未配置，使用快速模型: {quick_model}")

    if not target_model:
        target_model = deep_model or quick_model or default_llm
    if not target_model and llm_configs:
        for cfg in llm_configs:
            if cfg.get("enabled", True):
                target_model = cfg.get("model_name")
                break

    if not target_model:
        logger.warning("[智能助手] 未找到可用的模型配置")
        return None

    return await _get_llm_config_for_model(db, target_model)


async def get_reasoning_llm_config(db=None):
    """
    获取深度推理模型配置，用于策略 DSL 生成、规划等需要强推理的场景
    优先 deep_reasoning_model，未配置时回退到 deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    return await _get_assistant_llm_config(db, use_reasoning_model=True)


async def get_coding_llm_config(db=None):
    """
    获取编程模型配置，用于策略 DSL 生成等需要结构化 JSON 输出的场景
    优先 coding_model，未配置时回退到 deep_reasoning_model → deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        return await get_reasoning_llm_config(db)
    _, deep_model, reasoning_model, coding_model = _resolve_models(config_doc)
    target_model = coding_model or reasoning_model or deep_model
    if target_model:
        logger.info(f"[编程模型] 使用: {target_model} (coding={bool(coding_model)}, reasoning={bool(reasoning_model)})")
    return await _get_llm_config_for_model(db, target_model) if target_model else await get_reasoning_llm_config(db)


class IntelligentAssistantService:
    """智能助手服务"""

    def __init__(self, db):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[List[Dict[str, Any]]] = None
        self._tool_functions: Optional[Dict[str, Any]] = None

    async def _ensure_client(self) -> bool:
        """确保 LLM 客户端和工具已加载"""
        if self._llm_client is not None:
            return True

        # 智能助手使用深度推理模型（deep_reasoning_model），未配置时回退到深度分析模型
        llm_config = await _get_assistant_llm_config(self._db, use_reasoning_model=True)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能助手] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        registry = get_tool_registry()
        all_metadata = registry.list_all()
        self._openai_tools = tool_metadata_list_to_openai(all_metadata)

        self._tool_functions = {}
        for tool in all_metadata:
            if tool.fc_enabled and tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能助手] 已加载 {len(self._openai_tools)} 个工具")
        return True

    async def chat(self, user_message: str, conversation_id: Optional[str] = None, assistant_settings: dict = None, is_im: bool = False, history_messages: Optional[List[Message]] = None, user_profile: Optional[dict] = None) -> Dict[str, Any]:
        """
        处理用户对话

        Args:
            user_message: 用户输入
            conversation_id: 会话 ID（首版未使用，预留）
            assistant_settings: 用户助理个性化设置
            is_im: 是否来自 IM 渠道，为 True 时注入移动端格式规范到 system prompt

        Returns:
            {"reply": str, "tools_used": List[str], "data_refs": Optional[List]}
        """
        # 前置检查：不支持的品种类型
        from app.services.planned_analysis_service import _check_unsupported_asset
        unsupported_msg = _check_unsupported_asset(user_message)
        if unsupported_msg:
            return {
                "reply": unsupported_msg,
                "tools_used": [],
                "data_refs": None,
            }

        if not await self._ensure_client():
            return {
                "reply": "智能助手暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "data_refs": None,
            }

        # RAG 动态知识检索（优雅降级：不可用时返回空字符串）
        knowledge_snippets = ""
        try:
            from core.knowledge import FinancialKnowledgeManager
            km = FinancialKnowledgeManager(db=self._db)
            knowledge_snippets = km.retrieve_for_prompt(user_message)
            if knowledge_snippets:
                logger.info(f"[智能助手] ✅ RAG 知识检索成功 ({len(knowledge_snippets)} 字符)")
            else:
                logger.info("[智能助手] RAG 知识检索返回空（无匹配知识）")
        except Exception as e:
            logger.warning(f"[智能助手] ⚠️ 知识检索失败（降级为静态知识）: {e}")

        # 构建消息列表：系统提示 + 历史记录 + 当前用户消息
        messages = [
            Message(role=MessageRole.SYSTEM, content=_get_system_prompt(knowledge_snippets, assistant_settings, is_im=is_im, user_profile=user_profile)),
        ]
        if history_messages:
            messages.extend(history_messages)
            logger.info(f"[智能助手] 已注入 {len(history_messages)} 条历史消息")
        messages.append(Message(role=MessageRole.USER, content=user_message.strip()))

        tools_used: List[str] = []

        async def _do_chat():
            nonlocal tools_used
            resp = await self._llm_client.achat(
                messages,
                tools=self._openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=8,
                tools_used=tools_used,
            )
            return resp.content

        try:
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=ASSISTANT_TIMEOUT_SECONDS,
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
            if tools_used:
                logger.info("[智能助手] 已调用工具: %s", tools_used)
            else:
                logger.info("[智能助手] 未调用任何工具（纯文本回复）")
            logger.info("[智能助手] 回复内容(前200字): %s", reply[:200])
            return {
                "reply": reply,
                "tools_used": tools_used,
                "data_refs": None,
            }
        except asyncio.TimeoutError:
            logger.warning(f"[智能助手] 请求超时（{ASSISTANT_TIMEOUT_SECONDS}s）")
            return {
                "reply": f"抱歉，处理您的问题用时过长（已超过 {ASSISTANT_TIMEOUT_SECONDS} 秒），为避免长时间等待已中断。\n\n"
                "建议您：\n"
                "• 尝试将问题拆分得更具体一些\n"
                "• 检查网络连接是否稳定\n"
                "• 稍后重试",
                "tools_used": tools_used,
                "data_refs": None,
            }
        except Exception as e:
            logger.exception("[智能助手] 对话失败")
            return {
                "reply": f"处理您的请求时发生错误：{str(e)}。请检查网络和 LLM 配置后重试。",
                "tools_used": tools_used,
                "data_refs": None,
            }


async def save_assistant_message(
    db,
    user_id: str,
    user_content: str,
    assistant_content: str,
    tools_used: List[str],
) -> None:
    """将会话追加写入 MongoDB"""
    now = datetime.now(timezone.utc)
    user_msg = {"role": "user", "content": user_content}
    assistant_msg = {"role": "assistant", "content": assistant_content}
    if tools_used:
        assistant_msg["tools_used"] = tools_used
    await db.assistant_conversations.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "messages": {
                    "$each": [user_msg, assistant_msg],
                    "$slice": -ASSISTANT_CONVERSATION_LIMIT,
                }
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
    )


async def get_assistant_conversation(db, user_id: str) -> List[Dict[str, Any]]:
    """获取用户的智能助手会话历史"""
    doc = await db.assistant_conversations.find_one({"user_id": user_id})
    if not doc or not doc.get("messages"):
        return []
    return doc["messages"]


async def clear_assistant_conversation(db, user_id: str) -> None:
    """清空用户的智能助手会话"""
    await db.assistant_conversations.update_one(
        {"user_id": user_id},
        {"$set": {"messages": [], "updated_at": datetime.now(timezone.utc)}},
    )


async def load_user_profile(db, user_id: str) -> Optional[dict]:
    """从 assistant_user_profiles 集合加载用户画像"""
    try:
        doc = await db.assistant_user_profiles.find_one({"user_id": user_id})
        return doc
    except Exception as e:
        logger.warning("[智能助手] 加载用户画像失败: %s", e)
    return None


async def update_user_profile_with_analysis(
    db,
    user_id: str,
    symbol: str,
    name: str,
    conclusion: str,
    task_id: str,
) -> None:
    """
    分析任务完成后，将结果追加到用户画像的 recently_analyzed 列表。
    保留最近 20 条，upsert 方式写入 assistant_user_profiles 集合。
    """
    try:
        now = datetime.now(timezone.utc)
        entry = {
            "symbol": symbol,
            "name": name,
            "analyzed_at": now.strftime("%Y-%m-%d"),
            "conclusion": conclusion,
            "task_id": task_id,
        }
        await db.assistant_user_profiles.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "recently_analyzed": {
                        "$each": [entry],
                        "$slice": -20,
                    }
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
        logger.info(f"[用户画像] ✅ 已更新 {user_id} 的 recently_analyzed: {symbol}({name})")
    except Exception as e:
        logger.warning(f"[用户画像] 更新失败（已忽略）: {e}")


async def _load_assistant_settings(db, user_id: str) -> Optional[dict]:
    """从数据库加载用户的助理个性化设置"""
    try:
        from bson import ObjectId
        user_doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"preferences.assistant_settings": 1},
        )
        if user_doc:
            prefs = user_doc.get("preferences", {})
            return prefs.get("assistant_settings")
    except Exception as e:
        logger.warning("[智能助手] 加载助理设置失败: %s", e)
    return None


async def chat_with_assistant(
    db,
    user_message: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    is_im: bool = False,
) -> Dict[str, Any]:
    """
    便捷函数：使用智能助手进行对话
    user_id: 用于持久化会话；若提供则对话会后保存
    is_im: 是否来自 IM 渠道（QQ Bot 等），为 True 时注入移动端格式规范
    """
    # 设置用户上下文，供 assistant_ops 工具获取当前用户
    if user_id:
        set_current_user_id(user_id)

    # 加载用户助理个性化设置
    assistant_settings = None
    if user_id:
        assistant_settings = await _load_assistant_settings(db, user_id)

    # 加载用户画像（跨会话持久记忆）
    user_profile: Optional[dict] = None
    if user_id:
        try:
            user_profile = await load_user_profile(db, user_id)
            if user_profile and user_profile.get("recently_analyzed"):
                logger.info(f"[智能助手] ✅ 用户画像加载成功，最近分析 {len(user_profile['recently_analyzed'])} 条")
        except Exception as e:
            logger.warning(f"[智能助手] 加载用户画像失败（已跳过）: {e}")

    # 加载最近会话历史（最多 10 条，注入到 LLM 上下文）
    history_messages: Optional[List[Message]] = None
    if user_id:
        try:
            raw_history = await get_assistant_conversation(db, user_id)
            if raw_history:
                # 取最近 10 条，截断过长内容
                recent = raw_history[-10:]
                history_messages = []
                for m in recent:
                    role = MessageRole.USER if m.get("role") == "user" else MessageRole.ASSISTANT
                    content = (m.get("content") or "").strip()
                    if content:
                        history_messages.append(Message(role=role, content=content[:800]))
                if not history_messages:
                    history_messages = None
        except Exception as e:
            logger.warning(f"[智能助手] 加载历史会话失败（已跳过）: {e}")

    service = IntelligentAssistantService(db)
    result = await service.chat(user_message, conversation_id, assistant_settings, is_im=is_im, history_messages=history_messages, user_profile=user_profile)
    if user_id and result.get("reply"):
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=result["reply"],
                tools_used=result.get("tools_used") or [],
            )
        except Exception as e:
            logger.warning("[智能助手] 保存会话失败: %s", e)
    return result
