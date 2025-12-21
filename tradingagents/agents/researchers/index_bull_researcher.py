from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_index_bull_researcher(llm):
    def index_bull_node(state) -> dict:
        logger.debug(f"🐂 [DEBUG] ===== 指数多头研究员节点开始 =====")

        investment_debate_state = state.get("investment_debate_state", {"count": 0, "history": "", "bull_history": "", "bear_history": "", "current_response": ""})
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")
        current_response = investment_debate_state.get("current_response", "")
        
        # 获取目标指数
        index_name = state.get("company_of_interest", "目标指数")
        
        # 获取上游报告
        macro_report = state.get("macro_report", "无宏观报告")
        policy_report = state.get("policy_report", "无政策报告")
        sector_report = state.get("sector_report", "无板块报告")
        international_news_report = state.get("international_news_report", "无国际新闻报告")
        technical_report = state.get("technical_report", "无技术分析报告")

        prompt = f"""你是一位**指数多头策略师 (Index Bull Strategist)**，负责为**增加 {index_name} 的仓位 (Increase Exposure)** 建立强有力的论证。

你的目标是基于宏观经济、政策环境、板块轮动、国际局势和技术面分析，挖掘所有支持 {index_name} 上涨的积极因素，并反驳空方观点。你的最终目的是说服决策者提高仓位配置。

请用中文回答，重点关注以下几个方面：

1.  **宏观与政策红利**：强调经济复苏迹象、宽松货币政策、产业扶持政策对 {index_name} 的直接利好。
2.  **资金面与情绪**：强调增量资金入场、市场情绪回暖、成分股业绩回升等。
3.  **技术面支撑**：指出 {index_name} 的关键支撑位有效、上升趋势形成或超跌反弹信号。
4.  **反驳空方观点**：针对空方提出的风险点（如估值高、外部冲击等），从“已被定价”、“成长性消化估值”或“影响有限”的角度进行有力反驳。
5.  **仓位建议逻辑**：论证为什么现在是加仓或重仓持有 {index_name} 的好时机。

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

**上一轮空方观点：**
{current_response}

---
**你的任务：**
请基于上述信息，发表你的多头观点。
- 必须引用报告中的具体数据或结论作为论据。
- 语气要自信、坚定，但逻辑要严密。
- 直接回应上一轮空方的质疑（如果有）。
- 明确表达这一轮是对“增加仓位”的强力支持。

请用中文撰写。
"""

        response = llm.invoke(prompt)
        argument = f"Bull Strategist: {response.content}"

        new_count = investment_debate_state.get("count", 0) + 1
        logger.info(f"🐂 [指数多头] 发言完成，计数: {new_count}")

        new_investment_debate_state = {
            "history": history + "\n\n" + argument,
            "bull_history": bull_history + "\n\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return index_bull_node
