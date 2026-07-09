# 开发工作流规则 - Development Workflow Rules

## ⚠️ 关键安全规则

### 🔒 Main 分支保护
- **绝对禁止** 直接向 `main` 分支推送未经测试的代码
- **绝对禁止** 未经用户测试确认就合并 PR 到 `main` 分支
- 所有对 `main` 分支的修改必须经过严格的测试流程

### 🚫 禁止操作
1. 直接在 `main` 分支开发功能
2. 未经测试就推送到 `main` 分支
3. 跳过测试流程强制合并 PR
4. 在生产环境部署未经验证的代码

## 📋 强制工作流程

### 1. 功能开发流程
```bash
# 1. 从 main 分支创建功能分支
git checkout main
git pull origin main
git checkout -b feature/功能名称

# 2. 在功能分支中开发
# 开发代码...

# 3. 提交到功能分支
git add .
git commit -m "描述性提交信息"
git push origin feature/功能名称
```

### 2. 测试确认流程
```bash
# 1. 切换到功能分支进行测试
git checkout feature/功能名称

# 2. 运行完整测试套件
python -m pytest tests/
python scripts/syntax_checker.py
# 其他相关测试...

# 3. 用户手动测试确认
# - 功能测试
# - 集成测试
# - 回归测试
```

### 3. 合并到 Main 流程
```bash
# 只有在用户明确确认测试通过后才能执行：

# 1. 切换到 main 分支
git checkout main
git pull origin main

# 2. 合并功能分支（需要用户明确批准）
git merge feature/功能名称

# 3. 推送到远程（需要用户明确批准）
git push origin main

# 4. 清理功能分支
git branch -d feature/功能名称
git push origin --delete feature/功能名称
```

## 🛡️ 技术保护措施

### 1. Git Pre-push 钩子
- 自动阻止直接推送到 `main` 分支
- 位置：`.git/hooks/pre-push`
- 绕过方式：`git push --no-verify`（仅紧急情况使用）

### 2. 建议的 GitHub 分支保护规则
```yaml
分支：main
保护规则：
  - 需要拉取请求审核才能合并
  - 要求状态检查通过才能合并
  - 要求分支在合并前保持最新
  - 包括管理员在内的所有人都需要遵守
  - 允许强制推送：否
  - 允许删除：否
```

## 🚨 紧急情况处理

### 生产事故回滚流程
```bash
# 1. 立即回滚到已知稳定版本
git checkout main
git reset --hard <稳定版本SHA>

# 2. 强制推送（需要明确确认）
git push origin main --force-with-lease

# 3. 创建事故分析分支
git checkout -b hotfix/incident-YYYY-MM-DD

# 4. 分析问题并制定修复方案
# 5. 在修复分支中测试解决方案
# 6. 经过完整测试后合并修复
```

## 📝 操作检查清单

### 合并前检查清单
- [ ] 功能在独立分支中开发完成
- [ ] 通过所有自动化测试
- [ ] 经过用户手动测试确认
- [ ] 代码审查通过
- [ ] 文档已更新
- [ ] 备份计划已制定

### 推送前检查清单
- [ ] 确认目标分支正确
- [ ] 确认推送内容已经过测试
- [ ] 确认有回滚计划
- [ ] 用户已明确批准推送操作

## 🎯 最佳实践

1. **小步快跑**：功能拆分成小的、可测试的单元
2. **持续测试**：每个提交都要经过测试
3. **明确沟通**：所有重要操作都要获得明确确认
4. **文档先行**：重要变更要先更新文档
5. **备份意识**：重要操作前要有回滚计划

## 🔄 版本管理策略

### 分支命名规范
- `main`: 生产稳定版本
- `develop`: 开发集成分支
- `feature/功能名`: 功能开发分支
- `hotfix/问题描述`: 紧急修复分支
- `release/版本号`: 发布准备分支

### 提交信息规范
```
类型(范围): 简短描述

详细描述（可选）

相关问题：#issue号码
```

类型包括：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

---

**记住：安全和稳定性永远是第一优先级！**