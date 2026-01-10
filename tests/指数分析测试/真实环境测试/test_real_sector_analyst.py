#!/usr/bin/env python3
"""
Real Environment Test for Sector Analyst (DeepSeek)
"""

import sys
import os
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
from test_utils import check_environment

import asyncio
from langchain_core.messages import ToolMessage
from tradingagents.tools.index_tools import (
    fetch_sector_rotation, 
    fetch_index_constituents, 
    fetch_sector_news, 
    fetch_stock_sector_info
)

# Load environment variables
load_dotenv()

# Tool mapping
TOOL_MAP = {
    "fetch_sector_rotation": fetch_sector_rotation,
    "fetch_index_constituents": fetch_index_constituents,
    "fetch_sector_news": fetch_sector_news,
    "fetch_stock_sector_info": fetch_stock_sector_info
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

def test_real_sector_analyst():
    check_environment()

    print("🔄 Initializing LLM and Toolkit...")
    llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
    toolkit = Toolkit()

    print("🔄 Creating Sector Analyst Node...")
    sector_node = create_sector_analyst(llm, toolkit)

    state = {
        "messages": [],
        "sector_report": "",
        "sector_tool_call_count": 0,
        "company_of_interest": "000001.SH",
        "trade_date": "2024-05-20" 
    }

    print("🚀 Invoking Sector Analyst (End-to-End Loop)...")
    max_steps = 5
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        try:
            result = sector_node(state)
            
            # Update state manually
            if "messages" in result:
                state["messages"].extend(result["messages"])
            
            if "sector_tool_call_count" in result:
                state["sector_tool_call_count"] = result["sector_tool_call_count"]
                
            if "sector_report" in result and result["sector_report"]:
                 state["sector_report"] = result["sector_report"]
                 print("\n✅ Sector Report Generated!")
                 print(result["sector_report"])
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
    test_real_sector_analyst()
