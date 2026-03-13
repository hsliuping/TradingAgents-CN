# 升级配置说明

## 概述

当用户使用**升级安装**（保留配置和数据）时，新版本可能新增模板、配置项等。升级配置机制在首次启动时自动检测版本变化并增量导入这些新项。

## 文件位置

- **版本目录**：`releases/{version}/`，例如 `releases/2.0.1/`
- **升级配置**：`releases/{version}/upgrade_config.json`
- **清单**：`releases/{version}/manifest.json`

## 升级配置文件格式

升级配置文件格式与 `database_export_config` 相同，但**仅包含该版本新增的文档**。已存在的文档会被跳过（增量模式）。

## 版本追踪

- 文件：`runtime/.config_version`
- 内容：上次应用配置的版本号
- 首次安装时由 `start_all.ps1` 写入当前版本
- 升级导入后由 `apply_upgrade_config.py` 更新

## 添加新版本的升级配置

1. 创建 `releases/{version}/` 目录
2. 创建 `releases/{version}/manifest.json`
3. 创建 `releases/{version}/upgrade_config.json`
4. 在 `data` 中仅添加**新增**的文档（新模板、新配置项等）
5. 空数组表示该版本无新增项
6. 确保文档包含唯一键（如 `agent_id`、`preference_type`、`key` 等），以便增量模式正确判断是否已存在

## 相关脚本

- `scripts/apply_upgrade_config.py`：升级配置检测与导入（从 releases/ 读取）
- `scripts/import_config_and_create_user.py`：底层导入逻辑（支持 `--incremental`）
