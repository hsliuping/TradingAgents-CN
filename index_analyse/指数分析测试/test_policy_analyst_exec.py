import sys
import os
import pytest
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from dotenv import load_dotenv
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
from tradingagents.tools.index_tools import fetch_policy_news, fetch_macro_data

# Load env
load_dotenv()

def test_policy_analyst_execution():
    print("\n\n>>> Testing Policy Analyst Execution <<<")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL")
    )
    
    # 2. Tools
    tools = [fetch_policy_news, fetch_macro_data]
    
    # 3. Create Node
    policy_analyst = create_policy_analyst(llm, tools)
    
    # 4. Prepare State
    state = {
        "messages": [HumanMessage(content="请分析当前的政策环境对市场的影响")],
        "policy_tool_call_count": 0,
        "policy_report": ""
    }
    
    # 5. Run Loop
    max_steps = 6
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        result = policy_analyst(state)
        
        # Check if report is generated
        if "policy_report" in result and result["policy_report"]:
            print("✅ Report generated!")
            report_preview = result["policy_report"][:500]
            print(report_preview + "...")
            
            # Check for fallback
            if "数据获取受限" in result["policy_report"] or "无法获取政策数据" in result["policy_report"]:
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
            state["policy_tool_call_count"] = result["policy_tool_call_count"]
            
            for tc in last_msg.tool_calls:
                print(f"  - Tool: {tc['name']}, Args: {tc['args']}")
                
                # Execute Tool
                tool_name = tc['name']
                tool_args = tc['args']
                tool_output = ""
                
                try:
                    if tool_name == 'fetch_policy_news':
                        print("  > Executing fetch_policy_news...")
                        tool_output = fetch_policy_news.invoke(tool_args)
                    elif tool_name == 'fetch_macro_data':
                        print("  > Executing fetch_macro_data...")
                        tool_output = fetch_macro_data.invoke(tool_args)  # fetch_macro_data is async tool but wrapped? Wait, it's defined as async def in index_tools.py
                        # If it's async, invoke might fail if not awaited or if LangChain doesn't handle it automatically in sync context.
                        # However, for this test script, we might need to handle async if the tool is async.
                        # fetch_policy_news is sync. fetch_macro_data is async.
                        # Let's check how other tests handle async tools.
                        # test_sector_analyst_exec.py uses invoke() on fetch_index_constituents (sync).
                        # If fetch_macro_data is async, we should use ainvoke or run it in loop.
                        # But for simplicity, if it fails, we'll see.
                        pass
                    else:
                        tool_output = f"Unknown tool: {tool_name}"
                    
                    # For this test, since we are mocking the loop manually and running sync, 
                    # we need to handle async tools if they are async.
                    # Actually, fetch_macro_data is async. We might need asyncio.run for it.
                    import asyncio
                    if tool_name == 'fetch_macro_data':
                         tool_output = asyncio.run(fetch_macro_data.invoke(tool_args))
                    elif tool_name == 'fetch_policy_news': # Sync
                         tool_output = fetch_policy_news.invoke(tool_args)

                    
                    output_str = str(tool_output)
                    print(f"  > Tool Output (First 100 chars): {output_str[:100].replace(chr(10), ' ')}...")
                    
                    state["messages"].append(ToolMessage(tool_call_id=tc['id'], content=output_str))
                    
                except Exception as e:
                    print(f"  ❌ Tool Execution Failed: {e}")
                    state["messages"].append(ToolMessage(tool_call_id=tc['id'], content=f"Error: {e}"))
        else:
            print("No tool calls and no report. Ending.")
            break

if __name__ == "__main__":
    test_policy_analyst_execution()
