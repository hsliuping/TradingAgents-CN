"""近期信息搜索工具。"""

import logging
import os
from datetime import datetime
from typing import Annotated, Any, Optional

from langchain_core.tools import tool
from openai import OpenAI

from core.tools.base import register_tool
from tradingagents.agents.utils.agent_utils import Toolkit

logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_SEARCH_MODEL = os.getenv("DASHSCOPE_SEARCH_MODEL", "qwen3.5-plus")


def _invoke_legacy_tool(tool_func, **kwargs):
    try:
        if hasattr(tool_func, "invoke"):
            return tool_func.invoke(kwargs)
        return tool_func(**kwargs)
    except Exception as exc:
        logger.error("调用近期搜索底层工具失败 %s: %s", tool_func, exc)
        return f"近期信息搜索失败: {str(exc)}"


def _resolve_dashscope_runtime_config() -> tuple[Optional[str], str, str]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL)
    model = DEFAULT_SEARCH_MODEL

    if api_key:
        return api_key, base_url, model

    try:
        from pymongo import MongoClient
        from app.core.config import settings

        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
        provider_doc = db.llm_providers.find_one({"name": "dashscope"}) or {}
        client.close()

        api_key = provider_doc.get("api_key") or api_key
        base_url = provider_doc.get("default_base_url") or base_url
    except Exception as exc:
        logger.warning("读取 DashScope 配置失败，回退环境变量: %s", exc)

    return api_key, base_url, model


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    pieces: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                pieces.append(str(text).strip())
    return "\n\n".join(piece for piece in pieces if piece).strip()


def _search_with_qwen(query: str, curr_date: str) -> str:
    api_key, base_url, model = _resolve_dashscope_runtime_config()
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，也未在 llm_providers 中找到 DashScope API Key")

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = (
        f"请联网搜索并确认以下问题的近期公开信息：{query}。"
        f"当前日期是 {curr_date}。"
        "优先使用最近30天的信息；如果没有，再回退到最近90天。"
        "请优先引用交易所公告、公司公告、权威财经媒体。"
        "不要凭常识补充历史背景，不要自行推断未被近期来源直接支持的结论。"
        "不要用‘很可能’‘大概率’这类模糊措辞来冒充确定结论。"
        "如果证据不足以完全确认，不要只回答‘无法确认’就结束；应继续列出可参考的近期媒体报道或市场信息，并标明它们不是最终确证。"
        "不要输出时间线表格，除非每个时间点都有近期可验证来源。"
        "请严格按下面格式输出："
        "【最新结论】先给当前能确认到的最稳妥结论。若不能完全确认，要明确写‘目前无法完全确认’，但仍要补充参考信息。"
        "【确证依据】列出2-4条确证性来源，每条包含：日期 | 来源 | 标题 | 可直接确认的信息。没有就写‘无直接确证来源’。"
        "【参考报道】列出2-5条参考性来源，例如财新、证券时报、路透、彭博、主流财经媒体报道；每条包含：日期 | 来源 | 标题 | 报道口径。并在本段开头明确说明‘以下为参考报道，未必等同于最终官方确证’。"
        "【不确定点】明确写还缺什么证据，例如‘缺少港交所最新权益披露’。如果没有，写‘无’。"
        "如果有媒体明确报道‘已清仓’‘已降至5%以下’‘已不再披露’，这些内容应该进入【参考报道】或【最新结论】中，但必须区分是媒体报道还是官方确证。"
    )

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "medium",
            }
        ],
        temperature=0.2,
        max_output_tokens=2048,
        top_p=0.9,
        store=False,
    )

    text = _extract_response_text(response)
    if not text:
        raise RuntimeError("百炼搜索返回为空")
    return text


def run_recent_information_search(query: str) -> str:
    """搜索近期公开信息，优先用于事实确认类问题。

    搜索源优先级：
    1. SearXNG 本地实例（快，约1-2秒；SEARXNG_INSTANCES 配置时启用）
    2. DashScope 联网搜索（qwen + web_search_preview，较慢，可能超时）
    3. Google News（兜底）
    """
    query_clean = (query or "").strip()
    if not query_clean:
        return "请提供要搜索的关键词，例如：比亚迪 伯克希尔 减持 持股比例。"

    curr_date = datetime.now().strftime("%Y-%m-%d")

    # 1) SearXNG 本地搜索（优先，秒级返回）
    try:
        from core.tools.implementations.assistant_ops.web_search import run_web_search

        searx_result = run_web_search(query_clean, max_results=10)
        if searx_result and not searx_result.startswith("Web 搜索失败"):
            return (
                f"以下是“{query_clean}”的近期联网搜索结果（搜索引擎聚合，按相关性排序）。"
                "请优先依据发布时间最新、来源更权威的条目回答，并注意核对发布日期。\n\n"
                f"{searx_result}"
            )
        logger.warning("SearXNG 搜索无结果，回退 DashScope: %s", query_clean)
    except Exception as exc:
        logger.warning("SearXNG 搜索失败，回退 DashScope: %s", exc)

    # 2) DashScope 联网搜索（备选）
    try:
        result = _search_with_qwen(query_clean, curr_date)
        return (
            f"以下是“{query_clean}”的近期联网搜索结果。请优先依据发布时间最新、来源更权威的条目回答。\n\n"
            f"{result}"
        )
    except Exception as exc:
        logger.warning("百炼近期搜索失败，回退 Google News: %s", exc)

    # 3) Google News（兜底）
    result = _invoke_legacy_tool(Toolkit.get_google_news, query=query_clean, curr_date=curr_date)
    if not result or str(result).startswith("近期信息搜索失败"):
        return f"近期信息搜索失败：{result}"

    return (
        f"百炼搜索暂时不可用，以下回退为 Google News 近期搜索结果。请优先依据发布时间最新、来源更权威的条目回答。\n\n"
        f"{result}"
    )


@tool
@register_tool(
    tool_id="search_recent_information",
    name="近期信息搜索",
    description="搜索最近7天内的公开新闻与近期信息。适合回答‘截至目前’‘最新’‘近期是否有变化’‘需要确认最新持股比例/公告/消息’这类问题。输入应包含公司名、事件关键词或股票代码。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    data_source_handling="local_only",
    capability_tags=["information_search", "recent_news", "web_search", "assistant_ops", "fact_check", "news_query", "current_events", "online_search", "market_information", "real_time_info"],
    tool_role_hint="specialized",
    output_shape="report",
    preferred_for=["搜索近期公开新闻", "确认最新事实信息", "查询近期公告或事件", "核实最新持股或市场动态"],
    when_to_use="当用户问及‘截至目前’‘最新’‘近期是否有变化’或需要确认最新持股比例、公告、市场消息等时使用。",
    when_not_to_use="不适用于查询个股股价走势、行情涨跌、是否反弹/回调/突破等价格趋势判断——这类问题必须调用行情数据工具（get_stock_market_data_unified / get_technical_indicators / 实时行情）获取真实K线数据，网页搜索结果无法提供股价走势；也不适用于查询历史价格数据。",
    returns="返回文本格式的搜索结果，包含最新结论、确证依据、参考报道和不确定点。",
)
def search_recent_information(
    query: Annotated[str, "搜索关键词，例如：比亚迪 伯克希尔 减持 持股比例，或 宁德时代 最新 公告"],
) -> str:
    """搜索近期公开信息，用于最新事实确认类问题。"""
    return run_recent_information_search(query)