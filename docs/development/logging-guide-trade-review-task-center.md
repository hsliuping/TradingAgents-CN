# 交易复盘任务中心集成 - 日志指南

## 📋 概述

本文档说明交易复盘任务中心集成的日志输出，帮助开发者调试和监控系统运行。

## 🔍 日志标签说明

所有日志都使用统一的标签格式：`[交易复盘服务]` 或 `[交易复盘路由]`

### 日志级别

- `🎯` - 重要流程节点
- `🔧` - 方法调用
- `🔄` - 处理中
- `✅` - 成功
- `❌` - 失败
- `📋` - 详细信息
- `💾` - 数据库/存储操作
- `🚀` - 后台任务启动
- `🎉` - 完成

## 📊 完整日志流程

### 1. 路由层 (app/routers/review.py)

```
📝 [交易复盘路由] 收到复盘请求: code=600519, trade_ids=[...]
🔧 [交易复盘路由] 使用任务中心模式: True
============================================================
🎯 [交易复盘路由] 进入任务中心模式
============================================================
🔄 [交易复盘路由] 获取 UnifiedAnalysisService 实例...
✅ [交易复盘路由] 获取到 UnifiedAnalysisService 实例
🔄 [交易复盘路由] 开始创建任务...
   📋 user_id: 507f1f77bcf86cd799439011
   📋 code: 600519
   📋 trade_ids: [...]
   📋 review_type: single
✅ [交易复盘路由] 任务创建成功
   📋 task_id: 123e4567-e89b-12d3-a456-426614174000
   📋 status: pending
   📋 message: 交易复盘任务已创建，预计需要1-3分钟
   📋 review_id (兼容字段): 123e4567-e89b-12d3-a456-426614174000
🚀 [交易复盘路由] 启动后台任务执行...
   📋 这将在后台异步执行，不阻塞当前请求
✅ [交易复盘路由] 后台任务已启动
   📋 客户端可以通过 /api/v1/analysis/tasks/{task_id} 查询进度
============================================================
```

### 2. 创建任务 (UnifiedAnalysisService.create_trade_review_task)

```
🔧 [交易复盘服务] create_trade_review_task 被调用
   📋 user_id: 507f1f77bcf86cd799439011
   📋 code: 600519
   📋 trade_ids: [...]
   📋 review_type: single
   📋 source: paper
   📋 use_workflow: True
📝 [交易复盘服务] 生成任务ID: 123e4567-e89b-12d3-a456-426614174000
📦 [交易复盘服务] 任务参数: {...}
🔄 [交易复盘服务] 创建 UnifiedAnalysisTask 对象...
✅ [交易复盘服务] UnifiedAnalysisTask 对象创建成功
   📋 task_type: trade_review
   📋 engine_type: workflow
   📋 status: pending
💾 [交易复盘服务] 准备保存到数据库...
✅ [交易复盘服务] 获取数据库连接成功
📦 [交易复盘服务] 任务字典: ['task_id', 'user_id', 'task_type', ...]
✅ [交易复盘服务] 任务已保存到数据库: 123e4567-e89b-12d3-a456-426614174000
💾 [交易复盘服务] 准备保存到内存状态管理器...
✅ [交易复盘服务] 获取内存状态管理器成功
✅ [交易复盘服务] 任务已保存到内存: 123e4567-e89b-12d3-a456-426614174000
🎉 [交易复盘服务] create_trade_review_task 完成
   📋 返回结果: {...}
```

### 3. 执行任务 (UnifiedAnalysisService.execute_trade_review)

```
🚀 [交易复盘服务] execute_trade_review 被调用
   📋 task_id: 123e4567-e89b-12d3-a456-426614174000
   📋 user_id: 507f1f77bcf86cd799439011
   📋 trade_ids: [...]
   📋 code: 600519
   📋 review_type: single
   📋 source: paper
   📋 use_workflow: True
🔄 [交易复盘服务] 更新任务状态为 PROCESSING...
✅ [交易复盘服务] 任务状态已更新为 PROCESSING
🔄 [交易复盘服务] 获取 TradeReviewService 实例...
✅ [交易复盘服务] TradeReviewService 实例获取成功
🔄 [交易复盘服务] 调用 TradeReviewService.create_trade_review()...
   📋 这将使用现有的复盘逻辑（包括工作流引擎）
✅ [交易复盘服务] TradeReviewService.create_trade_review() 执行成功
   📋 review_id: rev_123456
   📋 status: completed
   📋 code: 600519
   📋 name: 贵州茅台
   📋 execution_time: 45.2s
🔄 [交易复盘服务] 格式化结果...
✅ [交易复盘服务] 结果格式化完成
🔄 [交易复盘服务] 更新任务状态为 COMPLETED...
✅ [交易复盘服务] 任务状态已更新为 COMPLETED
🎉 [交易复盘服务] 任务执行成功: 123e4567-e89b-12d3-a456-426614174000
   📋 总耗时: 45.2s
```

### 4. 更新任务状态 (UnifiedAnalysisService._update_trade_review_task_status)

```
🔄 [交易复盘服务] _update_trade_review_task_status 被调用
   📋 task_id: 123e4567-e89b-12d3-a456-426614174000
   📋 status: processing
   📋 message: 正在进行交易复盘...
   📋 has_result: False
   📋 error_message: None
💾 [交易复盘服务] 准备更新数据库...
✅ [交易复盘服务] 获取数据库连接成功
   📋 设置 started_at: 2025-12-31 13:30:00
🔄 [交易复盘服务] 执行数据库更新...
✅ [交易复盘服务] 数据库更新成功
💾 [交易复盘服务] 准备更新内存状态...
✅ [交易复盘服务] 获取内存状态管理器成功
   📋 内存状态: running
🔄 [交易复盘服务] 更新内存状态为 RUNNING...
✅ [交易复盘服务] 内存状态已更新为 RUNNING
🎉 [交易复盘服务] _update_trade_review_task_status 完成
```

## 🐛 错误日志示例

### 任务执行失败

```
❌ [交易复盘服务] 任务执行失败: 123e4567-e89b-12d3-a456-426614174000
   📋 错误类型: ValueError
   📋 错误信息: 无效的交易ID
   📋 详细堆栈:
   Traceback (most recent call last):
     ...
🔄 [交易复盘服务] 更新任务状态为 FAILED...
✅ [交易复盘服务] 任务状态已更新为 FAILED
📋 [交易复盘服务] 返回错误结果: {...}
```

## 🔧 调试技巧

### 1. 查看完整流程

搜索日志中的 task_id：
```bash
grep "123e4567-e89b-12d3-a456-426614174000" logs/tradingagents.log
```

### 2. 查看特定阶段

- 任务创建：`grep "create_trade_review_task" logs/tradingagents.log`
- 任务执行：`grep "execute_trade_review" logs/tradingagents.log`
- 状态更新：`grep "_update_trade_review_task_status" logs/tradingagents.log`

### 3. 查看错误

```bash
grep "❌.*交易复盘" logs/tradingagents.log
```

## 📝 注意事项

1. **日志级别**：确保 `LOG_LEVEL=DEBUG` 以查看所有详细日志
2. **性能影响**：详细日志可能影响性能，生产环境建议使用 `INFO` 级别
3. **敏感信息**：日志中不包含敏感信息（如密码、token等）
4. **日志轮转**：建议配置日志轮转，避免日志文件过大

## 🔗 相关文档

- [交易复盘任务中心集成设计](../design/v2.0/trade-review-task-center-integration.md)
- [统一分析服务架构](../design/v2.0/unified-analysis-service.md)

