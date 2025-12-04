# 紧急回滚和事故处理程序

## 🚨 紧急情况分类

### 1级：严重生产事故
- 系统完全无法使用
- 数据丢失或损坏
- 安全漏洞暴露

### 2级：功能性问题
- 核心功能异常
- 性能严重下降
- 部分用户受影响

### 3级：一般性问题
- 非核心功能异常
- 轻微性能问题
- 少数用户受影响

## 🔄 立即回滚程序

### 步骤1：确认问题严重性
```bash
# 检查当前版本
git log --oneline -5

# 确认最后已知稳定版本
git log --oneline --grep="stable" -10
```

### 步骤2：执行紧急回滚
```bash
# 切换到 main 分支
git checkout main

# 回滚到最后已知稳定版本
git reset --hard <稳定版本SHA>

# 强制推送（需要明确确认风险）
git push origin main --force-with-lease
```

### 步骤3：验证回滚成功
```bash
# 确认当前版本
git rev-parse HEAD

# 检查系统状态
python -c "import tradingagents; print('导入成功')"
```

## 📋 事故处理检查清单

### 立即响应（0-15分钟）
- [ ] 确认事故严重性级别
- [ ] 通知相关人员
- [ ] 记录事故开始时间
- [ ] 评估是否需要立即回滚
- [ ] 执行回滚操作（如需要）
- [ ] 验证回滚成功

### 短期处理（15分钟-2小时）
- [ ] 创建事故分析分支
- [ ] 收集错误日志和信息
- [ ] 分析根本原因
- [ ] 制定修复计划
- [ ] 评估影响范围
- [ ] 更新利益相关者

### 中期修复（2-24小时）
- [ ] 在修复分支中开发解决方案
- [ ] 进行充分测试
- [ ] 准备修复部署计划
- [ ] 代码审查修复方案
- [ ] 准备回滚计划（以防修复失败）

### 长期改进（1-7天）
- [ ] 完成事故后分析报告
- [ ] 识别流程改进点
- [ ] 更新文档和程序
- [ ] 实施预防措施
- [ ] 团队回顾和学习

## 🔧 常用回滚命令

### 查找稳定版本
```bash
# 查看最近的标签版本
git tag --sort=-version:refname | head -10

# 查看包含"stable"的提交
git log --oneline --grep="stable" -20

# 查看发布相关的提交
git log --oneline --grep="release\\|版本" -20
```

### 不同类型的回滚
```bash
# 1. 回滚到特定提交（推荐）
git reset --hard <commit-sha>

# 2. 回滚最近的几个提交
git reset --hard HEAD~<数量>

# 3. 创建反向提交（保留历史）
git revert <commit-sha>

# 4. 回滚到特定标签
git reset --hard <tag-name>
```

### 强制推送选项
```bash
# 推荐：安全的强制推送
git push origin main --force-with-lease

# 谨慎：完全强制推送（可能覆盖他人工作）
git push origin main --force

# 最安全：先备份分支
git push origin main:backup-before-rollback
git push origin main --force-with-lease
```

## 🛡️ 预防措施

### 1. 定期备份
```bash
# 每日备份重要分支
git push origin main:backup-$(date +%Y%m%d)
git push origin develop:backup-develop-$(date +%Y%m%d)
```

### 2. 标记稳定版本
```bash
# 在确认稳定后打标签
git tag -a v0.1.13-stable -m "稳定版本 v0.1.13"
git push origin v0.1.13-stable
```

### 3. 监控和警报
- 设置自动化测试在每次推送后运行
- 配置错误日志监控
- 建立性能监控基线

## 📞 紧急联系流程

### 联系顺序
1. **项目负责人**：立即通知
2. **技术负责人**：协助技术决策
3. **测试负责人**：验证修复方案
4. **运维负责人**：监控系统状态

### 沟通模板
```
【紧急事故通知】
事故级别：[1级/2级/3级]
发生时间：[YYYY-MM-DD HH:mm]
影响范围：[描述]
当前状态：[已回滚/修复中/调查中]
预计恢复：[时间估计]
负责人：[姓名]
```

## 📊 事故报告模板

### 事故概述
- 事故开始时间：
- 事故结束时间：
- 影响持续时间：
- 严重性级别：
- 影响用户数量：

### 时间线
- [时间] 事故发生
- [时间] 事故发现
- [时间] 开始响应
- [时间] 执行回滚
- [时间] 服务恢复
- [时间] 根本原因确认

### 根本原因分析
- 直接原因：
- 根本原因：
- 贡献因素：

### 修复措施
- 立即修复：
- 短期改进：
- 长期预防：

### 经验教训
- 做得好的地方：
- 需要改进的地方：
- 行动计划：

## 🔄 测试环境快速恢复

### 创建测试环境
```bash
# 克隆仓库到测试目录
git clone . ../TradingAgentsCN-test
cd ../TradingAgentsCN-test

# 切换到问题版本进行调试
git checkout <问题版本SHA>

# 安装依赖进行测试
pip install -r requirements.txt
```

### 问题复现和验证
```bash
# 运行相关测试
python -m pytest tests/ -v

# 检查特定功能
python -c "
import sys
sys.path.append('.')
# 测试有问题的功能
"
```

---

**记住：在紧急情况下，稳定性优于完美性。先恢复服务，再慢慢修复问题！**