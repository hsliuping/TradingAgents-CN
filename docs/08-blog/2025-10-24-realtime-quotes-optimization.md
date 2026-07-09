# 2025-10-24 项目优化日志：数据源统一、实时行情优化与基本面分析增强

**日期**: 2025-10-24
**作者**: TradingAgents-CN 开发团队
**标签**: `feature`, `optimization`, `refactor`, `bug-fix`, `data-quality`, `performance`

---

## 📋 概述

2025年10月24日是项目开发的高产日，完成了 **31 次提交**，涵盖数据源管理、实时行情优化、基本面分析增强、Docker 构建优化等多个方面。主要亮点包括：

1. **创建统一数据源编码管理系统**，解决数据源标识混乱问题
2. **优化实时行情入库服务**，实现智能频率控制和接口轮换机制
3. **增强基本面分析功能**，优化 PE/PB 计算策略，同时提供 PE 和 PE_TTM 两个指标
4. **完善定时任务管理界面**，新增搜索和筛选功能
5. **优化 Docker 构建策略**，采用分架构独立仓库提高发布效率
6. **修复多个数据同步和索引冲突问题**

**总计**：
- **31 次提交**
- **涉及 80+ 个文件修改**
- **新增 6,000+ 行代码**
- **删除 1,000+ 行冗余代码**

---

## 🎯 核心改进

### 一、数据源管理系统重构（早上 8:00-10:00）

#### 1.1 创建统一数据源编码管理系统

**提交记录**：
- `bc4d0b4` - feat: 创建统一数据源编码管理系统
- `a0a4840` - refactor: 后端代码使用统一数据源编码
- `650b22a` - refactor: 前端代码使用统一数据源编码

**问题背景**：

原有代码中数据源标识混乱：
- 后端使用：`"tushare"`, `"akshare"`, `"baostock"`
- 前端使用：`"Tushare"`, `"AKShare"`, `"BaoStock"`
- 数据库存储：`"tushare"`, `"akshare"`, `"baostock"`
- 配置文件：`DATA_SOURCE_PRIORITY = ["tushare", "akshare", "baostock"]`

导致问题：
- ❌ 前后端数据源标识不一致
- ❌ 数据源优先级配置不生效
- ❌ 代码中硬编码数据源名称
- ❌ 难以维护和扩展

**解决方案**：

创建 `tradingagents/core/data_source_codes.py` 统一管理：

```python
class DataSourceCode:
    """统一数据源编码"""
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    MANUAL = "manual"
    SYSTEM = "system"

    # 显示名称映射
    DISPLAY_NAMES = {
        TUSHARE: "Tushare",
        AKSHARE: "AKShare",
        BAOSTOCK: "BaoStock",
        MANUAL: "手动",
        SYSTEM: "系统",
    }

    @classmethod
    def get_display_name(cls, code: str) -> str:
        """获取数据源显示名称"""
        return cls.DISPLAY_NAMES.get(code, code)

    @classmethod
    def normalize(cls, code: str) -> str:
        """标准化数据源编码（大小写不敏感）"""
        code_lower = code.lower()
        for attr_name in dir(cls):
            if not attr_name.startswith('_'):
                attr_value = getattr(cls, attr_name)
                if isinstance(attr_value, str) and attr_value.lower() == code_lower:
                    return attr_value
        return code
```

**效果**：
- ✅ 统一数据源编码标准
- ✅ 前后端使用相同编码
- ✅ 支持大小写不敏感转换
- ✅ 便于维护和扩展

#### 1.2 修复数据源优先级配置不生效问题

**提交记录**：
- `e994035` - fix: 修复数据源优先级配置不生效的问题
- `9d1a5c5` - fix: 修复分析时数据源降级优先级硬编码问题
- `3e6998c` - fix: 数据源降级优先级支持市场分类（A股/美股/港股）

**问题背景**：

1. MongoDB 查询返回多个数据源的重复数据
2. 代码中硬编码数据源优先级：`["tushare", "akshare", "baostock"]`
3. 不使用配置文件中的 `DATA_SOURCE_PRIORITY`
4. 不同市场（A股/美股/港股）应该有不同的数据源优先级

**解决方案**：

```python
# app/services/data_query_service.py
def _apply_source_priority(self, records: List[Dict], market: str = "A") -> List[Dict]:
    """应用数据源优先级，去重并选择最优数据源"""
    # 根据市场选择优先级
    if market == "A":
        priority = settings.DATA_SOURCE_PRIORITY  # ["tushare", "akshare", "baostock"]
    elif market == "US":
        priority = ["yahoo", "alphavantage"]
    elif market == "HK":
        priority = ["yahoo", "tushare"]
    else:
        priority = settings.DATA_SOURCE_PRIORITY

    # 按 code 分组
    grouped = {}
    for record in records:
        code = record.get("code")
        if code not in grouped:
            grouped[code] = []
        grouped[code].append(record)

    # 选择最优数据源
    result = []
    for code, records_list in grouped.items():
        best_record = None
        best_priority = len(priority)

        for record in records_list:
            source = record.get("source", "")
            try:
                idx = priority.index(source)
                if idx < best_priority:
                    best_priority = idx
                    best_record = record
            except ValueError:
                continue

        if best_record:
            result.append(best_record)

    return result
```

