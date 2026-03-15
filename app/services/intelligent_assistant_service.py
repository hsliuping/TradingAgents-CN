"""
智能助手服务 - Agent 自主编排模式

支持 ReAct 模式的工具自主调用，用于事件驱动分析、探索性查询等场景。
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

# 智能助手整体超时（LLM + 多轮工具调用），默认 120 秒
ASSISTANT_TIMEOUT_SECONDS = int(os.environ.get("ASSISTANT_TIMEOUT_SECONDS", "120"))

# 会话历史最大条数（每用户）
ASSISTANT_CONVERSATION_LIMIT = 100
ASSISTANT_DEFAULT_THREAD_ID = "default"
ASSISTANT_MAX_CONTEXT_MESSAGES = 10
ASSISTANT_MAX_REPORT_REFS = 12
ASSISTANT_REPORT_INBOX_TITLE = "报告收纳"

from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_assistant_thread_id, set_current_user_id
from core.llm import UnifiedLLMClient
from core.llm.models import LLMConfig, LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)


def _should_force_tool_retry(user_message: str) -> bool:
    """判断是否属于“应优先调用工具”的个人数据查询请求。"""
    text = (user_message or "").strip().lower()
    if not text:
        return False

    # 个人数据+操作查询意图（计划/持仓/复盘/任务/报告等）
    personal_markers = ["我的", "我", "当前", "现在"]
    domain_markers = [
        "交易计划", "投资计划", "计划", "持仓", "仓位", "复盘", "报告", "分析任务", "任务状态",
        "自选股", "定时分析", "提醒", "schedule", "watchlist", "position", "review", "plan",
    ]
    query_markers = ["查看", "列出", "查询", "获取", "多少", "有没有", "是什么", "详情", "状态"]

    has_personal = any(k in text for k in personal_markers)
    has_domain = any(k in text for k in domain_markers)
    has_query = any(k in text for k in query_markers)

    # 至少满足：个人+领域，或 领域+查询
    return (has_personal and has_domain) or (has_domain and has_query)


def _should_use_recent_search(user_message: str) -> bool:
    """判断是否属于应优先走近期搜索的事实确认类问题。"""
    text = (user_message or "").strip().lower()
    if not text:
        return False

    recency_markers = [
        "截至目前", "截至现在", "最新", "近期", "最近", "刚刚", "今日", "现在",
        "确认", "核实", "联网", "公告", "新闻", "消息", "进展",
    ]
    fact_markers = [
        "持股", "持股比例", "减持", "增持", "伯克希尔", "巴菲特", "公告",
        "有没有", "是否", "还持有", "变化", "最新情况",
    ]

    has_recency = any(marker in text for marker in recency_markers)
    has_fact = any(marker in text for marker in fact_markers)
    return has_recency and has_fact


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


def _get_system_prompt(
    knowledge_snippets: str = "",
    assistant_settings: dict = None,
    is_im: bool = False,
    user_profile: Optional[dict] = None,
    current_topic_title: Optional[str] = None,
) -> str:
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

    topic_block = ""
    if current_topic_title:
        topic_block = f"""
【当前外部会话绑定主题】
- 当前研究主题：{current_topic_title}
- 当用户提到“这个主题”“当前主题”“继续这个方向”时，默认指这个主题
- 如果用户明确要求切换到别的主题，请先调用主题切换工具，再继续后续操作
"""

    return f"""你是 TradingAgents-CN 平台的**{assistant_name}（操作员）**，同时具备投资教练能力。你既能帮用户执行操作（触发分析、查报告、管理定时任务、管理自选股），也能教用户投资分析方法。

{personalization_block}

【角色定位】
- **首要角色：操作员** —— 用户想做某件事，你立即调用合适工具完成，而不是讲理论
- **附加角色：教练** —— 用户想学某个方法，你获取数据后教方法、讲框架

【系统能力说明】
本系统是一个多智能体股票分析平台。核心能力：
- **即时分析**：发起一次新的分析任务（支持单只或批量），由多个 AI 智能体在后台协作数分钟生成完整报告
- **进度查询**：查询已发起的分析任务执行状态（排队中/运行中/已完成/失败）
- **报告查阅**：已生成的报告保存在数据库中，随时可读取、解读、搜索历史报告
- **定时分析**：创建周期性自动分析计划（如每天早9点分析自选股），管理已有的定时分析配置（仅限分析任务，不支持闹钟等无关功能）
- **自选股管理**：查看、添加、移除自选股分组
- **数据查询**：直接获取个股行情、财务报表（利润表/资产负债表/现金流）、技术指标（MACD/RSI/布林带等）、新闻资讯等原始数据
- **持仓分析**：查看用户的持仓列表（实盘/模拟），获取某只持仓股票的最新 AI 分析报告，或发起一次新的持仓分析任务（含操作建议、目标价位、风险评估）
- **交易复盘**：查看复盘历史，获取复盘报告详情，或对指定交易发起一次新的 AI 复盘分析（评分、总结、改进建议、经验教训）
- **投资计划**：查看用户创建的个人交易计划（投资纪律），获取当前激活计划的完整规则（选股、择时、仓位、止盈止损等）
- **风险提醒**：为股票设置/查看/清除止损提醒，当价格接近或跌破止损线时自动发送通知
你拥有的工具覆盖了上述所有操作，请根据用户意图自主选择合适的工具

【诚实原则】
- 只承诺你确实能通过工具完成的事情，不要编造不存在的功能
- 如果用户的需求超出上述能力范围，直接坦诚告知「目前不支持该功能」，不要虚构解决方案
- 回答问题时只使用工具返回的真实数据，不要凭空捏造数字或结论

【领域边界（重要）】
- 你的核心服务范围是：股票/基金/宏观经济/行业研究、交易计划、持仓分析、交易复盘、金融数据解读。
- 对明显无关金融的话题（如娱乐八卦、菜谱、情感倾诉、通用编程教学等），不展开回答，礼貌拒绝并引导回金融问题。
- 对弱相关话题（如时间管理、学习方法、情绪管理），可用 1-2 句简短回应，但必须快速引导到投资/交易场景。
- 严禁为了“显得有帮助”而在非金融话题上长篇发挥。

【政治类话题处理】
- 纯政治立场、意识形态争论、站队评价：不回答，直接说明不在服务范围。
- 仅当用户明确关注“政策/监管对市场与行业的影响”时，才可以回答。
- 回答政策影响时：只讨论金融影响路径（行业景气、估值、资金面、风险偏好、盈利预期），避免政治价值判断。
- 涉及政策影响的结论，优先调用工具或基于可验证数据，不得主观臆断。

