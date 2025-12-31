import sys
import os
import pytest
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from dotenv import load_dotenv
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
from tradingagents.tools.index_tools import fetch_sector_rotation, fetch_index_constituents, fetch_sector_news

# Load env
load_dotenv()

def test_sector_analyst_execution():
    print("\n\n>>> Testing Sector Analyst Execution (Robot Sector) <<<")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(
        model="deepseek-chat", # 使用DeepSeek模型
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL")
    )
    
    # 2. Tools
    tools = [fetch_sector_rotation, fetch_index_constituents, fetch_sector_news]
    
    # 3. Create Node
    sector_analyst = create_sector_analyst(llm, tools)
    
    # 4. Prepare State
    # Changed prompt to focus on Robot sector to reproduce user issue
    state = {
        "messages": [HumanMessage(content="请分析机器人板块的当前表现和未来趋势")],
        "policy_report": "当前政策鼓励高端制造，重点支持人形机器人、工业机器人产业发展，推动智能制造升级。",
        "session_type": "post",
        "sector_tool_call_count": 0,
        "sector_report": ""
    }
    
    # 5. Run Loop (Simulation of Graph)
    max_steps = 6
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        result = sector_analyst(state)
        
        # Check if report is generated
        if "sector_report" in result and result["sector_report"]:
            print("✅ Report generated!")
            report_preview = result["sector_report"][:500]
            print(report_preview + "...")
            
            # Check for fallback
            if "数据获取受限" in result["sector_report"]:
                print("❌ FALLBACK REPORT DETECTED!")
            else:
                print("✅ SUCCESS: Full report generated.")
            return

        # Check for tool calls
        messages = result["messages"]
        last_msg = messages[-1]
        
        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
            print(f"🔧 Tool calls generated: {len(last_msg.tool_calls)}")
            
            # Update state with the assistant's message
            state["messages"].append(last_msg)
            state["sector_tool_call_count"] = result["sector_tool_call_count"]
            
            for tc in last_msg.tool_calls:
                print(f"  - Tool: {tc['name']}, Args: {tc['args']}")
                
                # Execute Tool
                tool_name = tc['name']
                tool_args = tc['args']
                tool_output = ""
                
                try:
                    if tool_name == 'fetch_sector_rotation':
                        print("  > Executing fetch_sector_rotation...")
                        tool_output = fetch_sector_rotation.invoke(tool_args)
                    elif tool_name == 'fetch_index_constituents':
                        print("  > Executing fetch_index_constituents...")
                        tool_output = fetch_index_constituents.invoke(tool_args)
                    elif tool_name == 'fetch_sector_news':
                        print("  > Executing fetch_sector_news...")
                        tool_output = fetch_sector_news.invoke(tool_args)
                    else:
                        tool_output = f"Unknown tool: {tool_name}"
                    
                    output_str = str(tool_output)
                    print(f"  > Tool Output (First 100 chars): {output_str[:100].replace(chr(10), ' ')}...")
                    
                except Exception as e:
                    print(f"  ❌ Tool Execution Failed: {e}")
                    tool_output = f"Tool execution error: {str(e)}"
                
                # Create ToolMessage
                tool_msg = ToolMessage(content=str(tool_output), tool_call_id=tc['id'], name=tool_name)
                state["messages"].append(tool_msg)
        else:
            print("⚠️ No tool calls and no report? Unexpected state.")
            print(result)
            break

    print("❌ Max steps reached without report generation.")

if __name__ == "__main__":
    test_sector_analyst_execution()