**效果**：
- ✅ 使用配置文件中的数据源优先级
- ✅ 支持不同市场的数据源优先级
- ✅ 自动去重，选择最优数据源
- ✅ 提高数据质量

---

### 二、实时行情入库服务优化（中午 12:00-14:00）

#### 2.1 早期优化：降低 AkShare 实时行情同步频率

**提交记录**：
- `3f009da` - opt: 优化 AkShare 批量获取实时行情，避免频率限制
- `3915f5e` - fix: 支持带前缀的股票代码匹配，增强批量获取兼容性
- `3193107` - opt: 降低 AkShare 实时行情同步频率，避免被封

**问题背景**：

1. **AkShare 接口频繁调用被封 IP**
   - 原有代码每次获取全市场行情
   - 单次请求数据量大，容易触发限流

2. **股票代码匹配问题**
   - 部分代码带前缀（如 `SH600000`）
   - 部分代码不带前缀（如 `600000`）
   - 导致批量获取失败

**解决方案**：

```python
# app/services/data_sources/akshare_adapter.py
def get_realtime_quotes_batch(self, codes: List[str]) -> Dict[str, Dict]:
    """批量获取实时行情（支持带前缀的代码）"""
    # 标准化代码（去除前缀）
    normalized_codes = []
    for code in codes:
        if '.' in code:
            code = code.split('.')[0]  # 去除后缀
        if len(code) > 6:
            code = code[-6:]  # 去除前缀，保留6位数字
        normalized_codes.append(code)

    # 获取全市场行情
    all_quotes = self.get_realtime_quotes()

    # 筛选指定股票
    result = {}
    for code in normalized_codes:
        if code in all_quotes:
            result[code] = all_quotes[code]

    return result
```

**效果**：
- ✅ 支持带前缀的股票代码
- ✅ 提高批量获取成功率
- ✅ 降低被封 IP 风险

#### 2.2 核心优化：智能频率控制和接口轮换

**提交记录**：
- `ebb9197` - feat: 优化实时行情入库服务 - 智能频率控制和接口轮换
- `bd4c976` - docs: 添加实时行情入库服务配置文档和优化总结

**问题背景**：

1. **默认30秒采集频率过高**
   - Tushare 免费用户每小时只能调用 2 次 `rt_k` 接口
   - 30秒采集 = 每小时 120 次，立即超限
   - 导致免费用户服务完全不可用

2. **AKShare 只使用单一接口**
   - 只使用东方财富接口（`stock_zh_a_spot_em`）
   - 未使用新浪财经接口（`stock_zh_a_spot`）
   - 频繁调用单一接口容易被封 IP

3. **无智能频率控制**
   - 付费用户和免费用户使用相同配置
   - 付费用户无法充分利用权限
   - 免费用户容易超限

#### 解决方案

**方案 1：调整默认采集频率为 6 分钟**

```python
# app/core/config.py
QUOTES_INGEST_INTERVAL_SECONDS: int = Field(
    default=360,  # 从 30 秒改为 360 秒（6 分钟）
    description="实时行情采集间隔（秒）。默认360秒（6分钟），免费用户建议>=300秒，付费用户可设置5-60秒"
)
```

**效果**：
- ✅ 每小时采集 10 次，Tushare 最多调用 2 次（不超限）
- ✅ 免费用户可正常使用
- ✅ 满足大多数场景需求

**方案 2：为 AKShare 添加新浪财经备用接口**

```python
# app/services/data_sources/akshare_adapter.py
def get_realtime_quotes(self, source: str = "eastmoney"):
    """
    获取全市场实时快照
    
    Args:
        source: "eastmoney"（东方财富）或 "sina"（新浪财经）
    """
    if source == "sina":
        df = ak.stock_zh_a_spot()  # 新浪财经接口
        logger.info("使用 AKShare 新浪财经接口获取实时行情")
    else:
        df = ak.stock_zh_a_spot_em()  # 东方财富接口
        logger.info("使用 AKShare 东方财富接口获取实时行情")
```

**效果**：
- ✅ 支持两个 AKShare 接口
- ✅ 可轮换使用，降低被封 IP 风险
- ✅ 提高服务可靠性

**方案 3：实现三种接口轮换机制**

**轮换顺序**：Tushare rt_k → AKShare 东方财富 → AKShare 新浪财经

