"""
检查 index_analyst_v2 模板中的日期问题
查找是否有硬编码的日期示例（如 2024-04-05）
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync
import re

def check_index_analyst_templates():
    """检查 index_analyst_v2 模板中的日期问题"""
    print("=" * 80)
    print("检查 index_analyst_v2 模板中的日期问题")
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
    
    # 匹配日期的正则表达式（YYYY-MM-DD格式）
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    
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
        
        # 检查各个字段中的日期
        fields_to_check = [
            ("system_prompt", content.get("system_prompt", "")),
            ("user_prompt", content.get("user_prompt", "")),
            ("tool_guidance", content.get("tool_guidance", "")),
            ("analysis_requirements", content.get("analysis_requirements", "")),
            ("constraints", content.get("constraints", "")),
        ]
        
        found_dates = []
        for field_name, field_content in fields_to_check:
            if not field_content:
                continue
                
            # 查找所有日期
            dates = re.findall(date_pattern, field_content)
            if dates:
                # 检查是否有2024年的日期（可能是硬编码的示例）
                old_dates = [d for d in dates if d.startswith("2024")]
                if old_dates:
                    found_dates.append((field_name, old_dates))
                    print(f"\n⚠️ 在 {field_name} 中发现2024年日期:")
                    for date in old_dates:
                        # 找到日期在文本中的位置
                        idx = field_content.find(date)
                        context_start = max(0, idx - 50)
                        context_end = min(len(field_content), idx + len(date) + 50)
                        context = field_content[context_start:context_end]
                        print(f"   日期: {date}")
                        print(f"   上下文: ...{context}...")
        
        if not found_dates:
            print("\n✅ 未发现2024年日期")
        else:
            print(f"\n❌ 共发现 {len(found_dates)} 个字段包含2024年日期")
        
        print()

if __name__ == "__main__":
    check_index_analyst_templates()

