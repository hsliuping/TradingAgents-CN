---
name: prepare-release
description: 基于 Git 版本对比分析变更，生成 manifest.json、upgrade_config.json、migrations 的智能建议。在用户说「准备发布」「执行发布准备流程」「发布准备」时使用。
---

# 发布准备智能体流程

当用户触发「准备发布」「执行发布准备流程」时，按以下步骤执行。

## 输入

- 当前版本：从 `VERSION` 文件读取，或用户指定
- 项目根目录：`scripts/prepare_release/` 的上级目录

## 步骤 1：确定上一版本

运行：
```bash
python scripts/prepare_release/scripts/get_prev_version.py [current_version]
```

- 输出：上一版本号（如 `2.0.1`），若无则输出空、退出码 1
- 若失败：尝试 `git tag -l "v*"` 手动取最近 tag，或询问用户

## 步骤 2：获取变更文件列表

运行：
```bash
python scripts/prepare_release/scripts/git_changed_files.py <prev_ref>
```

`prev_ref` 用 `v{prev}` 或 `{prev}`（如 `v2.0.0` 或 `2.0.0`），若 git 报错则尝试另一种。

可选过滤路径：
```bash
python scripts/prepare_release/scripts/git_changed_files.py <prev_ref> --paths app core migrations
```

- 输出：JSON 数组，变更文件路径列表

## 步骤 3：获取 .env.example 的 env_changes

运行：
```bash
python scripts/prepare_release/scripts/env_diff_keys.py <prev_ref>
```

- 输出：JSON 数组，新增/修改的 KEY 列表

## 步骤 4：解析 CHANGELOG 提取 features

- 查找 `docs/releases/CHANGELOG.md` 或 `CHANGELOG.md`
- 匹配 `## [vX.Y.Z]` 或 `## [vX.Y.Z] - ...` 对应当前版本的段落
- 提取到下一个 `## [` 之间的内容
- 将子标题、列表项转为 `features` 列表（简短描述）

## 步骤 5：分析变更文件

根据变更文件列表：

**可能影响 schema 的路径**：`app/`、`core/` 下 `*models*`、`*schemas*`、含 `create_index`、`insert_one`、`update_many`、`db.` 等

**可能影响配置的路径**：`scripts/template_upgrades/`、`app/services/config_service.py`、`core/config/`、`prompt_templates` 相关

**config_changes**：在变更文件中搜索 `system_configs`、`get_system_config`、`{"key":` 等，提取可能的新 key

## 步骤 6：创建/更新 releases/{version}/

确保目录存在：`releases/{version}/`

**manifest.json**：按 [reference.md](reference.md) 格式写入，包含：
- `version`、`release_date`、`migrations`、`upgrade_config`
- `features`、`config_changes`、`env_changes`（来自步骤 3–5）

**upgrade_config.json**：若不存在则创建，结构见 reference.md。`data` 各集合可为空，需人工填入新增项。

**UPGRADE_SUGGESTIONS.md**：若存在可能影响配置的变更，生成建议文档，包含：
- 列出可能影响配置的变更文件
- 操作指引：导出当前配置、对比上一版本、将新增项填入 upgrade_config.json 的 data
- 引用 `install/README_UPGRADE_CONFIG.md`

## 步骤 7：创建/更新 migrations/v{version}.py

版本号格式：`2.0.2` → `v2_0_2.py`

在文件顶部添加注释块：
```python
# === 变更分析建议 ===
# 以下文件在本版本有变更，请检查是否需要迁移：
#   - path/to/file1.py
#   - path/to/file2.py
# 建议操作：
#   1. 若新增集合：创建索引（参考 migrations/v2_0_0.py）
#   2. 若新增字段：update_many 设置默认值
#   3. 若字段重命名：$rename
```

`upgrade()` 和 `downgrade()` 保留示例或 `pass`，附注释说明需按实际修改。

参考 [migrations/v2_0_0.py](../../migrations/v2_0_0.py) 的索引和操作模式。

## 步骤 8：生成 RELEASE_SUGGESTIONS.md

路径：`releases/{version}/RELEASE_SUGGESTIONS.md`

内容：
- 本版本需人工确认的项
- manifest 中 features / config_changes / env_changes 的审核建议
- upgrade_config 的检查清单（是否有新增模板/配置需填入）
- migrations 的检查清单（是否需补充迁移逻辑）

## 步骤 9：输出清单

向用户汇报：
- 已创建/更新的文件
