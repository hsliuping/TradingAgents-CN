"""
端到端测试：验证所有13个Agent都能正确使用模板系统
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.template_client import get_agent_prompt
from tradingagents.utils.logging_init import get_logger

logger = get_logger("test")

# 所有13个Agent的配置
AGENTS_CONFIG = [
    # Analysts (4)
    ("analysts", "fundamentals_analyst", "neutral"),
    ("analysts", "market_analyst", "neutral"),
    ("analysts", "news_analyst", "neutral"),
    ("analysts", "social_media_analyst", "neutral"),
    # Researchers (2)
    ("researchers", "bull_researcher", "neutral"),
    ("researchers", "bear_researcher", "neutral"),
    # Debators (3)
    ("debators", "aggressive_debator", "aggressive"),
    ("debators", "conservative_debator", "conservative"),
    ("debators", "neutral_debator", "neutral"),
    # Managers (2)
    ("managers", "research_manager", "neutral"),
    ("managers", "risk_manager", "neutral"),
    # Trader (1)
    ("trader", "trader", "neutral"),
]


def test_agent_template(agent_type, agent_name, preference_id):
    """测试单个Agent的模板"""
    try:
        variables = {
            "ticker": "000858.SZ",
            "company_name": "五粮液",
            "market_name": "A股",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": ""
        }
        
        prompt = get_agent_prompt(
            agent_type=agent_type,
            agent_name=agent_name,
            variables=variables,
            preference_id=preference_id
        )
        
        return True, len(prompt)
    except Exception as e:
        return False, str(e)


def main():
    """运行所有Agent的模板测试"""
    print("\n" + "🚀" * 40)
    print("  所有Agent模板系统端到端测试")
    print("🚀" * 40)
    
    results = {}
    total_length = 0
    
    for agent_type, agent_name, preference_id in AGENTS_CONFIG:
        success, result = test_agent_template(agent_type, agent_name, preference_id)
        
        if success:
            results[f"{agent_type}/{agent_name}"] = ("✅", result)
            total_length += result
            print(f"✅ {agent_type:12} / {agent_name:25} ({result:4} 字符)")
        else:
            results[f"{agent_type}/{agent_name}"] = ("❌", result)
            print(f"❌ {agent_type:12} / {agent_name:25} 失败: {result}")
    
    # 统计
    print("\n" + "=" * 80)
    passed = sum(1 for status, _ in results.values() if status == "✅")
    total = len(results)
    
    print(f"测试结果: {passed}/{total} 通过")
    print(f"总提示词长度: {total_length} 字符")
    print(f"平均提示词长度: {total_length // total} 字符")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 所有Agent模板系统集成测试通过！")
        return 0
    else:
        print(f"\n❌ 有 {total - passed} 个Agent测试失败")
        return 1


if __name__ == "__main__":
    exit(main())

