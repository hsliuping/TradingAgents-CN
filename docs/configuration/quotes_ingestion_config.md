# 实时行情入库服务配置指南

## 📋 概述

实时行情入库服务已优化，支持智能频率控制和接口轮换机制，适配不同用户的 Tushare 权限。

---

## 🎯 核心特性

### 1. 智能频率控制

| 用户类型 | Tushare 权限 | 建议频率 | 说明 |
|---------|-------------|---------|------|
| **免费用户** | 无或免费版 | **6 分钟**（360秒） | 每小时10次，避免超限 |
| **付费用户** | 有 rt_k 权限 | **5-60 秒** | 充分利用权限，建议30-60秒 |

### 2. 接口轮换机制

**轮换顺序**：Tushare rt_k → AKShare 东方财富 → AKShare 新浪财经

**优势**：
- ✅ 避免单一接口被限流或封IP
- ✅ 提高服务可靠性
- ✅ 自动降级，任意接口失败不影响服务

### 3. Tushare 调用限制

**免费用户限制**：
- 每小时最多调用 **2 次** rt_k 接口
- 超过限制自动跳过，使用 AKShare 备用接口
- 不影响服务正常运行

**付费用户**：
- 无调用次数限制
- 可设置高频采集（5-60秒）

### 4. 自动权限检测

**首次运行自动检测**：
- ✅ 检测 Tushare rt_k 接口权限
- ✅ 付费用户：提示可设置高频采集
- ✅ 免费用户：提示当前限制和建议

---

## ⚙️ 配置项说明

### 环境变量配置（`.env` 文件）

```bash
# ========================================
# 实时行情入库服务配置
# ========================================

# 是否启用实时行情入库服务
QUOTES_INGEST_ENABLED=true

# 采集间隔（秒）
# - 免费用户建议: 300-600 秒（5-10分钟）
# - 付费用户建议: 5-60 秒
# - 默认: 360 秒（6分钟）
QUOTES_INGEST_INTERVAL_SECONDS=360

# 休市期/启动兜底补数
QUOTES_BACKFILL_ON_STARTUP=true
QUOTES_BACKFILL_ON_OFFHOURS=true

# ========================================
# 接口轮换和限流配置
# ========================================

# 启用接口轮换机制
# - true: 轮流使用 Tushare/AKShare东方财富/AKShare新浪财经
# - false: 按默认优先级使用（Tushare > AKShare）
QUOTES_ROTATION_ENABLED=true

# Tushare rt_k 接口每小时调用次数限制
# - 免费用户: 2 次（Tushare 官方限制）
# - 付费用户: 可设置更高（如 1000）
QUOTES_TUSHARE_HOURLY_LIMIT=2

# 自动检测 Tushare rt_k 接口权限
# - true: 首次运行自动检测，付费用户会收到提示
# - false: 不检测，按配置运行
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true
```

---

## 📊 不同场景的配置方案

### 场景 1：免费用户（推荐配置）

```bash
# 6分钟采集一次，每小时10次
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=360
QUOTES_ROTATION_ENABLED=true
QUOTES_TUSHARE_HOURLY_LIMIT=2
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true
```

**说明**：
- ✅ 每小时采集10次，Tushare 最多调用2次（不超限）
- ✅ 其余8次使用 AKShare 接口
- ✅ 避免被限流或封IP

### 场景 2：Tushare 付费用户（高频采集）

```bash
# 30秒采集一次，每小时120次
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=30
QUOTES_ROTATION_ENABLED=true
QUOTES_TUSHARE_HOURLY_LIMIT=1000  # 付费用户限制更高
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true
```

**说明**：
- ✅ 充分利用 Tushare 付费权限
- ✅ 30秒更新一次，接近实时
- ✅ 仍然启用轮换，提高可靠性

### 场景 3：只使用 AKShare（无 Tushare Token）

```bash
# 5分钟采集一次，只使用 AKShare
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=300
QUOTES_ROTATION_ENABLED=true
QUOTES_TUSHARE_HOURLY_LIMIT=0  # 禁用 Tushare
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=false

# 不配置 Tushare Token
TUSHARE_TOKEN=
```

**说明**：
- ✅ 完全依赖 AKShare（免费）
- ✅ 东方财富和新浪财经接口轮换
- ✅ 避免 Tushare 相关错误

### 场景 4：极简配置（使用默认值）

```bash
# 只需启用服务，其他使用默认值
QUOTES_INGEST_ENABLED=true
```

**说明**：
- ✅ 默认6分钟采集一次
- ✅ 自动检测 Tushare 权限
- ✅ 自动轮换接口

---

## 🔍 权限检测说明

### 自动检测流程

