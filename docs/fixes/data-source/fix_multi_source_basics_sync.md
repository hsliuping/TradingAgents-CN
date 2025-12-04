# 修复：股票基础信息同步支持多数据源自动切换

## 📋 问题描述

### 用户反馈

用户在 `.env` 文件中配置了 `TUSHARE_ENABLED=false`，但系统仍然尝试连接 Tushare 并等待 5 秒后超时，而不是立即切换到其他可用的数据源（AKShare/BaoStock）。

**错误日志**：
```
2025-10-17 09:25:32 | app.services.basics_sync_service | ERROR    | ❌ Tushare 数据源已禁用 (TUSHARE_ENABLED=false)
💡 股票基础信息同步需要 Tushare 数据源
📋 解决方案：
   1. 在 .env 文件中设置 TUSHARE_ENABLED=true
   2. 配置有效的 TUSHARE_TOKEN
   3. 或者使用其他数据源的同步任务（AKShare/BaoStock）
```

### 根本原因

系统使用的是 `BasicsSync Service` (`app/services/basics_sync_service.py`)，该服务**只支持 Tushare 数据源**，没有实现多数据源自动切换逻辑。

当 `TUSHARE_ENABLED=false` 时，服务直接报错退出，而不是自动切换到其他可用的数据源。

---

## 🎯 解决方案

### 方案选择

项目中已经存在两套股票基础信息同步服务：

1. **`BasicsSync Service`** (`app/services/basics_sync_service.py`)
   - ❌ 只支持 Tushare 数据源
   - ❌ 没有自动切换逻辑
   - ✅ 代码简单，性能较好

2. **`MultiSourceBasicsSync Service`** (`app/services/multi_source_basics_sync_service.py`)
   - ✅ 支持多数据源自动切换
   - ✅ 优先级：Tushare > AKShare > BaoStock
   - ✅ 详细的数据源使用统计
   - ✅ 支持 `preferred_sources` 参数

**选择方案 2**：切换到 `MultiSourceBasicsSync Service`，因为它已经实现了完整的多数据源自动切换逻辑。

---

## 🔧 代码修改

### 1. 修改 `app/main.py` - 切换到多数据源服务

**修改位置**：第 181-223 行

**修改内容**：

```python
# 使用多数据源同步服务（支持自动切换）
multi_source_service = MultiSourceBasicsSyncService()

# 根据 TUSHARE_ENABLED 配置决定优先数据源
# 如果 Tushare 被禁用，系统会自动使用其他可用数据源（AKShare/BaoStock）
preferred_sources = None  # None 表示使用默认优先级顺序

if settings.TUSHARE_ENABLED:
    # Tushare 启用时，优先使用 Tushare
    preferred_sources = ["tushare", "akshare", "baostock"]
    logger.info("📊 股票基础信息同步优先数据源: Tushare > AKShare > BaoStock")
else:
    # Tushare 禁用时，使用 AKShare 和 BaoStock
    preferred_sources = ["akshare", "baostock"]
    logger.info("📊 股票基础信息同步优先数据源: AKShare > BaoStock (Tushare已禁用)")

# 立即在启动后尝试一次（不阻塞）
async def run_sync_with_sources():
    await multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources)

asyncio.create_task(run_sync_with_sources())

# 配置调度任务
if settings.SYNC_STOCK_BASICS_ENABLED:
    if settings.SYNC_STOCK_BASICS_CRON:
        scheduler.add_job(
            lambda: multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources),
            CronTrigger.from_crontab(settings.SYNC_STOCK_BASICS_CRON, timezone=settings.TIMEZONE),
            id="basics_sync_service"
        )
    else:
        hh, mm = (settings.SYNC_STOCK_BASICS_TIME or "06:30").split(":")
        scheduler.add_job(
            lambda: multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources),
            CronTrigger(hour=int(hh), minute=int(mm), timezone=settings.TIMEZONE),
            id="basics_sync_service"
        )
```

**关键改动**：
1. ✅ 导入 `MultiSourceBasicsSyncService`
2. ✅ 创建 `multi_source_service` 实例
3. ✅ 根据 `TUSHARE_ENABLED` 配置决定优先数据源
4. ✅ 调度任务使用 `multi_source_service.run_full_sync()`

### 2. 更新 `app/services/basics_sync_service.py` - 添加提示信息

**修改位置**：第 89-102 行

**修改内容**：

```python
# Step 0: Check if Tushare is enabled
if not settings.TUSHARE_ENABLED:
    error_msg = (
        "❌ Tushare 数据源已禁用 (TUSHARE_ENABLED=false)\n"
        "💡 此服务仅支持 Tushare 数据源\n"
        "📋 解决方案：\n"
        "   1. 在 .env 文件中设置 TUSHARE_ENABLED=true 并配置 TUSHARE_TOKEN\n"
        "   2. 系统已自动切换到多数据源同步服务（支持 AKShare/BaoStock）"
    )
    logger.warning(error_msg)
    raise RuntimeError(error_msg)
```

**关键改动**：
1. ✅ 更新错误提示信息，说明系统已自动切换到多数据源服务
2. ✅ 将日志级别从 `error` 改为 `warning`

### 3. 更新 `app/services/basics_sync/utils.py` - 添加提示信息

**修改位置**：第 24-33 行

**修改内容**：

