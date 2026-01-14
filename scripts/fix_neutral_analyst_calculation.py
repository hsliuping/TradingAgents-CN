"""
修复中性评估师的收益计算说明

问题：
- 当目标价 < 当前价时，LLM 错误地计算为正收益
- 提示词中缺少明确的计算公式

修复：
- 在 analysis_requirements 中添加明确的计算公式
- 强调收益率可以为负数
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_mongo_db_sync
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 新的风险收益平衡说明（包含计算公式）
RISK_REWARD_REQUIREMENTS = """⚖️ **风险收益平衡**:
- 客观评估收益潜力（基于数据和逻辑）
- 全面识别风险因素（技术、基本面、市场）
- 风险收益比计算（量化评估）
- 期望收益评估（概率加权）

**📐 计算公式**（必须严格遵守）:
1. **预期收益率** = (目标价 - 当前价) / 当前价 × 100%
   - 如果目标价 > 当前价 → 预期收益为正（如 +15%）
   - 如果目标价 < 当前价 → 预期收益为负（如 -5.2%）
   - 如果目标价 = 当前价 → 预期收益为 0%

2. **潜在风险** = (止损价 - 当前价) / 当前价 × 100%
   - 通常为负数（如 -10%）

3. **风险收益比** = |预期收益| : |潜在风险|
   - 示例：预期收益 +20%，潜在风险 -10% → 风险收益比 2:1
   - 示例：预期收益 -5%，潜在风险 -10% → 不建议买入

4. **期望收益** = 上涨概率 × 预期收益 + 下跌概率 × 潜在风险
   - 示例：55% × (+20%) + 45% × (-10%) = +6.5%"""


def update_neutral_analyst_templates():
    """更新中性评估师的提示词模板"""
    db = get_mongo_db_sync()
    collection = db["prompt_templates"]
    
    logger.info("\n" + "="*80)
    logger.info("更新中性评估师的收益计算说明")
    logger.info("="*80)
    
    # 查找所有中性评估师的模板
    templates = list(collection.find({"agent_name": "neutral_analyst_v2"}))
    logger.info(f"找到 {len(templates)} 个模板")
    
    updated_count = 0
    
    for template in templates:
        template_id = template["_id"]
        template_name = template.get("template_name", "未知")
        preference_type = template.get("preference_type", "unknown")
        
        logger.info(f"\n处理模板: {template_name} (偏好: {preference_type})")
        
        content = template.get("content", {})
        analysis_requirements = content.get("analysis_requirements", "")
        
        # 检查是否已经包含计算公式
        if "📐 计算公式" in analysis_requirements:
            logger.info(f"  ℹ️ 模板已包含计算公式，跳过")
            continue
        
        # 替换风险收益平衡部分
        import re
        pattern = r'⚖️ \*\*风险收益平衡\*\*:[\s\S]*?(?=\n\n📊|\n\n💰|\Z)'
        new_analysis_requirements = re.sub(
            pattern,
            RISK_REWARD_REQUIREMENTS,
            analysis_requirements
        )
        
        if new_analysis_requirements != analysis_requirements:
            # 更新模板
            result = collection.update_one(
                {"_id": template_id},
                {"$set": {
                    "content.analysis_requirements": new_analysis_requirements
                }}
            )
            
            if result.modified_count > 0:
                logger.info(f"  ✅ 模板更新成功")
                updated_count += 1
            else:
                logger.warning(f"  ⚠️ 模板更新失败")
        else:
            logger.info(f"  ℹ️ 模板无需更新")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"更新完成！共更新 {updated_count} 个模板")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    update_neutral_analyst_templates()