1. **首次运行**：服务启动后第一次采集时自动检测
2. **检测方法**：尝试调用 `rt_k` 接口获取单只股票数据
3. **检测结果**：
   - ✅ **有权限**：提示可设置高频采集
   - ❌ **无权限**：提示当前限制和建议

### 日志示例

**付费用户**：
```
🔍 首次运行，检测 Tushare rt_k 接口权限...
✅ 检测到 Tushare rt_k 接口权限（付费用户）
✅ 检测到 Tushare 付费权限！建议将 QUOTES_INGEST_INTERVAL_SECONDS 设置为 5-60 秒以充分利用权限
```

**免费用户**：
```
🔍 首次运行，检测 Tushare rt_k 接口权限...
⚠️ Tushare rt_k 接口无权限（免费用户）
ℹ️ Tushare 免费用户，每小时最多调用 2 次 rt_k 接口。当前采集间隔: 360 秒
```

---

## 📈 运行监控

### 查看任务状态

**前端**：系统配置 → 定时任务管理 → 实时行情入库服务

**后端日志**：
```bash
# 查看实时日志
tail -f logs/app.log | grep "行情入库"

# 查看轮换日志
tail -f logs/app.log | grep "使用.*接口获取实时行情"
```

### 关键日志

**成功采集**：
```
📊 使用 Tushare rt_k 接口获取实时行情
✅ 行情入库完成 source=tushare, matched=5440, modified=5440
```

**接口轮换**：
```
📊 使用 AKShare eastmoney 接口获取实时行情
✅ AKShare eastmoney 获取到 5440 只股票的实时行情
✅ 行情入库完成 source=akshare_eastmoney, matched=5440, modified=5440
```

**Tushare 限流**：
```
⚠️ Tushare rt_k 接口已达到每小时调用限制 (2次)，跳过本次调用，使用 AKShare 备用接口
📊 使用 AKShare sina 接口获取实时行情
✅ 行情入库完成 source=akshare_sina, matched=5440, modified=5440
```

---

## ⚠️ 常见问题

### Q1: 为什么默认是6分钟，不是30秒？

**A**: 
- Tushare 免费用户每小时只能调用2次 rt_k 接口
- 30秒采集会立即超限，导致服务不可用
- 6分钟是平衡实时性和限制的最佳选择

### Q2: 我是付费用户，如何设置高频采集？

**A**: 修改 `.env` 文件：
```bash
QUOTES_INGEST_INTERVAL_SECONDS=30  # 30秒一次
QUOTES_TUSHARE_HOURLY_LIMIT=1000  # 提高限制
```
然后重启后端服务。

### Q3: 如何禁用 Tushare，只使用 AKShare？

**A**: 
1. 不配置 `TUSHARE_TOKEN`（留空）
2. 或设置 `QUOTES_TUSHARE_HOURLY_LIMIT=0`

### Q4: 接口轮换是什么意思？

**A**: 
- 第1次采集：使用 Tushare
- 第2次采集：使用 AKShare 东方财富
- 第3次采集：使用 AKShare 新浪财经
- 第4次采集：回到 Tushare
- 循环往复

### Q5: 如何查看当前使用的是哪个接口？

**A**: 查看后端日志，搜索 "使用.*接口获取实时行情"

### Q6: AKShare 会被封IP吗？

**A**: 
- 6分钟采集一次，被封概率很低
- 启用轮换机制，东方财富和新浪财经交替使用，进一步降低风险
- 如果被封，会自动切换到另一个接口

### Q7: 如何手动触发采集？

**A**: 
1. **前端**：系统配置 → 定时任务管理 → 实时行情入库服务 → 立即执行
2. **API**：`POST /api/scheduler/jobs/quotes_ingestion_service/trigger`

---

## 🚀 升级指南

### 从旧版本升级

**步骤 1**：更新代码
```bash
git pull origin v1.0.0-preview
```

**步骤 2**：更新 `.env` 配置
```bash
# 添加新配置项（可选，使用默认值也可以）
QUOTES_INGEST_INTERVAL_SECONDS=360
QUOTES_ROTATION_ENABLED=true
QUOTES_TUSHARE_HOURLY_LIMIT=2
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true
```

**步骤 3**：重启后端服务
```bash
# 停止当前服务（Ctrl+C）
# 重新启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**步骤 4**：验证
- 查看后端日志，确认权限检测和接口轮换正常
- 访问前端任务管理页面，查看任务状态

---

## 📝 总结

**核心改进**：
- ✅ 默认6分钟采集，免费用户友好
- ✅ 三种接口轮换，避免限流
- ✅ 自动检测权限，智能调整
- ✅ 付费用户可高频采集

**推荐配置**：
- **免费用户**：使用默认配置（6分钟）
- **付费用户**：设置30-60秒高频采集

**监控建议**：
- 定期查看后端日志
- 关注接口轮换和限流日志
- 根据实际情况调整配置

