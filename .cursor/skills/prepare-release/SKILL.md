---
name: prepare-release
description: 基于 Git 版本对比分析变更，生成 manifest.json、upgrade_config.json、migrations 的智能建议。在用户说「准备发布」「执行发布准备流程」「发布准备」时使用。
---

# 发布准备

当用户说「准备发布」「执行发布准备流程」「发布准备」时，阅读并遵循 [scripts/prepare_release/SKILL.md](../../scripts/prepare_release/SKILL.md) 中的完整步骤。

## 关键步骤概览

1. 确定上一版本：`python scripts/prepare_release/scripts/get_prev_version.py`
2. 获取变更文件：`python scripts/prepare_release/scripts/git_changed_files.py <prev_ref>`
3. 获取 env_changes：`python scripts/prepare_release/scripts/env_diff_keys.py <prev_ref>`
4. 解析 CHANGELOG 提取 features
5. 分析变更、生成 manifest、upgrade_config、migrations
6. 生成 RELEASE_SUGGESTIONS.md

格式参考：[scripts/prepare_release/reference.md](../../scripts/prepare_release/reference.md)
