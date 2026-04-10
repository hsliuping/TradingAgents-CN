import functools
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入模板客户端
from tradingagents.utils.template_client import get_agent_prompt
from tradingagents.agents.utils.compliance_prompting import apply_compliance_guardrails, build_research_only_closing


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state.get("company_of_interest", "")
        investment_plan = state.get("investment_plan", "")
        # 使用 .get() 安全访问，支持用户只选择部分分析师的情况
        market_research_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        # 🆕 新增板块和大盘分析报告
        sector_report = state.get("sector_report", "")
        index_report = state.get("index_report", "")

        # 使用统一的股票类型检测
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(company_name)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        # 根据股票类型确定货币单位
        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

        logger.debug("💰 [DEBUG] ===== 交易员节点开始 =====")
        logger.debug(f"💰 [DEBUG] 交易员检测股票类型: {company_name} -> {market_info['market_name']}, 货币: {currency}")
        logger.debug(f"💰 [DEBUG] 货币符号: {currency_symbol}")
        logger.debug(f"💰 [DEBUG] 市场详情: 中国A股={is_china}, 港股={is_hk}, 美股={is_us}")
        logger.debug(f"💰 [DEBUG] 基本面报告长度: {len(fundamentals_report)}")
        logger.debug(f"💰 [DEBUG] 板块报告长度: {len(sector_report)}, 大盘报告长度: {len(index_report)}")

        # 🆕 整合所有分析报告（包括新增的板块和大盘分析）
        curr_situation_parts = [market_research_report, sentiment_report, news_report, fundamentals_report]
        if index_report:
            curr_situation_parts.insert(0, f"【宏观大盘分析】\n{index_report}")
        if sector_report:
            curr_situation_parts.insert(1 if index_report else 0, f"【行业板块分析】\n{sector_report}")
        curr_situation = "\n\n".join(curr_situation_parts)

        # 检查memory是否可用
        if memory is not None:
            logger.warning(f"⚠️ [DEBUG] memory可用，获取历史记忆")
            past_memories = memory.get_memories(curr_situation, n_matches=2)
            past_memory_str = ""
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []
            past_memory_str = "暂无历史记忆数据可参考。"

        # 🆕 使用模板系统获取提示词
        try:
            # 准备模板变量
            template_variables = {
                "ticker": company_name,
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
                agent_type="trader",
                agent_name="trader",
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                context=None
            )
            if tpl_info:
                logger.info(f"📚 [模板选择] source={tpl_info.get('source')} id={tpl_info.get('template_id')} version={tpl_info.get('version')} agent=trader/trader")

            # 从模板系统获取提示词
            system_prompt = get_agent_prompt(
                agent_type="trader",
                agent_name="trader",
                variables=template_variables,
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                fallback_prompt=None,
                context=None
            )

            system_prompt = apply_compliance_guardrails(system_prompt, "trader")
            logger.info(f"✅ [交易员] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.error(f"❌ [交易员] 从模板系统获取提示词失败: {e}")
            # 降级：使用硬编码提示词
            system_prompt = f"""您是一位研究整合员，负责整合市场数据并形成研究摘要。

⚠️ 重要提醒：当前分析的股票代码是 {company_name}，请使用正确的货币单位：{currency}（{currency_symbol}）

请在您的分析中包含以下关键信息：
1. **研究摘要**: 当前证据显示的主要结论
2. **关键信号**: 影响判断的核心变量与变化
3. **风险提示**: 当前需要重点关注的不确定性
4. **观察清单**: 后续需要继续跟踪的数据或事件
5. **详细推理**: 支持研究结论的具体理由

请用中文撰写分析内容。"""
            system_prompt = apply_compliance_guardrails(system_prompt, "trader")
            logger.warning(f"⚠️ [交易员] 使用降级提示词 (长度: {len(system_prompt)})")

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        messages = [
            {
                "role": "system",
                "content": f"""{system_prompt}

过去的交易反思和经验教训：
{past_memory_str}

{build_research_only_closing(["请基于以上信息输出研究摘要、关键信号、风险提示和观察清单。"])}""",
            },
            context,
        ]

        logger.debug(f"💰 [DEBUG] 准备调用LLM，系统提示包含货币: {currency}")
        logger.debug(f"💰 [DEBUG] 系统提示中的关键部分: 目标价格({currency})")

        result = llm.invoke(messages)

        logger.debug(f"💰 [DEBUG] LLM调用完成")
        logger.debug(f"💰 [DEBUG] 交易员回复长度: {len(result.content)}")
        logger.debug(f"💰 [DEBUG] 交易员回复前500字符: {result.content[:500]}...")
        logger.debug(f"💰 [DEBUG] ===== 交易员节点结束 =====")

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