```python
# app/services/quotes_ingestion_service.py
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

**工作流程（免费用户，6分钟采集一次）**：

```
时间轴：
00:00 → Tushare rt_k（第1次调用）✅
06:00 → AKShare 东方财富
12:00 → AKShare 新浪财经
18:00 → Tushare rt_k（第2次调用）✅
24:00 → AKShare 东方财富
30:00 → AKShare 新浪财经
36:00 → Tushare rt_k（超限，跳过）❌ → AKShare 东方财富（自动降级）✅
42:00 → AKShare 新浪财经
48:00 → Tushare rt_k（超限，跳过）❌ → AKShare 东方财富（自动降级）✅
54:00 → AKShare 新浪财经
60:00 → 新的一小时开始，Tushare 限制重置
```

**效果**：
- ✅ 三种接口轮流使用
- ✅ 避免单一接口被限流
- ✅ 提高服务稳定性

**方案 4：添加 Tushare 调用次数限制**

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
- ✅ 免费用户每小时最多调用 2 次
- ✅ 超过限制自动跳过，使用 AKShare
- ✅ 不影响服务正常运行

**方案 5：自动检测 Tushare 付费权限**

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

**首次运行日志**：

**免费用户**：
```
🔍 首次运行，检测 Tushare rt_k 接口权限...
⚠️ Tushare rt_k 接口无权限（免费用户）
ℹ️ Tushare 免费用户，每小时最多调用 2 次 rt_k 接口。当前采集间隔: 360 秒
```

**付费用户**：
```
🔍 首次运行，检测 Tushare rt_k 接口权限...
✅ 检测到 Tushare rt_k 接口权限（付费用户）
✅ 检测到 Tushare 付费权限！建议将 QUOTES_INGEST_INTERVAL_SECONDS 设置为 5-60 秒以充分利用权限
```

**效果**：
- ✅ 首次运行自动检测权限
- ✅ 付费用户：提示可设置高频采集
- ✅ 免费用户：提示当前限制

#### 新增配置项

**`.env.example` 中新增**：

```bash
# ==================== 实时行情入库服务配置 ====================
# 📈 实时行情入库服务

# 启用/禁用实时行情入库服务
QUOTES_INGEST_ENABLED=true

# 行情采集间隔（秒）
# - 免费用户建议: 300-600 秒（5-10分钟）
# - 付费用户建议: 5-60 秒
# - 默认: 360 秒（6分钟）
QUOTES_INGEST_INTERVAL_SECONDS=360

# 启用接口轮换机制
# - true: 轮流使用 Tushare rt_k → AKShare东方财富 → AKShare新浪财经
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

# 休市期/启动兜底补数
QUOTES_BACKFILL_ON_STARTUP=true
QUOTES_BACKFILL_ON_OFFHOURS=true
```

#### 性能对比

| 指标 | 优化前（免费用户） | 优化后（免费用户） |
|------|------------------|------------------|
| 采集频率 | 30 秒 | 6 分钟 |
| 每小时采集次数 | 120 次 | 10 次 |
| Tushare 调用次数 | 120 次（超限❌） | 2 次（不超限✅） |
| 服务可用性 | ❌ 不可用 | ✅ 可用 |
| 被封 IP 风险 | ⚠️ 高 | ✅ 低 |

---

### 三、基本面分析功能增强（下午 14:00-18:00）

#### 3.1 优化基本面分析数据获取策略

**提交记录**：
- `7b723b6` - refactor: 优化基本面分析数据获取策略
- `bec86db` - feat: 将分析师数据获取范围改为可配置参数

**问题背景**：

1. **数据获取策略不合理**
   - 每次分析都重新获取所有数据
   - 没有利用缓存机制
   - 数据获取效率低

2. **分析师数据获取范围固定**
   - 硬编码获取最近 30 天数据
   - 无法根据需求调整

**解决方案**：

```python
# app/core/config.py
ANALYST_RATING_DAYS: int = Field(
    default=30,
    description="分析师评级数据获取天数范围"
)

# app/services/fundamental_analysis_service.py
async def get_fundamental_data(self, code: str) -> Dict:
    """获取基本面数据（优化缓存策略）"""
    # 1. 尝试从缓存获取
    cached = await self._get_from_cache(code)
    if cached and self._is_cache_valid(cached):
        return cached

    # 2. 从数据库获取
    data = await self._get_from_database(code)

    # 3. 缓存数据
    await self._save_to_cache(code, data)

    return data
