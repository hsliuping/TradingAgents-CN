"""
超短行情分析师
专门用于分析A股股票的超短期行情，预测明日涨停、上涨、下跌的概率
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
import traceback
from datetime import datetime, timedelta

# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler


def _get_company_name(ticker: str, market_info: dict) -> str:
    """
    根据股票代码获取公司名称
    """
    try:
        if market_info['is_china']:
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)
            
            if stock_info and "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.info(f"✅ [超短行情分析师] 成功获取股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                return f"股票代码{ticker}"
        else:
            return f"股票{ticker}"
    except Exception as e:
        logger.error(f"❌ [超短行情分析师] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_short_term_analyst(llm, toolkit):
    """
    创建超短行情分析师节点
    
    该分析师专门用于分析A股股票的超短期行情，预测明日涨停、上涨、下跌的概率
    需要的数据包括：
    1. 股票基本信息
    2. 历史K线数据（最近30天）
    3. 财务数据
    4. 新闻数据
    5. 打板相关数据（龙虎榜、涨跌停历史、热度数据、板块数据）
    """
    @log_analyst_module("short_term")
    def short_term_analyst_node(state):
        logger.info(f"🚀 [超短行情分析师] ===== 开始分析 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        
        # 计算开始日期（最近30天）
        try:
            current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
            start_date_obj = current_date_obj - timedelta(days=30)
            start_date = start_date_obj.strftime("%Y-%m-%d")
        except:
            start_date = '2025-01-01'  # 默认值

        logger.info(f"📊 [超短行情分析师] 分析参数: ticker={ticker}, date={current_date}, start_date={start_date}")

        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        
        # 只支持A股
        if not market_info['is_china']:
            logger.warning(f"⚠️ [超短行情分析师] 当前只支持A股分析，股票 {ticker} 不是A股")
            return {
                "short_term_report": f"⚠️ 超短行情分析目前只支持A股，股票 {ticker} 不是A股代码。",
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": f"⚠️ 超短行情分析目前只支持A股，股票 {ticker} 不是A股代码。"
                }]
            }

        # 获取公司名称
        company_name = _get_company_name(ticker, market_info)
        logger.info(f"📊 [超短行情分析师] 公司名称: {company_name}")

        # 定义可用工具
        tools = [
            toolkit.get_stock_market_data_unified,  # 获取历史K线数据
            toolkit.get_stock_fundamentals_unified,  # 获取财务数据
            toolkit.get_realtime_stock_news,  # 获取新闻数据
            toolkit.get_short_term_board_data,  # 获取打板相关数据（需要创建）
        ]

        # 系统提示词（基于参考文档设计）
        system_message = (
            f"你是一位专业的A股股票分析师，擅长短期股价预测。\n"
            f"\n"
            f"📋 **分析任务：**\n"
            f"分析以下股票数据，预测该股票明日（下一个交易日）的以下概率：\n"
            f"1. **明日涨停概率**：收盘价达到涨停板（上涨10%）的概率。\n"
            f"2. **明日上涨概率**：收盘价高于今日收盘价的概率（包括涨停）。\n"
            f"3. **明日下跌概率**：收盘价低于今日收盘价的概率。\n"
            f"\n"
            f"⚠️ **注意事项：**\n"
            f"- 概率值以百分比表示，三个概率之和不一定为100%（因为可能存在平盘情况，但重点预测上涨和下跌）。\n"
            f"- 你的分析应基于综合数据，包括技术指标、基本面、新闻情绪、资金流向和市场热点。\n"
            f"- 输出必须严格遵循指定格式，先输出概率值，后可选添加简要解释。\n"
            f"\n"
            f"🔧 **工具使用：**\n"
            f"你必须调用以下工具获取数据：\n"
            f"1. get_stock_market_data_unified - 获取历史K线数据（最近30天）\n"
            f"2. get_stock_fundamentals_unified - 获取财务数据（最新季度或年度）\n"
            f"3. get_realtime_stock_news - 获取新闻数据（最近3-7天）\n"
            f"4. get_short_term_board_data - 获取打板相关数据（龙虎榜、涨跌停历史、热度数据、板块数据）\n"
            f"\n"
            f"📊 **分析框架：**\n"
            f"请基于获取的数据，按以下框架分析：\n"
            f"1. **技术分析**：评估价格趋势、成交量变化、支撑阻力位（例如使用移动平均线、RSI等）。\n"
            f"2. **基本面分析**：检查财务健康度和估值水平是否支持短期波动。\n"
            f"3. **市场情绪分析**：从新闻情感、板块热度和热榜数据判断市场关注度。\n"
            f"4. **资金流向分析**：从龙虎榜、游资交易和竞价数据推断资金介入程度。\n"
            f"5. **历史模式匹配**：参考类似打板情况下的股价行为。\n"
            f"\n"
            f"📝 **输出格式（必须严格遵守）：**\n"
            f"- 明日涨停概率: [数值]%\n"
            f"- 明日上涨概率: [数值]%\n"
            f"- 明日下跌概率: [数值]%\n"
            f"（可选）简要解释: [用几句话总结关键因素，例如：由于龙虎榜机构大额买入和板块热度高涨，涨停概率较高。）\n"
            f"\n"
            f"🚫 **严格禁止：**\n"
            f"- 不允许假设任何数据\n"
            f"- 不允许编造信息\n"
            f"- 不允许不调用工具就直接回答\n"
            f"- 必须基于真实数据进行分析\n"
            f"\n"
            f"✅ **工作流程：**\n"
            f"1. 首先调用所有工具获取数据\n"
            f"2. 基于获取的真实数据进行分析\n"
            f"3. 输出三个概率值和简要解释\n"
            f"\n"
            f"现在开始分析 {company_name}（股票代码：{ticker}）："
        )

        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
        ])

        # 绑定工具
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        logger.info(f"📊 [超短行情分析师] 绑定的工具: {tool_names}")

        # 检测阿里百炼模型并创建新实例
        if hasattr(llm, '__class__') and 'DashScope' in llm.__class__.__name__:
            logger.debug(f"📊 [DEBUG] 检测到阿里百炼模型，创建新实例以避免工具缓存")
            from tradingagents.llm_adapters import ChatDashScopeOpenAI
            
            original_base_url = getattr(llm, 'openai_api_base', None)
            original_api_key = getattr(llm, 'openai_api_key', None)
            
            fresh_llm = ChatDashScopeOpenAI(
                model=llm.model_name,
                api_key=original_api_key,
                base_url=original_base_url if original_base_url else None,
                temperature=llm.temperature,
                max_tokens=getattr(llm, 'max_tokens', 2000)
            )
        else:
            fresh_llm = llm

        try:
            chain = prompt | fresh_llm.bind_tools(tools)
            logger.info(f"📊 [超短行情分析师] ✅ 工具绑定成功，绑定了 {len(tools)} 个工具")
        except Exception as e:
            logger.error(f"📊 [超短行情分析师] ❌ 工具绑定失败: {e}")
            raise e

        logger.info(f"📊 [超短行情分析师] 开始调用LLM...")
        
        try:
            # 清理消息历史，确保格式正确
            # OpenAI API要求：ToolMessage 必须紧跟在带有对应 tool_calls 的 AIMessage 之后
            from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
            
            messages = state.get("messages", [])
            clean_messages = []
            
            # 如果消息为空，添加初始消息
            if not messages:
                clean_messages = [HumanMessage(content=f"请分析股票 {ticker} 的超短期行情")]
            else:
                # 遍历消息，确保格式正确
                i = 0
                while i < len(messages):
                    msg = messages[i]
                    
                    if isinstance(msg, (HumanMessage, AIMessage)):
                        clean_messages.append(msg)
                        i += 1
                    elif isinstance(msg, ToolMessage):
                        # ToolMessage 必须紧跟在带有对应 tool_calls 的 AIMessage 之后
                        if clean_messages and isinstance(clean_messages[-1], AIMessage):
                            last_ai_msg = clean_messages[-1]
                            if hasattr(last_ai_msg, 'tool_calls') and last_ai_msg.tool_calls:
                                # 检查 tool_call_id 是否匹配
                                tool_call_ids = []
                                for tc in last_ai_msg.tool_calls:
                                    if isinstance(tc, dict):
                                        tool_call_ids.append(tc.get('id'))
                                    elif hasattr(tc, 'get'):
                                        tool_call_ids.append(tc.get('id'))
                                
                                if hasattr(msg, 'tool_call_id') and msg.tool_call_id in tool_call_ids:
                                    clean_messages.append(msg)
                                    logger.debug(f"✅ [超短行情分析师] 保留匹配的ToolMessage: {msg.tool_call_id}")
                                else:
                                    logger.warning(f"⚠️ [超短行情分析师] 跳过不匹配的ToolMessage: {getattr(msg, 'tool_call_id', 'unknown')}")
                            else:
                                logger.warning(f"⚠️ [超短行情分析师] 跳过ToolMessage（前一条AIMessage没有tool_calls）")
                        else:
                            logger.warning(f"⚠️ [超短行情分析师] 跳过ToolMessage（前一条消息不是AIMessage）")
                        i += 1
                    else:
                        # 未知类型的消息，跳过
                        logger.warning(f"⚠️ [超短行情分析师] 跳过未知类型的消息: {type(msg).__name__}")
                        i += 1
            
            # 如果清理后消息为空，添加初始消息
            if not clean_messages:
                clean_messages = [HumanMessage(content=f"请分析股票 {ticker} 的超短期行情")]
            
            logger.info(f"📊 [超短行情分析师] 清理后的消息数量: {len(clean_messages)} (原始: {len(messages)})")
            
            result = chain.invoke({"messages": clean_messages})
            logger.info(f"📊 [超短行情分析师] LLM调用完成")
            
            # 检查是否有工具调用
            if hasattr(result, 'tool_calls') and result.tool_calls:
                logger.info(f"📊 [超短行情分析师] 检测到 {len(result.tool_calls)} 个工具调用")
                return {"messages": [result]}
            else:
                # 没有工具调用，直接返回分析结果
                logger.info(f"📊 [超短行情分析师] 没有工具调用，返回分析结果")
                report_content = result.content if hasattr(result, 'content') else str(result)
                return {
                    "short_term_report": report_content,
                    "messages": [result]  # 只返回新消息，让服务层合并
                }
        except Exception as e:
            logger.error(f"❌ [超短行情分析师] LLM调用失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "short_term_report": f"❌ 分析失败: {str(e)}",
                "messages": state["messages"]
            }

    return short_term_analyst_node

