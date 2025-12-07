from datetime import datetime

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.tools.tool_registry import get_news_toolset
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.utils.tool_logging import log_analyst_module

logger = get_logger("analysts.news")


def create_news_analyst(llm, toolkit):
    @log_analyst_module("news")
    def news_analyst_node(state):
        start_time = datetime.now()

        # 🔧 工具调用计数器 - 防止无限循环
        tool_call_count = state.get("news_tool_call_count", 0)
        max_tool_calls = 3  # 最大工具调用轮次
        logger.info(f"🔧 [死循环修复] 当前工具调用次数: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.info(f"[新闻分析师] 开始分析 {ticker} 的新闻，交易日期: {current_date}")
        session_id = state.get("session_id", "未知会话")
        logger.info(f"[新闻分析师] 会话ID: {session_id}，开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 获取市场信息
        market_info = StockUtils.get_market_info(ticker)
        logger.info(f"[新闻分析师] 股票类型: {market_info['market_name']}")

        # 获取公司名称
        def _get_company_name(ticker: str, market_info: dict) -> str:
            """根据股票代码获取公司名称"""
            try:
                if market_info["is_china"]:
                    from tradingagents.dataflows.interface import get_china_stock_info_unified

                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                        logger.debug(f"📊 [DEBUG] 从统一接口获取中国股票名称: {ticker} -> {company_name}")
                        return company_name
                    logger.warning(f"⚠️ [DEBUG] 无法从统一接口解析股票名称: {ticker}")
                    return f"股票代码{ticker}"

                if market_info["is_hk"]:
                    try:
                        from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved

                        company_name = get_hk_company_name_improved(ticker)
                        logger.debug(f"📊 [DEBUG] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                        return company_name
                    except Exception as exc:
                        logger.debug(f"📊 [DEBUG] 改进港股工具获取名称失败: {exc}")
                        clean_ticker = ticker.replace(".HK", "").replace(".hk", "")
                        return f"港股{clean_ticker}"

                if market_info["is_us"]:
                    us_stock_names = {
                        "AAPL": "苹果公司",
                        "TSLA": "特斯拉",
                        "NVDA": "英伟达",
                        "MSFT": "微软",
                        "GOOGL": "谷歌",
                        "AMZN": "亚马逊",
                        "META": "Meta",
                        "NFLX": "奈飞",
                    }
                    company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
                    logger.debug(f"📊 [DEBUG] 美股名称映射: {ticker} -> {company_name}")
                    return company_name

                return f"股票{ticker}"

            except Exception as exc:
                logger.error(f"❌ [DEBUG] 获取公司名称失败: {exc}")
                return f"股票{ticker}"

        company_name = _get_company_name(ticker, market_info)
        logger.info(f"[新闻分析师] 公司名称: {company_name}")

        # 统一工具装配（预留 MCP 扩展）
        tools = get_news_toolset(toolkit=toolkit, enable_mcp=False)
        tool_lookup = {tool.name: tool for tool in tools}
        logger.info(f"[新闻分析师] 已加载工具: {', '.join(tool_lookup.keys()) if tool_lookup else '无'}")
        if not tool_lookup:
            logger.error("[新闻分析师] 未能加载任何新闻工具，无法继续分析")
            failure_report = "❌ 未加载到新闻工具，无法基于真实数据进行分析。"
            clean_message = AIMessage(content=failure_report)
            return {
                "messages": [clean_message],
                "news_report": failure_report,
                "news_tool_call_count": tool_call_count,
            }

        system_message = (
            """您是一位专业的财经新闻分析师，负责分析最新市场新闻对股票价格的潜在影响。

您的主要职责包括：
1. 获取和分析最新的实时新闻（优先15-30分钟内的新闻）
2. 评估新闻事件的紧急程度和市场影响
3. 识别可能影响股价的关键信息
4. 分析新闻的时效性和可靠性
5. 提供基于新闻的交易建议和价格影响评估

重点关注：
- 财报/业绩指引、合作并购、政策监管、突发事件、行业趋势、管理层变动

分析要点：
- 时效性、可信度、市场影响、情绪变化、历史对比
- 不允许回复“无法评估影响”或“需要更多信息”

输出要求：
- 评估短期影响（1-3天）与市场情绪
- 给出利好/利空判断、潜在市场反应、长期价值影响
- 结尾附Markdown表格总结关键发现。"""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "您是一位专业的财经新闻分析师。"
                    "\n🚨 强制要求：第一步必须调用 get_stock_news_unified 获取真实新闻，然后基于结果分析。"
                    "\n✅ 必须基于工具返回的数据进行分析，不得凭空推测。"
                    "\n可用工具：{tool_names}。"
                    "\n{system_message}"
                    "\n当前日期: {current_date}，公司: {ticker}。"
                    "\n用中文输出所有分析。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join(tool_lookup.keys()))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        llm_chain = prompt | llm.bind_tools(tools)

        messages = list(state.get("messages", []))
        executed_tool_calls = 0
        final_report = ""
        forced_tool_used = False

        logger.info(f"[新闻分析师] 开始LLM+工具循环，最大轮次: {max_tool_calls}")
        for round_idx in range(max_tool_calls):
            logger.info(f"[新闻分析师] 轮次 {round_idx + 1} 开始，当前消息数: {len(messages)}")
            ai_message = llm_chain.invoke({"messages": messages})
            messages.append(ai_message)

            tool_calls = getattr(ai_message, "tool_calls", []) or []
            logger.info(f"[新闻分析师] 本轮工具调用数: {len(tool_calls)}")

            if tool_calls:
                for call in tool_calls:
                    name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
                    args = getattr(call, "args", None) if not isinstance(call, dict) else call.get("args", {})
                    call_id = getattr(call, "id", None) if not isinstance(call, dict) else call.get("id")

                    tool = tool_lookup.get(name)
                    if not tool:
                        logger.warning(f"[新闻分析师] 未注册的工具调用: {name}")
                        continue

                    logger.info(f"[新闻分析师] 执行工具: {name}，参数: {args}")
                    tool_output = tool.invoke(args if isinstance(args, dict) else {})
                    executed_tool_calls += 1

                    messages.append(
                        ToolMessage(
                            content=str(tool_output),
                            name=name,
                            tool_call_id=str(call_id) if call_id else None,
                        )
                    )
                continue

            # 未产生工具调用
            if executed_tool_calls == 0:
                # 强制调用默认新闻工具，确保有真实新闻数据
                default_tool = next(iter(tool_lookup.values()))
                logger.warning("[新闻分析师] 模型未调用工具，强制执行 get_stock_news_unified")
                forced_args = {"stock_code": ticker, "max_news": 10, "model_info": llm.__class__.__name__}
                tool_output = default_tool.invoke(forced_args)
                executed_tool_calls += 1
                forced_tool_used = True
                messages.append(
                    ToolMessage(
                        content=str(tool_output),
                        name=default_tool.name,
                        tool_call_id="forced-news-call-1",
                    )
                )
                continue

            final_report = ai_message.content or ""
            logger.info(f"[新闻分析师] 获得最终分析内容，长度: {len(final_report)} 字符")
            break
        else:
            logger.warning("[新闻分析师] 达到最大工具调用轮次，返回最后一次模型内容")
            if messages and hasattr(messages[-1], "content"):
                final_report = messages[-1].content or ""

        total_time_taken = (datetime.now() - start_time).total_seconds()
        logger.info(f"[新闻分析师] 新闻分析完成，总耗时: {total_time_taken:.2f}秒")

        clean_message = AIMessage(content=final_report)
        logger.info(f"[新闻分析师] ✅ 返回清洁消息，报告长度: {len(final_report)} 字符")

        return {
            "messages": [clean_message],
            "news_report": final_report,
            "news_tool_call_count": tool_call_count + executed_tool_calls,
        }

    return news_analyst_node
