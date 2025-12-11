from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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

def create_safe_debator(llm):
    def safe_node(state) -> dict:
        # 1. 设置工具状态
        set_state(state)
        
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")
        
        trader_decision = state.get("trader_investment_plan")
        if not trader_decision:
             trader_decision = state.get("investment_plan", "")
             logger.info("ℹ️ [Safe Analyst] 未找到交易员计划，使用研究团队计划作为辩论基础")

        # 绑定工具
        tools = [list_reports, get_report_content, get_reports_batch]
        llm_with_tools = llm.bind_tools(tools)

        prompt = f"""作为安全/保守风险分析师，您的主要目标是保护资产、最小化波动性，并确保稳定、可靠的增长。您优先考虑稳定性、安全性和风险缓解，仔细评估潜在损失、经济衰退和市场波动。在评估交易员的决策或计划时，请批判性地审查高风险要素，指出决策可能使公司面临不当风险的地方，以及更谨慎的替代方案如何能够确保长期收益。
        
以下是交易员的决策：
{trader_decision}

**任务要求：**
1. **主动查阅**相关的分析报告（市场、新闻、基本面、情绪等）来支持您的观点。请使用工具获取这些报告。
2. 积极反驳激进和中性分析师的论点，突出他们的观点可能忽视的潜在威胁或未能优先考虑可持续性的地方。
3. 质疑他们的乐观态度并强调他们可能忽视的潜在下行风险。
4. 证明低风险策略相对于他们方法的优势。

以下是当前对话历史：
{history} 

以下是激进分析师的最后回应：
{current_risky_response} 

以下是中性分析师的最后回应：
{current_neutral_response}。

如果其他观点没有回应，请不要虚构，只需提出您的观点。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info(f"🔄 [Safe Analyst] 开始执行分析流程 (Agent模式)")
        
        messages = [HumanMessage(content=prompt)]
        final_content = ""
        
        # Agent Loop
        max_steps = 10
        step = 0
        
        while step < max_steps:
            try:
                logger.info(f"🔄 [Safe Analyst] Step {step+1}: 调用 LLM")
                response = llm_with_tools.invoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"🛠️ [Safe Analyst] LLM 请求调用 {len(response.tool_calls)} 个工具")
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_id = tool_call["id"]
                        
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
                            
                        messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    
                    step += 1
                    continue
                else:
                    final_content = response.content
                    break
                    
            except Exception as e:
                logger.error(f"❌ [Safe Analyst] 执行出错: {e}")
                final_content = f"分析出错: {str(e)}"
                break

        if not final_content:
            final_content = "无法生成分析。"

        argument = f"Safe Analyst: {final_content}"
        new_count = risk_debate_state["count"] + 1
        logger.info(f"🛡️ [保守风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": safe_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Safe",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node
