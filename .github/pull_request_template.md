# Pull Request

> 提交前请阅读 [CONTRIBUTING.md](../CONTRIBUTING.md) —— 我们不看简历、不面试，**PR 是考察贡献者的唯一方式**。好的 PR = 解决真问题 + 说明修改原因 + 响应 review 意见。

## PR 类型

标题遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)（如 `fix: 修复xxx` / `feat: 新增xxx`）。

- [ ] 🐛 Bug 修复 (fix)
- [ ] 🌟 新功能 (feat)
- [ ] 📝 文档 (docs)
- [ ] 🧹 重构 (refactor)
- [ ] ⚡ 性能优化 (perf)
- [ ] 🧪 测试 (test)
- [ ] 🔧 构建/配置 (chore)

## 变更摘要

<!-- 一段话说清楚：为什么改（解决什么问题）、改了什么 -->

## 相关 Issue

<!-- 如果此 PR 解决了某个 Issue，请链接：Fixes #123 -->

## 测试验证

<!-- 描述如何验证本 PR。参考：后端改动 python -m py_compile + import app.main；前端改动 npx vue-tsc --noEmit + npm run build -->

1. 
2. 
3. 

## 合规红线确认

本项目定位为研究辅助工具，请逐项确认：

- [ ] 不引入目标价、止损止盈、买卖时机等交易指令类功能
- [ ] 不移除或弱化"不构成投资建议"等合规声明
- [ ] 不抓取需登录/付费的数据源，不绕过平台反爬限制
- [ ] 无硬编码密钥或敏感信息

## 破坏性变更

- [ ] 无
- [ ] 有（请说明影响与迁移方式）

## 截图/演示

<!-- 涉及 UI 变更时请提供截图或演示 -->
