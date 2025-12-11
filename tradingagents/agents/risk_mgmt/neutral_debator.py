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

def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        # 1. 设置工具状态
        set_state(state)
        
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_safe_response = risk_debate_state.get("current_safe_response", "")
        
        # 获取交易员计划（作为基础输入，可以直接保留在 Prompt 中）
        trader_decision = state.get("trader_investment_plan")
        if not trader_decision:
             trader_decision = state.get("investment_plan", "")
             logger.info("ℹ️ [Neutral Analyst] 未找到交易员计划，使用研究团队计划作为辩论基础")

        # 绑定工具
        tools = [list_reports, get_report_content, get_reports_batch]
        llm_with_tools = llm.bind_tools(tools)

        prompt = f"""作为中性风险分析师，您的角色是提供平衡的视角，权衡交易员决策或计划的潜在收益和风险。您优先考虑全面的方法，评估上行和下行风险，同时考虑更广泛的市场趋势、潜在的经济变化和多元化策略。
        
以下是交易员的决策：
{trader_decision}

**任务要求：**
1. **主动查阅**相关的分析报告（市场、新闻、基本面、情绪等）来支持您的观点。请使用工具获取这些报告。
2. 挑战激进和安全分析师，指出每种观点可能过于乐观或过于谨慎的地方。
3. 说明为什么适度风险策略可能提供两全其美的效果，既提供增长潜力又防范极端波动。
4. 专注于辩论而不是简单地呈现数据，旨在表明平衡的观点可以带来最可靠的结果。

以下是当前对话历史：
{history} 

以下是激进分析师的最后回应：
{current_risky_response} 

以下是安全分析师的最后回应：
{current_safe_response}。

如果其他观点没有回应，请不要虚构，只需提出您的观点。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info(f"🔄 [Neutral Analyst] 开始执行分析流程 (Agent模式)")
        
        messages = [HumanMessage(content=prompt)]
        final_content = ""
        
        # Agent Loop
        max_steps = 10
        step = 0
        
        while step < max_steps:
            try:
                logger.info(f"🔄 [Neutral Analyst] Step {step+1}: 调用 LLM")
                response = llm_with_tools.invoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"🛠️ [Neutral Analyst] LLM 请求调用 {len(response.tool_calls)} 个工具")
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
                logger.error(f"❌ [Neutral Analyst] 执行出错: {e}")
                final_content = f"分析出错: {str(e)}"
                break

        if not final_content:
            final_content = "无法生成分析。"

        argument = f"Neutral Analyst: {final_content}"
        new_count = risk_debate_state["count"] + 1
        logger.info(f"⚖️ [中性风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": argument,
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