【非金融请求回复模板】
- 可直接使用以下风格回复：
    「这个话题不在我的服务范围内。我主要提供金融研究与交易分析支持。你可以问我持仓、复盘、交易计划、个股/板块分析等问题。」

【先确认再执行原则】
根据任务复杂度和明确程度，决定是直接执行还是先和用户确认：

**可直接执行（轻量、明确、可重复）**：
- 数据查询（行情、财务、新闻等）
- 读取/搜索已有报告
- 查看自选股列表、查看定时配置列表
- 查看持仓列表、查看持仓分析报告、发起新的持仓分析
- 查看复盘历史、查看复盘报告详情、发起新的交易复盘
- 查看投资计划列表、查看当前激活计划
- 设置止损提醒、查看止损提醒、清除止损提醒

**需要先确认再执行（复杂、有副作用、或意图模糊）**：
- **意图模糊时**：用户表达不明确（如「分析一下茅台」「看看茅台」），先结合上下文判断，仍不确定则主动询问用户意图，不要猜测执行
- **创建定时分析**：先查看已有配置告知用户，再确认时间、频率、股票等参数，用户确认后再创建
- **触发分析任务**：如果用户指令明确（如「帮我分析600519」）可直接执行；如果模糊则先确认
- **删除/移除操作**：先告知用户将要做什么，得到确认后再执行
- **复杂多步任务**：先向用户说明你的执行方案，用户确认后再逐步执行

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

【A股交易执行规则】
- 讨论A股买卖数量时，默认遵守整手交易：普通买入/卖出应为100股整数倍。
- 只有配股、送转等历史原因形成的零股，才可能出现不足100股仍可卖出的情况；不要把这类情况当成常规规则。
- 如果根据仓位比例计算出的结果不是100股整数倍，不要直接给出诸如30股、60股、80股之类的执行建议；应改为“按100股整数倍取整执行”，并明确说明剩余零头如何处理。
- 当工具返回的是比例规则而不是实际下单数量时，要主动提醒用户：实际执行需结合当前持仓股数按整手约束换算。

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
- 对“截至目前”“最新”“近期是否有变化”“请确认最新口径”“最新公告/持股比例/减持进展”这类问题，优先调用“近期信息搜索”或相关新闻工具，先检索近期公开信息，再回答
- **板块/行业类问题**优先使用板块级别工具，无需股票代码
- **操作类请求**（分析、报告、定时、自选股）优先使用 assistant_ops 类工具
- 对“分析某只股票”“看看持仓”“查一下报告”这类零星查询，直接完成查询或分析，不要为了记录上下文而新建研究主题
{topic_block}
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
            # 无参数工具同样需要注入，否则会出现“工具已加载但无法执行”
            if tool.fc_enabled:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能助手] 已加载 {len(self._openai_tools)} 个工具")
        return True

    async def chat(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        assistant_settings: dict = None,
        is_im: bool = False,
        history_messages: Optional[List[Message]] = None,
        user_profile: Optional[dict] = None,
        current_topic_title: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        # 快路径：对“最新/截至目前/近期确认”类事实问题，优先直接执行近期搜索工具，
        # 避免模型在首轮未触发工具时退回训练期知识。
        if _should_use_recent_search(user_message):
            try:
                from core.tools.implementations.assistant_ops.recent_search import run_recent_information_search

                tool_result = run_recent_information_search(user_message.strip())
                if inspect.isawaitable(tool_result):
                    tool_result = await tool_result
                tool_text = str(tool_result or "").strip()
                if tool_text:
                    logger.info("[智能助手] 命中近期搜索快路径，直接返回搜索结果")
                    return {
                        "reply": tool_text,
                        "tools_used": ["search_recent_information"],
                        "data_refs": None,
                    }
            except Exception as e:
                logger.warning(f"[智能助手] 近期搜索快路径失败，回退常规对话: {e}")

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
            Message(
                role=MessageRole.SYSTEM,
                content=_get_system_prompt(
                    knowledge_snippets,
                    assistant_settings,
                    is_im=is_im,
                    user_profile=user_profile,
                    current_topic_title=current_topic_title,
                ),
            ),
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
                dry_run=False,
            )

            # 兜底：对于“应走工具”的个人数据查询，如果首轮未调工具，则二次强制引导
            if not tools_used and _should_force_tool_retry(user_message):
                logger.warning("[智能助手] 首轮未调用工具，触发工具重试兜底")
                retry_messages = list(messages)
                retry_messages.append(Message(
                    role=MessageRole.USER,
                    content=(
                        "请不要直接根据上下文猜测或编造结果。"
                        "这类问题必须先调用相关工具获取真实数据，再基于工具返回回答。"
                        "如果工具返回为空，再明确说明为空。"
                    ),
                ))

                # 优先尝试强制 tool choice；若模型侧不支持则降级为普通重试
                try:
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        dry_run=False,
                        tool_choice="required",
                    )
                except Exception as retry_err:
                    logger.warning("[智能助手] tool_choice=required 重试失败，降级普通重试: %s", retry_err)
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        dry_run=False,
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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_thread_id() -> str:
    return f"thr_{uuid.uuid4().hex[:12]}"


