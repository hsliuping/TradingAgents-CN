# 定时分析功能 - 完整总结

## 📋 功能概述

定时分析功能允许用户配置多个时间段，在指定时间自动分析自选股分组中的股票。

**版本**: v1.0.1  
**状态**: ✅ 已完整实现并可用  
**权限**: 需要 Pro 版授权  
**分析引擎**: v2.0 统一任务引擎

---

## 🎯 核心功能

### 1. 多时段配置
- ✅ 支持配置多个时间段（开盘前、午盘、收盘后等）
- ✅ 每个时间段独立配置 CRON 表达式
- ✅ 每个时间段可选择不同的分组和参数
- ✅ 可单独启用/禁用某个时间段

### 2. 自选股分组支持
- ✅ 每个时间段可选择多个自选股分组
- ✅ 支持不同时段分析不同的股票组合
- ✅ 自动批量分析分组内的所有股票

### 3. 灵活的参数配置
- ✅ 分析深度：快速(1) / 基础(2) / 标准(3) / 深度(4) / 全面(5)
- ✅ LLM 模型：快速分析模型 + 深度分析模型
- ✅ 优先级：时间段配置 > 分组配置 > 全局默认配置

### 4. CRON 表达式
- ✅ 支持标准 CRON 表达式（5 个字段）
- ✅ 提供预览功能，查看下 5 次执行时间
- ✅ 自动注册到 APScheduler 调度器

### 5. 测试执行功能 (v1.0.1 新增)
- ✅ 立即执行配置，无需等待 CRON 时间
- ✅ 自动验证配置是否正确
- ✅ 快速查看分析效果

### 6. v2.0 引擎 (v1.0.1 升级)
- ✅ 使用与单股分析相同的 v2.0 统一任务引擎
- ✅ 报告格式完全一致
- ✅ 更好的性能和可维护性

---

## 📁 核心文件

### 后端
- `app/routers/scheduled_analysis.py` - API 路由（配置管理、测试执行）
- `app/worker/watchlist_analysis_task.py` - 执行逻辑（v2.0 引擎）
- `app/models/scheduled_analysis.py` - 数据模型
- `app/services/scheduler_service.py` - 调度器服务
- `app/services/task_analysis_service.py` - v2.0 统一任务引擎

### 前端
- `frontend/src/views/Settings/ScheduledAnalysis.vue` - 配置页面
- `frontend/src/api/scheduled-analysis.ts` - API 客户端
- `frontend/src/views/Settings/WatchlistGroups.vue` - 分组管理

### 数据库
- `scheduled_analysis_configs` - 定时分析配置
- `scheduled_analysis_history` - 执行历史
- `unified_analysis_tasks` - 分析任务（v2.0）
- `analysis_reports` - 分析报告（兼容）

---

## 🚀 使用流程

### 第 1 步：创建自选股分组
1. 前往 **设置 → 自选股分组管理**
2. 创建分组并添加股票代码

### 第 2 步：创建定时分析配置
1. 前往 **设置 → 定时分析配置**
2. 点击"创建配置"
3. 添加时间段并配置 CRON 表达式
4. 为每个时间段选择分组和分析参数

### 第 3 步：测试配置（推荐）
1. 点击"测试执行"按钮
2. 验证配置是否正确
3. 查看执行历史和分析报告

### 第 4 步：启用配置
1. 打开"状态"开关
2. 系统自动注册定时任务
3. 到达指定时间自动执行分析

---

## 📊 执行流程

```
1. 到达 CRON 时间
   ↓
2. 触发 run_scheduled_analysis_slot()
   ↓
3. 获取配置和时间段信息
   ↓
4. 遍历时间段指定的分组
   ↓
5. 为每个分组的股票创建 v2.0 任务
   ↓
6. 使用 TaskAnalysisService 并发执行
   ↓
7. 保存到 unified_analysis_tasks 集合
   ↓
8. 记录执行历史
   ↓
9. 发送完成通知（可选）
```

---

## 🆕 v1.0.1 更新内容

### 1. 测试执行功能
- **端点**: `POST /api/scheduled-analysis/configs/{config_id}/test`
- **功能**: 立即执行第一个启用的时间段
- **用途**: 验证配置、调试参数、快速查看效果

### 2. v2.0 引擎升级
- **变更**: 从 v1.x 引擎升级到 v2.0 统一任务引擎
- **优势**: 
  - 报告格式与单股分析完全一致
  - 更好的性能和并发控制
  - 更详细的进度跟踪
  - 更容易维护和扩展

### 3. 代码优化
- **文件**: `app/worker/watchlist_analysis_task.py`
- **变更**: 
  - 使用 `TaskAnalysisService` 创建任务
  - 使用 `task_service.execute_task()` 执行任务
  - 任务存储在 `unified_analysis_tasks` 集合

---

## 📚 文档索引

### 快速开始
- `docs/features/SCHEDULED_ANALYSIS_QUICK_START.md` - 快速开始指南

### 详细文档
- `docs/features/scheduled_analysis_guide.md` - 详细使用指南
- `docs/features/scheduled_analysis_test_feature.md` - 测试执行功能
- `docs/features/scheduled_analysis_v2_engine_upgrade.md` - v2.0 引擎升级说明

### 技术文档
- `app/routers/scheduled_analysis.py` - API 文档
- `app/worker/watchlist_analysis_task.py` - 执行逻辑
- `docs/design/v2.0/stock-analysis-engine-design.md` - v2.0 引擎设计

---

## 🔧 配置示例

### 示例 1: 日内三次分析

```json
{
  "name": "日内三次分析",
  "description": "开盘前、午盘、收盘后各分析一次",
  "enabled": true,
  "time_slots": [
    {
      "name": "开盘前",
      "cron_expression": "0 9 * * 1-5",
      "enabled": true,
      "group_ids": ["重点关注"],
      "analysis_depth": 1,
      "quick_analysis_model": "qwen-turbo",
      "deep_analysis_model": "qwen-plus"
    },
    {
      "name": "午盘",
      "cron_expression": "30 11 * * 1-5",
      "enabled": true,
      "group_ids": ["科技股"],
      "analysis_depth": 2,
      "quick_analysis_model": "qwen-plus",
      "deep_analysis_model": "qwen-plus"
    },
    {
      "name": "收盘后",
      "cron_expression": "30 15 * * 1-5",
      "enabled": true,
      "group_ids": ["所有分组"],
      "analysis_depth": 4,
      "quick_analysis_model": "qwen-plus",
      "deep_analysis_model": "qwen-max"
    }
  ]
}
```

---

## ✅ 测试清单

- [ ] 创建自选股分组
- [ ] 创建定时分析配置
- [ ] 添加多个时间段
- [ ] 配置 CRON 表达式
- [ ] 预览 CRON 执行时间
- [ ] 测试执行配置
- [ ] 查看执行历史
- [ ] 查看分析报告
- [ ] 验证报告格式与单股分析一致
- [ ] 启用/禁用配置
- [ ] 编辑配置
- [ ] 删除配置

---

**最后更新**: 2026-01-07  
**功能版本**: v1.0.1  
**维护者**: TradingAgents-CN Pro Team

