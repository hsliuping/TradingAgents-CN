# AKShare 同步频率配置指南

## 📋 概述

本文档说明如何配置 AKShare 实时行情同步频率，以及如何避免被数据源封禁。

---

## ⚠️ 频率限制问题

### 问题描述

AKShare 使用的数据源（新浪财经、东方财富）都有反爬虫机制：

- **频繁调用**：触发频率限制，导致连接被关闭
- **并发请求**：多个并发请求会被识别为爬虫
- **IP 封禁**：严重时可能导致 IP 被临时封禁

### 典型错误

```
Remote end closed connection without response
HTTPSConnectionPool: Max retries exceeded
Network is unreachable
```

---

## 🔧 同步频率配置

### 当前默认配置（推荐）

```bash
# 交易时间每30分钟同步一次
AKSHARE_QUOTES_SYNC_CRON="*/30 9-15 * * 1-5"
```

**说明**：
- `*/30`：每30分钟执行一次
- `9-15`：交易时间段（9:00-15:59）
- `* * 1-5`：周一到周五

**优点**：
- ✅ 避免频率限制
- ✅ 数据更新及时（30分钟延迟可接受）
- ✅ 服务器负载低

---

## 📊 不同场景的推荐配置

### 场景 1：高频交易（不推荐）

```bash
# 每5分钟同步一次（容易被封）
AKSHARE_QUOTES_SYNC_CRON="*/5 9-15 * * 1-5"
```

**风险**：
- ❌ 极易触发频率限制
- ❌ 可能导致 IP 被封
- ❌ 不推荐使用

### 场景 2：中频交易（推荐）

```bash
# 每30分钟同步一次（默认配置）
AKSHARE_QUOTES_SYNC_CRON="*/30 9-15 * * 1-5"
```

**适用**：
- ✅ 日内交易
- ✅ 波段交易
- ✅ 大部分使用场景

### 场景 3：低频交易

```bash
# 每小时同步一次
AKSHARE_QUOTES_SYNC_CRON="0 9-15 * * 1-5"
```

**适用**：
- ✅ 长线投资
- ✅ 基本面分析
- ✅ 服务器资源有限

### 场景 4：仅收盘数据

```bash
# 仅在收盘后同步一次
AKSHARE_QUOTES_SYNC_CRON="0 15 * * 1-5"
```

**适用**：
- ✅ 不需要盘中数据
- ✅ 仅关注收盘价
- ✅ 最小化 API 调用

---

## 🚀 优化建议

### 1. 批量获取优化（已实现）

**优化前**：
```python
# 每个股票调用一次接口（100次调用）
for symbol in symbols:
    quotes = get_stock_quotes(symbol)
```

**优化后**：
```python
# 一次获取全市场快照（1次调用）
quotes_map = get_batch_stock_quotes(symbols)
```

**效果**：
- ✅ API 调用次数减少 100 倍
- ✅ 避免触发频率限制
- ✅ 同步速度更快

### 2. 数据源回退（已实现）

```python
# 优先使用新浪财经
try:
    data = fetch_from_sina()
except:
    # 失败时回退到东方财富
    data = fetch_from_eastmoney()
```

**效果**：
- ✅ 提高成功率
- ✅ 自动容错
- ✅ 避免单点故障

### 3. 代码前缀匹配（已实现）

```python
# 支持带前缀的代码匹配
# sh600000 -> 600000
# sz000001 -> 000001
```

**效果**：
- ✅ 兼容不同数据源
- ✅ 提高匹配成功率
- ✅ 避免"未找到行情"错误

---

## 📝 配置修改方法

### 方法 1：修改 .env 文件

```bash
# 编辑 .env 文件
vim .env

# 修改配置
AKSHARE_QUOTES_SYNC_CRON="*/30 9-15 * * 1-5"

# 重启服务
systemctl restart tradingagents
```

### 方法 2：环境变量

```bash
# 设置环境变量
export AKSHARE_QUOTES_SYNC_CRON="*/30 9-15 * * 1-5"

# 重启服务
systemctl restart tradingagents
```

### 方法 3：Docker 环境

```bash
# 编辑 docker-compose.yml
environment:
  - AKSHARE_QUOTES_SYNC_CRON=*/30 9-15 * * 1-5

# 重启容器
docker-compose restart
```

---

## 🔍 监控和调试

### 查看同步日志

```bash
# 查看实时日志
tail -f logs/app.log | grep "AKShare行情同步"

# 查看错误日志
grep "ERROR" logs/app.log | grep "akshare"
```

### 检查同步状态

```bash
# 使用 CLI 工具
python cli/akshare_init.py status

# 或使用 API
curl http://localhost:8000/api/akshare/status
```

### 常见问题排查

**问题 1：未找到行情数据**
```
⚠️ 未找到688485的行情数据
```

**原因**：
- 代码格式不匹配
- 股票已退市或停牌
- 数据源暂时无数据

**解决**：
- ✅ 已实现代码前缀匹配
- ✅ 自动跳过无效股票

**问题 2：连接被关闭**
```
Remote end closed connection without response
```

**原因**：
- 触发频率限制
- 并发请求过多

**解决**：
- ✅ 降低同步频率（30分钟）
- ✅ 批量获取优化（1次调用）

**问题 3：网络不可达**
```
Network is unreachable
```

**原因**：
- 服务器网络配置问题
- 防火墙限制
- DNS 解析失败

**解决**：
- 检查网络配置
- 配置代理（如需要）
- 使用数据源回退机制

---

## 📊 性能对比

| 配置 | API 调用次数/次 | 同步时间 | 被封风险 | 推荐度 |
|------|----------------|---------|---------|--------|
| 每5分钟 | 1 | ~30秒 | 高 ⚠️ | ❌ 不推荐 |
| 每10分钟 | 1 | ~30秒 | 中 ⚠️ | ⚠️ 谨慎使用 |
| **每30分钟** | 1 | ~30秒 | 低 ✅ | ✅ **推荐** |
| 每小时 | 1 | ~30秒 | 极低 ✅ | ✅ 推荐 |
| 仅收盘 | 1 | ~30秒 | 无 ✅ | ✅ 推荐 |

**注**：批量获取优化后，每次同步只调用 1 次 API（获取全市场快照）

---

## 🎯 最佳实践

### 1. 生产环境配置

```bash
# 推荐配置
AKSHARE_QUOTES_SYNC_ENABLED=true
AKSHARE_QUOTES_SYNC_CRON="*/30 9-15 * * 1-5"  # 每30分钟
```

### 2. 开发/测试环境配置

```bash
# 测试时可以更频繁
AKSHARE_QUOTES_SYNC_ENABLED=true
AKSHARE_QUOTES_SYNC_CRON="*/15 9-15 * * 1-5"  # 每15分钟（谨慎）
```

### 3. 禁用自动同步

```bash
# 手动触发同步
AKSHARE_QUOTES_SYNC_ENABLED=false
```

然后使用 API 或 CLI 手动触发：

```bash
# 使用 CLI
python cli/akshare_init.py sync-quotes

# 使用 API
curl -X POST http://localhost:8000/api/akshare/sync/quotes
```

---

## 📚 相关文档

- [AKShare 统一数据源集成方案](./README.md)
- [数据同步服务文档](./SYNC_SERVICE.md)
- [初始化服务文档](./INIT_SERVICE.md)

---

## 🆘 获取帮助

如果遇到问题：

1. 查看日志：`logs/app.log`
2. 检查配置：`python cli/akshare_init.py status`
3. 提交 Issue：[GitHub Issues](https://github.com/your-repo/issues)

---

**最后更新**：2025-10-24