def _normalize_thread_title(title: str) -> str:
    text = (title or "").strip().lower()
    if not text:
        return ""

    replacements = {
        "新能源汽车": "新能源车",
        "新能源汽車": "新能源车",
        "个股": "公司",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    for token in ["（", "）", "(", ")", "-", "_", " ", "　", "/", "\\", "·", "、"]:
        text = text.replace(token, "")

    removable_suffixes = [
        "研究主题",
        "产业链研究",
        "行业研究",
        "板块研究",
        "公司研究",
        "个股研究",
        "深度研究",
        "专题研究",
        "课题研究",
        "产业链",
        "行业",
        "板块",
        "研究",
        "分析",
        "跟踪",
        "专题",
        "主题",
    ]
    changed = True
    while changed and len(text) > 2:
        changed = False
        for suffix in removable_suffixes:
            if text.endswith(suffix) and len(text) > len(suffix) + 1:
                text = text[: -len(suffix)]
                changed = True
                break

    return text


def _thread_titles_match(first: str, second: str) -> bool:
    normalized_first = _normalize_thread_title(first)
    normalized_second = _normalize_thread_title(second)
    if not normalized_first or not normalized_second:
        return False
    return normalized_first == normalized_second


def _find_similar_thread(
    docs: List[Dict[str, Any]],
    title: str,
    parent_thread_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_parent_id = (parent_thread_id or "").strip() or None
    candidates = [
        doc for doc in docs
        if (doc.get("parent_thread_id") or None) == normalized_parent_id
    ]
    for doc in candidates:
        if _thread_titles_match(doc.get("title") or "", title):
            return doc
    return None


def _is_external_session_thread_id(thread_id: Optional[str]) -> bool:
    return bool(thread_id and ":" in thread_id)


def _is_visible_assistant_topic(doc: Dict[str, Any]) -> bool:
    if doc.get("archived") is True:
        return False
    if (doc.get("topic_type") or "") == "im_session":
        return False
    return not _is_external_session_thread_id(doc.get("thread_id"))


def _thread_doc_to_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    summary = doc.get("current_summary") or {}
    updated_at = doc.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()
    report_refs = []
    for ref in doc.get("report_refs") or []:
        created_at = ref.get("created_at")
        linked_at = ref.get("linked_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(linked_at, datetime):
            linked_at = linked_at.isoformat()
        report_refs.append({
            "ref_type": ref.get("ref_type") or "unknown",
            "report_key": ref.get("report_key") or "",
            "source_collection": ref.get("source_collection") or "",
            "title": ref.get("title") or "未命名报告",
            "symbol": ref.get("symbol") or None,
            "summary": ref.get("summary") or "",
            "status": ref.get("status") or None,
            "task_id": ref.get("task_id") or None,
            "analysis_id": ref.get("analysis_id") or None,
            "created_at": created_at,
            "linked_at": linked_at,
        })
    return {
        "thread_id": doc.get("thread_id", ASSISTANT_DEFAULT_THREAD_ID),
        "title": doc.get("title") or "默认主题",
        "parent_thread_id": doc.get("parent_thread_id"),
        "topic_type": doc.get("topic_type") or "general",
        "pinned": bool(doc.get("pinned", False)),
        "archived": bool(doc.get("archived", False)),
        "message_count": int(doc.get("message_count", 0)),
        "last_user_message": doc.get("last_user_message", ""),
        "updated_at": updated_at,
        "report_refs": report_refs,
        "current_summary": {
            "abstract": summary.get("abstract") or "",
            "confirmed_facts": summary.get("confirmed_facts") or [],
            "open_questions": summary.get("open_questions") or [],
            "next_actions": summary.get("next_actions") or [],
            "focus_score": float(summary.get("focus_score") or 0.0),
        } if summary else None,
    }


def serialize_assistant_report_ref(ref: Dict[str, Any]) -> Dict[str, Any]:
    created_at = ref.get("created_at")
    linked_at = ref.get("linked_at")
    return {
        "ref_type": ref.get("ref_type") or "unknown",
        "report_key": ref.get("report_key") or "",
        "source_collection": ref.get("source_collection") or "",
        "title": ref.get("title") or "未命名报告",
        "symbol": ref.get("symbol") or None,
        "summary": ref.get("summary") or "",
        "status": ref.get("status") or None,
        "task_id": ref.get("task_id") or None,
        "analysis_id": ref.get("analysis_id") or None,
        "created_at": _to_iso_datetime(created_at),
        "linked_at": _to_iso_datetime(linked_at),
    }


def _normalize_summary_items(items: List[str], limit: int = 3) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in items:
        text = (item or "").strip().replace("\n", " ")
        if not text:
            continue
        text = text[:120]
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_report_ref_item(report_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ref_type = (report_ref.get("ref_type") or "").strip()
    report_key = (report_ref.get("report_key") or report_ref.get("task_id") or report_ref.get("analysis_id") or "").strip()
    if not ref_type or not report_key:
        return None

    now = _now_utc()
    created_at = report_ref.get("created_at")
    if not isinstance(created_at, datetime):
        created_at = now

    return {
        "ref_type": ref_type,
        "report_key": report_key,
        "source_collection": (report_ref.get("source_collection") or "").strip(),
        "title": (report_ref.get("title") or "未命名报告").strip(),
        "symbol": (report_ref.get("symbol") or "").strip() or None,
        "summary": (report_ref.get("summary") or "").strip()[:600],
        "status": (report_ref.get("status") or "").strip() or None,
        "task_id": (report_ref.get("task_id") or "").strip() or None,
        "analysis_id": (report_ref.get("analysis_id") or "").strip() or None,
        "created_at": created_at,
        "linked_at": now,
    }


async def attach_report_ref_to_thread(
    db,
    user_id: str,
    thread_id: Optional[str],
    report_ref: Dict[str, Any],
) -> bool:
    normalized_thread_id = (thread_id or "").strip()
    if not normalized_thread_id or _is_external_session_thread_id(normalized_thread_id):
        return False

    normalized_ref = _normalize_report_ref_item(report_ref)
    if not normalized_ref:
        return False

    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": normalized_thread_id,
        "archived": {"$ne": True},
    })
    if not thread or (thread.get("topic_type") or "") == "im_session":
        return False

    existing_refs = thread.get("report_refs") or []
    merged_refs = [
        ref for ref in existing_refs
        if not (
            (ref.get("ref_type") or "") == normalized_ref["ref_type"]
            and (ref.get("report_key") or "") == normalized_ref["report_key"]
        )
    ]
    merged_refs.insert(0, normalized_ref)
    merged_refs = merged_refs[:ASSISTANT_MAX_REPORT_REFS]

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": normalized_thread_id},
        {
            "$set": {
                "report_refs": merged_refs,
                "updated_at": _now_utc(),
            }
        },
    )
    return True


async def resolve_thread_for_report_writeback(
    db,
    user_id: str,
    preferred_thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_thread_id = (preferred_thread_id or "").strip()
    if normalized_thread_id and not _is_external_session_thread_id(normalized_thread_id):
        thread = await db.assistant_threads.find_one({
            "user_id": user_id,
            "thread_id": normalized_thread_id,
            "archived": {"$ne": True},
        })
        if thread and (thread.get("topic_type") or "") != "im_session":
            return thread

    fallback_thread = await create_assistant_thread(
        db,
        user_id=user_id,
        title=ASSISTANT_REPORT_INBOX_TITLE,
        parent_thread_id=None,
    )
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": fallback_thread["thread_id"],
        "archived": {"$ne": True},
    })
    return thread or fallback_thread


