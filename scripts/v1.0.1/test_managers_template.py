"""
测试managers使用模板系统
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


def test_manager_template(agent_name):
    """测试manager模板"""
    print("\n" + "=" * 80)
    print(f"  测试: {agent_name}模板")
    print("=" * 80)
    
    try:
        # 准备模板变量
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
        
        # 获取提示词
        prompt = get_agent_prompt(
            agent_type="managers",
            agent_name=agent_name,
            variables=variables,
            preference_id="neutral"
        )
        
        print(f"\n✅ 提示词生成成功")
        print(f"   - 长度: {len(prompt)} 字符")
        print(f"   - 包含公司名: {'五粮液' in prompt}")
        print(f"   - 包含股票代码: {'000858.SZ' in prompt}")
        
        # 显示提示词预览
        print(f"\n📝 提示词预览 (前400字符):")
        print("-" * 80)
        print(prompt[:400] + "...")
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行测试"""
    print("\n" + "🚀" * 40)
    print("  Managers 模板系统测试")
    print("🚀" * 40)
    
    results = {}
    for agent_name in ["research_manager", "risk_manager"]:
        results[agent_name] = test_manager_template(agent_name)
    
    print("\n" + "=" * 80)
    print("测试结果汇总:")
    for agent_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {agent_name}: {status}")
    print("=" * 80)


if __name__ == "__main__":
    main()

