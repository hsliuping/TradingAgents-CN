#!/usr/bin/env python3
"""
Real Environment Test for Macro Analyst (DeepSeek)
"""

import sys
import os
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
from test_utils import check_environment

import asyncio
from langchain_core.messages import ToolMessage
from tradingagents.tools.index_tools import fetch_macro_data

# Load environment variables
load_dotenv()

# Tool mapping
TOOL_MAP = {
    "fetch_macro_data": fetch_macro_data
}

def execute_tool(tool_name, tool_args):
    """Execute a tool by name with arguments"""
    if tool_name not in TOOL_MAP:
        return f"Error: Tool '{tool_name}' not found."
    
    tool_func = TOOL_MAP[tool_name]
    print(f"🛠️ Executing tool: {tool_name} with args: {tool_args}")
    
    try:
        # Check if the tool has an async implementation (LangChain StructuredTool)
        if hasattr(tool_func, 'coroutine') and tool_func.coroutine:
             return asyncio.run(tool_func.ainvoke(tool_args))
        # Check if the tool function itself is a coroutine (raw function, less likely here)
        elif asyncio.iscoroutinefunction(tool_func):
             return asyncio.run(tool_func(**tool_args))
        else:
             return tool_func.invoke(tool_args)
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"

def test_real_macro_analyst():
    # Pre-check environment
    check_environment()

    print("🔄 Initializing LLM and Toolkit...")
    llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
    toolkit = Toolkit()

    print("🔄 Creating Macro Analyst Node...")
    macro_node = create_macro_analyst(llm, toolkit)

    # Construct initial state
    state = {
        "messages": [],
        "macro_report": "",
        "macro_tool_call_count": 0,
        "company_of_interest": "000001.SH", 
        "trade_date": "2024-05-20",
        "data_source_status": {"macro_db": True} # Assume available
    }

    print("🚀 Invoking Macro Analyst (End-to-End Loop)...")
    max_steps = 5
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        try:
            result = macro_node(state)
            
            # Update state manually
            if "messages" in result:
                new_msgs = result["messages"]
                # Append new messages (usually the last one is the new one)
                # But careful not to duplicate if the agent returns the whole history (some do, some don't)
                # create_macro_analyst returns {"messages": [result]} which is just the new message.
                state["messages"].extend(new_msgs)
            
            if "macro_tool_call_count" in result:
                state["macro_tool_call_count"] = result["macro_tool_call_count"]
                
            if "macro_report" in result and result["macro_report"]:
                 state["macro_report"] = result["macro_report"]
                 print("\n✅ Final Report Generated!")
                 print(result["macro_report"])
                 break
            
            # Check for tool calls
            last_msg = state["messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                print(f"⚠️ Agent requested {len(last_msg.tool_calls)} tool calls.")
                
                for call in last_msg.tool_calls:
                    tool_name = call['name']
                    tool_args = call['args']
                    call_id = call['id']
                    
                    output = execute_tool(tool_name, tool_args)
                    print(f"   Tool Output: {str(output)[:500]}...")
                    
                    tool_msg = ToolMessage(
                        content=str(output),
                        tool_call_id=call_id,
                        name=tool_name
                    )
                    state["messages"].append(tool_msg)
                
                print("🔄 Tool outputs added to history. Continuing...")
                continue
            
            print("ℹ️ No tool calls and no report? (Should not happen unless finished without report)")
            break
        
        except Exception as e:
            print(f"\n❌ Test Failed with Exception: {e}")
            import traceback
            traceback.print_exc()
            break

if __name__ == "__main__":
    test_real_macro_analyst()