async def write_report_back_to_assistant_thread(
    db,
    user_id: str,
    report_ref: Dict[str, Any],
    preferred_thread_id: Optional[str] = None,
    summary_message: Optional[str] = None,
) -> Optional[str]:
    target_thread = await resolve_thread_for_report_writeback(db, user_id, preferred_thread_id)
    if not target_thread:
        return None

    target_thread_id = target_thread.get("thread_id")
    attached = await attach_report_ref_to_thread(db, user_id, target_thread_id, report_ref)
    if not attached:
        return None

    text = (summary_message or "").strip()
    if text:
        await append_assistant_message(
            db,
            user_id=user_id,
            role="assistant",
            content=text,
            conversation_id=target_thread_id,
            tools_used=["report_writeback"],
        )
        await summarize_assistant_thread(
            db,
            user_id=user_id,
            conversation_id=target_thread_id,
            summary_type="report_writeback",
        )

    return target_thread_id


def _to_iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    return text or None


def _build_stock_report_detail_content(task: Any) -> str:
    result = task.result or {}
    symbol = task.task_params.get("symbol", "未知") if task.task_params else "未知"
    lines = [f"# {symbol} 分析报告"]

    recommendation = result.get("recommendation")
    if recommendation:
        lines.append(f"\n## 投资建议\n{recommendation}")

    summary = result.get("summary") or result.get("executive_summary")
    if summary:
        lines.append(f"\n## 摘要\n{summary}")

    decision = result.get("decision") or {}
    if decision:
        decision_lines: List[str] = []
        if decision.get("action"):
            decision_lines.append(f"- 操作观点: {decision['action']}")
        if decision.get("confidence") is not None:
            decision_lines.append(f"- 置信度: {decision['confidence']}")
        if decision.get("risk_score") is not None:
            decision_lines.append(f"- 风险分: {decision['risk_score']}")
        reasoning = decision.get("reasoning")
        if reasoning:
            decision_lines.append(f"- 决策依据: {reasoning}")
        if decision_lines:
            lines.append("\n## 决策信息\n" + "\n".join(decision_lines))

    key_points = result.get("key_points") or []
    if key_points:
        lines.append("\n## 关键要点\n" + "\n".join(f"- {item}" for item in key_points[:8]))

    reports = result.get("reports") or {}
    if reports:
        lines.append("\n## 分析师摘录")
        for key, text in reports.items():
            cleaned = str(text or "").strip()
            if not cleaned:
                continue
            lines.append(f"\n### {key}\n{cleaned[:1500]}")

    lines.append(f"\n---\n任务ID: {task.task_id}")
    return "\n".join(lines)


def _build_stock_report_detail_content_from_doc(report_doc: Dict[str, Any]) -> str:
    stock_symbol = (report_doc.get("stock_symbol") or "未知").strip() or "未知"
    stock_name = (report_doc.get("stock_name") or "").strip()
    title = f"{stock_name}({stock_symbol})" if stock_name else stock_symbol
    lines = [f"# {title} 分析报告"]

    recommendation = str(report_doc.get("recommendation") or "").strip()
    if recommendation:
        lines.append(f"\n## 投资建议\n{recommendation}")

    summary = str(report_doc.get("summary") or "").strip()
    if summary:
        lines.append(f"\n## 摘要\n{summary}")

    decision = report_doc.get("decision") or {}
    if isinstance(decision, dict) and decision:
        decision_lines: List[str] = []
        if decision.get("action"):
            decision_lines.append(f"- 操作观点: {decision['action']}")
        if decision.get("confidence") is not None:
            decision_lines.append(f"- 置信度: {decision['confidence']}")
        if decision.get("risk_score") is not None:
            decision_lines.append(f"- 风险分: {decision['risk_score']}")
        reasoning = decision.get("reasoning")
        if reasoning:
            decision_lines.append(f"- 决策依据: {reasoning}")
        if decision_lines:
            lines.append("\n## 决策信息\n" + "\n".join(decision_lines))

    key_points = report_doc.get("key_points") or []
    if key_points:
        lines.append("\n## 关键要点\n" + "\n".join(f"- {item}" for item in key_points[:8]))

    reports = report_doc.get("reports") or {}
    if isinstance(reports, dict) and reports:
        lines.append("\n## 分析师摘录")
        for key, text in reports.items():
            cleaned = str(text or "").strip()
            if not cleaned:
                continue
            lines.append(f"\n### {key}\n{cleaned[:1500]}")

    if report_doc.get("analysis_id"):
        lines.append(f"\n---\n分析ID: {report_doc['analysis_id']}")
    if report_doc.get("task_id"):
        lines.append(f"任务ID: {report_doc['task_id']}")
    return "\n".join(lines)


def _build_position_report_detail_content(report: Dict[str, Any]) -> str:
    code = report.get("code") or "未知"
    name = report.get("name") or code
    lines = [f"# {name}({code}) 持仓分析报告"]

    status = report.get("status")
    action = report.get("action")
    confidence = report.get("confidence")
    meta: List[str] = []
    if status:
        meta.append(f"- 状态: {status}")
    if action:
        meta.append(f"- 操作建议: {action}")
    if confidence is not None:
        meta.append(f"- 置信度: {confidence}")
    if meta:
        lines.append("\n## 核心结论\n" + "\n".join(meta))

    summary = report.get("summary") or {}
    summary_lines: List[str] = []
    if summary.get("quantity") is not None:
        summary_lines.append(f"- 持仓数量: {summary['quantity']}")
    if summary.get("cost_price") is not None:
        summary_lines.append(f"- 成本价: {summary['cost_price']}")
    if summary.get("current_price") is not None:
        summary_lines.append(f"- 当前价: {summary['current_price']}")
    if summary.get("unrealized_pnl") is not None:
        summary_lines.append(f"- 浮动盈亏: {summary['unrealized_pnl']}")
    if summary.get("unrealized_pnl_pct") is not None:
        summary_lines.append(f"- 盈亏比例: {summary['unrealized_pnl_pct']}%")
    if summary_lines:
        lines.append("\n## 持仓概览\n" + "\n".join(summary_lines))

    targets = report.get("price_targets") or {}
    target_lines: List[str] = []
    for label, key in (("目标价", "target_price"), ("止损价", "stop_loss"), ("止盈价", "take_profit_price")):
        if targets.get(key) is not None:
            target_lines.append(f"- {label}: {targets[key]}")
    if target_lines:
        lines.append("\n## 目标价位\n" + "\n".join(target_lines))

    action_reason = str(report.get("action_reason") or "").strip()
    if action_reason:
        lines.append(f"\n## 分析详情\n{action_reason}")

    detailed = str(report.get("detailed_analysis") or "").strip()
    if detailed:
        lines.append(f"\n## 详细分析\n{detailed}")

    analysis_id = report.get("analysis_id")
    if analysis_id:
        lines.append(f"\n---\n分析ID: {analysis_id}")
    return "\n".join(lines)


