#!/usr/bin/env python3
"""
Real Environment Test for Strategy Advisor (DeepSeek)
"""

import sys
import os
import json
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
from test_utils import check_environment

# Load environment variables
load_dotenv()

def test_real_strategy_advisor():
    check_environment()

    print("🔄 Initializing LLM...")
    llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
    
    print("🔄 Creating Strategy Advisor Node...")
    strategy_node = create_strategy_advisor(llm)

    # Manually construct a full upstream state
    state = {
        "messages": [],
        "company_of_interest": "000001.SH",
        "trade_date": "2024-05-20",
        
        # Macro Report
        "macro_report": json.dumps({
            "economic_cycle": "复苏期",
            "liquidity": "宽松",
            "key_indicators": ["GDP增长5%", "CPI温和上涨"],
            "analysis_summary": "经济复苏迹象明显，流动性充裕。",
            "confidence": 0.8,
            "sentiment_score": 0.7
        }, ensure_ascii=False),
        
        # Policy Report
        "policy_report": json.dumps({
            "monetary_policy": "宽松",
            "fiscal_policy": "积极",
            "industry_policy": ["金融支持", "科技创新"],
            "long_term_policies": [
                {"name": "金融强国", "duration": "长期", "support_strength": "强", "policy_continuity": 0.9}
            ],
            "overall_support_strength": "强",
            "long_term_confidence": 0.85,
            "analysis_summary": "政策支持力度大，利好金融板块。",
            "confidence": 0.85
        }, ensure_ascii=False),
        
        # International News Report
        "international_news_report": json.dumps({
            "key_news": [
                {"source": "Bloomberg", "title": "全球股市普涨", "type": "市场动态", "impact_strength": "中"}
            ],
            "overall_impact": "外部环境平稳偏好",
            "impact_strength": "中",
            "confidence": 0.7,
            "impact_duration": "短期"
        }, ensure_ascii=False),
        
        # Sector Report
        "sector_report": json.dumps({
            "sector_name": "银行",
            "sector_trend": "上涨",
            "relative_strength": "强于大盘",
            "analysis_summary": "低估值高股息，具备防御价值。",
            "confidence": 0.8,
            "sentiment_score": 0.75
        }, ensure_ascii=False),
        
        # Technical Report
        "technical_report": json.dumps({
            "trend": "上升趋势",
            "support_levels": ["10.5", "10.0"],
            "resistance_levels": ["11.5", "12.0"],
            "indicators": {"MACD": "金叉", "KDJ": "超买"},
            "analysis_summary": "技术面多头排列，注意短期回调风险。",
            "confidence": 0.75,
            "signal": "买入"
        }, ensure_ascii=False)
    }

    print("🚀 Invoking Strategy Advisor...")
    try:
        result = strategy_node(state)
        
        if "strategy_report" in result:
             print("\n✅ Strategy Report Generated:\n")
             print(result["strategy_report"])
             
             # Try to parse it to check JSON validity
             try:
                 report_json = json.loads(result["strategy_report"])
                 print("\n📊 Parsed JSON Content:")
                 print(f"Final Position: {report_json.get('final_position')}")
                 print(f"Outlook: {report_json.get('market_outlook')}")
                 print(f"Breakdown: {report_json.get('position_breakdown')}")
             except json.JSONDecodeError:
                 print("\n⚠️ Report is not valid JSON")

    except Exception as e:
        print(f"\n❌ Test Failed with Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_strategy_advisor()
