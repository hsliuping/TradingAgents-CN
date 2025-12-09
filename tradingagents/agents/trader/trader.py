import functools
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_trader(llm, memory):
    def trader_node(state, name):
        # 使用安全读取，确保缺失字段不会导致整个流程中断
        company_name = state.get("company_of_interest", "")
        investment_plan = state.get("investment_plan", "")
        
        # 🔥 动态发现所有 *_report 字段，自动支持新添加的分析师报告
        all_reports = {}
        for key in state.keys():
            if key.endswith("_report") and state[key]:
                all_reports[key] = state[key]

        # 使用统一的股票类型检测
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(company_name)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        # 根据股票类型确定货币单位
        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

        logger.debug(f"💰 [DEBUG] ===== 交易员节点开始 =====")
        logger.debug(f"💰 [DEBUG] 交易员检测股票类型: {company_name} -> {market_info['market_name']}, 货币: {currency}")
        logger.debug(f"💰 [DEBUG] 货币符号: {currency_symbol}")
        logger.debug(f"💰 [DEBUG] 市场详情: 中国A股={is_china}, 港股={is_hk}, 美股={is_us}")
        logger.debug(f"💰 [DEBUG] 发现的报告数量: {len(all_reports)}")

        # 🔥 使用所有动态发现的报告构建 curr_situation
        curr_situation = "\n\n".join([content for content in all_reports.values() if content])

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

        # 获取研究团队辩论历史 (替代原 Research Manager 的输入)
        investment_debate_state = state.get("investment_debate_state", {})
        debate_history = investment_debate_state.get("history", "暂无辩论历史")
        
        # 🔥 构建所有报告的格式化字符串（用于 prompt）
        # 从配置文件动态获取报告显示名称
        report_display_names = {}
        try:
            from tradingagents.agents.analysts.dynamic_analyst import DynamicAnalystFactory
            for agent in DynamicAnalystFactory.get_all_agents():
                slug = agent.get('slug', '')
                name = agent.get('name', '')
                if slug and name:
                    internal_key = slug.replace("-analyst", "").replace("-", "_")
                    report_key = f"{internal_key}_report"
                    report_display_names[report_key] = f"{name}报告"
        except Exception as e:
            logger.warning(f"⚠️ 无法从配置文件加载报告显示名称: {e}")
        
        all_reports_formatted = ""
        for key, content in all_reports.items():
            if content:
                display_name = report_display_names.get(key, key.replace("_report", "").replace("_", " ").title() + "报告")
                all_reports_formatted += f"\n**{display_name}**:\n{content}\n"
        
        # 构建上下文，整合辩论历史和各分析师报告
        context_content = f"""基于分析团队的全面分析和研究员之间的深入辩论，请为 {company_name} 制定一份详细的投资交易计划。

以下是所有可用的信息：

1. **研究团队辩论记录** (Bull vs Bear):
{debate_history}

2. **分析师报告**:
{all_reports_formatted if all_reports_formatted else "暂无分析师报告"}

请综合以上所有信息，特别是多空双方的辩论焦点，制定一份可执行的交易计划。"""

        context = {
            "role": "user",
            "content": context_content,
        }

        messages = [
            {
                "role": "system",
                "content": f"""您是一位专业的交易员，负责综合多空双方的研究观点和各类市场数据，制定最终的量化交易计划。您的角色是"执行者"，需要将定性的分析转化为定量的交易指令。

⚠️ 重要提醒：当前分析的股票代码是 {company_name}，请使用正确的货币单位：{currency}（{currency_symbol}）

🔴 严格要求：
1. **必须明确交易方向**：买入 (Buy)、卖出 (Sell) 或 持有 (Hold)。
2. **必须给出具体价格点位**：
   - **入场价格 (Entry Price)**：具体的建议买入/卖出价格或区间。
   - **目标价格 (Target Price)**：预期的获利了结价格。
   - **止损价格 (Stop Loss)**：明确的风险控制点位。
3. **必须基于真实数据**：严禁臆造价格，必须基于当前市价和技术/基本面分析。
4. **必须使用正确货币**：{company_name} 属于 {market_info['market_name']}，所有价格必须以 {currency} 计价。

您的输出将直接作为风险管理团队（激进/中性/保守分析师）的辩论基础，因此必须具体、清晰、有逻辑。

请按以下结构输出您的交易计划：
1. **交易决策**：买入/卖出/持有
2. **核心逻辑**：一句话总结为什么要这样做（基于多空辩论的结论）。
3. **关键点位**：
   - 当前市价：(从报告中提取)
   - 建议入场：XX
   - 目标止盈：XX
   - 止损风控：XX
4. **仓位建议**：建议的仓位比例（如：轻仓/半仓/满仓）。
5. **风险提示**：当前最大的潜在风险点。

请用中文撰写，确保专业性和可执行性。

请不要忘记利用过去决策的经验教训来避免重复错误。以下是类似情况下的交易反思和经验教训: {past_memory_str}""",
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
