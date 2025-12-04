# 定时任务管理系统

## 📋 概述

TradingAgents-CN 使用 APScheduler 作为定时任务调度器，提供了完整的定时任务管理功能，包括：

- ✅ 查看所有定时任务
- ✅ 查看任务详情
- ✅ 暂停/恢复任务
- ✅ 手动触发任务
- ✅ 查看任务执行历史
- ✅ 查看调度器统计信息

## 🔧 系统架构

### 核心组件

1. **APScheduler** - 定时任务调度器
   - 使用 `AsyncIOScheduler` 异步调度器
   - 支持 Cron 表达式和间隔触发
   - 在主应用进程中运行

2. **SchedulerService** - 定时任务管理服务
   - 提供任务查询、暂停、恢复、触发等功能
   - 记录任务执行历史到 MongoDB
   - 提供统计信息和健康检查

3. **Scheduler Router** - 定时任务管理 API
   - RESTful API 接口
   - 需要管理员权限（暂停/恢复/触发操作）
   - 支持分页查询

## 📊 当前定时任务列表

### 1. 股票基础信息同步
- **任务ID**: 无（未设置ID）
- **函数**: `BasicsSync Service.run_full_sync`
- **触发器**: Cron 表达式（可配置）
- **默认时间**: 每天 06:30

### 2. 实时行情入库
- **任务ID**: 无（未设置ID）
- **函数**: `QuotesIngestionService.run_once`
- **触发器**: 间隔触发
- **默认间隔**: 每 60 秒

### 3. Tushare 数据同步任务

#### 3.1 基础信息同步
- **任务ID**: `tushare_basic_info_sync`
- **函数**: `run_tushare_basic_info_sync`
- **触发器**: `0 2 * * *` (每天凌晨2点)

#### 3.2 行情同步
- **任务ID**: `tushare_quotes_sync`
- **函数**: `run_tushare_quotes_sync`
- **触发器**: `*/5 9-15 * * 1-5` (交易日 9:00-15:00，每5分钟)

#### 3.3 历史数据同步
- **任务ID**: `tushare_historical_sync`
- **函数**: `run_tushare_historical_sync`
- **触发器**: `0 18 * * 1-5` (交易日 18:00)

#### 3.4 财务数据同步
- **任务ID**: `tushare_financial_sync`
- **函数**: `run_tushare_financial_sync`
- **触发器**: `0 3 * * 0` (每周日凌晨3点)

#### 3.5 新闻数据同步
- **任务ID**: `tushare_news_sync`
- **函数**: `run_tushare_news_sync`
- **触发器**: `0 */2 * * *` (每2小时)

#### 3.6 状态检查
- **任务ID**: `tushare_status_check`
- **函数**: `run_tushare_status_check`
- **触发器**: `*/30 * * * *` (每30分钟)

### 4. AKShare 数据同步任务

#### 4.1 基础信息同步
- **任务ID**: `akshare_basic_info_sync`
- **函数**: `run_akshare_basic_info_sync`
- **触发器**: `0 2 * * *` (每天凌晨2点)

#### 4.2 行情同步
- **任务ID**: `akshare_quotes_sync`
- **函数**: `run_akshare_quotes_sync`
- **触发器**: `*/5 9-15 * * 1-5` (交易日 9:00-15:00，每5分钟)

#### 4.3 历史数据同步
- **任务ID**: `akshare_historical_sync`
- **函数**: `run_akshare_historical_sync`
- **触发器**: `0 18 * * 1-5` (交易日 18:00)

#### 4.4 财务数据同步
- **任务ID**: `akshare_financial_sync`
- **函数**: `run_akshare_financial_sync`
- **触发器**: `0 3 * * 0` (每周日凌晨3点)

#### 4.5 新闻数据同步
- **任务ID**: `akshare_news_sync`
- **函数**: `run_akshare_news_sync`
- **触发器**: `0 */2 * * *` (每2小时)

#### 4.6 状态检查
- **任务ID**: `akshare_status_check`
- **函数**: `run_akshare_status_check`
- **触发器**: `*/30 * * * *` (每30分钟)

### 5. BaoStock 数据同步任务

#### 5.1 基础信息同步
- **任务ID**: `baostock_basic_info_sync`
- **函数**: `run_baostock_basic_info_sync`
- **触发器**: `0 2 * * *` (每天凌晨2点)

