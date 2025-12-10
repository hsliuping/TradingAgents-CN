from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入模板客户端
from tradingagents.utils.template_client import get_agent_prompt


def _get_extension_reports(state: dict) -> dict:
    """
    动态获取扩展分析报告（板块、大盘等）

    使用 ReportAggregator 从注册表获取所有扩展报告，
    如果 core 模块不可用则返回空字典
    """
    try:
        from core.utils.report_aggregator import get_all_reports
        reports = get_all_reports(state)
        return reports.to_dict()
    except ImportError:
        # core 模块不可用，返回硬编码的扩展报告
        return {
            "sector_report": state.get("sector_report", ""),
            "index_report": state.get("index_report", ""),
        }


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        logger.debug(f"🐂 [DEBUG] ===== 看涨研究员节点开始 =====")

        # 使用 .get() 安全访问辩论状态
        investment_debate_state = state.get("investment_debate_state", {})
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")

        # 获取核心分析报告
        market_research_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")

        # 动态获取扩展分析报告（板块、大盘等）
        extension_reports = _get_extension_reports(state)

        # 使用统一的股票类型检测
        ticker = state.get('company_of_interest', 'Unknown')
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']

        # 获取公司名称
        def _get_company_name(ticker_code: str, market_info_dict: dict) -> str:
            """根据股票代码获取公司名称"""
            try:
                if market_info_dict['is_china']:
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker_code)
                    if stock_info and "股票名称:" in stock_info:
                        name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                        logger.info(f"✅ [多头研究员] 成功获取中国股票名称: {ticker_code} -> {name}")
                        return name
                    else:
                        # 降级方案
                        try:
                            from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                            info_dict = get_info_dict(ticker_code)
                            if info_dict and info_dict.get('name'):
                                name = info_dict['name']
                                logger.info(f"✅ [多头研究员] 降级方案成功获取股票名称: {ticker_code} -> {name}")
                                return name
                        except Exception as e:
                            logger.error(f"❌ [多头研究员] 降级方案也失败: {e}")
                elif market_info_dict['is_hk']:
                    try:
                        from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                        name = get_hk_company_name_improved(ticker_code)
                        return name
                    except Exception:
                        clean_ticker = ticker_code.replace('.HK', '').replace('.hk', '')
                        return f"港股{clean_ticker}"
                elif market_info_dict['is_us']:
                    us_stock_names = {
                        'AAPL': '苹果公司', 'TSLA': '特斯拉', 'NVDA': '英伟达',
                        'MSFT': '微软', 'GOOGL': '谷歌', 'AMZN': '亚马逊',
                        'META': 'Meta', 'NFLX': '奈飞'
                    }
                    return us_stock_names.get(ticker_code.upper(), f"美股{ticker_code}")
            except Exception as e:
                logger.error(f"❌ [多头研究员] 获取公司名称失败: {e}")
            return f"股票代码{ticker_code}"

        company_name = _get_company_name(ticker, market_info)
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

        logger.debug("🐂 [DEBUG] 接收到的报告:")
        logger.debug(f"🐂 [DEBUG] - 市场报告长度: {len(market_research_report)}")
        logger.debug(f"🐂 [DEBUG] - 情绪报告长度: {len(sentiment_report)}")
        logger.debug(f"🐂 [DEBUG] - 新闻报告长度: {len(news_report)}")
        logger.debug(f"🐂 [DEBUG] - 基本面报告长度: {len(fundamentals_report)}")
        logger.debug(f"🐂 [DEBUG] - 扩展报告数量: {len(extension_reports)}")
        logger.debug(f"🐂 [DEBUG] - 股票代码: {ticker}, 公司名称: {company_name}, 类型: {market_info['market_name']}, 货币: {currency}")
        logger.debug(f"🐂 [DEBUG] - 市场详情: 中国A股={is_china}, 港股={is_hk}, 美股={is_us}")

        # 整合所有分析报告（核心报告 + 扩展报告）
        curr_situation_parts = []

        # 先添加扩展报告（大盘、板块等，按优先级排序）
        index_report = extension_reports.get("index_report", "")
        sector_report = extension_reports.get("sector_report", "")
        if index_report:
            curr_situation_parts.append(f"【宏观大盘分析】\n{index_report}")
        if sector_report:
            curr_situation_parts.append(f"【行业板块分析】\n{sector_report}")

        # 再添加核心报告
        curr_situation_parts.extend([market_research_report, sentiment_report, news_report, fundamentals_report])
        curr_situation = "\n\n".join([p for p in curr_situation_parts if p])

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # 🆕 使用模板系统获取提示词
        try:
            # 准备模板变量
            template_variables = {
                "ticker": ticker,
                "company_name": company_name,
                "market_name": market_info['market_name'],
                "current_date": state.get("trade_date", ""),
                "start_date": state.get("trade_date", ""),
                "currency_name": currency,
                "currency_symbol": currency_symbol,
                "tool_names": ""
            }

            from tradingagents.utils.template_client import get_template_client
            ctx = state.get("agent_context") or {}
            tpl_info = get_template_client().get_effective_template(
                agent_type="researchers",
                agent_name="bull_researcher",
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                context=None
            )
            if tpl_info:
                logger.info(f"📚 [模板选择] source={tpl_info.get('source')} id={tpl_info.get('template_id')} version={tpl_info.get('version')} agent=researchers/bull_researcher")

            # 从模板系统获取提示词
            system_prompt = get_agent_prompt(
                agent_type="researchers",
                agent_name="bull_researcher",
                variables=template_variables,
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                fallback_prompt=None,
                context=None
            )

            logger.info(f"✅ [多头研究员] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.error(f"❌ [多头研究员] 从模板系统获取提示词失败: {e}")
            # 降级：使用硬编码提示词
            system_prompt = f"""你是一位看涨分析师，负责为股票 {company_name}（股票代码：{ticker}）的投资建立强有力的论证。

⚠️ 重要提醒：当前分析的是 {'中国A股' if is_china else '海外股票'}，所有价格和估值请使用 {currency}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的任务是构建基于证据的强有力案例，强调增长潜力、竞争优势和积极的市场指标。

请用中文回答，重点关注以下几个方面：
- 增长潜力：突出公司的市场机会、收入预测和可扩展性
- 竞争优势：强调独特产品、强势品牌或主导市场地位等因素
- 积极指标：使用财务健康状况、行业趋势和最新积极消息作为证据
- 反驳看跌观点：用具体数据和合理推理批判性分析看跌论点

请确保所有回答都使用中文。"""
            logger.warning(f"⚠️ [多头研究员] 使用降级提示词 (长度: {len(system_prompt)})")

        # 构建完整提示词
        prompt = f"""{system_prompt}

可用资源：
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务新闻：{news_report}
公司基本面报告：{fundamentals_report}
辩论对话历史：{history}
最后的看跌论点：{current_response}
类似情况的反思和经验教训：{past_memory_str}

请使用这些信息提供令人信服的看涨论点，反驳看跌担忧，并参与动态辩论。"""

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_count = investment_debate_state["count"] + 1
        logger.info(f"🐂 [多头研究员] 发言完成，计数: {investment_debate_state['count']} -> {new_count}")

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
