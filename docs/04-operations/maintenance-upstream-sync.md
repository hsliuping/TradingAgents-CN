# 上游同步策略

## 概述

本文档详细说明如何保持 TradingAgents-CN 与原项目 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 的同步。

## 🎯 同步目标

### 主要目标
- **保持技术先进性**: 及时获得原项目的新功能和改进
- **修复安全问题**: 快速同步安全补丁和Bug修复
- **维护兼容性**: 确保中文增强功能与原项目兼容
- **减少维护成本**: 避免重复开发已有功能

### 平衡原则
- **核心功能同步**: 同步所有核心功能更新
- **文档保持独立**: 保持我们的中文文档体系
- **增强功能保护**: 保护我们的中文增强功能
- **冲突优雅处理**: 妥善处理合并冲突

## 🔄 同步策略

### 1. 监控策略

#### 自动监控
```bash
# 设置GitHub通知
# 1. 访问 https://github.com/TauricResearch/TradingAgents
# 2. 点击 "Watch" -> "Custom" -> 选择 "Releases" 和 "Issues"
# 3. 启用邮件通知
```

#### 定期检查
- **每周检查**: 检查是否有新的提交和发布
- **每月深度同步**: 进行完整的同步和测试
- **重要更新立即同步**: 安全补丁和重大Bug修复

### 2. 分支策略

```
main (我们的主分支)
├── upstream-sync-YYYYMMDD (同步分支)
├── feature/chinese-enhancement (中文增强功能)
└── hotfix/urgent-fixes (紧急修复)

upstream/main (原项目主分支)
```

#### 分支说明
- **main**: 我们的稳定主分支，包含所有中文增强
- **upstream-sync-YYYYMMDD**: 临时同步分支，用于合并上游更新
- **feature/chinese-enhancement**: 我们的功能增强分支
- **hotfix/urgent-fixes**: 紧急修复分支

### 3. 同步流程

#### 标准同步流程

```bash
# 1. 检查当前状态
git status
git log --oneline -5

# 2. 获取上游更新
git fetch upstream

# 3. 检查新提交
git log --oneline HEAD..upstream/main

# 4. 使用自动化脚本同步
python scripts/sync_upstream.py

# 5. 解决冲突（如果有）
# 手动编辑冲突文件
git add <resolved_files>
git commit

# 6. 测试同步结果
python -m pytest tests/
python examples/basic_example.py

# 7. 推送更新
git push origin main
```

#### 使用自动化脚本

```bash
# 基本同步
python scripts/sync_upstream.py

# 使用rebase策略
python scripts/sync_upstream.py --strategy rebase

# 自动模式（不询问确认）
python scripts/sync_upstream.py --auto
```

## ⚠️ 冲突处理策略

### 常见冲突类型

#### 1. 文档冲突
**原因**: 我们有完整的中文文档，原项目可能更新英文文档

**处理策略**:
```bash
# 保持我们的中文文档，参考原项目更新内容
# 冲突文件: README.md, docs/
# 解决方案: 保留我们的版本，手动同步有价值的内容
```

#### 2. 配置文件冲突
**原因**: 配置文件格式或默认值变更

**处理策略**:
```bash
# 仔细比较差异，合并有价值的配置
git diff HEAD upstream/main -- config/
# 手动合并配置更改
```

#### 3. 代码功能冲突
**原因**: 核心代码逻辑变更

**处理策略**:
```bash
# 优先采用上游版本，然后重新应用我们的增强
# 1. 接受上游版本
git checkout --theirs <conflicted_file>
# 2. 重新应用我们的增强功能
# 3. 测试确保功能正常
```

### 冲突解决优先级

1. **安全修复**: 最高优先级，立即采用上游版本
2. **Bug修复**: 高优先级，通常采用上游版本
3. **新功能**: 中等优先级，评估后决定是否采用
4. **文档更新**: 低优先级，保持我们的中文版本
5. **配置变更**: 低优先级，谨慎合并

## 📋 同步检查清单

### 同步前检查
- [ ] 当前分支是否干净（无未提交更改）
- [ ] 是否有正在进行的功能开发
- [ ] 是否有未解决的Issue需要考虑
- [ ] 备份当前状态（创建标签）

### 同步过程检查
- [ ] 上游更新是否获取成功
- [ ] 新提交是否包含重大变更
- [ ] 是否存在合并冲突
- [ ] 冲突是否正确解决

### 同步后检查
- [ ] 代码是否能正常运行
- [ ] 测试是否全部通过
- [ ] 文档是否需要更新
- [ ] 中文增强功能是否正常
- [ ] 配置文件是否正确

## 🧪 测试策略

### 自动化测试
```bash
# 运行完整测试套件
python -m pytest tests/ -v

# 运行基本功能测试
python examples/basic_example.py

# 运行性能测试
python tests/performance_test.py
```

### 手动测试
```bash
# 测试核心功能
python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
state, decision = ta.propagate('AAPL', '2024-01-15')
print(f'Decision: {decision}')
"

# 测试中文文档
# 检查 docs/ 目录下的文档是否正常显示
```

## 📊 同步记录

### 同步日志格式
```json
{
  "sync_time": "2024-01-15T10:30:00Z",
  "upstream_commits": 5,
  "conflicts_resolved": 2,
  "files_changed": ["tradingagents/core.py", "config/default.yaml"],
  "tests_passed": true,
  "notes": "同步了新的风险管理功能"
}
```

### 版本标记策略
```bash
# 同步前创建标签
git tag -a v1.0.0-cn-pre-sync -m "同步前状态"

# 同步后创建标签
git tag -a v1.0.1-cn -m "同步上游更新 v1.2.3"

# 推送标签
git push origin --tags
```

## 🚨 应急处理

### 同步失败回滚
```bash
# 回滚到同步前状态
git reset --hard v1.0.0-cn-pre-sync

# 或者回滚到上一个提交
git reset --hard HEAD~1

# 强制推送（谨慎使用）
git push origin main --force-with-lease
```

### 紧急热修复
```bash
# 创建热修复分支
git checkout -b hotfix/urgent-fix

# 应用修复
# ... 修复代码 ...

# 快速合并
git checkout main
git merge hotfix/urgent-fix
git push origin main

# 删除热修复分支
git branch -d hotfix/urgent-fix
```

## 📅 同步计划

### 定期同步计划
- **每周一**: 检查上游更新，评估同步需求
- **每月第一周**: 进行完整同步和测试
- **重大版本发布后**: 立即评估和同步

### 特殊情况处理
- **安全漏洞**: 24小时内同步
- **重大Bug**: 48小时内同步
- **新功能**: 1周内评估，2周内同步

## 🤝 社区协作

### 与原项目互动
- **Issue报告**: 向原项目报告发现的Bug
- **功能建议**: 提出有价值的功能建议
- **代码贡献**: 将通用改进贡献回原项目

### 维护透明度
- **同步日志**: 公开同步记录和决策过程
- **变更说明**: 详细说明每次同步的内容
- **用户通知**: 及时通知用户重要更新

通过这套完整的同步策略，我们可以确保 TradingAgents-CN 始终保持与原项目的技术同步，同时维护我们独特的中文增强价值。
