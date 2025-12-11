import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入报告工具
from tradingagents.tools.mcp.tools.reports import (
    list_reports, 
    get_report_content, 
    get_reports_batch, 
    set_state
)
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:
        # 1. 设置工具状态，使其能访问当前 State
        set_state(state)
        
        company_name = state["company_of_interest"]
        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        
        # 优先读取交易员的投资计划
        trader_plan = state.get("trader_investment_plan")
        if not trader_plan:
            trader_plan = state.get("investment_plan", "")
            logger.info("ℹ️ [Portfolio Manager] 未找到交易员计划，使用研究团队计划作为基础")
        else:
            logger.info("ℹ️ [Portfolio Manager] 已获取交易员计划作为风险评估基础")

        # 绑定工具
        tools = [list_reports, get_report_content, get_reports_batch]
        llm_with_tools = llm.bind_tools(tools)

        # 构建 Prompt，移除硬编码报告，指示使用工具
        prompt = f"""作为首席投资组合经理(Portfolio Manager)和风险管理委员会主席，您的职责是基于全面的风险评估做出最终投资决策。

您必须**主动查阅**相关的分析报告（如市场分析、新闻分析、基本面分析、情绪分析等）来做出明智的决策。请使用提供的工具来获取这些报告的内容。如果调用工具获取报告失败，请在最终报告中明确说明缺失了哪些信息。

**当前任务：**
1. 查阅相关分析报告，了解市场、新闻、基本面和情绪状况。具体是 fundamentals_report 还是 news_report 请通过工具 list_reports 查看。
2. 听取激进、中性和保守三位风险分析师的辩论。
3. 权衡这些观点，并决定最终的执行方案。

**决策指导原则：**
1. **综合风险辩论**：评估激进派的机会主义与保守派的风险规避，结合中性派的平衡观点，找到最佳风险收益比。
2. **最终决策**：明确给出买入、卖出或持有的指令。
3. **完善执行计划**：基于交易员的原始计划**{trader_plan}**，结合风险分析师的反馈进行必要的修正或优化（例如调整仓位、设置更严格的止损、改变入场时机等）。

**交付成果：**
- 明确且可操作的建议：买入、卖出或持有。
- 详细的推理过程：解释为什么采纳或拒绝了某些风险分析师的观点，引用您查阅的报告内容作为支持。
- 最终调整后的交易计划。

---

**风险分析师辩论历史：**
{history}

---

**原始交易计划：**
{trader_plan}

请用中文撰写所有分析内容和建议，展现专业基金经理的决策能力。"""

        logger.info(f"🔄 [Risk Manager] 开始执行决策流程 (Agent模式)")
        
        messages = [HumanMessage(content=prompt)]
        final_content = ""
        
        # 简单的 Agent Loop
        max_steps = 10
        step = 0
        
        while step < max_steps:
            try:
                logger.info(f"🔄 [Risk Manager] Step {step+1}: 调用 LLM")
                response = llm_with_tools.invoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"🛠️ [Risk Manager] LLM 请求调用 {len(response.tool_calls)} 个工具")
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_id = tool_call["id"]
                        
                        logger.info(f"  - 调用工具: {tool_name} 参数: {tool_args}")
                        
                        # 执行工具
                        tool_result = "工具调用失败"
                        try:
                            if tool_name == "list_reports":
                                tool_result = list_reports()
                            elif tool_name == "get_report_content":
                                tool_result = get_report_content(**tool_args)
                            elif tool_name == "get_reports_batch":
                                tool_result = get_reports_batch(**tool_args)
                            else:
                                tool_result = f"未知工具: {tool_name}"
                        except Exception as e:
                            tool_result = f"工具执行出错: {str(e)}"
                            logger.error(f"❌ 工具 {tool_name} 执行失败: {e}")
                            
                        # 添加工具结果到消息历史
                        messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    
                    # 继续循环，让 LLM 处理工具结果
                    step += 1
                    continue
                else:
                    # 没有工具调用，说明是最终回复
                    final_content = response.content
                    logger.info(f"✅ [Risk Manager] 获得最终回复")
                    break
                    
            except Exception as e:
                logger.error(f"❌ [Risk Manager] 执行出错: {e}")
                final_content = f"执行过程中发生错误: {str(e)}。基于现有信息，建议采取保守策略（持有或观望）。"
                break
                
        if not final_content:
            final_content = "由于技术原因无法生成详细分析，建议暂时观望。"

        new_risk_debate_state = {
            "judge_decision": final_content,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }
        
        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_content,
        }

    return risk_manager_node
