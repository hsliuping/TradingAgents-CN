# 提示词合规修改操作步骤

## 📋 修改流程

### 步骤 1：导出备份（必须！）

在修改之前，**必须先导出所有提示词模板作为备份**：

```bash
python scripts/compliance/export_prompts_before_compliance.py
```

**输出文件**：
- `exports/compliance_backup/prompts_backup_YYYYMMDD_HHMMSS.json` - 完整备份
- `exports/compliance_backup/prompts_backup_grouped_YYYYMMDD_HHMMSS.json` - 按类型分组

**备份内容**：
- 所有相关 Agent 的提示词模板
- 包括 system_prompt、analysis_requirements、output_format 等所有字段

### 步骤 2：预览修改内容

预览修改效果（**不实际修改数据库**）：

```bash
python scripts/compliance/update_prompts_for_compliance.py preview
```

这会显示：
- 修改前后的对比
- 主要术语替换
- 不会实际修改数据库

### 步骤 3：执行数据库模板修改

确认预览无误后，执行实际修改：

```bash
python scripts/compliance/update_prompts_for_compliance.py
```

**修改内容**：
- ✅ 替换所有"目标价" → "价格分析区间"
- ✅ 替换所有"操作建议" → "分析观点"
- ✅ 替换所有"买入/卖出/持有" → "看涨/看跌/中性"
- ✅ 添加免责声明

### 步骤 4：代码修改已完成

代码中的降级提示词已经修改完成：
- ✅ `core/agents/adapters/position/action_advisor_v2.py`
- ✅ `core/agents/adapters/position/action_advisor.py`
- ✅ `core/agents/adapters/trader_v2.py`
- ✅ `core/agents/adapters/research_manager_v2.py`
- ✅ `core/agents/adapters/risk_manager_v2.py`

### 步骤 5：验证修改

1. **检查数据库模板**：
   ```python
   # 在 MongoDB 中查询
   db.prompt_templates.find({
       "agent_name": "pa_advisor_v2"
   })
   ```

2. **测试 Agent 输出**：
   - 运行一个分析任务
   - 检查输出是否使用新的字段名
   - 确认包含免责声明

3. **检查前端显示**：
   - 确认前端能正确解析新字段
   - 确认免责声明正确显示

## 🔄 如果需要恢复备份

如果修改后发现问题，可以使用备份恢复：

```python
import asyncio
import json
from app.core.database import init_database, get_mongo_db, close_database
from bson import ObjectId

async def restore_backup(backup_file):
    """恢复备份"""
    await init_database()
    db = get_mongo_db()
    collection = db.prompt_templates
    
    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    restored_count = 0
    for template in backup_data["templates"]:
        template_id = ObjectId(template["_id"])
        # 移除 _id，使用 update
        template_doc = {k: v for k, v in template.items() if k != "_id"}
        
        await collection.update_one(
            {"_id": template_id},
            {"$set": template_doc}
        )
        restored_count += 1
    
    print(f"✅ 恢复了 {restored_count} 个模板")
    await close_database()

# 使用
# asyncio.run(restore_backup("exports/compliance_backup/prompts_backup_xxx.json"))
```

## 📝 修改检查清单

- [ ] ✅ 已导出备份
- [ ] ✅ 已预览修改内容
- [ ] ✅ 代码中的降级提示词已修改
- [ ] ✅ 数据库模板已更新
- [ ] ✅ 测试验证通过
- [ ] ✅ 前端显示正常

## ⚠️ 注意事项

1. **备份很重要**：修改前必须导出备份
2. **测试验证**：修改后需要测试 Agent 输出
3. **前端兼容**：可能需要更新前端解析逻辑
4. **向后兼容**：考虑是否需要支持旧字段名的兼容处理

## 📚 相关文档

- [详细修改方案](./prompt_compliance_modification_plan.md)
- [代码修改示例](./code_modification_examples.py)
- [修改总结](./compliance_modification_summary.md)