```

**效果**：
- ✅ 提高数据获取效率
- ✅ 减少数据库查询次数
- ✅ 支持配置分析师数据范围

#### 3.2 优化 PE/PB 计算策略

**提交记录**：
- `7724255` - feat: 优化PE/PB计算策略 - 优先使用动态PE（基于实时股价+Tushare TTM）
- `2baa89f` - fix: 修复PE计算日志中变量引用错误

**问题背景**：

1. **PE 计算不准确**
   - 只使用静态 PE（基于财报数据）
   - 不考虑实时股价变化
   - 数据滞后

2. **缺少 TTM（Trailing Twelve Months）指标**
   - TTM 是更准确的 PE 计算方式
   - 考虑最近 12 个月的盈利

**解决方案**：

**计算策略**：

1. **优先使用动态 PE（实时股价 + Tushare TTM 数据）**
   ```python
   # 获取实时股价
   current_price = await self._get_realtime_price(code)

   # 获取 Tushare TTM 数据
   ttm_data = await self._get_tushare_ttm(code)

   # 计算动态 PE
   if ttm_data and ttm_data.get("eps_ttm"):
       pe_dynamic = current_price / ttm_data["eps_ttm"]
   ```

2. **降级使用静态 PE（财报数据）**
   ```python
   # 如果没有 TTM 数据，使用最新财报
   if not pe_dynamic:
       latest_report = await self._get_latest_financial_report(code)
       if latest_report and latest_report.get("eps"):
           pe_static = current_price / latest_report["eps"]
   ```

3. **最终降级使用数据源提供的 PE**
   ```python
   # 如果都没有，使用数据源提供的 PE
   if not pe_dynamic and not pe_static:
       pe = stock_info.get("pe")
   ```

**效果**：
- ✅ PE 计算更准确
- ✅ 考虑实时股价变化
- ✅ 支持多级降级策略

#### 3.3 同时提供 PE 和 PE_TTM 两个指标

**提交记录**：
- `410fd21` - feat: 基本面分析同时提供PE和PE_TTM两个指标

**问题背景**：

用户需要同时查看：
- **PE（静态市盈率）**：基于最新财报的 EPS
- **PE_TTM（动态市盈率）**：基于最近 12 个月的 EPS

**解决方案**：

```python
# app/schemas/analysis.py
class FundamentalAnalysisResponse(BaseModel):
    """基本面分析响应"""
    code: str
    name: str

    # 估值指标
    pe: Optional[float] = Field(None, description="静态市盈率（基于最新财报）")
    pe_ttm: Optional[float] = Field(None, description="动态市盈率（TTM）")
    pb: Optional[float] = Field(None, description="市净率")
    ps: Optional[float] = Field(None, description="市销率")

    # ... 其他字段
```

**前端显示**：

```vue
<el-descriptions-item label="市盈率(PE)">
  {{ data.pe?.toFixed(2) || 'N/A' }}
</el-descriptions-item>
<el-descriptions-item label="市盈率(PE_TTM)">
  {{ data.pe_ttm?.toFixed(2) || 'N/A' }}
  <el-tag v-if="data.pe_ttm" type="info" size="small">动态</el-tag>
</el-descriptions-item>
```

**效果**：
- ✅ 同时提供两个指标
- ✅ 用户可对比静态和动态 PE
- ✅ 提高分析准确性

---

### 四、数据同步和索引问题修复（上午 10:00-12:00）

#### 4.1 修复 market_quotes 集合索引冲突

**提交记录**：
- `6bab35b` - fix: 修复 market_quotes 集合 code 字段为 null 导致的唯一索引冲突
- `2d993c5` - docs: 添加 market_quotes code 字段 null 值修复指南
- `3741ab7` - fix: 修复脚本日志配置问题
- `071fd4e` - fix: 脚本添加数据库初始化
- `28e1579` - fix: 使用正确的数据库初始化函数名
- `f46f952` - test: 添加测试脚本并验证修复效果

**问题背景**：

MongoDB `market_quotes` 集合存在 `code` 字段为 `null` 的记录，导致唯一索引冲突：

```
E11000 duplicate key error collection: tradingagents.market_quotes
index: code_1 dup key: { code: null }
```

**原因分析**：

1. 早期代码没有验证 `code` 字段
2. 部分数据源返回的数据缺少 `code` 字段
3. 插入时没有检查必填字段

**解决方案**：

**步骤 1：创建修复脚本**

```python
# scripts/fix_market_quotes_null_code.py
async def fix_null_code_records():
    """修复 code 字段为 null 的记录"""
    db = get_database()
    collection = db[settings.MARKET_QUOTES_COLLECTION]

    # 查找 code 为 null 的记录
    null_records = await collection.find({"code": None}).to_list(None)

    logger.info(f"找到 {len(null_records)} 条 code 为 null 的记录")

    # 删除这些记录
    if null_records:
        result = await collection.delete_many({"code": None})
        logger.info(f"已删除 {result.deleted_count} 条记录")
```

**步骤 2：添加数据验证**

```python
# app/services/quotes_ingestion_service.py
async def _save_quotes(self, quotes: Dict[str, Dict]):
    """保存行情数据（添加验证）"""
    valid_quotes = []

    for code, quote in quotes.items():
        # 验证必填字段
        if not code or not quote.get("name"):
            logger.warning(f"跳过无效记录：code={code}, quote={quote}")
            continue

        valid_quotes.append({
            "code": code,
            "name": quote["name"],
            "price": quote.get("price"),
            # ... 其他字段
        })

    # 批量插入
    if valid_quotes:
        await collection.insert_many(valid_quotes)