async def get_assistant_thread_report_detail(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str,
    report_key: str,
) -> Dict[str, Any]:
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not thread:
        raise ValueError("主题不存在或已删除")

    target_ref = None
    for ref in thread.get("report_refs") or []:
        if (ref.get("ref_type") or "") == ref_type and (ref.get("report_key") or "") == report_key:
            target_ref = ref
            break
    if not target_ref:
        raise ValueError("当前主题下未找到对应的关联报告")

    detail = {
        "ref_type": target_ref.get("ref_type") or ref_type,
        "report_key": target_ref.get("report_key") or report_key,
        "title": target_ref.get("title") or "未命名报告",
        "symbol": target_ref.get("symbol") or None,
        "status": target_ref.get("status") or None,
        "task_id": target_ref.get("task_id") or None,
        "analysis_id": target_ref.get("analysis_id") or None,
        "created_at": _to_iso_datetime(target_ref.get("created_at")),
        "linked_at": _to_iso_datetime(target_ref.get("linked_at")),
        "content": (target_ref.get("summary") or "").strip(),
        "content_format": "markdown",
    }

    if ref_type == "stock_report":
        from app.services.task_analysis_service import get_task_analysis_service

        task_id = (target_ref.get("task_id") or report_key or "").strip()
        task = await get_task_analysis_service().get_task(task_id) if task_id else None
        if task and str(task.user_id) == str(user_id):
            detail["status"] = str(task.status)
            detail["created_at"] = _to_iso_datetime(task.created_at)
            detail["content"] = _build_stock_report_detail_content(task)
            return detail

        analysis_key = (target_ref.get("analysis_id") or report_key or task_id or "").strip()
        report_doc = await db.analysis_reports.find_one(_build_analysis_report_lookup_query(user_id, analysis_key))
        if not report_doc:
            raise ValueError("原始报告不存在或已被删除")
        detail["status"] = report_doc.get("status") or detail["status"]
        detail["task_id"] = report_doc.get("task_id") or detail["task_id"]
        detail["analysis_id"] = report_doc.get("analysis_id") or detail["analysis_id"]
        detail["created_at"] = _to_iso_datetime(report_doc.get("created_at"))
        detail["content"] = _build_stock_report_detail_content_from_doc(report_doc)
        return detail

    if ref_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        analysis_id = (target_ref.get("analysis_id") or report_key or "").strip()
        report = await get_portfolio_service().get_position_analysis_by_id(user_id, analysis_id)
        if not report:
            raise ValueError("原始持仓报告不存在或已被删除")
        detail["created_at"] = _to_iso_datetime(report.get("created_at"))
        detail["content"] = _build_position_report_detail_content(report)
        detail["status"] = report.get("status") or detail["status"]
        return detail

    if ref_type == "position_task":
        task_id = (target_ref.get("task_id") or report_key or "").strip()
        task_doc = await db.unified_analysis_tasks.find_one({"task_id": task_id})
        if not task_doc:
            raise ValueError("原始任务不存在或已被删除")
        if str(task_doc.get("user_id")) != str(user_id):
            raise ValueError("无权访问该任务")

        result = task_doc.get("result") or {}
        analysis_id = (result.get("analysis_id") or target_ref.get("analysis_id") or "").strip()
        if analysis_id:
            from app.services.portfolio_service import get_portfolio_service

            report = await get_portfolio_service().get_position_analysis_by_id(user_id, analysis_id)
            if report:
                detail["analysis_id"] = analysis_id
                detail["created_at"] = _to_iso_datetime(report.get("created_at"))
                detail["status"] = report.get("status") or detail["status"]
                detail["content"] = _build_position_report_detail_content(report)
                return detail

        status = task_doc.get("status") or detail["status"] or "unknown"
        detail["status"] = str(status)
        detail["created_at"] = _to_iso_datetime(task_doc.get("created_at"))
        detail["content"] = (
            f"# {detail['title']}\n\n"
            f"- 任务状态: {status}\n"
            f"- 任务ID: {task_id}\n\n"
            f"{(target_ref.get('summary') or '该任务尚未生成完整报告，后续完成后可在这里查看。').strip()}"
        )
        return detail

    return detail


def _build_stock_report_ref_from_task(task: Any, stock_name: Optional[str] = None) -> Dict[str, Any]:
    result = task.result or {}
    task_params = task.task_params or {}
    symbol = (task_params.get("symbol") or "").strip()
    display_name = (stock_name or "").strip()
    title_prefix = f"{display_name}({symbol})" if display_name and symbol else display_name or symbol or "未知标的"
    return {
        "ref_type": "stock_report",
        "report_key": task.task_id,
        "source_collection": "unified_analysis_tasks",
        "title": f"{title_prefix} 分析报告",
        "symbol": symbol or None,
        "summary": ((result.get("summary") or result.get("recommendation") or "")[:400]).strip(),
        "status": str(task.status),
        "task_id": task.task_id,
        "created_at": getattr(task, "created_at", None),
    }


def _build_stock_report_ref_from_analysis_doc(report_doc: Dict[str, Any]) -> Dict[str, Any]:
    stock_symbol = (report_doc.get("stock_symbol") or "").strip()
    stock_name = (report_doc.get("stock_name") or "").strip()
    title_prefix = f"{stock_name}({stock_symbol})" if stock_name and stock_symbol else stock_name or stock_symbol or "未知标的"
    report_key = (report_doc.get("task_id") or report_doc.get("analysis_id") or str(report_doc.get("_id") or "")).strip()
    return {
        "ref_type": "stock_report",
        "report_key": report_key,
        "source_collection": "analysis_reports",
        "title": f"{title_prefix} 分析报告",
        "symbol": stock_symbol or None,
        "summary": ((report_doc.get("summary") or report_doc.get("recommendation") or "")[:400]).strip(),
        "status": report_doc.get("status") or "completed",
        "task_id": (report_doc.get("task_id") or "").strip() or None,
        "analysis_id": (report_doc.get("analysis_id") or "").strip() or None,
        "created_at": report_doc.get("created_at"),
    }


def _build_analysis_report_lookup_query(user_id: str, report_key: str) -> Dict[str, Any]:
    report_query = {
        "$or": [
            {"task_id": report_key},
            {"analysis_id": report_key},
        ]
    }
    if ObjectId.is_valid(report_key):
        report_query["$or"].append({"_id": ObjectId(report_key)})

    return {
        "$and": [
            {"$or": [{"user_id": user_id}, {"user_id": str(user_id)}]},
            report_query,
        ]
    }


