#!/usr/bin/env python3
"""
Integration Test for Session-Aware Logic (v2.2)

Target:
1. Verify Sector Analyst adapts prompt based on session_type (morning/closing/post).
2. Verify Strategy Advisor adjusts position based on session_type and technical signals.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
import json
import logging

# Add project root to path
sys.path.insert(0, '.')

from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
from tradingagents.agents.analysts.technical_analyst import create_technical_analyst

# Configure logging to capture output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agents")

class TestSessionAwareness(unittest.TestCase):
    
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_toolkit = MagicMock()
        
        # Mock LLM response for Sector Analyst
        self.mock_llm.bind_tools.return_value.invoke.return_value.content = json.dumps({
            "top_sectors": ["Test Sector"],
            "bottom_sectors": [],
            "rotation_trend": "None",
            "hot_themes": [],
            "analysis_summary": "Test Summary",
            "confidence": 0.8,
            "sentiment_score": 0.5
        })
        
        # Mock LLM response for Strategy Advisor
        self.mock_llm.invoke.return_value.content = json.dumps({
            "market_outlook": "看多",
            "final_position": 0.6,
            "position_breakdown": {
                "core_holding": 0.3,
                "tactical_allocation": 0.2,
                "cash_reserve": 0.5
            },
            "adjustment_triggers": {
                "increase_to": 0.8,
                "increase_condition": "cond",
                "decrease_to": 0.4,
                "decrease_condition": "cond"
            },
            "rationale": "Test",
            "confidence": 0.8
        })

    def test_sector_analyst_session_prompts(self):
        """Test if Sector Analyst receives correct session context in prompt"""
        print("\n=== Testing Sector Analyst Session Logic ===")
        
        # We need to intercept the prompt passed to the chain
        # Since the code does `chain = prompt | llm.bind_tools(tools)`, we can verify by mocking the chain construction
        # But simpler is to check the log output or if we can inspect the prompt object.
        # The prompt is constructed inside the function. 
        # However, we can use `patch` on `ChatPromptTemplate.from_messages` to capture the system message.
        
        node = create_sector_analyst(self.mock_llm, self.mock_toolkit)
        
        sessions = {
            "morning": "当前是早盘阶段",
            "closing": "当前是尾盘阶段",
            "post": "当前是盘后复盘阶段"
        }
        
        for session, expected_text in sessions.items():
            print(f"Testing session: {session}")
            state = {
                "messages": [],
                "sector_tool_call_count": 0,
                "policy_report": "Policy Report",
                "session_type": session
            }
            
            # We use a trick to capture the prompt:
            # The code uses `prompt.partial(...)` then `chain.invoke(...)`
            # We can mock `ChatPromptTemplate.from_messages`
            
            with patch("tradingagents.agents.analysts.sector_analyst.ChatPromptTemplate") as MockPrompt:
                # Setup the mock to behave like a real prompt template enough to pass
                mock_template = MagicMock()
                MockPrompt.from_messages.return_value = mock_template
                mock_template.partial.return_value = mock_template
                
                # Mock the chain
                mock_chain = MagicMock()
                self.mock_llm.bind_tools.return_value = mock_chain
                mock_template.__or__.return_value = mock_chain # prompt | llm...
                
                # Run node
                node(state)
                
                # Verify from_messages was called
                args, _ = MockPrompt.from_messages.call_args
                messages = args[0]
                system_msg = messages[0][1] # ("system", prompt_template)
                
                # Verify the template contains the expected text (it is constructed before partial)
                # Wait, the code constructs the string `prompt_template` using `time_context` based on session_type
                # THEN calls `from_messages`.
                # So `system_msg` should contain the `expected_text`.
                
                if expected_text in system_msg:
                    print(f"✅ Verified prompt contains: '{expected_text}'")
                else:
                    print(f"❌ Failed: Prompt does not contain '{expected_text}'")
                    # print(f"Actual prompt: {system_msg}")
                    self.fail(f"Prompt missing session context for {session}")

    def test_strategy_advisor_technical_adjustment(self):
        """Test Strategy Advisor technical adjustment logic"""
        print("\n=== Testing Strategy Advisor Technical Adjustment ===")
        
        # Base case: Policy suggests ~50% (need to mock extracting functions)
        # We need to mock `make_strategy_decision` to return a known base position
        
        with patch("tradingagents.agents.analysts.strategy_advisor.make_strategy_decision") as mock_decision, \
             patch("tradingagents.agents.analysts.strategy_advisor.ChatPromptTemplate") as MockPrompt:
            
            # Setup Mock Chain to avoid "MagicMock" issues with prompt | llm
            mock_chain = MagicMock()
            mock_template = MagicMock()
            MockPrompt.from_messages.return_value = mock_template
            mock_template.partial.return_value = mock_template
            mock_template.__or__.return_value = mock_chain
            
            # Return: base, short_term, final, breakdown, triggers
            # Let's say decision returns 0.5 final position before technicals
            mock_decision.return_value = (
                0.5, # base
                0.0, # short term
                0.5, # final (pre-tech)
                {"core_holding":0.3, "tactical_allocation":0.2, "cash_reserve":0.5},
                {"increase_to":0.6, "increase_condition":"a", "decrease_to":0.4, "decrease_condition":"b"}
            )
            
            # Mock the result of chain.invoke
            mock_result = MagicMock()
            mock_result.content = json.dumps({
                "market_outlook": "看多",
                "final_position": 0.6,
                "position_breakdown": {
                    "core_holding": 0.3,
                    "tactical_allocation": 0.2,
                    "cash_reserve": 0.5
                },
                "adjustment_triggers": {},
                "rationale": "Test",
                "confidence": 0.8
            })
            mock_chain.invoke.return_value = mock_result
            
            node = create_strategy_advisor(self.mock_llm)
            
            test_cases = [
                # (session, tech_signal, expected_adjustment)
                ("morning", "BULLISH", 0.1),
                ("morning", "BEARISH", -0.1),
                ("closing", "BULLISH", 0.05),
                ("closing", "BEARISH", -0.05),
                ("post", "BULLISH", 0.0), # No explicit logic for post, so 0 adjustment
            ]
            
            for session, signal, expected_adj in test_cases:
                print(f"Testing {session} with {signal} signal...")
                
                tech_report = json.dumps({"trend_signal": f"{signal} (View)"})
                
                state = {
                    "messages": [],
                    "macro_report": "Macro",
                    "policy_report": "Policy",
                    "sector_report": "Sector",
                    "international_news_report": "News",
                    "technical_report": tech_report,
                    "session_type": session
                }
                
                # We need to capture the logs or the partial variables passed to prompt
                # Because the function returns a result message, but we want to verify the internal calculation.
                # The log says: "⚡ [策略顾问] 技术面调整 ({tech_signal}): ... Adj: ..."
                
                with self.assertLogs("agents", level="INFO") as cm:
                    node(state)
                    
                    # Verify logs
                    logs = "\n".join(cm.output)
                    if expected_adj != 0:
                        expected_log_part = f"Adj: {expected_adj:+.2%}"
                        if expected_log_part in logs:
                            print(f"✅ Verified adjustment log: {expected_log_part}")
                        else:
                            print(f"❌ Log not found: {expected_log_part}")
                            print(f"Logs: {logs}")
                            self.fail(f"Adjustment not applied correctly for {session}/{signal}")
                    else:
                        # For 0 adjustment, we shouldn't see the specific log
                        if "技术面调整" in logs:
                            # It might log if logic is wrong
                            # Check specifically for non-zero adjustment log format
                            if "Adj: +0.00%" not in logs and "Adj: -0.00%" not in logs:
                                 # If it logged "Adj: ...", and we expect 0, that's wrong unless it's 0.00%
                                 # The code only logs if tech_adjustment != 0.
                                 print(f"❌ Unexpected adjustment log found for {session}/{signal}")
                                 self.fail("Should not adjust for this case")
                        else:
                            print(f"✅ Verified no adjustment log for {session}/{signal}")


if __name__ == "__main__":
    unittest.main()