```python
# 检查 Tushare 是否启用
if not settings.TUSHARE_ENABLED:
    logger.error("❌ Tushare 数据源已禁用 (TUSHARE_ENABLED=false)")
    logger.error("💡 请在 .env 文件中设置 TUSHARE_ENABLED=true 或使用多数据源同步服务")
    raise RuntimeError(
        "Tushare is disabled (TUSHARE_ENABLED=false). "
        "Set TUSHARE_ENABLED=true in .env or use MultiSourceBasicsSyncService."
    )
```

**关键改动**：
1. ✅ 更新错误提示信息，建议使用多数据源同步服务

---

## ✅ 预期效果

### 1. Tushare 启用时（`TUSHARE_ENABLED=true`）

**优先级**：Tushare > AKShare > BaoStock

**日志输出**：
```
📊 股票基础信息同步优先数据源: Tushare > AKShare > BaoStock
Available data sources: ['tushare', 'akshare', 'baostock']
Successfully fetched 5000 stocks from tushare
```

### 2. Tushare 禁用时（`TUSHARE_ENABLED=false`）

**优先级**：AKShare > BaoStock

**日志输出**：
```
📊 股票基础信息同步优先数据源: AKShare > BaoStock (Tushare已禁用)
Available data sources: ['akshare', 'baostock']
Successfully fetched 5000 stocks from akshare
```

### 3. 自动切换逻辑

- ✅ 如果 AKShare 失败，自动切换到 BaoStock
- ✅ 如果所有数据源都失败，记录错误日志
- ✅ 详细的数据源使用统计

---

## 📊 数据源对比

| 数据源 | 优先级 | 需要 Token | 实时行情 | 历史数据 | 财务数据 |
|--------|--------|-----------|---------|---------|---------|
| **Tushare** | 1 | ✅ 是 | ✅ 支持 | ✅ 完整 | ✅ 完整 |
| **AKShare** | 2 | ❌ 否 | ✅ 支持 | ✅ 完整 | ⚠️ 部分 |
| **BaoStock** | 3 | ❌ 否 | ❌ 不支持 | ✅ 完整 | ⚠️ 部分 |

---

## 🧪 测试验证

### 测试场景 1：Tushare 禁用

**配置**：
```bash
TUSHARE_ENABLED=false
```

**预期结果**：
- ✅ 系统启动时显示：`📊 股票基础信息同步优先数据源: AKShare > BaoStock (Tushare已禁用)`
- ✅ 自动使用 AKShare 获取股票列表
- ✅ 如果 AKShare 失败，自动切换到 BaoStock
- ✅ 不再出现 5 秒等待超时

### 测试场景 2：Tushare 启用

**配置**：
```bash
TUSHARE_ENABLED=true
TUSHARE_TOKEN=your_token_here
```

**预期结果**：
- ✅ 系统启动时显示：`📊 股票基础信息同步优先数据源: Tushare > AKShare > BaoStock`
- ✅ 优先使用 Tushare 获取股票列表
- ✅ 如果 Tushare 失败，自动切换到 AKShare
- ✅ 如果 AKShare 失败，自动切换到 BaoStock

### 测试场景 3：所有数据源都失败

**预期结果**：
- ✅ 记录详细的错误日志
- ✅ 同步状态标记为 `failed`
- ✅ 错误信息包含所有尝试过的数据源

---

## 📝 配置说明

### 相关配置项

```bash
# 股票基础信息同步总开关
SYNC_STOCK_BASICS_ENABLED=true

# 调度时间（CRON 表达式优先）
SYNC_STOCK_BASICS_CRON=30 6 * * *

# 或者使用固定时间（HH:MM）
SYNC_STOCK_BASICS_TIME=06:30

# Tushare 数据源开关
TUSHARE_ENABLED=false

# AKShare 和 BaoStock 不需要额外配置
# 只要库已安装，就会自动可用
```

### 数据源可用性检查

- **Tushare**：检查 `TUSHARE_ENABLED` 配置和连接状态
- **AKShare**：检查 `akshare` 库是否安装
- **BaoStock**：检查 `baostock` 库是否安装

---

## 🎉 总结

### 问题解决

✅ **问题**：`TUSHARE_ENABLED=false` 时系统仍然尝试连接 Tushare  
✅ **解决**：切换到多数据源同步服务，支持自动切换到 AKShare/BaoStock

### 优势

1. ✅ **自动切换**：数据源失败时自动切换到备用数据源
2. ✅ **灵活配置**：根据 `TUSHARE_ENABLED` 配置决定优先级
3. ✅ **详细统计**：记录每个数据源的使用情况
4. ✅ **向后兼容**：保留原有的 `BasicsSync Service`，不影响现有代码

### 影响范围

- ✅ 修改文件：`app/main.py`（调度任务配置）
- ✅ 修改文件：`app/services/basics_sync_service.py`（错误提示）
- ✅ 修改文件：`app/services/basics_sync/utils.py`（错误提示）
- ✅ 新增文档：`docs/fix_multi_source_basics_sync.md`

---

## 📚 相关文档

- [数据源管理器](../app/services/data_sources/manager.py)
- [多数据源同步服务](../app/services/multi_source_basics_sync_service.py)
- [数据源适配器](../app/services/data_sources/)
- [定时任务配置](./scheduled_tasks_configuration.md)