def _build_position_report_ref_from_report(report: Dict[str, Any]) -> Dict[str, Any]:
    code = (report.get("code") or "").strip()
    name = (report.get("name") or "").strip()
    title_prefix = f"{name}({code})" if name and code else name or code or "未知持仓"
    return {
        "ref_type": "position_report",
        "report_key": report.get("analysis_id") or "",
        "source_collection": "position_analysis_reports",
        "title": f"{title_prefix} 持仓分析",
        "symbol": code or None,
        "summary": ((report.get("summary") or report.get("action_reason") or "")[:400]).strip(),
        "status": report.get("status") or None,
        "analysis_id": report.get("analysis_id") or None,
        "created_at": report.get("created_at"),
    }


async def search_assistant_attachable_reports(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str = "stock_report",
    keyword: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not thread or (thread.get("topic_type") or "") == "im_session":
        raise ValueError("当前主题不存在或不支持关联报告")

    normalized_type = (ref_type or "stock_report").strip() or "stock_report"
    normalized_keyword = (keyword or "").strip()
    limit = max(1, min(limit, 20))

    if normalized_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        query: Dict[str, Any] = {
            "user_id": user_id,
            "analysis_id": {"$exists": True, "$ne": ""},
        }
        if normalized_keyword:
            query["$or"] = [
                {"code": {"$regex": normalized_keyword, "$options": "i"}},
                {"name": {"$regex": normalized_keyword, "$options": "i"}},
                {"summary": {"$regex": normalized_keyword, "$options": "i"}},
                {"analysis_id": {"$regex": normalized_keyword, "$options": "i"}},
            ]

        docs = await db.position_analysis_reports.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        service = get_portfolio_service()
        results: List[Dict[str, Any]] = []
        for doc in docs:
            analysis_id = (doc.get("analysis_id") or "").strip()
            if not analysis_id:
                continue
            report = await service.get_position_analysis_by_id(user_id, analysis_id)
            if not report:
                continue
            results.append(_normalize_report_ref_item(_build_position_report_ref_from_report(report)))
        return [item for item in results if item][:limit]

    from app.services.task_analysis_service import get_task_analysis_service

    service = get_task_analysis_service()
    results: List[Dict[str, Any]] = []
    seen_keys = set()

    if normalized_keyword:
        analysis_query: Dict[str, Any] = {
            "$and": [
                {"$or": [{"user_id": user_id}, {"user_id": str(user_id)}]},
                {
                    "$or": [
                        {"stock_symbol": {"$regex": normalized_keyword, "$options": "i"}},
                        {"stock_name": {"$regex": normalized_keyword, "$options": "i"}},
                        {"summary": {"$regex": normalized_keyword, "$options": "i"}},
                        {"analysis_id": {"$regex": normalized_keyword, "$options": "i"}},
                        {"task_id": {"$regex": normalized_keyword, "$options": "i"}},
                    ]
                },
            ]
        }
        analysis_docs = await db.analysis_reports.find(analysis_query).sort("created_at", -1).limit(limit * 3).to_list(length=limit * 3)
        for doc in analysis_docs:
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_analysis_doc(doc))
            ref_key = (ref or {}).get("report_key") if ref else None
            if not ref_key or ref_key in seen_keys:
                continue
            if ref:
                results.append(ref)
                seen_keys.add(ref_key)
            if len(results) >= limit:
                return results[:limit]

    task_query: Dict[str, Any] = {
        "$and": [
            {"status": "completed"},
            {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id)}]},
        ]
    }
    if normalized_keyword:
        task_query["$and"].append({
            "$or": [
                {"task_params.symbol": {"$regex": normalized_keyword, "$options": "i"}},
                {"result.summary": {"$regex": normalized_keyword, "$options": "i"}},
                {"result.recommendation": {"$regex": normalized_keyword, "$options": "i"}},
                {"task_id": {"$regex": normalized_keyword, "$options": "i"}},
            ]
        })

    task_docs = await db.unified_analysis_tasks.find(task_query).sort("created_at", -1).limit(limit * 2).to_list(length=limit * 2)
    for doc in task_docs:
        task_id = (doc.get("task_id") or "").strip()
        if not task_id or task_id in seen_keys:
            continue
        task = await service.get_task(task_id)
        if not task or str(task.user_id) != str(user_id) or str(task.status) != "completed":
            continue
        ref = _normalize_report_ref_item(_build_stock_report_ref_from_task(task))
        if ref:
            results.append(ref)
            seen_keys.add(task_id)
        if len(results) >= limit:
            break

    return results[:limit]


async def attach_existing_report_to_thread(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str,
    report_key: str,
) -> Dict[str, Any]:
    normalized_type = (ref_type or "").strip()
    normalized_key = (report_key or "").strip()
    if not normalized_type or not normalized_key:
        raise ValueError("报告类型和报告标识不能为空")

    if normalized_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        report = await get_portfolio_service().get_position_analysis_by_id(user_id, normalized_key)
        if not report:
            raise ValueError("未找到可关联的持仓报告")
        ref = _normalize_report_ref_item(_build_position_report_ref_from_report(report))
    else:
        from app.services.task_analysis_service import get_task_analysis_service

        task = await get_task_analysis_service().get_task(normalized_key)
        if task and str(task.user_id) == str(user_id) and str(task.status) == "completed":
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_task(task))
        else:
            report_doc = await db.analysis_reports.find_one(_build_analysis_report_lookup_query(user_id, normalized_key))
            if not report_doc:
                raise ValueError("未找到可关联的历史分析报告")
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_analysis_doc(report_doc))

    if not ref:
        raise ValueError("报告信息不完整，无法关联")

    attached = await attach_report_ref_to_thread(db, user_id, thread_id, ref)
    if not attached:
        raise ValueError("当前主题不支持关联该报告")
    return ref


def _extract_sentences(text: str) -> List[str]:
    raw = (text or "").replace("\r", "\n")
    fragments: List[str] = []
    for chunk in raw.split("\n"):
        chunk = chunk.strip(" -•\t")
        if not chunk:
            continue
        parts = [part.strip() for part in chunk.replace("！", "。").replace("？", "。").split("。")]
        for part in parts:
            if part:
                fragments.append(part)
    return fragments


