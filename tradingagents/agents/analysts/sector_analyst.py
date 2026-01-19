"""
行业/板块分析师 - 兼容函数接口

为了与现有的 LangGraph 工作流兼容，提供函数式接口

⚠️ 重要：行业报告不支持缓存
- 行业报告是结合了具体股票进行分析的，包含该股票的代码和名称
- 如果缓存行业报告，同行业其他股票分析时会错误地使用其他股票的代码和名称
- 因此，每次分析都必须重新生成行业报告，不能使用缓存
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, AIMessage

from tradingagents.utils.tool_logging import log_analyst_module
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.template_client import get_agent_prompt

logger = get_logger("default")

# 缓存配置（已废弃）
# ⚠️ 行业报告不支持缓存：行业报告包含具体股票的代码和名称，缓存会导致同行业其他股票分析时出现错误信息
SECTOR_REPORT_CACHE_TTL_HOURS = 12  # 板块分析报告缓存有效期（小时）- 已废弃，不再使用


def _get_cache_manager():
    """获取缓存管理器（延迟加载避免循环导入）"""
    try:
        from tradingagents.dataflows.cache import get_cache
        return get_cache()
    except Exception as e:
        logger.warning(f"⚠️ 无法获取缓存管理器: {e}")
        return None


def _get_cached_sector_report(ticker: str, trade_date: str) -> Optional[str]:
    """
    ⚠️ 已废弃：行业报告不支持缓存
    行业报告包含具体股票的代码和名称，缓存会导致同行业其他股票分析时出现错误信息
    
    Args:
        ticker: 股票代码
        trade_date: 交易日期

    Returns:
        缓存的报告内容，如果没有命中则返回 None
    """
    cache = _get_cache_manager()
    if not cache:
        return None

    try:
        cache_key = cache.find_cached_analysis_report(
            report_type="sector_report",
            symbol=ticker,
            trade_date=trade_date,
            max_age_hours=SECTOR_REPORT_CACHE_TTL_HOURS
        )
        if cache_key:
            report = cache.load_analysis_report(cache_key)
            if report and len(report) > 100:
                logger.info(f"📦 [板块分析] 命中缓存: {ticker} @ {trade_date}")
                return report
    except Exception as e:
        logger.warning(f"⚠️ 读取板块分析缓存失败: {e}")

    return None


def _save_sector_report_to_cache(ticker: str, trade_date: str, report: str) -> bool:
    """
    ⚠️ 已废弃：行业报告不支持缓存
    行业报告包含具体股票的代码和名称，缓存会导致同行业其他股票分析时出现错误信息
    
    Args:
        ticker: 股票代码
        trade_date: 交易日期
        report: 报告内容

    Returns:
        是否保存成功
    """
    cache = _get_cache_manager()
    if not cache:
        return False

    try:
        cache.save_analysis_report(
            report_type="sector_report",
            report_data=report,
            symbol=ticker,
            trade_date=trade_date
        )
        logger.info(f"💾 [板块分析] 已缓存: {ticker} @ {trade_date}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ 保存板块分析缓存失败: {e}")
        return False


def create_sector_analyst(llm, toolkit):
    """
    创建行业/板块分析师节点

    Args:
        llm: 语言模型实例
        toolkit: 工具包实例

    Returns:
        分析师节点函数
    """

    @log_analyst_module("sector")
    def sector_analyst_node(state):
        """
        行业/板块分析师节点

        分析行业趋势、板块轮动和同业对比

        🔥 重要：此分析师采用"自包含"模式，不使用 LangGraph 的工具调用机制。
        它在单次调用中完成所有工作：获取数据 + LLM 分析。
        返回的 AIMessage 不包含 tool_calls，确保图立即结束。
        """
        ticker = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")

        # 🔍 调试日志：打印当前状态
        logger.info(f"🔍 [sector_analyst] 节点被调用")
        logger.info(f"🔍 [sector_analyst] ticker={ticker}, trade_date={trade_date}")
        logger.info(f"🔍 [sector_analyst] 当前 messages 数量: {len(state.get('messages', []))}")
        logger.info(f"🔍 [sector_analyst] 当前 sector_report 长度: {len(state.get('sector_report', ''))}")
        logger.info(f"🔍 [sector_analyst] 当前 sector_tool_call_count: {state.get('sector_tool_call_count', 0)}")

        # 打印最后一条消息的信息
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            logger.info(f"🔍 [sector_analyst] 最后一条消息类型: {type(last_msg).__name__}")
            if hasattr(last_msg, 'tool_calls'):
                logger.info(f"🔍 [sector_analyst] 最后一条消息 tool_calls: {last_msg.tool_calls}")
            if hasattr(last_msg, 'name'):
                logger.info(f"🔍 [sector_analyst] 最后一条消息 name: {last_msg.name}")

        # 🔥 防止死循环：检查是否已经生成过报告
        existing_report = state.get("sector_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"🏭 板块分析师: 已存在报告 ({len(existing_report)} 字符)，跳过重复分析")
            # 返回空更新，保持状态不变
            return {}

        # ⚠️ 行业报告不支持缓存：行业报告包含具体股票的代码和名称，缓存会导致同行业其他股票分析时出现错误信息
        # 因此，每次分析都必须重新生成，不能使用缓存
        logger.info(f"🏭 板块分析师: 跳过缓存检查（行业报告不支持缓存），直接生成新报告")

        logger.info(f"🏭 板块分析师开始分析: {ticker} @ {trade_date}")

        try:
            # 导入并调用板块分析工具
            from core.tools.sector_tools import analyze_sector
            import asyncio
            import concurrent.futures

            # 在线程池中运行异步函数以避免事件循环冲突
            def run_async_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(analyze_sector(ticker, trade_date))
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_in_thread)
                sector_data = future.result()

            logger.info(f"✅ 板块数据获取完成: {ticker}")

            # 🆕 使用 LLM 对数据进行分析解读
            sector_report = _analyze_with_llm(
                llm=llm,
                ticker=ticker,
                trade_date=trade_date,
                sector_data=sector_data,
                state=state
            )

            logger.info(f"✅ 板块分析报告生成完成: {ticker}")

            # ⚠️ 行业报告不支持缓存：行业报告包含具体股票的代码和名称，缓存会导致同行业其他股票分析时出现错误信息
            # 因此，不保存到缓存

            # 🔥 返回 AIMessage 而不是 HumanMessage
            # AIMessage 没有 tool_calls 属性（或 tool_calls 为空列表），
            # 这样 should_continue 函数会检测到没有工具调用，直接结束图
            final_message = AIMessage(content=sector_report, name="sector_analyst")

            # 只返回需要更新的字段（LangGraph 会自动合并）
            return {
                "sector_report": sector_report,
                "messages": [final_message],
            }

        except Exception as e:
            logger.error(f"❌ 板块分析失败: {e}")
            import traceback
            logger.error(f"❌ 详细错误: {traceback.format_exc()}")
            error_msg = f"板块分析遇到错误: {str(e)}"

            # 返回错误消息
            error_message = AIMessage(content=error_msg, name="sector_analyst")

            return {
                "sector_report": error_msg,
                "messages": [error_message],
            }

    return sector_analyst_node


def _analyze_with_llm(llm, ticker: str, trade_date: str, sector_data: str, state: dict) -> str:
    """
    使用 LLM 对板块数据进行分析解读

    Args:
        llm: 语言模型实例
        ticker: 股票代码
        trade_date: 交易日期
        sector_data: 板块数据报告
        state: 状态字典

    Returns:
        LLM 生成的分析报告
    """
    try:
        # 获取 AgentContext
        ctx = state.get("agent_context") or {}

        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "trade_date": trade_date,
        }

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_template_client
            tpl_info = get_template_client().get_effective_template(
                agent_type="analysts",
                agent_name="sector_analyst",
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                context=None
            )
            if tpl_info:
                logger.info(f"📚 [模板选择] source={tpl_info.get('source')} id={tpl_info.get('template_id')} agent=analysts/sector_analyst")

            system_prompt = get_agent_prompt(
                agent_type="analysts",
                agent_name="sector_analyst",
                variables=template_variables,
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                fallback_prompt=None,
                context=None
            )
            logger.info(f"✅ [板块分析师] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.warning(f"⚠️ [板块分析师] 从模板系统获取提示词失败: {e}，使用默认提示词")
            system_prompt = _get_default_system_prompt(ticker, trade_date)

        # 构建完整的分析请求
        analysis_request = f"""{system_prompt}

