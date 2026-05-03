---
name: hotfix
description: >
  Use this skill when the user asks to "create a hotfix", "fix a production bug",
  "emergency fix", "patch a release", "apply fix to other versions",
  "紧急修复", "线上Bug修复", "hotfix",
  or reports a bug that needs to be fixed across multiple version lines.
version: 0.1.0
---

# Hotfix Skill — 交互式紧急修复流程

引导用户完成从创建 hotfix 分支到 cherry-pick 多版本的完整流程。

## 流程

### 1. 确认受影响的版本线

询问用户 Bug 影响哪些版本线（可多选）：
- 2.0.x
- 2.1.x
- 3.0.x

### 2. 创建 Hotfix 分支

从最低受影响版本的最新 tag 创建 hotfix 分支：

```bash
bash scripts/release/hotfix.sh start <version-line> <issue-name>
# 例如: bash scripts/release/hotfix.sh start 2.1 null-pointer-fix
```

### 3. 等待用户修复

提醒用户在 hotfix 分支上进行修复。修复完成后告知继续。

### 4. 确认 Cherry-pick 目标

根据 Cherry-pick 矩阵（见 references/cherry-pick-matrix.md）建议同步目标：

- Bug 在 2.0.x → 仅 release/2.0.x
- Bug 在 2.1.x → release/2.1.x + main
- Bug 在 3.0.x → main
- Bug 在 main → release/2.1.x + release/2.0.x（按需）

询问用户确认或调整。

### 5. 完成 Hotfix

```bash
bash scripts/release/hotfix.sh finish
```

这会自动完成：版本 bump、打 tag、cherry-pick、推送、清理分支。

如果不想自动推送，加 `--no-push`：
```bash
bash scripts/release/hotfix.sh finish --no-push
```

### 6. 后续步骤

提醒用户：
- 为所有受影响版本构建 Docker 镜像
- 部署到服务器
- 发布通知

## 注意事项

- Hotfix 分支是短生命周期的，完成后自动删除
- Cherry-pick 可能遇到冲突，此时脚本会停止并提示手动解决
- 补丁版本（如 2.1.0 → 2.1.1）不应包含数据库结构变更