def _build_thread_summary_from_messages(messages: List[Dict[str, Any]], title: str = "") -> Dict[str, Any]:
    user_messages = [m.get("content", "").strip() for m in messages if m.get("role") == "user" and m.get("content")]
    assistant_messages = [m.get("content", "").strip() for m in messages if m.get("role") == "assistant" and m.get("content")]

    latest_user = user_messages[-1] if user_messages else ""
    latest_assistant = assistant_messages[-1] if assistant_messages else ""
    abstract = latest_assistant[:160] or latest_user[:160] or (title[:160] if title else "") or "当前主题尚未形成摘要"

    confirmed_candidates: List[str] = []
    for content in reversed(assistant_messages[-4:]):
        confirmed_candidates.extend(_extract_sentences(content))

    question_candidates: List[str] = []
    for content in reversed(user_messages[-4:]):
        question_candidates.extend(_extract_sentences(content))

    next_actions: List[str] = []
    if latest_user:
        next_actions.append(f"围绕“{latest_user[:40]}”继续追问或补数")
    if latest_assistant:
        next_actions.append("结合当前结论继续细化估值、行业或风险主线")
    if not next_actions:
        next_actions.append("继续在当前主题下补充问题或触发深度分析")

    total_messages = len(messages)
    assistant_ratio = len(assistant_messages) / total_messages if total_messages else 0
    focus_score = 0.55
    if total_messages >= 4:
        focus_score += 0.1
    if total_messages >= 8:
        focus_score += 0.05
    if latest_user and title and any(token for token in title.split() if token and token in latest_user):
        focus_score += 0.1
    if assistant_ratio >= 0.4:
        focus_score += 0.1
    focus_score = min(round(focus_score, 2), 0.95)

    return {
        "abstract": abstract,
        "confirmed_facts": _normalize_summary_items(confirmed_candidates),
        "open_questions": _normalize_summary_items(question_candidates),
        "next_actions": _normalize_summary_items(next_actions),
        "focus_score": focus_score,
    }


async def _create_thread_document(
    db,
    user_id: str,
    thread_id: str,
    title: str,
    parent_thread_id: Optional[str] = None,
    topic_type: str = "general",
) -> Dict[str, Any]:
    now = _now_utc()
    doc = {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": title,
        "parent_thread_id": parent_thread_id,
        "topic_type": topic_type,
        "pinned": thread_id == ASSISTANT_DEFAULT_THREAD_ID,
        "archived": False,
        "message_count": 0,
        "last_user_message": "",
        "report_refs": [],
        "current_summary": {
            "abstract": "",
            "confirmed_facts": [],
            "open_questions": [],
            "next_actions": [],
            "focus_score": 0.0,
        },
        "created_at": now,
        "updated_at": now,
    }
    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})


async def _migrate_legacy_conversation_if_needed(db, user_id: str, thread_id: str) -> None:
    if thread_id != ASSISTANT_DEFAULT_THREAD_ID:
        return

    message_count = await db.assistant_thread_messages.count_documents({
        "user_id": user_id,
        "thread_id": thread_id,
    })
    if message_count > 0:
        return

    legacy_doc = await db.assistant_conversations.find_one({"user_id": user_id})
    legacy_messages = (legacy_doc or {}).get("messages") or []
    if not legacy_messages:
        return

    now = _now_utc()
    payload = []
    last_user_message = ""
    for idx, message in enumerate(legacy_messages):
        content = (message.get("content") or "").strip()
        if not content:
            continue
        role = message.get("role") or "assistant"
        if role == "user":
            last_user_message = content
        payload.append({
            "message_id": f"legacy_{idx}_{uuid.uuid4().hex[:8]}",
            "thread_id": thread_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "tools_used": message.get("tools_used") or [],
            "created_at": now,
        })

    if not payload:
        return

    await db.assistant_thread_messages.insert_many(payload)
    abstract = ""
    for message in reversed(payload):
        if message["role"] == "assistant":
            abstract = message["content"][:120]
            break

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {
            "$set": {
                "message_count": len(payload),
                "last_user_message": last_user_message,
                "current_summary": {
                    "abstract": abstract,
                    "confirmed_facts": [],
                    "open_questions": [],
                    "next_actions": [],
                    "focus_score": 0.5,
                },
                "updated_at": now,
            }
        },
    )


async def get_or_create_assistant_thread(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    thread_id = (conversation_id or ASSISTANT_DEFAULT_THREAD_ID).strip() if conversation_id else ASSISTANT_DEFAULT_THREAD_ID
    topic_type = "im_session" if _is_external_session_thread_id(thread_id) else "general"
    doc = await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})
    if doc is None:
        title = "默认主题" if thread_id == ASSISTANT_DEFAULT_THREAD_ID else ("外部会话" if topic_type == "im_session" else f"新主题 {datetime.now().strftime('%m-%d %H:%M')}")
        doc = await _create_thread_document(db, user_id, thread_id, title, topic_type=topic_type)
    elif topic_type == "im_session" and doc.get("topic_type") != "im_session":
        await db.assistant_threads.update_one(
            {"user_id": user_id, "thread_id": thread_id},
            {
                "$set": {
                    "topic_type": "im_session",
                    "title": doc.get("title") or "外部会话",
                    "updated_at": _now_utc(),
                }
            },
        )
    await _migrate_legacy_conversation_if_needed(db, user_id, thread_id)
    return await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})


async def list_assistant_threads(db, user_id: str) -> List[Dict[str, Any]]:
    await get_or_create_assistant_thread(db, user_id)
    items: List[Dict[str, Any]] = []
    cursor = db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).sort([("pinned", -1), ("parent_thread_id", 1), ("updated_at", -1)])
    async for doc in cursor:
        if _is_visible_assistant_topic(doc):
            items.append(_thread_doc_to_item(doc))
    return items


async def create_assistant_thread(
    db,
    user_id: str,
    title: Optional[str] = None,
    parent_thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_parent_id = (parent_thread_id or "").strip() or None
    if normalized_parent_id:
        parent = await db.assistant_threads.find_one({
            "user_id": user_id,
            "thread_id": normalized_parent_id,
            "archived": {"$ne": True},
        })
        if not parent:
            raise ValueError("父主题不存在或已删除")

    thread_id = _generate_thread_id()
    thread_title = (title or "").strip() or f"新主题 {datetime.now().strftime('%m-%d %H:%M')}"
    existing_docs = await db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).to_list(length=None)
    existing_docs = [doc for doc in existing_docs if _is_visible_assistant_topic(doc)]
    similar_doc = _find_similar_thread(existing_docs, thread_title, normalized_parent_id)
    if similar_doc:
        return _thread_doc_to_item(similar_doc)

    doc = await _create_thread_document(
        db,
        user_id,
        thread_id,
        thread_title,
        parent_thread_id=normalized_parent_id,
        topic_type="subtopic" if normalized_parent_id else "general",
    )
    return _thread_doc_to_item(doc)