```

**效果**：
- ✅ 修复历史数据
- ✅ 防止新数据出现问题
- ✅ 提供修复指南文档

#### 4.2 修复 Tushare 同步服务 Pydantic 模型错误

**提交记录**：
- `bcd9d09` - fix: 修复 Tushare 同步服务中 Pydantic 模型调用字典方法的错误

**问题背景**：

Pydantic v2 模型不再支持字典方法（如 `.get()`），导致代码报错：

```python
# 错误代码
stock_info = StockBasicInfo(...)
name = stock_info.get("name")  # AttributeError: 'StockBasicInfo' object has no attribute 'get'
```

**解决方案**：

```python
# 修复后
stock_info = StockBasicInfo(...)
name = stock_info.name  # 直接访问属性

# 或者转换为字典
stock_dict = stock_info.model_dump()
name = stock_dict.get("name")
```

**效果**：
- ✅ 兼容 Pydantic v2
- ✅ 修复同步服务错误
- ✅ 提高代码质量

#### 4.3 修复数据同步和数据源优先级问题

**提交记录**：
- `7fd534c` - fix: 修复数据同步和数据源优先级问题

**问题背景**：

1. **任务手动触发功能不支持暂停任务**
2. **历史数据同步存在问题**
   - 股票列表查询条件不正确
   - 每次全量同步，导致数据重复
3. **财务数据同步问题**
   - 只同步季报，缺少年报
   - 只获取最近 4 期（约 1 年）

**解决方案**：

详见之前的提交记录。

**效果**：
- ✅ 支持暂停任务的手动触发
- ✅ 历史数据增量同步
- ✅ 财务数据包含年报和季报

---

### 五、定时任务管理界面优化（下午 16:00-17:00）

#### 5.1 为所有任务添加友好的中文名称

**提交记录**：
- `8bb8e02` - fix: 为所有定时任务添加友好的中文名称

**问题背景**：

1. **任务名称显示不友好**
   - 部分任务显示为函数路径（如 `lifespan.<locals>.run_news_sync`）
   - 部分任务显示为函数名（如 `run_akshare_basic_info_sync`）

2. **用户体验差**
   - 无法快速识别任务功能
   - 需要查看代码才能理解

**解决方案**：

```python
# app/main.py
scheduler.add_job(
    run_akshare_basic_info_sync,
    CronTrigger.from_crontab(settings.AKSHARE_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE),
    id="akshare_basic_info_sync",
    name="股票基础信息同步（AKShare）",  # ← 新增友好名称
    kwargs={"force_update": False}
)
```

**命名格式**：`功能描述（数据源）`

**修改的任务**：
- ✅ 18 个定时任务全部添加中文名称
- ✅ 统一命名格式
- ✅ 提升用户体验

#### 5.2 添加搜索和筛选功能

**提交记录**：
- `b349e89` - feat: 为定时任务管理页面添加搜索和筛选功能

**问题背景**：

1. **任务查找困难**
   - 10+ 个任务，没有搜索和筛选功能
   - 查找特定任务需要手动翻找

2. **无法按条件筛选**
   - 无法只查看某个数据源的任务
   - 无法只查看运行中或暂停的任务

**解决方案**：

```vue
<!-- frontend/src/views/System/SchedulerManagement.vue -->
<el-form :inline="true" class="filter-form">
  <!-- 任务名称搜索 -->
  <el-form-item label="任务名称">
    <el-input
      v-model="searchKeyword"
      placeholder="搜索任务名称"
      clearable
      :prefix-icon="Search"
      @input="handleSearch"
    />
  </el-form-item>
  
  <!-- 数据源筛选 -->
  <el-form-item label="数据源">
    <el-select v-model="filterDataSource" @change="handleSearch">
      <el-option label="全部数据源" value="" />
      <el-option label="Tushare" value="Tushare" />
      <el-option label="AKShare" value="AKShare" />
      <el-option label="BaoStock" value="BaoStock" />
      <el-option label="多数据源" value="多数据源" />
      <el-option label="其他" value="其他" />
    </el-select>
  </el-form-item>
  
  <!-- 状态筛选 -->
  <el-form-item label="状态">
    <el-select v-model="filterStatus" @change="handleSearch">
      <el-option label="全部状态" value="" />
      <el-option label="运行中" value="running" />
      <el-option label="已暂停" value="paused" />
    </el-select>
  </el-form-item>
  
  <el-form-item>
    <el-button :icon="Refresh" @click="handleReset">重置</el-button>
  </el-form-item>
