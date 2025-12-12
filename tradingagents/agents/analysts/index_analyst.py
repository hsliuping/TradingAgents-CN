"""
大盘/指数分析师 - 兼容函数接口

为了与现有的 LangGraph 工作流兼容，提供函数式接口

支持缓存机制：
- 同一天的大盘分析结果会被缓存（不依赖具体股票）
- 缓存有效期为 12 小时（当天数据不变）
- 下次分析时先检查缓存，命中则直接返回
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, AIMessage

from tradingagents.utils.tool_logging import log_analyst_module
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.template_client import get_agent_prompt

logger = get_logger("default")

# 缓存配置
INDEX_REPORT_CACHE_TTL_HOURS = 12  # 大盘分析报告缓存有效期（小时）


def _get_cache_manager():
    """获取缓存管理器（延迟加载避免循环导入）"""
    try:
        from tradingagents.dataflows.cache import get_cache
        return get_cache()
    except Exception as e:
        logger.warning(f"⚠️ 无法获取缓存管理器: {e}")
        return None


def _get_cached_index_report(trade_date: str) -> Optional[str]:
    """
    从缓存获取大盘分析报告

    Args:
        trade_date: 交易日期

    Returns:
        缓存的报告内容，如果没有命中则返回 None
    """
    cache = _get_cache_manager()
    if not cache:
        return None

    try:
        # 大盘分析不依赖具体股票，使用 "market" 作为 symbol
        cache_key = cache.find_cached_analysis_report(
            report_type="index_report",
            symbol="market",
            trade_date=trade_date,
            max_age_hours=INDEX_REPORT_CACHE_TTL_HOURS
        )
        if cache_key:
            report = cache.load_analysis_report(cache_key)
            if report and len(report) > 100:
                logger.info(f"📦 [大盘分析] 命中缓存: @ {trade_date}")
                return report
    except Exception as e:
        logger.warning(f"⚠️ 读取大盘分析缓存失败: {e}")

    return None


def _save_index_report_to_cache(trade_date: str, report: str) -> bool:
    """
    将大盘分析报告保存到缓存

    Args:
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
            report_type="index_report",
            report_data=report,
            symbol="market",
            trade_date=trade_date
        )
        logger.info(f"💾 [大盘分析] 已缓存: @ {trade_date}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ 保存大盘分析缓存失败: {e}")
        return False


def create_index_analyst(llm, toolkit):
    """
    创建大盘/指数分析师节点

    Args:
        llm: 语言模型实例
        toolkit: 工具包实例

    Returns:
        分析师节点函数
    """

    @log_analyst_module("index")
    def index_analyst_node(state):
        """
        大盘/指数分析师节点

        分析主要指数走势、市场环境和系统性风险

        🔥 重要：此分析师采用"自包含"模式，不使用 LangGraph 的工具调用机制。
        它在单次调用中完成所有工作：获取数据 + LLM 分析。
        返回的 AIMessage 不包含 tool_calls，确保图立即结束。
        """
        trade_date = state.get("trade_date", "")

        # 🔥 防止死循环：检查是否已经生成过报告
        existing_report = state.get("index_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"🌐 大盘分析师: 已存在报告 ({len(existing_report)} 字符)，跳过重复分析")
            # 返回空更新，保持状态不变
            return {}

        # 📦 检查缓存：如果有有效缓存，直接返回
        cached_report = _get_cached_index_report(trade_date)
        if cached_report:
            logger.info(f"🌐 大盘分析师: 使用缓存报告 ({len(cached_report)} 字符)")
            final_message = AIMessage(content=cached_report, name="index_analyst")
            return {
                "index_report": cached_report,
                "messages": [final_message],
            }

        logger.info(f"🌐 大盘分析师开始分析 @ {trade_date}")

        try:
            # 导入并调用大盘分析工具
            from core.tools.index_tools import analyze_index
            import asyncio
            import concurrent.futures

            # 在线程池中运行异步函数以避免事件循环冲突
            def run_async_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(analyze_index(trade_date))
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_in_thread)
                index_data = future.result()

            logger.info(f"✅ 大盘数据获取完成")

            # 🆕 使用 LLM 对数据进行分析解读
            index_report = _analyze_with_llm(
                llm=llm,
                trade_date=trade_date,
                index_data=index_data,
                state=state
            )

            logger.info(f"✅ 大盘分析报告生成完成")

            # 💾 保存到缓存
            _save_index_report_to_cache(trade_date, index_report)

            # 🔥 返回 AIMessage 而不是 HumanMessage
            # AIMessage 没有 tool_calls 属性（或 tool_calls 为空列表），
            # 这样 should_continue 函数会检测到没有工具调用，直接结束图
            final_message = AIMessage(content=index_report, name="index_analyst")

            # 只返回需要更新的字段（LangGraph 会自动合并）
            return {
                "index_report": index_report,
                "messages": [final_message],
            }

        except Exception as e:
            logger.error(f"❌ 大盘分析失败: {e}")
            import traceback
            logger.error(f"❌ 详细错误: {traceback.format_exc()}")
            error_msg = f"大盘分析遇到错误: {str(e)}"

            # 返回错误消息
            error_message = AIMessage(content=error_msg, name="index_analyst")

            return {
                "index_report": error_msg,
                "messages": [error_message],
            }

    return index_analyst_node


