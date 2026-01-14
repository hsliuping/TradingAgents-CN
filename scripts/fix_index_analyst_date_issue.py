"""
修复 index_analyst_v2 用户提示词中的日期问题
明确说明要使用 current_date 变量调用工具
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync

def fix_index_analyst_templates():
    """修复 index_analyst_v2 模板中的日期问题"""
    print("=" * 80)
    print("修复 index_analyst_v2 用户提示词中的日期问题")
    print("=" * 80)
    
    db = get_mongo_db_sync()
    collection = db.prompt_templates
    
    # 查找所有 index_analyst_v2 的模板
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "index_analyst_v2"
    }))
    
    if not templates:
        print("❌ 未找到 index_analyst_v2 模板")
        return
    
    print(f"\n找到 {len(templates)} 个模板\n")
    
    # 新的用户提示词模板（明确说明所有参数）
    new_user_prompt = """请进行**客观中立**的大盘分析。

**分析日期**：{current_date}

**请先调用工具获取数据**，建议调用：
- get_china_market_overview: 获取中国市场概览
  - 参数：curr_date='{current_date}'
- get_index_data: 获取指数走势和均线
  - 参数：trade_date='{current_date}', lookback_days=60
- get_market_breadth: 获取市场宽度
  - 参数：trade_date='{current_date}'
- get_north_flow: 获取北向资金流向（仅A股）
  - 参数：trade_date='{current_date}', lookback_days=10
- get_margin_trading: 获取两融余额（仅A股）
  - 参数：trade_date='{current_date}', lookback_days=10
- get_limit_stats: 获取涨跌停统计（仅A股）
  - 参数：trade_date='{current_date}'
- get_index_technical: 获取技术指标（MACD/RSI/KDJ）
  - 参数：trade_date='{current_date}', lookback_days=60
- get_market_environment: 获取市场环境（估值/波动率）
  - 参数：trade_date='{current_date}'
- identify_market_cycle: 识别市场周期
  - 参数：trade_date='{current_date}'

**重要提示**：
- **必须使用上述参数值**：trade_date='{current_date}' 或 curr_date='{current_date}'
- **不要使用其他日期**，必须严格使用上述日期参数
- 所有工具调用必须包含所有必需参数

基于数据撰写分析报告，平衡评估风险与机会。"""
    
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
    from datetime import datetime
    fix_index_analyst_templates()

