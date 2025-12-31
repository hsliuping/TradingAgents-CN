import sys
import os
import pytest
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from dotenv import load_dotenv
import json
import asyncio

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tradingagents.agents.analysts.technical_analyst import create_technical_analyst
from tradingagents.tools.index_tools import fetch_technical_indicators

# Load env
load_dotenv()

def test_technical_analyst_execution():
    print("\n\n>>> Testing Technical Analyst Execution (Code: 980022) <<<")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL")
    )
    
    # 2. Tools
    tools = [fetch_technical_indicators]
    
    # 3. Create Node
    tech_analyst = create_technical_analyst(llm, tools)
    
    # 4. Prepare State
    # Explicitly asking for 980022
    state = {
        "messages": [HumanMessage(content="请对指数 980022 进行技术分析")],
        "tech_tool_call_count": 0,
        "technical_report": ""
    }
    
    # 5. Run Loop
    max_steps = 6
    step = 0
    
    while step < max_steps:
        step += 1
        print(f"\n--- Step {step} ---")
        
        result = tech_analyst(state)
        
        # Check if report is generated
        if "technical_report" in result and result["technical_report"]:
            print("✅ Report generated!")
            report_preview = result["technical_report"][:500]
            print(report_preview + "...")
            
            # Check for fallback
            if "技术分析降级" in result["technical_report"]:
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
            state["tech_tool_call_count"] = result["tech_tool_call_count"]
            
            for tc in last_msg.tool_calls:
                print(f"  - Tool: {tc['name']}, Args: {tc['args']}")
                
                # Execute Tool
                tool_name = tc['name']
                tool_args = tc['args']
                tool_output = ""
                
                try:
                    if tool_name == 'fetch_technical_indicators':
                        print("  > Executing fetch_technical_indicators...")
                        # It is async
                        tool_output = asyncio.run(fetch_technical_indicators.ainvoke(tool_args))
                    else:
                        tool_output = f"Unknown tool: {tool_name}"
                    
                    output_str = str(tool_output)
                    print(f"  > Tool Output (First 100 chars): {output_str[:100].replace(chr(10), ' ')}...")
                    
                    state["messages"].append(ToolMessage(tool_call_id=tc['id'], content=output_str))
                    
                except Exception as e:
                    print(f"  ❌ Tool Execution Failed: {e}")
                    state["messages"].append(ToolMessage(tool_call_id=tc['id'], content=f"Error: {e}"))
        else:
            print("No tool calls and no report. Ending.")
            # If no tool calls, print the content to see why
            print(f"Assistant Content: {last_msg.content}")
            break

if __name__ == "__main__":
    test_technical_analyst_execution()