</el-form>
```

**筛选逻辑**：

```typescript
const filteredJobs = computed(() => {
  let result = [...jobs.value]
  
  // 按任务名称搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(job => 
      job.name.toLowerCase().includes(keyword) ||
      job.id.toLowerCase().includes(keyword)
    )
  }
  
  // 按数据源筛选
  if (filterDataSource.value) {
    result = result.filter(job => job.name.includes(filterDataSource.value))
  }
  
  // 按状态筛选
  if (filterStatus.value) {
    if (filterStatus.value === 'running') {
      result = result.filter(job => !job.paused)
    } else if (filterStatus.value === 'paused') {
      result = result.filter(job => job.paused)
    }
  }
  
  // 默认排序：运行中的任务优先
  result.sort((a, b) => {
    if (a.paused !== b.paused) {
      return a.paused ? 1 : -1
    }
    return a.name.localeCompare(b.name, 'zh-CN')
  })
  
  return result
})
```

**效果**：
- ✅ 支持任务名称搜索
- ✅ 支持数据源筛选
- ✅ 支持状态筛选
- ✅ 运行中的任务优先显示
- ✅ 实时搜索，无需点击按钮

---

### 六、Docker 构建优化（上午 9:00-11:00）

#### 6.1 采用分架构独立仓库策略

**提交记录**：
- `76f24e0` - feat: 采用分架构独立仓库策略，提高发布效率
- `2ac8dd5` - docs: 添加快速构建参考指南
- `c04fc53` - refactor: 删除 Apple Silicon 独立脚本，统一使用 ARM64

**问题背景**：

1. **多架构构建耗时长**
   - 同时构建 AMD64 和 ARM64 需要 30+ 分钟
   - 每次发布都要等待很久

2. **Apple Silicon 脚本冗余**
   - 有独立的 `build-apple-silicon.sh` 脚本
   - 与 ARM64 脚本功能重复

**解决方案**：

**策略 1：分架构独立仓库**

```bash
# AMD64 架构（Linux/Windows）
docker build --platform linux/amd64 -t tradingagents-cn:amd64 .
docker tag tradingagents-cn:amd64 your-registry/tradingagents-cn:amd64
docker push your-registry/tradingagents-cn:amd64

# ARM64 架构（Apple Silicon/ARM服务器）
docker build --platform linux/arm64 -t tradingagents-cn:arm64 .
docker tag tradingagents-cn:arm64 your-registry/tradingagents-cn:arm64
docker push your-registry/tradingagents-cn:arm64
```

**策略 2：用户根据架构选择镜像**

```bash
# AMD64 用户
docker pull your-registry/tradingagents-cn:amd64

# ARM64 用户
docker pull your-registry/tradingagents-cn:arm64
```

**效果**：
- ✅ 构建时间从 30+ 分钟降低到 10 分钟
- ✅ 提高发布效率
- ✅ 简化构建脚本

#### 6.2 删除冗余脚本

**删除的脚本**：
- `scripts/build-apple-silicon.sh`（与 ARM64 脚本重复）

**保留的脚本**：
- `scripts/build-amd64.sh`（AMD64 架构）
- `scripts/build-arm64.sh`（ARM64 架构，包括 Apple Silicon）

**效果**：
- ✅ 减少维护成本
- ✅ 避免脚本冗余
- ✅ 统一构建流程

---

### 七、系统架构优化（早上 7:00-8:00）

#### 7.1 完全移除 SSE + Redis PubSub 通知系统

**提交记录**：
- `947a791` - refactor: 完全移除 SSE + Redis PubSub 通知系统，只保留 WebSocket

**问题背景**：

1. **双通知系统冗余**
   - 同时维护 SSE 和 WebSocket 两套系统
   - 增加维护成本

2. **Redis PubSub 连接泄漏**
   - 之前已修复，但仍有潜在风险

**解决方案**：

完全移除 SSE + Redis PubSub，只保留 WebSocket：

```python
# 删除的代码
# app/routers/sse.py
# app/services/notification_service.py (Redis PubSub 部分)

# 保留的代码
# app/routers/websocket.py
# app/services/websocket_manager.py
```

**效果**：
- ✅ 简化系统架构
- ✅ 减少维护成本
- ✅ 避免连接泄漏风险

#### 7.2 统一使用配置时区

**提交记录**：
- `a85c86c` - fix: 统一使用配置时区（now_tz）替代 UTC 时间（datetime.utcnow）

**问题背景**：

1. **时区混乱**
   - 部分代码使用 `datetime.utcnow()`（UTC 时间）
   - 部分代码使用 `datetime.now(tz)`（配置时区）
   - 导致时间显示不一致

2. **用户体验差**
   - 日志时间显示为 UTC
   - 前端显示时间需要转换

**解决方案**：

统一使用配置时区：

```python
# 错误写法
now = datetime.utcnow()  # UTC 时间

# 正确写法
from app.core.config import settings
from zoneinfo import ZoneInfo

