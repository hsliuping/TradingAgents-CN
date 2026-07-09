# 定时分析功能使用指南

## 📋 功能概述

**定时分析配置** 是 TradingAgents-CN Pro 的专业版功能，允许用户配置多个时间段的自动分析任务，每个时间段可以：
- ✅ 选择不同的自选股分组
- ✅ 配置不同的分析深度
- ✅ 使用不同的 LLM 模型
- ✅ 自定义 CRON 表达式

---

## 🎯 功能特性

### 1. 多时段配置
- 支持配置多个时间段（如开盘前、午盘、收盘后）
- 每个时间段独立配置分析参数
- 可单独启用/禁用某个时间段

### 2. 分组支持
- 每个时间段可选择多个自选股分组
- 支持不同时段分析不同的股票组合
- 自动批量分析分组内的所有股票

### 3. 灵活的参数配置
- **分析深度**: 快速(1) / 基础(2) / 标准(3) / 深度(4) / 全面(5)
- **LLM 模型**: 快速分析模型 + 深度分析模型
- **优先级**: 时间段配置 > 分组配置 > 全局默认配置

### 4. CRON 表达式
- 支持标准 CRON 表达式（5 个字段）
- 提供预览功能，查看下 5 次执行时间
- 自动注册到 APScheduler 调度器

---

## 🚀 使用方法

### 1. 创建定时分析配置

**前端页面**: 设置 → 定时分析配置 → 创建配置

**API 端点**: `POST /api/scheduled-analysis/configs`

**请求示例**:
```json
{
  "name": "我的定时分析",
  "description": "每日三次定时分析",
  "enabled": true,
  "time_slots": [
    {
      "name": "开盘前",
      "cron_expression": "0 9 * * 1-5",
      "enabled": true,
      "group_ids": ["group_tech_id"],
      "analysis_depth": 3,
      "quick_analysis_model": "qwen-turbo",
      "deep_analysis_model": "qwen-plus"
    },
    {
      "name": "午盘",
      "cron_expression": "30 11 * * 1-5",
      "enabled": true,
      "group_ids": ["group_finance_id"],
      "analysis_depth": 2
    },
    {
      "name": "收盘后",
      "cron_expression": "30 15 * * 1-5",
      "enabled": true,
      "group_ids": ["group_tech_id", "group_finance_id"],
      "analysis_depth": 4
    }
  ],
  "default_analysis_depth": 3,
  "default_quick_analysis_model": "qwen-turbo",
  "default_deep_analysis_model": "qwen-plus",
  "notify_on_complete": true,
  "send_email": false
}
```

### 2. CRON 表达式格式

**格式**: `分钟 小时 日 月 星期`

**示例**:
- `0 9 * * 1-5` - 每周一到周五的 9:00
- `30 11 * * 1-5` - 每周一到周五的 11:30
- `30 15 * * 1-5` - 每周一到周五的 15:30
- `0 */2 * * *` - 每 2 小时执行一次
- `0 9,15 * * *` - 每天 9:00 和 15:00

**预览 CRON**:
```bash
POST /api/scheduled-analysis/preview-cron
{
  "cron_expression": "0 9 * * 1-5"
}
```

### 3. 启用/禁用配置

**启用配置**:
```bash
POST /api/scheduled-analysis/configs/{config_id}/enable
```

**禁用配置**:
```bash
POST /api/scheduled-analysis/configs/{config_id}/disable
```

### 4. 查看执行历史

**API 端点**: `GET /api/scheduled-analysis/configs/{config_id}/history`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "history": [
      {
        "id": "history_123",
        "config_id": "config_456",
        "slot_index": 0,
        "slot_name": "开盘前",
        "executed_at": "2026-01-07T09:00:00+08:00",
        "total_stocks": 10,
        "success_count": 9,
        "failed_count": 1,
        "task_ids": ["task_1", "task_2", ...]
      }
    ]
  }
}
```

---

## 🔧 技术实现

### 1. 核心组件

**API 路由**: `app/routers/scheduled_analysis.py`
- 配置管理（CRUD）
- 任务注册/取消注册
- CRON 预览

**执行逻辑**: `app/worker/watchlist_analysis_task.py`
- `run_scheduled_analysis_slot()` - 执行定时分析时间段任务
- `analyze_user_watchlist_batch()` - 批量分析自选股

**调度器**: `app/services/scheduler_service.py`
- APScheduler 集成
- 任务管理和监控

### 2. 数据库集合

**配置集合**: `scheduled_analysis_configs`
```javascript
{
  "_id": ObjectId,
  "user_id": "user_123",
  "name": "我的定时分析",
  "enabled": true,
  "time_slots": [...],
  "last_run_at": ISODate,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**历史记录**: `scheduled_analysis_history`
```javascript
{
  "_id": ObjectId,
  "config_id": "config_456",
  "slot_index": 0,
  "executed_at": ISODate,
  "total_stocks": 10,
  "success_count": 9,
  "failed_count": 1,
  "task_ids": [...]
}
```

---

## 📊 执行流程

```
1. 用户创建定时分析配置
   ↓
2. 配置启用后，自动注册到 APScheduler
   ↓
3. 到达指定时间，触发 run_scheduled_analysis_slot()
   ↓
4. 获取配置和时间段信息
   ↓
5. 遍历时间段指定的分组
   ↓
6. 为每个分组的股票创建批量分析任务
   ↓
7. 并发执行所有分析任务
   ↓
8. 记录执行历史
   ↓
9. 发送完成通知（可选）
```

---

## ✅ 最佳实践

1. **合理设置时间段**
   - 开盘前（9:00）：快速分析，了解市场情绪
   - 午盘（11:30）：基础分析，跟踪盘中变化
   - 收盘后（15:30）：深度分析，总结全天表现

2. **分组策略**
   - 按行业分组（科技、金融、消费等）
   - 按市值分组（大盘、中盘、小盘）
   - 按策略分组（价值、成长、趋势等）

3. **模型选择**
   - 快速分析：使用 `qwen-turbo` 或 `qwen-flash`
   - 深度分析：使用 `qwen-plus` 或 `qwen-max`

4. **避免过度分析**
   - 不要在同一时间段分析过多股票
   - 合理设置分析深度，避免浪费 Token

---

**最后更新**: 2026-01-07  
**功能状态**: ✅ 已实现并可用  
**权限要求**: 🔐 需要 Pro 版授权

