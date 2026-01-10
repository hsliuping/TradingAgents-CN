#!/usr/bin/env python3
"""
Real Environment Test for News Analyst (DeepSeek)
"""

import sys
import os
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.agents.analysts.international_news_analyst import create_index_news_analyst
from test_utils import check_environment

import asyncio
from langchain_core.messages import ToolMessage
from tradingagents.tools.international_news_tools import (
    fetch_aggregated_news,
    fetch_bloomberg_news,
    fetch_reuters_news,
    fetch_google_news,
    fetch_cn_international_news
)
from tradingagents.tools.index_tools import fetch_policy_news

# Load environment variables
load_dotenv()

# Tool mapping
TOOL_MAP = {
    "fetch_aggregated_news": fetch_aggregated_news,
    "fetch_bloomberg_news": fetch_bloomberg_news,
    "fetch_reuters_news": fetch_reuters_news,
    "fetch_google_news": fetch_google_news,
    "fetch_cn_international_news": fetch_cn_international_news,
    "fetch_policy_news": fetch_policy_news
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

def test_real_news_analyst():
    check_environment()

    print("🔄 Initializing LLM and Toolkit...")
    llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
    toolkit = Toolkit()

    print("🔄 Creating News Analyst Node...")
    news_node = create_index_news_analyst(llm, toolkit)

    state = {
        "messages": [],
        "international_news_messages": [],
        "international_news_report": "",
        "international_news_tool_call_count": 0,
        "company_of_interest": "sh000001", 
        "trade_date": "2024-05-20",
        "data_source_status": {"news_api": True} # Assume available
    }

    print("🚀 Invoking News Analyst (End-to-End Loop)...")
    max_steps = 5
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        try:
            result = news_node(state)
            
            # Update state manually (simulating graph reducer)
            if "international_news_messages" in result:
                new_msgs = result["international_news_messages"]
                # Only append if they are new (simple check)
                # In a real graph, this is handled by the reducer.
                # Here, news_node returns the NEW message.
                state["international_news_messages"].extend(new_msgs)
            
            if "international_news_tool_call_count" in result:
                state["international_news_tool_call_count"] = result["international_news_tool_call_count"]
                
            if "international_news_report" in result and result["international_news_report"]:
                 state["international_news_report"] = result["international_news_report"]
                 print("\n✅ News Report Generated!")
                 print(result["international_news_report"])
                 break
            
            # Check for tool calls
            last_msg = state["international_news_messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                print(f"⚠️ Agent requested {len(last_msg.tool_calls)} tool calls.")
                
                tool_outputs = []
                for call in last_msg.tool_calls:
                    tool_name = call['name']
                    tool_args = call['args']
                    call_id = call['id']
                    
                    output = execute_tool(tool_name, tool_args)
                    # print(f"   Output preview: {str(output)[:100]}...")
                    
                    tool_msg = ToolMessage(
                        content=str(output),
                        tool_call_id=call_id,
                        name=tool_name
                    )
                    state["international_news_messages"].append(tool_msg)
                
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
    test_real_news_analyst()