tz = ZoneInfo(settings.TIMEZONE)  # 配置时区（如 "Asia/Shanghai"）
now = datetime.now(tz)  # 配置时区时间
```

**效果**：
- ✅ 时间显示一致
- ✅ 提高用户体验
- ✅ 避免时区转换错误

---

## 📊 提交统计

### 今日提交总览

**总计**：
- **31 次提交**
- **涉及 80+ 个文件修改**
- **新增 6,000+ 行代码**
- **删除 1,000+ 行冗余代码**

### 核心提交分类

#### 数据源管理（3 commits）
- `bc4d0b4` - feat: 创建统一数据源编码管理系统
- `a0a4840` - refactor: 后端代码使用统一数据源编码
- `650b22a` - refactor: 前端代码使用统一数据源编码

#### 数据源优先级（3 commits）
- `e994035` - fix: 修复数据源优先级配置不生效的问题
- `9d1a5c5` - fix: 修复分析时数据源降级优先级硬编码问题
- `3e6998c` - fix: 数据源降级优先级支持市场分类（A股/美股/港股）

#### 实时行情优化（5 commits）
- `3f009da` - opt: 优化 AkShare 批量获取实时行情，避免频率限制
- `3915f5e` - fix: 支持带前缀的股票代码匹配，增强批量获取兼容性
- `3193107` - opt: 降低 AkShare 实时行情同步频率，避免被封
- `ebb9197` - feat: 优化实时行情入库服务 - 智能频率控制和接口轮换
- `bd4c976` - docs: 添加实时行情入库服务配置文档和优化总结

#### 基本面分析（4 commits）
- `7b723b6` - refactor: 优化基本面分析数据获取策略
- `bec86db` - feat: 将分析师数据获取范围改为可配置参数
- `7724255` - feat: 优化PE/PB计算策略 - 优先使用动态PE（基于实时股价+Tushare TTM）
- `2baa89f` - fix: 修复PE计算日志中变量引用错误
- `410fd21` - feat: 基本面分析同时提供PE和PE_TTM两个指标

#### 数据同步修复（7 commits）
- `6bab35b` - fix: 修复 market_quotes 集合 code 字段为 null 导致的唯一索引冲突
- `2d993c5` - docs: 添加 market_quotes code 字段 null 值修复指南
- `3741ab7` - fix: 修复脚本日志配置问题
- `071fd4e` - fix: 脚本添加数据库初始化
- `28e1579` - fix: 使用正确的数据库初始化函数名
- `f46f952` - test: 添加测试脚本并验证修复效果
- `bcd9d09` - fix: 修复 Tushare 同步服务中 Pydantic 模型调用字典方法的错误
- `7fd534c` - fix: 修复数据同步和数据源优先级问题

#### 定时任务管理（2 commits）
- `8bb8e02` - fix: 为所有定时任务添加友好的中文名称
- `b349e89` - feat: 为定时任务管理页面添加搜索和筛选功能

#### Docker 构建（3 commits）
- `76f24e0` - feat: 采用分架构独立仓库策略，提高发布效率
- `2ac8dd5` - docs: 添加快速构建参考指南
- `c04fc53` - refactor: 删除 Apple Silicon 独立脚本，统一使用 ARM64

#### 系统架构（2 commits）
- `947a791` - refactor: 完全移除 SSE + Redis PubSub 通知系统，只保留 WebSocket
- `a85c86c` - fix: 统一使用配置时区（now_tz）替代 UTC 时间（datetime.utcnow）

---

## 📚 新增文档

### 配置文档
1. **`docs/configuration/quotes_ingestion_config.md`**
   - 实时行情入库服务配置指南
   - 配置项详细说明
   - 不同场景的配置方案（免费用户/付费用户/只用AKShare）
   - 权限检测说明
   - 运行监控指南
   - 常见问题解答

### 分析文档
2. **`docs/analysis/quotes_ingestion_optimization_summary.md`**
   - 实时行情入库服务优化总结
   - 优化背景和原有问题
   - 优化方案详解
   - 工作流程图示
   - 性能对比
   - 代码变更统计

3. **`docs/analysis/market_quotes_null_code_fix.md`**
   - market_quotes code 字段 null 值修复指南
   - 问题分析
   - 修复步骤
   - 预防措施

### 构建文档
4. **`docs/deployment/quick-build-reference.md`**
   - Docker 快速构建参考指南
   - 分架构构建策略
   - 构建脚本使用说明

---

## 🚀 升级指南

### 步骤 1：更新代码

```bash
git pull origin v1.0.0-preview
```

### 步骤 2：修复历史数据（如果有 market_quotes 索引冲突）

```bash
# 运行修复脚本
.\.venv\Scripts\python scripts/fix_market_quotes_null_code.py
```

### 步骤 3：更新配置（可选）

如果您想自定义配置，可以在 `.env` 文件中添加：

```bash
# ==================== 实时行情入库服务配置 ====================
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=360  # 免费用户使用默认值（6分钟）
# QUOTES_INGEST_INTERVAL_SECONDS=30  # 付费用户可设置为30秒

QUOTES_ROTATION_ENABLED=true
QUOTES_TUSHARE_HOURLY_LIMIT=2  # 免费用户
# QUOTES_TUSHARE_HOURLY_LIMIT=1000  # 付费用户
QUOTES_AUTO_DETECT_TUSHARE_PERMISSION=true

# ==================== 基本面分析配置 ====================
ANALYST_RATING_DAYS=30  # 分析师评级数据获取天数范围
```

### 步骤 4：重启后端服务

```bash
# 停止当前服务（Ctrl+C）
# 重新启动
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤 5：验证

