"""
验证研究员模板中是否包含当前股价信息
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_mongo_db_sync
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def verify_templates():
    """验证模板中是否包含当前股价"""
    db = get_mongo_db_sync()
    collection = db["prompt_templates"]
    
    # 查找所有看多和看空研究员的模板
    agent_names = ["bull_researcher_v2", "bear_researcher_v2"]
    
    print("\n" + "="*80)
    print("验证研究员模板中的当前股价信息")
    print("="*80)
    
    for agent_name in agent_names:
        print(f"\n{'='*80}")
        print(f"检查 {agent_name} 的模板")
        print(f"{'='*80}")
        
        templates = list(collection.find({"agent_name": agent_name}))
        
        for template in templates:
            template_name = template.get("template_name", "未知")
            preference_type = template.get("preference_type", "unknown")
            content = template.get("content", {})
            user_prompt = content.get("user_prompt", "")
            
            print(f"\n📋 模板: {template_name} (偏好: {preference_type})")
            
            # 检查是否包含当前股价
            has_current_price = "{current_price}" in user_prompt
            has_currency_symbol = "{currency_symbol}" in user_prompt
            has_price_section = "📈 当前股价" in user_prompt
            
            print(f"  ✓ 包含 {{current_price}} 变量: {has_current_price}")
            print(f"  ✓ 包含 {{currency_symbol}} 变量: {has_currency_symbol}")
            print(f"  ✓ 包含 '📈 当前股价' 标题: {has_price_section}")
            
            if has_current_price and has_currency_symbol and has_price_section:
                print(f"  ✅ 模板验证通过")
            else:
                print(f"  ❌ 模板验证失败")
                
            # 显示相关片段
            if has_price_section:
                # 找到包含当前股价的行
                lines = user_prompt.split("\n")
                for i, line in enumerate(lines):
                    if "📈 当前股价" in line:
                        print(f"\n  📝 当前股价片段:")
                        # 显示前后各2行
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        for j in range(start, end):
                            prefix = "  >>> " if j == i else "      "
                            print(f"{prefix}{lines[j]}")
                        break
    
    print(f"\n{'='*80}")
    print("验证完成！")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    verify_templates()

