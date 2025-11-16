"""
测试social_media_analyst使用模板系统
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


def test_social_media_analyst_template():
    """测试social_media_analyst模板"""
    print("\n" + "=" * 80)
    print("  测试: social_media_analyst模板")
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
            "tool_names": "get_stock_sentiment_unified"
        }
        
        print(f"\n📊 模板变量:")
        for key, value in variables.items():
            print(f"   - {key}: {value}")
        
        # 获取提示词
        prompt = get_agent_prompt(
            agent_type="analysts",
            agent_name="social_media_analyst",
            variables=variables,
            preference_id="neutral"
        )
        
        print(f"\n✅ 提示词生成成功")
        print(f"   - 长度: {len(prompt)} 字符")
        print(f"   - 包含公司名: {'五粮液' in prompt}")
        print(f"   - 包含股票代码: {'000858.SZ' in prompt}")
        print(f"   - 包含工具名: {'get_stock_sentiment_unified' in prompt}")
        
        # 显示提示词预览
        print(f"\n📝 提示词预览 (前500字符):")
        print("-" * 80)
        print(prompt[:500] + "...")
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
    print("  Social Media Analyst 模板系统测试")
    print("🚀" * 40)
    
    result = test_social_media_analyst_template()
    
    print("\n" + "=" * 80)
    if result:
        print("✅ 测试通过！")
    else:
        print("❌ 测试失败！")
    print("=" * 80)


if __name__ == "__main__":
    main()

