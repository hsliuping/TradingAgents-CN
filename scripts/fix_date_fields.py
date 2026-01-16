"""
修复提示词模板的日期字段类型

将字符串类型的日期字段转换为 datetime 对象
"""

from pymongo import MongoClient
from datetime import datetime


def fix_date_fields():
    """修复日期字段"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔧 修复提示词模板的日期字段类型")
    print("=" * 80)
    
    # 查询所有模板
    templates = list(collection.find({}))
    
    print(f"\n找到 {len(templates)} 个模板")
    
    fixed_count = 0
    
    for template in templates:
        template_id = template.get("_id")
        template_name = template.get("template_name", "未知")
        
        update_fields = {}
        
        # 检查 created_at
        created_at = template.get("created_at")
        if isinstance(created_at, str):
            try:
                # 尝试解析 ISO 格式的日期字符串
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                update_fields["created_at"] = dt
                print(f"📝 {template_name}: 转换 created_at")
            except Exception as e:
                print(f"⚠️ {template_name}: 无法转换 created_at - {e}")
        
        # 检查 updated_at
        updated_at = template.get("updated_at")
        if isinstance(updated_at, str):
            try:
                # 尝试解析 ISO 格式的日期字符串
                dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                update_fields["updated_at"] = dt
                print(f"📝 {template_name}: 转换 updated_at")
            except Exception as e:
                print(f"⚠️ {template_name}: 无法转换 updated_at - {e}")
        
        # 执行更新
        if update_fields:
            result = collection.update_one(
                {"_id": template_id},
                {"$set": update_fields}
            )
            
            if result.modified_count > 0:
                fixed_count += 1
    
    print("\n" + "=" * 80)
    print("✅ 修复完成")
    print("=" * 80)
    print(f"  - 修复了 {fixed_count} 个模板")
    print("=" * 80)


if __name__ == "__main__":
    fix_date_fields()

