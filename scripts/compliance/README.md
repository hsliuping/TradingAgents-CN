# 提示词合规修改脚本

## 📋 使用步骤

### 步骤 1：导出备份（重要！）

在修改之前，先导出所有提示词模板作为备份：

```bash
python scripts/compliance/export_prompts_before_compliance.py
```

这会创建：
- `exports/compliance_backup/prompts_backup_YYYYMMDD_HHMMSS.json` - 完整备份
- `exports/compliance_backup/prompts_backup_grouped_YYYYMMDD_HHMMSS.json` - 按类型分组

### 步骤 2：预览修改内容

预览修改效果（不实际修改数据库）：

```bash
python scripts/compliance/update_prompts_for_compliance.py preview
```

### 步骤 3：执行修改

确认无误后，执行实际修改：

```bash
python scripts/compliance/update_prompts_for_compliance.py
```

## 📝 修改内容

### 术语替换

- `目标价` → `价格分析区间`
- `操作建议` → `分析观点`
- `买入/卖出/持有` → `看涨/看跌/中性`
- `止损价位` → `风险控制参考价位`
- `止盈价位` → `收益预期参考价位`

### 字段名替换

- `target_price` → `price_analysis_range`
- `action` → `analysis_view`
- `stop_loss_price` → `risk_reference_price`
- `take_profit_price` → `profit_reference_price`

### 添加免责声明

所有提示词末尾会添加免责声明。

## 🔄 恢复备份

如果需要恢复备份：

```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def restore_backup(backup_file):
    client = AsyncIOMotorClient("your_mongodb_uri")
    db = client["tradingagents"]
    collection = db.prompt_templates
    
    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    for template in backup_data["templates"]:
        # 恢复模板
        await collection.update_one(
            {"_id": template["_id"]},
            {"$set": template},
            upsert=True
        )
    
    print("✅ 恢复完成")

# 使用
# asyncio.run(restore_backup("exports/compliance_backup/prompts_backup_xxx.json"))
```
