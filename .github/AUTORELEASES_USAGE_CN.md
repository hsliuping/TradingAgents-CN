# 发布准备智能体使用说明

这套发布准备工具由 1 个中文自定义 agent 和 3 个中文 prompt 组成，用于帮助你完成版本差异分析、升级包检查、upgrade_config 建议、migration 建议和发布就绪评估。

## 组成

### 1. 自定义 Agent

文件：.github/agents/autoreleases.agent.md

用途：
- 准备发布
- 扫描上一个版本到目标版本的 git 差异
- 检查升级包完整性
- 检查发布归档目录和上传物料是否完整
- 检查 upgrade_config 覆盖情况
- 检查 migration 是否缺失、不完整或有风险
- 输出发布阻塞项、修改建议、验证清单和最终结论
- 额外生成“本次版本相对上一版本的改进说明文档”草稿或最终 Markdown 文件

特点：
- 中文触发词
- TradingAgentsCN 仓库专属规则
- 自动识别当前版本和上一个版本
- 默认只读分析，不会自动改文件
- 只有你明确要求“开始实施”“直接修改”“落地修复”时才进入修改模式

### 2. 中文 Prompt

文件：.github/prompts/prepare-current-release.prompt.md
用途：准备当前版本发布

文件：.github/prompts/check-current-upgrade-package.prompt.md
用途：检查当前升级包是否可发

文件：.github/prompts/generate-upgrade-suggestions.prompt.md
用途：生成 upgrade_config、migration、manifest 和发布修复建议

## 推荐使用方式

### 场景 1：准备当前版本发布

直接在聊天中运行：
/准备当前版本发布

适用场景：
- 你准备开始发版
- 你想先知道当前版本有哪些阻塞项
- 你希望 agent 自动识别当前版本和上一个版本

### 场景 2：检查当前升级包是否可以发布

直接在聊天中运行：
/检查当前升级包是否可发

适用场景：
- 你已经有升级包方案
- 你想检查 build_update_package 和 apply_update 是否一致
- 你想重点看升级安全性、回滚风险和 upgrade_config 覆盖情况

### 场景 3：生成升级建议

直接在聊天中运行：
/生成升级建议

适用场景：
- 你已经完成部分开发
- 你不确定是否要补 migration
- 你不确定 upgrade_config 是否完整
- 你想让 agent 输出需要修改哪些文件

## 推荐工作流

### 第一步：做只读发布准备分析

先用：
/准备当前版本发布

目标：
- 找出阻塞项
- 找出需要修改的发布文件
- 判断是否需要补 upgrade_config 或 migration

### 第二步：专项检查升级包安全性

再用：
/检查当前升级包是否可发

目标：
- 检查升级包包含项是否完整
- 检查更新器替换清单是否一致
- 检查重启流程、回滚风险和升级链路缺口

### 第三步：生成修复建议

如果前两步发现问题，再用：
/生成升级建议

目标：
- 输出 manifest 建议
- 输出 upgrade_config 建议
- 输出 migration 建议
- 输出需要修改的脚本或文档

### 第四步：明确授权后再实施

如果你希望 agent 开始改文件，要明确说：
- 开始实施
- 直接修改这些发布文件
- 帮我生成并写入 upgrade_config
- 帮我落地这些发布改动

如果你没有明确授权，agent 默认只会分析，不会自动改动仓库文件。

## 常见提问方式

### 自动识别版本范围

你可以直接说：
- 为当前版本准备发布
- 检查当前升级包是否可发
- 生成当前版本的升级建议

### 手动指定版本范围

你也可以明确写：
- 为 2.0.0 到 2.0.1 准备发布
- 检查 2.0.0 到 2.0.1 的升级安全性
- 为 2.0.0 到 2.0.1 生成 migration 和 upgrade_config 建议

## 这套工具重点检查什么

在 TradingAgentsCN 仓库中，默认重点检查这些内容：
- VERSION
- BUILD_INFO
- releases/<version>/manifest.json
- releases/<version>/upgrade_config.json
- migrations
- D:/release/<version>/revNNN/ 归档结果（如果已生成）
- scripts/deployment/build_update_package.ps1
- scripts/deployment/archive_release_outputs.ps1
- scripts/windows-installer/build/build_installer.ps1
- scripts/updater/apply_update.ps1
- scripts/installer/start_all.ps1
- scripts/apply_upgrade_config.py
- releases/RELEASE_PROCESS.md

## 打包归档约定

当前约定的正式留档目录是：

- D:/release/<version>/revNNN/

例如：

- D:/release/2.0.1/rev001/
- D:/release/2.0.1/rev002/

每次重新打包，同一版本下都应递增一个新的 revNNN 子版本目录，避免覆盖历史构建。

每个归档目录应至少包含：

- 安装包
- 升级包
- 升级包 sha256 文件
- BUILD_INFO 快照
- manifest 快照
- RELEASE_UPLOAD_INFO.md
- release_metadata.json

其中 RELEASE_UPLOAD_INFO.md 会自动整理网站后台录入所需字段，包括：

- 安装包字节数
- 升级包字节数
- SHA256
- 推荐 download_url
- 可直接复制的 JSON 草稿

如果你让 autoreleases agent 执行完整发版或生成最终物料，它还应额外给出一份版本改进说明文档，推荐命名为：

- `VERSION_IMPROVEMENTS_<version>.md`

推荐放在本次归档目录下，内容用于回答“这次版本比上一版本具体改进了什么”。

## 输出结果怎么看

这套 agent 的输出通常包含：
- 版本范围
- 发现项
- 必需修改的文件
- 升级包一致性
- 发布归档与上传物料
- upgrade_config 覆盖情况
- migration 审查
- 验证清单
- 发布结论
- 版本改进说明文档草稿或最终文档路径

建议你优先看：
1. 阻塞项
2. 必需修改的文件
3. 发布结论
4. 验证清单

## 建议

建议把这套工具当作“发布前审查流程”的第一步，而不是最后一步。

推荐顺序：
1. 先跑只读分析
2. 再确认要不要实施修改
3. 最后做真实打包和回归验证