def _analyze_with_llm(llm, trade_date: str, index_data: str, state: dict) -> str:
    """
    使用 LLM 对大盘数据进行分析解读

    Args:
        llm: 语言模型实例
        trade_date: 交易日期
        index_data: 大盘数据报告
        state: 状态字典

    Returns:
        LLM 生成的分析报告
    """
    try:
        # 获取 AgentContext
        ctx = state.get("agent_context") or {}

        # 准备模板变量
        template_variables = {
            "trade_date": trade_date,
        }

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_template_client
            tpl_info = get_template_client().get_effective_template(
                agent_type="analysts",
                agent_name="index_analyst",
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                context=None
            )
            if tpl_info:
                logger.info(f"📚 [模板选择] source={tpl_info.get('source')} id={tpl_info.get('template_id')} agent=analysts/index_analyst")

            system_prompt = get_agent_prompt(
                agent_type="analysts",
                agent_name="index_analyst",
                variables=template_variables,
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                fallback_prompt=None,
                context=None
            )
            logger.info(f"✅ [大盘分析师] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.warning(f"⚠️ [大盘分析师] 从模板系统获取提示词失败: {e}，使用默认提示词")
            system_prompt = _get_default_system_prompt(trade_date)

        # 构建完整的分析请求
        analysis_request = f"""{system_prompt}

## 📊 大盘数据

以下是通过数据工具获取的大盘分析数据：

{index_data}

## 🎯 分析要求

请基于以上数据，生成一份专业的大盘分析报告。报告必须包含：

1. **市场概况**
   - 主要指数今日表现（上证、深证、创业板等）
   - 涨跌家数和市场情绪
   - 成交额变化分析

2. **技术面分析**
   - 各指数技术形态判断
   - 关键支撑位和压力位
   - 均线系统分析

3. **市场宽度分析**
   - 涨跌比和强弱指标
   - 板块分化程度
   - 市场参与度评估

4. **风险评估与建议**
   - 市场风险等级：🟢低风险 / 🟡中等风险 / 🔴高风险
   - 市场趋势：📈上涨 / 📉下跌 / ➡️震荡
   - 仓位建议：基于当前市场环境的具体建议

请用中文输出，分析要有理有据，结论要明确。"""

        # 调用 LLM 生成分析报告
        logger.info(f"📤 [大盘分析师] 调用 LLM 生成分析报告...")
        response = llm.invoke(analysis_request)

        # 提取响应内容
        if hasattr(response, 'content'):
            report = response.content
        else:
            report = str(response)

        logger.info(f"✅ [大盘分析师] LLM 分析报告生成完成 (长度: {len(report)})")
        return report

    except Exception as e:
        logger.error(f"❌ [大盘分析师] LLM 分析失败: {e}")
        # 如果 LLM 分析失败，返回原始数据报告
        return index_data


def _get_default_system_prompt(trade_date: str) -> str:
    """
    获取默认的系统提示词

    Args:
        trade_date: 交易日期

    Returns:
        默认系统提示词
    """
    return f"""你是一位专业的大盘/指数分析师，专注于宏观市场分析和系统性风险评估。

📋 **分析日期：** {trade_date}

🎯 **你的职责：**
1. 分析主要指数（上证、深证、创业板等）的走势
2. 评估市场整体环境和情绪
3. 识别系统性风险和机会
4. 提供市场层面的投资建议

📊 **分析维度：**
- 指数表现：涨跌幅、成交额
- 市场宽度：涨跌家数、强弱分布
- 技术面：支撑压力、趋势判断
- 风险评估：系统性风险水平

请基于提供的数据进行专业分析，给出明确的结论和建议。"""