#### 5.2 历史数据同步
- **任务ID**: `baostock_historical_sync`
- **函数**: `run_baostock_historical_sync`
- **触发器**: `0 18 * * 1-5` (交易日 18:00)

#### 5.3 状态检查
- **任务ID**: `baostock_status_check`
- **函数**: `run_baostock_status_check`
- **触发器**: `*/30 * * * *` (每30分钟)

## 🔌 API 接口

### 1. 获取任务列表
```http
GET /api/scheduler/jobs
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": "tushare_basic_info_sync",
      "name": "tushare_basic_info_sync",
      "next_run_time": "2025-10-09T02:00:00",
      "paused": false,
      "trigger": "cron[day='*', hour='2', minute='0']"
    }
  ],
  "message": "获取到 15 个定时任务"
}
```

### 2. 获取任务详情
```http
GET /api/scheduler/jobs/{job_id}
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "tushare_basic_info_sync",
    "name": "tushare_basic_info_sync",
    "func": "app.worker.tushare_sync_service.run_tushare_basic_info_sync",
    "kwargs": {"force_update": false},
    "next_run_time": "2025-10-09T02:00:00",
    "paused": false,
    "trigger": "cron[day='*', hour='2', minute='0']"
  },
  "message": "获取任务详情成功"
}
```

### 3. 暂停任务
```http
POST /api/scheduler/jobs/{job_id}/pause
Authorization: Bearer {token}
```

**权限要求**: 管理员

### 4. 恢复任务
```http
POST /api/scheduler/jobs/{job_id}/resume
Authorization: Bearer {token}
```

**权限要求**: 管理员

### 5. 手动触发任务
```http
POST /api/scheduler/jobs/{job_id}/trigger
Authorization: Bearer {token}
```

**权限要求**: 管理员

### 6. 获取任务执行历史
```http
GET /api/scheduler/jobs/{job_id}/history?limit=20&offset=0
Authorization: Bearer {token}
```

### 7. 获取所有执行历史
```http
GET /api/scheduler/history?limit=50&offset=0&job_id={job_id}&status={status}
Authorization: Bearer {token}
```

**查询参数**:
- `limit`: 返回数量限制 (1-200)
- `offset`: 偏移量
- `job_id`: 任务ID过滤（可选）
- `status`: 状态过滤 (success/failed)（可选）

### 8. 获取统计信息
```http
GET /api/scheduler/stats
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total_jobs": 15,
    "running_jobs": 14,
    "paused_jobs": 1,
    "scheduler_running": true,
    "scheduler_state": 1
  },
  "message": "获取统计信息成功"
}
```

### 9. 健康检查
```http
GET /api/scheduler/health
Authorization: Bearer {token}
```

## 📝 数据库集合

### scheduler_history
存储任务执行历史和操作记录

**字段**:
- `job_id`: 任务ID
- `action`: 操作类型 (pause/resume/trigger/execute)
- `status`: 状态 (success/failed)
- `error_message`: 错误信息（如果有）
- `timestamp`: 时间戳

**索引**:
```javascript
db.scheduler_history.createIndex({"job_id": 1, "timestamp": -1})
db.scheduler_history.createIndex({"timestamp": -1})
db.scheduler_history.createIndex({"status": 1})
```

## 🧪 测试

运行测试脚本：
```bash
python scripts/test_scheduler_management.py
```

测试内容：
1. ✅ 获取任务列表
2. ✅ 获取任务详情
3. ✅ 暂停任务
4. ✅ 恢复任务
5. ✅ 手动触发任务（可选）
6. ✅ 获取统计信息
7. ✅ 获取执行历史

## 🔒 权限控制

- **查看任务**: 所有登录用户
- **暂停/恢复/触发任务**: 仅管理员

## 📌 注意事项

1. **暂停任务不会停止正在执行的任务**，只会阻止下次调度
2. **手动触发任务会立即执行**，请谨慎使用
3. **执行历史记录会持久化到 MongoDB**，建议定期清理旧记录
4. **调度器在主应用进程中运行**，重启应用会重置所有任务状态

## 🚀 未来改进

- [ ] 添加任务执行结果通知
- [ ] 支持动态添加/删除任务
- [ ] 支持修改任务的 Cron 表达式
- [ ] 添加任务执行超时控制
- [ ] 添加任务执行失败重试机制
- [ ] 添加任务执行日志查看
- [ ] 添加任务执行性能监控