## 📊 板块数据

以下是通过数据工具获取的板块分析数据：

{sector_data}

## 🎯 分析要求

请基于以上数据，生成一份专业的板块分析报告。报告必须包含：

1. **板块表现总结**
   - 目标股票所属的主要板块
   - 各板块近期表现评价
   - 板块相对大盘的强弱

2. **板块轮动分析**
   - 当前市场热点板块识别
   - 资金流向趋势判断
   - 板块轮动阶段判断

3. **同业对比评估**
   - 目标股票在行业中的地位
   - 估值水平评价（PE/PB）
   - 与行业龙头的差距

4. **投资建议**
   - 板块热度评估：🔥热门 / ⚡一般 / ❄️冷门
   - 资金方向：💰流入 / 💸流出 / ⚖️平衡
   - 个股位置：👑龙头 / 🥈第二梯队 / 🥉跟随
   - 操作建议：基于板块趋势的具体建议

请用中文输出，分析要有理有据，结论要明确。"""

        # 调用 LLM 生成分析报告
        logger.info(f"📤 [板块分析师] 调用 LLM 生成分析报告...")
        response = llm.invoke(analysis_request)

        # 提取响应内容
        if hasattr(response, 'content'):
            report = response.content
        else:
            report = str(response)

        logger.info(f"✅ [板块分析师] LLM 分析报告生成完成 (长度: {len(report)})")
        return report

    except Exception as e:
        logger.error(f"❌ [板块分析师] LLM 分析失败: {e}")
        # 如果 LLM 分析失败，返回原始数据报告
        return sector_data


def _get_default_system_prompt(ticker: str, trade_date: str) -> str:
    """
    获取默认的系统提示词

    Args:
        ticker: 股票代码
        trade_date: 交易日期

    Returns:
        默认系统提示词
    """
    return f"""你是一位专业的行业/板块分析师，专注于板块轮动和同业对比分析。

📋 **分析对象：**
- 股票代码：{ticker}
- 分析日期：{trade_date}

🎯 **你的职责：**
1. 分析目标股票所属行业的整体表现
2. 识别板块轮动趋势和资金流向
3. 进行同业竞争对手对比分析
4. 评估个股在行业中的地位和估值水平

📊 **分析维度：**
- 板块表现：涨跌幅、相对强弱
- 资金流向：主力资金进出方向
- 估值对比：PE/PB相对行业水平
- 行业地位：市值排名、龙头地位

请基于提供的数据进行专业分析，给出明确的结论和建议。"""