async def delete_assistant_thread(db, user_id: str, thread_id: str) -> List[str]:
    normalized_thread_id = (thread_id or "").strip()
    if not normalized_thread_id:
        raise ValueError("主题 ID 不能为空")
    if normalized_thread_id == ASSISTANT_DEFAULT_THREAD_ID:
        raise ValueError("默认主题不能删除")

    docs = await db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).to_list(length=None)
    docs = [doc for doc in docs if _is_visible_assistant_topic(doc)]

    by_id = {doc.get("thread_id"): doc for doc in docs}
    if normalized_thread_id not in by_id:
        raise ValueError("主题不存在或已删除")

    children_by_parent: Dict[str, List[str]] = {}
    for doc in docs:
        parent_id = doc.get("parent_thread_id")
        child_id = doc.get("thread_id")
        if parent_id and child_id:
            children_by_parent.setdefault(parent_id, []).append(child_id)

    pending = [normalized_thread_id]
    deleted_ids: List[str] = []
    while pending:
        current_id = pending.pop()
        if current_id in deleted_ids:
            continue
        deleted_ids.append(current_id)
        pending.extend(children_by_parent.get(current_id, []))

    await db.assistant_thread_messages.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })
    await db.assistant_thread_checkpoints.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })
    await db.assistant_threads.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })

    return deleted_ids


async def get_assistant_thread_messages(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    messages: List[Dict[str, Any]] = []
    cursor = db.assistant_thread_messages.find({
        "user_id": user_id,
        "thread_id": thread["thread_id"],
    }).sort("created_at", 1)
    async for doc in cursor:
        messages.append({
            "role": doc.get("role", "assistant"),
            "content": doc.get("content", ""),
            "tools_used": doc.get("tools_used") or None,
        })
    return _thread_doc_to_item(thread), messages


async def append_assistant_message(
    db,
    user_id: str,
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
) -> str:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    thread_id = thread["thread_id"]
    text = (content or "").strip()
    if not text:
        return thread_id

    await db.assistant_thread_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex}",
        "thread_id": thread_id,
        "user_id": user_id,
        "role": role,
        "content": text,
        "tools_used": tools_used or [],
        "created_at": _now_utc(),
    })

    updates: Dict[str, Any] = {"updated_at": _now_utc()}
    if role == "user":
        updates["last_user_message"] = text[:200]
    elif role == "assistant":
        updates["current_summary.abstract"] = text[:120]

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {
            "$set": updates,
            "$inc": {"message_count": 1},
        },
    )
    return thread_id


async def summarize_assistant_thread(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
    summary_type: str = "manual",
) -> Dict[str, Any]:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    _, messages = await get_assistant_thread_messages(db, user_id, thread["thread_id"])
    summary = _build_thread_summary_from_messages(messages[-12:], thread.get("title") or "")
    now = _now_utc()

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread["thread_id"]},
        {
            "$set": {
                "current_summary": summary,
                "updated_at": now,
            }
        },
    )

    await db.assistant_thread_checkpoints.insert_one({
        "checkpoint_id": f"chk_{uuid.uuid4().hex[:12]}",
        "thread_id": thread["thread_id"],
        "user_id": user_id,
        "summary_type": summary_type,
        "summary_text": summary.get("abstract", ""),
        "structured_summary": summary,
        "created_at": now,
    })

    return summary


async def save_assistant_message(
    db,
    user_id: str,
    user_content: str,
    assistant_content: str,
    tools_used: List[str],
    conversation_id: Optional[str] = None,
) -> None:
    """将会话追加写入 MongoDB"""
    thread_id = await append_assistant_message(
        db,
        user_id=user_id,
        role="user",
        content=user_content,
        conversation_id=conversation_id,
    )
    await append_assistant_message(
        db,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        conversation_id=thread_id,
        tools_used=tools_used,
    )
    await summarize_assistant_thread(
        db,
        user_id=user_id,
        conversation_id=thread_id,
        summary_type="auto",
    )


async def get_assistant_conversation(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取用户的智能助手会话历史"""
    _, messages = await get_assistant_thread_messages(db, user_id, conversation_id)
    return messages


async def clear_assistant_conversation(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> None:
    """清空用户的智能助手会话"""
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    await db.assistant_thread_messages.delete_many(
        {"user_id": user_id, "thread_id": thread["thread_id"]}
    )
    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread["thread_id"]},
        {
            "$set": {
                "message_count": 0,
                "last_user_message": "",
                "current_summary": {
                    "abstract": "",
                    "confirmed_facts": [],
                    "open_questions": [],
                    "next_actions": [],
                    "focus_score": 0.0,
                },
                "updated_at": _now_utc(),
            }
        },
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
    current_thread_id: Optional[str] = None,
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
    if current_thread_id:
        set_current_assistant_thread_id(current_thread_id)
    elif conversation_id:
        set_current_assistant_thread_id(conversation_id)

    # 加载用户助理个性化设置
    assistant_settings = None
    if user_id:
        assistant_settings = await _load_assistant_settings(db, user_id)

    # 加载用户画像（跨会话持久记忆）
    user_profile: Optional[dict] = None
    current_topic_title: Optional[str] = None
    if user_id:
        try:
            user_profile = await load_user_profile(db, user_id)
            if user_profile and user_profile.get("recently_analyzed"):
                logger.info(f"[智能助手] ✅ 用户画像加载成功，最近分析 {len(user_profile['recently_analyzed'])} 条")
        except Exception as e:
            logger.warning(f"[智能助手] 加载用户画像失败（已跳过）: {e}")

    if user_id and current_thread_id:
        try:
            current_topic = await db.assistant_threads.find_one(
                {
                    "user_id": user_id,
                    "thread_id": current_thread_id,
                    "archived": {"$ne": True},
                },
                {"title": 1},
            )
            if current_topic:
                current_topic_title = (current_topic.get("title") or "").strip() or None
        except Exception as e:
            logger.warning(f"[智能助手] 加载当前主题失败（已跳过）: {e}")

    # 加载最近会话历史（最多 10 条，注入到 LLM 上下文）
    history_messages: Optional[List[Message]] = None
    if user_id:
        try:
            raw_history = await get_assistant_conversation(db, user_id, conversation_id)
            if raw_history:
                recent = raw_history[-ASSISTANT_MAX_CONTEXT_MESSAGES:]
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
    result = await service.chat(
        user_message,
        conversation_id,
        assistant_settings,
        is_im=is_im,
        history_messages=history_messages,
        user_profile=user_profile,
        current_topic_title=current_topic_title,
    )
    if user_id and result.get("reply"):
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=result["reply"],
                tools_used=result.get("tools_used") or [],
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.warning("[智能助手] 保存会话失败: %s", e)
    if user_id:
        thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
        result["conversation_id"] = thread["thread_id"]
    return result
