import time
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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

def create_risky_debator(llm):
    def risky_node(state) -> dict:
        # 1. 设置工具状态
        set_state(state)
        
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        risky_history = risk_debate_state.get("risky_history", "")

        current_safe_response = risk_debate_state.get("current_safe_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")
        
        trader_decision = state.get("trader_investment_plan")
        if not trader_decision:
             trader_decision = state.get("investment_plan", "")
             logger.info("ℹ️ [Risky Analyst] 未找到交易员计划，使用研究团队计划作为辩论基础")

        # 绑定工具
        tools = [list_reports, get_report_content, get_reports_batch]
        llm_with_tools = llm.bind_tools(tools)

        prompt = f"""作为激进风险分析师，您的职责是积极倡导高回报、高风险的投资机会，强调大胆策略和竞争优势。在评估交易员的决策或计划时，请重点关注潜在的上涨空间、增长潜力和创新收益——即使这些伴随着较高的风险。
        
以下是交易员的决策：
{trader_decision}

**任务要求：**
1. **主动查阅**相关的分析报告（市场、新闻、基本面、情绪等）来支持您的观点。请使用工具获取这些报告。
2. 直接回应保守和中性分析师提出的每个观点，用数据驱动的反驳和有说服力的推理进行反击。
3. 突出他们的谨慎态度可能错过的关键机会，或者他们的假设可能过于保守的地方。
4. 挑战每个反驳点，强调为什么高风险方法是最优的。

以下是当前对话历史：
{history} 

以下是保守分析师的最后论点：
{current_safe_response} 

以下是中性分析师的最后论点：
{current_neutral_response}。

如果其他观点没有回应，请不要虚构，只需提出您的观点。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info(f"🔄 [Risky Analyst] 开始执行分析流程 (Agent模式)")
        
        messages = [HumanMessage(content=prompt)]
        final_content = ""
        
        # Agent Loop
        max_steps = 10
        step = 0
        
        while step < max_steps:
            try:
                logger.info(f"🔄 [Risky Analyst] Step {step+1}: 调用 LLM")
                response = llm_with_tools.invoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"🛠️ [Risky Analyst] LLM 请求调用 {len(response.tool_calls)} 个工具")
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
                logger.error(f"❌ [Risky Analyst] 执行出错: {e}")
                final_content = f"分析出错: {str(e)}"
                break

        if not final_content:
            final_content = "无法生成分析。"

        argument = f"Risky Analyst: {final_content}"
        new_count = risk_debate_state["count"] + 1
        logger.info(f"🔥 [激进风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risky_history + "\n" + argument,
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "current_risky_response": argument,
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return risky_node
