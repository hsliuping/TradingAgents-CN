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

def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        # 1. 设置工具状态
        set_state(state)
        
        history = state["investment_debate_state"].get("history", "")
        investment_debate_state = state["investment_debate_state"]

        # 安全检查：确保memory不为None
        # 注意：这里我们保留 memory 检索逻辑，但将其作为 prompt 的一部分注入
        # 更好的做法是将其也封装为工具，但目前先保持兼容性
        past_memories = []
        if memory is not None:
             # 为了构建 memory query，我们可能需要先获取一些摘要
             # 但为了简化，我们暂时使用简单的查询或跳过
             pass

        # 绑定工具
        tools = [list_reports, get_report_content, get_reports_batch]
        llm_with_tools = llm.bind_tools(tools)

        prompt = f"""作为研究部主管(Head of Research)和首席分析师，您的职责是主持看涨(Bull)和看跌(Bear)研究员之间的辩论，并综合各方观点生成一份权威的投资分析报告。

您必须**主动查阅**所有可用的分析报告（市场、新闻、基本面、情绪等）来做出判断。请使用提供的工具来获取报告内容。

**任务要求：**
1. 使用工具查阅所有相关的分析报告。
2. 批判性地评估看涨和看跌研究员的辩论观点。
3. 简洁地总结双方的关键观点。
4. 提供明确且可操作的建议（买入、卖出或持有）。
5. 制定一份详细的初步投资计划(Investment Plan)。

**投资计划内容：**
1. **核心观点**：确立研究团队的立场。
2. **详细理由**：解释支持该立场的关键数据和逻辑。
3. **战略行动建议**：具体的实施步骤。
4. **📊 目标价格分析**：基于您查阅的报告（基本面、新闻、情绪），提供全面的目标价格区间和具体价格目标。
   - 💰 **您必须提供具体的目标价格** - 不要回复"无法确定"或"需要更多信息"。

请用中文撰写所有分析内容和建议，确保为交易员提供高质量的决策依据。

以下是辩论历史：
{history}
"""

        logger.info(f"🔄 [Research Manager] 开始执行分析流程 (Agent模式)")
        
        messages = [HumanMessage(content=prompt)]
        final_content = ""
        
        # Agent Loop
        max_steps = 10
        step = 0
        
        while step < max_steps:
            try:
                logger.info(f"🔄 [Research Manager] Step {step+1}: 调用 LLM")
                response = llm_with_tools.invoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"🛠️ [Research Manager] LLM 请求调用 {len(response.tool_calls)} 个工具")
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_id = tool_call["id"]
                        
                        logger.info(f"  - 调用工具: {tool_name} 参数: {tool_args}")
                        
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
                            
                        messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    
                    step += 1
                    continue
                else:
                    final_content = response.content
                    logger.info(f"✅ [Research Manager] 获得最终回复")
                    break
                    
            except Exception as e:
                logger.error(f"❌ [Research Manager] 执行出错: {e}")
                final_content = f"执行过程中发生错误: {str(e)}"
                break
        
        if not final_content:
            final_content = "分析生成失败。"

        new_investment_debate_state = {
            "judge_decision": final_content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": final_content,
            "count": investment_debate_state["count"],
        }
        
        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": final_content
        }

    return research_manager_node
