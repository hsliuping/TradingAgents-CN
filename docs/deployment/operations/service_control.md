# 🎛️ TradingAgents-CN 服务启动控制指南

## 📋 概述

TradingAgents-CN 系统包含多个后台服务和定时任务，您可以通过配置文件灵活控制哪些服务启动，哪些服务不启动。

## 🔧 配置方式

### 1. 主要配置文件

- **`.env` 文件**: 主要配置文件，优先级最高
- **`app/core/config.py`**: 默认配置，当 `.env` 中没有配置时使用

### 2. 配置生效方式

修改配置后需要重启应用：
```bash
# 停止应用 (Ctrl+C)
# 重新启动
python -m app
```

## 🚀 可控制的服务类型

### 📊 基础服务

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SYNC_STOCK_BASICS_ENABLED` | `true` | 股票基础信息同步 |
| `QUOTES_INGEST_ENABLED` | `true` | 实时行情入库任务 |
| `QUOTES_INGEST_INTERVAL_SECONDS` | `30` | 行情入库间隔（秒） |

### 📈 Tushare 数据服务

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `TUSHARE_UNIFIED_ENABLED` | `true` | Tushare服务总开关 |
| `TUSHARE_BASIC_INFO_SYNC_ENABLED` | `true` | 基础信息同步 |
| `TUSHARE_QUOTES_SYNC_ENABLED` | `true` | 行情同步 |
| `TUSHARE_HISTORICAL_SYNC_ENABLED` | `true` | 历史数据同步 |
| `TUSHARE_FINANCIAL_SYNC_ENABLED` | `true` | 财务数据同步 |
| `TUSHARE_STATUS_CHECK_ENABLED` | `true` | 状态检查 |

### 📊 AKShare 数据服务

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AKSHARE_UNIFIED_ENABLED` | `true` | AKShare服务总开关 |
| `AKSHARE_BASIC_INFO_SYNC_ENABLED` | `true` | 基础信息同步 |
| `AKSHARE_QUOTES_SYNC_ENABLED` | `true` | 行情同步 |
| `AKSHARE_HISTORICAL_SYNC_ENABLED` | `true` | 历史数据同步 |
| `AKSHARE_FINANCIAL_SYNC_ENABLED` | `true` | 财务数据同步 |
| `AKSHARE_STATUS_CHECK_ENABLED` | `true` | 状态检查 |

### 📋 BaoStock 数据服务

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `BAOSTOCK_UNIFIED_ENABLED` | `true` | BaoStock服务总开关 |
| `BAOSTOCK_BASIC_INFO_SYNC_ENABLED` | `true` | 基础信息同步 |
| `BAOSTOCK_QUOTES_SYNC_ENABLED` | `true` | 行情同步 |
| `BAOSTOCK_HISTORICAL_SYNC_ENABLED` | `true` | 历史数据同步 |
| `BAOSTOCK_STATUS_CHECK_ENABLED` | `true` | 状态检查 |

## ⏰ 定时任务配置

### CRON 表达式格式

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── 星期几 (0-7, 0和7都表示周日)
│ │ │ └───── 月份 (1-12)
│ │ └─────── 日期 (1-31)
│ └───────── 小时 (0-23)
└─────────── 分钟 (0-59)
```

### 常用 CRON 示例

| CRON表达式 | 说明 |
|------------|------|
| `0 2 * * *` | 每日凌晨2点 |
| `*/5 9-15 * * 1-5` | 工作日9-15点每5分钟 |
| `0 16 * * 1-5` | 工作日16点 |
| `0 3 * * 0` | 每周日凌晨3点 |
| `0 * * * *` | 每小时整点 |

## 🎯 常见配置场景

### 场景1: 开发环境（最小化服务）

```env
# 只启用基础服务
SYNC_STOCK_BASICS_ENABLED=true
QUOTES_INGEST_ENABLED=false

# 禁用所有数据源同步
TUSHARE_UNIFIED_ENABLED=false
AKSHARE_UNIFIED_ENABLED=false
BAOSTOCK_UNIFIED_ENABLED=false
```

### 场景2: 生产环境（全功能）

```env
# 启用所有服务（默认配置）
SYNC_STOCK_BASICS_ENABLED=true
QUOTES_INGEST_ENABLED=true
TUSHARE_UNIFIED_ENABLED=true
AKSHARE_UNIFIED_ENABLED=true
BAOSTOCK_UNIFIED_ENABLED=true
```

### 场景3: 只使用 Tushare

```env
# 只启用 Tushare 服务
TUSHARE_UNIFIED_ENABLED=true
AKSHARE_UNIFIED_ENABLED=false
BAOSTOCK_UNIFIED_ENABLED=false
```

### 场景4: 禁用频繁任务

```env
# 禁用高频任务，只保留每日任务
QUOTES_INGEST_ENABLED=false
TUSHARE_QUOTES_SYNC_ENABLED=false
AKSHARE_QUOTES_SYNC_ENABLED=false
BAOSTOCK_QUOTES_SYNC_ENABLED=false
```

## 🔍 服务状态监控

### 查看启动日志

启动应用时会显示哪些服务已启用：

```
📅 Stock basics sync scheduled daily at 06:30 (Asia/Shanghai)
⏱ 实时行情入库任务已启动: 每 30s
🔄 配置Tushare统一数据同步任务...
📅 Tushare基础信息同步已配置: 0 2 * * *
📈 Tushare行情同步已配置: */5 9-15 * * 1-5
...
```

### API 健康检查

访问健康检查端点查看服务状态：
```
GET http://localhost:8000/api/health
```

## ⚠️ 注意事项

1. **重启生效**: 修改配置后必须重启应用才能生效
2. **依赖关系**: 某些服务之间有依赖关系，建议保持基础服务启用
3. **资源消耗**: 启用的服务越多，系统资源消耗越大
4. **API限制**: 注意各数据源的API调用限制，避免超限
5. **时区设置**: 确保 `TIMEZONE` 设置正确，影响定时任务执行时间

## 🛠️ 故障排除

### 服务未启动

1. 检查配置项是否正确设置为 `true`
2. 查看启动日志是否有错误信息
3. 确认相关API密钥是否配置正确

### 定时任务未执行

1. 检查CRON表达式格式是否正确
2. 确认时区设置是否正确
3. 查看应用日志中的任务执行记录

### 性能问题

1. 适当调整任务执行频率
2. 禁用不必要的服务
3. 监控系统资源使用情况
