"""
修复 sector_analyst_v2 用户提示词中的日期问题
明确说明要使用 current_date 变量调用工具
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync
from datetime import datetime

def fix_sector_analyst_templates():
    """修复 sector_analyst_v2 模板中的日期问题"""
    print("=" * 80)
    print("修复 sector_analyst_v2 用户提示词中的日期问题")
    print("=" * 80)
    
    db = get_mongo_db_sync()
    collection = db.prompt_templates
    
    # 查找所有 sector_analyst_v2 的模板
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "sector_analyst_v2"
    }))
    
    if not templates:
        print("❌ 未找到 sector_analyst_v2 模板")
        return
    
    print(f"\n找到 {len(templates)} 个模板\n")
    
    # 新的用户提示词模板（明确说明所有参数）
    new_user_prompt = """请对 **{company_name}（{ticker}）** 所属行业进行**客观中立**的分析。

**分析日期**：{current_date}
**股票代码**：{ticker}

**请先调用工具获取数据**，建议调用：
- get_china_market_overview: 获取中国市场概览
  - 参数：curr_date='{current_date}'
- get_sector_data: 获取板块基础数据
  - 参数：ticker='{ticker}', trade_date='{current_date}', lookback_days=20
- get_fund_flow_data: 获取板块资金流向
  - 参数：trade_date='{current_date}', top_n=10
- get_peer_comparison: 获取同行业对比（如果需要）
  - 参数：ticker='{ticker}', trade_date='{current_date}'

**重要提示**：
- **必须使用上述参数值**：ticker='{ticker}', trade_date='{current_date}' 或 curr_date='{current_date}'
- **不要使用其他股票代码或日期**，必须严格使用上述参数值
- 所有工具调用必须包含所有必需参数

基于数据撰写分析报告，平衡评估行业机会与风险。"""
    
    updated_count = 0
    
    for template in templates:
        template_id = template.get("_id")
        preference_type = template.get("preference_type", "neutral")
        template_name = template.get("template_name", "N/A")
        content = template.get("content", {})
        
        print(f"{'=' * 80}")
        print(f"模板ID: {template_id}")
        print(f"模板名称: {template_name}")
        print(f"偏好类型: {preference_type}")
        print(f"{'=' * 80}")
        
        # 更新用户提示词
        content["user_prompt"] = new_user_prompt
        
        # 更新数据库
        result = collection.update_one(
            {"_id": template_id},
            {
                "$set": {
                    "content": content,
                    "updated_at": datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"✅ 更新成功")
            updated_count += 1
        else:
            print(f"⚠️ 未修改（可能内容相同）")
        
        print()
    
    print("=" * 80)
    print(f"修复完成！成功更新 {updated_count} 个模板")
    print("=" * 80)

if __name__ == "__main__":
    fix_sector_analyst_templates()

