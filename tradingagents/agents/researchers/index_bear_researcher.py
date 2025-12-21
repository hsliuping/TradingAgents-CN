from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_index_bear_researcher(llm):
    def index_bear_node(state) -> dict:
        logger.debug(f"🐻 [DEBUG] ===== 指数空头研究员节点开始 =====")

        investment_debate_state = state.get("investment_debate_state", {"count": 0, "history": "", "bull_history": "", "bear_history": "", "current_response": ""})
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")
        current_response = investment_debate_state.get("current_response", "")
        
        # 获取目标指数
        index_name = state.get("company_of_interest", "目标指数")
        
        # 获取上游报告
        macro_report = state.get("macro_report", "无宏观报告")
        policy_report = state.get("policy_report", "无政策报告")
        sector_report = state.get("sector_report", "无板块报告")
        international_news_report = state.get("international_news_report", "无国际新闻报告")
        technical_report = state.get("technical_report", "无技术分析报告")

        prompt = f"""你是一位**指数空头策略师 (Index Bear Strategist)**，负责为**降低 {index_name} 的仓位 (Reduce Exposure) 或持有现金** 建立强有力的论证。

你的目标是基于宏观经济、政策环境、板块轮动、国际局势和技术面分析，挖掘所有 {index_name} 面临的潜在风险因素、泡沫迹象和不利信号，并反驳多方观点。你的最终目的是说服决策者降低仓位或保持谨慎。

请用中文回答，重点关注以下几个方面：

1.  **宏观与政策风险**：强调经济衰退风险、政策不及预期、流动性收紧对 {index_name} 的负面影响。
2.  **估值与泡沫**：指出 {index_name} 整体估值过高、获利盘回吐压力、成分股业绩暴雷风险。
3.  **技术面压力**：指出关键阻力位、头部形态、背离信号或破位风险。
4.  **外部冲击**：强调地缘政治动荡、汇率波动、外围市场暴跌等输入性风险。
5.  **反驳多方观点**：针对多方提出的利好（如复苏、政策等），从“盲目乐观”、“边际效应递减”或“已被市场透支”的角度进行有力反驳。
6.  **仓位建议逻辑**：论证为什么现在应该减仓、止盈或空仓观望。

**可用资源：**
### 1️⃣ 宏观经济分析
{macro_report}

### 2️⃣ 政策分析
{policy_report}

### 3️⃣ 板块轮动分析
{sector_report}

### 4️⃣ 国际新闻分析
{international_news_report}

### 5️⃣ 技术面分析
{technical_report}

---
**辩论历史：**
{history}

**上一轮多方观点：**
{current_response}

---
**你的任务：**
请基于上述信息，发表你的空头观点。
- 必须引用报告中的具体数据或结论作为论据。
- 语气要冷静、犀利，揭示风险。
- 直接回应上一轮多方的盲目乐观（如果有）。
- 明确表达这一轮是对“降低仓位/持有现金”的强力支持。

请用中文撰写。
"""

        response = llm.invoke(prompt)
        argument = f"Bear Strategist: {response.content}"

        new_count = investment_debate_state.get("count", 0) + 1
        logger.info(f"🐻 [指数空头] 发言完成，计数: {new_count}")

        new_investment_debate_state = {
            "history": history + "\n\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "bear_history": bear_history + "\n\n" + argument,
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return index_bear_node
