import sys
import os
import pytest
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tradingagents.agents.analysts.international_news_analyst import create_international_news_analyst
from tradingagents.tools.international_news_tools import (
    fetch_bloomberg_news, 
    fetch_reuters_news, 
    fetch_google_news,
    fetch_cn_international_news
)

# Load env
load_dotenv()

def test_international_news_analyst_execution():
    print("\n\n>>> Testing International News Analyst Execution (Sector: Robotics) <<<")
    
    # 1. Initialize LLM
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.2,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL")
    )
    
    # 2. Tools
    tools = [fetch_bloomberg_news, fetch_reuters_news, fetch_google_news, fetch_cn_international_news]
    
    # 3. Create Node
    news_analyst = create_international_news_analyst(llm, tools)
    
    # 4. Prepare State
    # Testing specific sector "机器人"
    state = {
        "messages": [HumanMessage(content="请进行国际新闻分析")],
        "company_of_interest": "机器人", 
        "trade_date": "2024-05-20", 
        "policy_report": "",
        "international_news_tool_call_count": 0,
        "international_news_report": ""
    }
    
    # 5. Run Step-by-Step
    print("--- Step 1: Initial Call ---")
    current_result = news_analyst(state)
    
    round_count = 1
    max_rounds = 3
    
    while round_count <= max_rounds:
        if "international_news_report" in current_result and len(current_result["international_news_report"]) > 100:
            print(f"✅ Report generated in Round {round_count}:")
            print(current_result["international_news_report"][:500] + "...")
            return

        # Check for tool calls
        messages = current_result["messages"]
        last_msg = messages[-1]
        
        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
            print(f"\n🔧 Round {round_count} Tool calls generated: {len(last_msg.tool_calls)}")
            
            state["messages"].append(last_msg)
            state["international_news_tool_call_count"] = current_result["international_news_tool_call_count"]
            
            for tc in last_msg.tool_calls:
                print(f"  - Tool: {tc['name']}, Args: {tc['args']}")
                
                # Execute Tool
                tool_name = tc['name']
                tool_args = tc['args']
                tool_output = ""
                
                try:
                    if tool_name == 'fetch_bloomberg_news':
                        print("  > Executing fetch_bloomberg_news...")
                        tool_output = fetch_bloomberg_news.invoke(tool_args)
                    elif tool_name == 'fetch_reuters_news':
                        print("  > Executing fetch_reuters_news...")
                        tool_output = fetch_reuters_news.invoke(tool_args)
                    elif tool_name == 'fetch_google_news':
                        print("  > Executing fetch_google_news...")
                        tool_output = fetch_google_news.invoke(tool_args)
                    elif tool_name == 'fetch_cn_international_news':
                        print("  > Executing fetch_cn_international_news...")
                        tool_output = fetch_cn_international_news.invoke(tool_args)
                    else:
                        tool_output = f"Unknown tool: {tool_name}"
                    
                    print(f"  > Tool Output (First 100 chars): {str(tool_output)[:100].replace(chr(10), ' ')}...")
                    
                except Exception as e:
                    print(f"  ❌ Tool Execution Failed: {e}")
                    tool_output = f"Tool execution error: {str(e)}"
                
                # Create ToolMessage
                tool_msg = ToolMessage(content=str(tool_output), tool_call_id=tc['id'], name=tool_name)
                state["messages"].append(tool_msg)

            # Run Next Round
            print(f"\n--- Round {round_count + 1}: After Tool Execution ---")
            current_result = news_analyst(state)
            round_count += 1
            
        else:
            print(f"❌ No tool calls and no report in Round {round_count}")
            break
            
    if "international_news_report" not in current_result:
        print("❌ Failed to generate report after max rounds")

if __name__ == "__main__":
    test_international_news_analyst_execution()
