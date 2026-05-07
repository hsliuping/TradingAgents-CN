---
name: release
description: >
  Use this skill when the user asks to "create a release", "publish a new version",
  "bump version", "make a release", "push a release", "build and deploy",
  "start the release process", "发布新版本", "打包发布", "版本发布",
  or mentions any release-related workflow.
  Also use when the user asks about current version status or what changed since
  the last release.
version: 0.1.0
---

# Release Skill — 交互式发布流程

引导用户完成从版本号更新到 Docker 镜像发布的完整流程。

## 前置条件

- 工作树必须干净（无未提交更改）
- 确认当前在正确的分支上

## 流程

### 1. 查看当前状态

```bash
bash scripts/release/release.sh status
```

展示当前分支、VERSION、各版本线最新 tag、工作树状态。

### 2. 确定发布类型

询问用户发布类型：
- **测试构建**：只增加构建号，tag 格式 `v2.1.0-007`
- **补丁发布**：patch 版本号 +1（如 2.1.0 → 2.1.1），修 Bug 后正式发布
- **小版本发布**：minor 版本号 +1（如 2.1.0 → 2.2.0），新功能发布
- **大版本发布**：major 版本号 +1（如 2.x → 3.0.0），重大变更

### 3. 更新版本号

```bash
# 测试构建（VERSION 文件不变，只显示下一个构建号）
bash scripts/release/release.sh bump build

# 正式发布
bash scripts/release/release.sh bump patch  # 或 minor, major
```

确认版本号变更后，提交 VERSION 文件的修改：
```bash
git add VERSION
git commit -m "chore: bump version to $(cat VERSION)"
```

### 4. 预览变更日志

```bash
bash scripts/release/release.sh changelog
```

展示给用户审核。如需修改，让用户编辑后重新生成。

### 5. 创建 Release 分支（首次发布时）

如果是该版本线的首次正式发布，需要创建 release 分支：
```bash
bash scripts/release/release.sh branch <version-line>
# 例如: bash scripts/release/release.sh branch 2.1
```

### 6. 创建 Tag

```bash
# 测试构建
bash scripts/release/release.sh tag --build

# 正式发布
bash scripts/release/release.sh tag
```

### 7. 推送到远程

```bash
bash scripts/release/release.sh push
```

### 8. 构建 Docker 镜像

```bash
# 单架构构建（开发测试用）
bash scripts/release/release.sh docker-build

# 多架构构建（正式发布用）
bash scripts/release/release.sh docker-build --multiarch
```

### 9. 创建 GitHub Release（正式发布时）

```bash
bash scripts/release/release.sh github-release <tag>
```

### 10. 汇总

打印发布摘要：
- 版本号、Tag、分支
- Docker 镜像标签列表
- GitHub Release URL
- 提醒用户后续步骤：部署到服务器、上传安装包到百度网盘、发布通知

## 判断规则

- 如果当前分支是 `main` 且 VERSION 以 `2.` 开头，提醒用户是否应在 `release/2.x` 分支上发布
- 如果 tag 已存在，不覆盖（精确版本标签不可变）
- 测试构建不需要创建 GitHub Release
- 多架构构建需要更长时间，确认用户是否需要

## 版本线参考

详见 references/version-lines.md