1. **查看后端日志**，确认权限检测和接口轮换正常
   ```
   🔍 首次运行，检测 Tushare rt_k 接口权限...
   ✅ 检测到 Tushare rt_k 接口权限（付费用户）
   📊 使用 Tushare rt_k 接口获取实时行情
   ```

2. **访问前端任务管理页面**（`http://localhost:5173/system/scheduler`）
   - 查看任务名称是否显示为中文
   - 测试搜索功能
   - 测试数据源筛选
   - 测试状态筛选

3. **测试基本面分析**（`http://localhost:5173/analysis/fundamental`）
   - 查看是否同时显示 PE 和 PE_TTM
   - 验证数据准确性

---

## 💡 使用建议

### 场景 1：免费用户（推荐）

**推荐配置**：使用默认配置

```bash
QUOTES_INGEST_ENABLED=true
# 其他使用默认值
```

**说明**：
- ✅ 默认 6 分钟采集一次
- ✅ 自动检测权限
- ✅ 自动轮换接口（Tushare → AKShare 东方财富 → AKShare 新浪财经）
- ✅ Tushare 每小时最多调用 2 次
- ✅ 不会超限，不会被封 IP

### 场景 2：付费用户（充分利用权限）

**推荐配置**：设置高频采集

```bash
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=30  # 30秒一次
QUOTES_TUSHARE_HOURLY_LIMIT=1000  # 提高限制
```

**说明**：
- ✅ 充分利用付费权限
- ✅ 接近实时行情（30秒延迟）
- ✅ 仍然启用轮换机制
- ✅ 提高数据时效性

### 场景 3：只使用 AKShare（完全免费）

**推荐配置**：禁用 Tushare

```bash
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=300  # 5分钟
QUOTES_TUSHARE_HOURLY_LIMIT=0  # 禁用 Tushare
TUSHARE_TOKEN=  # 不配置 Token
```

**说明**：
- ✅ 完全依赖 AKShare
- ✅ 东方财富和新浪财经轮换
- ✅ 免费且稳定
- ✅ 适合没有 Tushare Token 的用户

---

## 🎉 总结

### 今日成果

**提交统计**：
- ✅ **31 次提交**
- ✅ **80+ 个文件修改**
- ✅ **6,000+ 行新增代码**
- ✅ **1,000+ 行删除代码**

**核心价值**：

1. **数据源管理更规范**
   - 统一数据源编码
   - 数据源优先级配置生效
   - 支持市场分类

2. **实时行情服务更可靠**
   - 免费用户可正常使用
   - 付费用户充分利用权限
   - 智能频率控制和接口轮换
   - 降低被限流和封 IP 风险

3. **基本面分析更准确**
   - 优化 PE/PB 计算策略
   - 同时提供 PE 和 PE_TTM
   - 优化数据获取策略

4. **任务管理更友好**
   - 友好的中文任务名称
   - 强大的搜索筛选功能
   - 提高用户体验

5. **系统架构更简洁**
   - 移除冗余的 SSE 通知系统
   - 统一使用配置时区
   - 优化 Docker 构建策略

6. **数据质量更高**
   - 修复索引冲突问题
   - 修复数据同步问题
   - 完善数据验证

**代码质量**：
- ✅ 完善的文档支持
- ✅ 详细的配置说明
- ✅ 清晰的代码注释
- ✅ 完整的测试脚本

**用户体验**：
- ✅ 自动检测权限
- ✅ 智能频率控制
- ✅ 友好的任务名称
- ✅ 强大的搜索筛选
- ✅ 准确的基本面分析

---

## 📖 相关文档

### 配置文档
- [实时行情入库服务配置指南](../configuration/quotes_ingestion_config.md)
- [环境变量配置说明](../configuration/environment-variables.md)

### 分析文档
- [实时行情入库服务优化总结](../analysis/quotes_ingestion_optimization_summary.md)
- [market_quotes code 字段 null 值修复指南](../analysis/market_quotes_null_code_fix.md)

### 部署文档
- [Docker 快速构建参考指南](../deployment/quick-build-reference.md)
- [Docker 部署指南](../deployment/docker-deployment.md)

### 功能文档
- [定时任务管理文档](../features/scheduler-management.md)
- [基本面分析功能说明](../features/fundamental-analysis.md)

---

## 🔮 下一步计划

1. **继续优化数据同步**
   - 增量同步优化
   - 数据去重优化
   - 同步性能优化

2. **增强基本面分析**
   - 添加更多财务指标
   - 优化分析算法
   - 提供行业对比

3. **完善前端功能**
   - 添加更多图表
   - 优化交互体验
   - 提高响应速度

4. **提高系统稳定性**
   - 添加更多错误处理
   - 优化日志记录
   - 完善监控告警

---

**感谢使用 TradingAgents-CN！** 🚀

如有问题或建议，欢迎在 [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues) 中反馈。

