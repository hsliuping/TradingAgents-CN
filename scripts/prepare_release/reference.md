# 发布准备格式参考

供智能体流程生成 manifest、upgrade_config、migrations 时参考。

## manifest.json

路径：`releases/{version}/manifest.json`

```json
{
  "version": "2.0.2",
  "release_date": "YYYY-MM-DD",
  "migrations": ["migrations/v2_0_2.py"],
  "upgrade_config": "upgrade_config.json",
  "features": ["功能描述1", "功能描述2"],
  "config_changes": ["New system_config key: xxx", "配置变更描述"],
  "env_changes": ["NEW_ENV_KEY", "ANOTHER_KEY"]
}
```

| 字段 | 说明 |
|------|------|
| version | 版本号，如 2.0.2 |
| release_date | 发布日期 YYYY-MM-DD |
| migrations | 迁移脚本路径列表，如 `["migrations/v2_0_2.py"]` |
| upgrade_config | 同目录下的升级配置文件名 |
| features | 新功能列表，可从 CHANGELOG 解析 |
| config_changes | 配置变更列表（如 system_config 新 key） |
| env_changes | .env 新增/修改的 KEY 列表 |

## upgrade_config.json

路径：`releases/{version}/upgrade_config.json`

格式与 `database_export_config` 相同，**仅包含该版本新增的文档**。已存在的文档会被跳过（增量模式）。

```json
{
  "export_info": {
    "created_at": "YYYY-MM-DDTHH:mm:ss",
    "target_version": "2.0.2",
    "description": "Incremental upgrade config for v2.0.2. Add only NEW items.",
    "collections": [
      "system_configs",
      "prompt_templates",
      "agent_configs",
      "workflow_definitions",
      "tool_configs"
    ],
    "format": "json"
  },
  "data": {
    "system_configs": [],
    "prompt_templates": [],
    "agent_configs": [],
    "workflow_definitions": [],
    "tool_configs": []
  }
}
```

各集合唯一键（增量判断用）：
- `agent_configs`: `agent_id`
- `prompt_templates`: `agent_id`, `preference_type`
- `system_configs`: `key`
- `workflow_definitions`: `id`
- `tool_configs`: `tool_id`

详见 [install/README_UPGRADE_CONFIG.md](../../install/README_UPGRADE_CONFIG.md)。

## migrations/v{version}.py

路径：`migrations/v{version}.py`，版本号如 `2_0_2` 对应 2.0.2。

结构：

```python
"""
v{version} 迁移说明

[变更分析建议注释块]
"""

VERSION = "{version}"
DESCRIPTION = "v{version} migration"


async def upgrade(db):
    # 幂等操作
    pass


async def downgrade(db):
    pass
```

常见操作参考 [migrations/v2_0_0.py](../../migrations/v2_0_0.py)：
- 创建索引：`await db.collection.create_index(...)`
- 添加字段：`update_many({"field": {"$exists": False}}, {"$set": {"field": default}})`
- 插入配置：先 `find_one` 检查是否已存在再 `insert_one`
- 字段重命名：`$rename`
- 删除字段：`$unset`

## CHANGELOG 解析

文件：`docs/releases/CHANGELOG.md` 或 `CHANGELOG.md`

匹配版本段落：`## [vX.Y.Z]` 或 `## [vX.Y.Z] - ...` 到下一个 `## [` 之间的内容。

提取 features：子标题（如 `### 新功能`）下的列表项，或直接段落中的要点。
