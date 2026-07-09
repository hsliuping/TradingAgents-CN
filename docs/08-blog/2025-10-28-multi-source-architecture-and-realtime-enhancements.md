# 多数据源架构完善与实时数据增强

**日期**: 2025-10-28  
**作者**: TradingAgents-CN 开发团队  
**标签**: `多数据源` `实时数据` `PE/PB计算` `K线图` `数据隔离`

---

## 📋 概述

2025年10月28日，我们完成了一次重大的系统架构升级。通过 **25 个提交**，完成了 **多数据源隔离存储设计**、**实时PE/PB计算优化**、**K线图实时数据支持**、**实时行情同步状态追踪**等多项核心功能。本次更新显著提升了系统的数据完整性、实时性和可靠性。

---

## 🎯 核心改进

### 1. 多数据源隔离存储架构

#### 1.1 问题背景

**提交记录**：
- `279937659` - feat: 实现多数据源隔离存储设计
- `253d60346` - fix: 修复多数据源同步的 MongoDB 连接和索引冲突问题
- `08bbee6eb` - fix: 修复多数据源同步的数据一致性问题
- `86e67b49a` - feat: 行业列表接口支持数据源优先级

**问题描述**：

系统支持 Tushare、AKShare、BaoStock 三个数据源，但存在严重的数据覆盖问题：

1. **数据覆盖问题**
   - 使用 `code` 作为唯一索引
   - 后运行的同步任务会覆盖先运行的数据
   - 无法保留不同数据源的独立数据

2. **数据源优先级不统一**
   - 不同模块使用不同的数据源
   - 查询结果不一致
   - 用户体验混乱

3. **索引冲突**
   - 多数据源同步时出现 `E11000 duplicate key error`
   - 同步任务失败
   - 数据不完整

**示例错误**：
```
E11000 duplicate key error collection: tradingagents.stock_basic_info 
index: code_1 dup key: { code: "000001" }
```

#### 1.2 解决方案

**步骤 1：设计多数据源隔离存储架构**

**核心思路**：在同一个集合中，通过 `(code, source)` 联合唯一索引实现数据源隔离

```javascript
// 联合唯一索引
db.stock_basic_info.createIndex(
  { "code": 1, "source": 1 }, 
  { unique: true }
);

// 辅助索引
db.stock_basic_info.createIndex({ "code": 1 });    // 查询所有数据源
db.stock_basic_info.createIndex({ "source": 1 });  // 按数据源查询
```

**数据结构**：
```json
{
  "code": "000001",
  "source": "tushare",
  "name": "平安银行",
  "industry": "银行",
  "list_date": "19910403",
  ...
}
```

**步骤 2：创建索引迁移脚本**

```python
# scripts/migrations/migrate_stock_basic_info_add_source_index.py
async def migrate_stock_basic_info_indexes():
    """迁移 stock_basic_info 集合的索引"""
    
    # 1. 删除旧的 code 唯一索引
    try:
        await db.stock_basic_info.drop_index("code_1")
        logger.info("✅ 已删除旧索引: code_1")
    except Exception as e:
        logger.warning(f"⚠️ 删除旧索引失败（可能不存在）: {e}")
    
    # 2. 创建新的联合唯一索引
    await db.stock_basic_info.create_index(
        [("code", 1), ("source", 1)],
        unique=True,
        name="code_source_unique"
    )
    logger.info("✅ 已创建联合唯一索引: (code, source)")
    
    # 3. 创建辅助索引
    await db.stock_basic_info.create_index([("code", 1)])
    await db.stock_basic_info.create_index([("source", 1)])
    logger.info("✅ 已创建辅助索引")
```

**步骤 3：统一数据源优先级查询**

```python
# app/services/stock_data_service.py
async def get_stock_basic_info(
    self, 
    symbol: str, 
    source: Optional[str] = None
) -> Optional[StockBasicInfoExtended]:
    """
    获取股票基础信息
    Args:
        symbol: 6位股票代码
        source: 数据源 (tushare/akshare/baostock/multi_source)
                默认优先级：tushare > multi_source > akshare > baostock
    """
    symbol6 = symbol.lstrip('shsz').zfill(6)
    
    if source:
        # 指定数据源
        query = {"code": symbol6, "source": source}
        doc = await db["stock_basic_info"].find_one(query, {"_id": 0})
    else:
        # 🔥 未指定数据源，按优先级查询
        source_priority = ["tushare", "multi_source", "akshare", "baostock"]
        doc = None
        for src in source_priority:
            query = {"code": symbol6, "source": src}
            doc = await db["stock_basic_info"].find_one(query, {"_id": 0})
            if doc:
                logger.debug(f"✅ 使用数据源: {src}")
                break
    
    if not doc:
        logger.warning(f"⚠️ 未找到股票信息: {symbol}")
        return None
    
    return StockBasicInfoExtended(**doc)
```

**步骤 4：修复多数据源同步服务**

```python
# app/services/multi_source_basics_sync_service.py
async def sync_from_source(self, source: str):
    """从指定数据源同步股票基础信息"""
    
    # 获取数据
    stocks_data = await self._fetch_data_from_source(source)
    
    # 批量更新（使用 upsert）
    operations = []
    for stock in stocks_data:
        operations.append(
            UpdateOne(
                {"code": stock["code"], "source": source},  # 🔥 联合查询条件
                {"$set": stock},
                upsert=True
            )
        )
    
    # 执行批量操作
    if operations:
        result = await db.stock_basic_info.bulk_write(operations)
        logger.info(f"✅ {source}: 更新 {result.modified_count} 条，插入 {result.upserted_count} 条")
```

**效果**：
- ✅ 同一股票可以有多条记录（不同数据源）
- ✅ 保证 `(code, source)` 组合唯一
- ✅ 支持灵活查询（指定数据源或按优先级）
- ✅ 彻底解决索引冲突问题

---

### 2. 实时PE/PB计算优化

#### 2.1 完善回退策略

**提交记录**：
- `f42fc1f61` - fix: 修复实时市值和PE/PB计算逻辑
- `18727ef3c` - feat: 完善实时PE/PB计算的回退策略
- `2460f47dc` - docs: 添加实时PE/PB计算与回退策略博文

**问题背景**：

实时PE/PB计算依赖多个数据源，但存在数据缺失和计算错误的问题：

1. **数据缺失**
   - 实时股价可能为空
   - 财务数据可能未同步
   - 总股本数据可能缺失

2. **计算错误**
   - 单位转换错误
   - 除零错误
   - 负值处理不当

3. **无回退机制**
   - 计算失败直接返回 None
   - 用户看不到任何数据
   - 体验不佳

**解决方案**：

**步骤 1：设计多层回退策略**

```python
# tradingagents/dataflows/realtime_metrics.py
async def get_realtime_pe_pb(
    self,
    symbol: str,
    source: str = "tushare"
) -> Dict[str, Optional[float]]:
    """
    获取实时PE/PB（多层回退策略）
    
    回退策略：
    1. 优先使用实时股价计算
    2. 降级使用数据库缓存值
    3. 最后使用历史数据
    """
    result = {
        "pe": None,
        "pb": None,
        "total_mv": None,
        "data_source": None
    }
    
    # 🔥 策略1：使用实时股价计算
    try:
        realtime_quote = await self._get_realtime_quote(symbol)
        if realtime_quote and realtime_quote.get("close"):
            pe, pb, total_mv = await self._calculate_from_realtime(
                symbol, 
                realtime_quote["close"],
                source
            )
            if pe or pb:
                result.update({
                    "pe": pe,
                    "pb": pb,
                    "total_mv": total_mv,
                    "data_source": "realtime_calculated"
                })
                return result
    except Exception as e:
        logger.warning(f"⚠️ 实时计算失败: {e}")
    
    # 🔥 策略2：使用数据库缓存值
    try:
        cached_data = await self._get_cached_pe_pb(symbol, source)
        if cached_data and (cached_data.get("pe") or cached_data.get("pb")):
            result.update({
                "pe": cached_data.get("pe"),
                "pb": cached_data.get("pb"),
                "total_mv": cached_data.get("total_mv"),
                "data_source": "database_cached"
            })
            return result
    except Exception as e:
        logger.warning(f"⚠️ 缓存查询失败: {e}")
    
    # 🔥 策略3：使用历史数据
    try:
        historical_data = await self._get_historical_pe_pb(symbol, source)
        if historical_data and (historical_data.get("pe") or historical_data.get("pb")):
            result.update({
                "pe": historical_data.get("pe"),
                "pb": historical_data.get("pb"),
                "total_mv": historical_data.get("total_mv"),
                "data_source": "historical_data"
            })
            return result
    except Exception as e:
        logger.warning(f"⚠️ 历史数据查询失败: {e}")
    
    logger.warning(f"⚠️ {symbol}: 所有策略均失败，返回空值")
    return result
```

**步骤 2：修复实时市值计算**

```python
# tradingagents/dataflows/realtime_metrics.py
async def _calculate_from_realtime(
    self,
    symbol: str,
    current_price: float,
    source: str
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """使用实时股价计算PE/PB/市值"""
    
    # 获取财务数据
    financial_data = await self._get_financial_data(symbol, source)
    if not financial_data:
        return None, None, None
    
    # 获取总股本（单位：万股）
    total_share = financial_data.get("total_share")
    if not total_share or total_share <= 0:
        logger.warning(f"⚠️ {symbol}: 总股本数据缺失或无效")
        return None, None, None
    
    # 🔥 计算实时市值（单位：亿元）
    # total_share 单位：万股
    # current_price 单位：元
    # 市值 = 总股本(万股) * 股价(元) / 10000 = 亿元
    total_mv = (total_share * current_price) / 10000
    
    # 🔥 计算PE（市盈率）
    net_profit = financial_data.get("net_profit")  # 单位：元
    if net_profit and net_profit > 0:
        # 市值(亿元) / 净利润(亿元) = PE
        net_profit_billion = net_profit / 100000000
        pe = total_mv / net_profit_billion
    else:
        pe = None
    
    # 🔥 计算PB（市净率）
    net_assets = financial_data.get("net_assets")  # 单位：元
    if net_assets and net_assets > 0:
        # 市值(亿元) / 净资产(亿元) = PB
        net_assets_billion = net_assets / 100000000
        pb = total_mv / net_assets_billion
    else:
        pb = None
    
    return pe, pb, total_mv
```

**效果**：
- ✅ 三层回退策略保证数据可用性
- ✅ 实时市值计算准确
- ✅ PE/PB 单位转换正确
- ✅ 详细的数据来源标识

---

### 3. K线图实时数据支持

#### 3.1 当天实时K线数据

**提交记录**：
- `389e7ddea` - feat: K线图支持当天实时数据 + 修复同步时间时区显示

**功能概述**：

K线图自动从 `market_quotes` 集合获取当天实时数据，实现盘中实时更新。

**实现方案**：

```python
# app/routers/stocks.py
@router.get("/{code}/kline", response_model=dict)
async def get_kline(
    code: str,
    period: str = "day",
    limit: int = 120,
    adj: str = "none"
):
    """获取K线数据（支持当天实时数据）"""
    
    # 获取历史K线数据
    items = await historical_service.get_kline_data(
        symbol=code,
        period=period,
        limit=limit,
        adj=adj
    )
    
    # 🔥 检查是否需要添加当天实时数据（仅针对日线）
    if period == "day" and items:
        # 获取当前时间（北京时间）
        tz = ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
        today_str = now.strftime("%Y%m%d")
        current_time = now.time()
        
        # 检查历史数据中是否已有当天的数据
        has_today_data = any(
            item.get("time") == today_str 
            for item in items
        )
        
        # 🔥 判断是否在交易时间内
        is_trading_time = (
            dtime(9, 30) <= current_time <= dtime(15, 0) and
            now.weekday() < 5  # 周一到周五
        )
        
        # 🔥 如果在交易时间内，或者收盘后但历史数据没有当天数据，则从 market_quotes 获取
        should_fetch_realtime = is_trading_time or not has_today_data
        
        if should_fetch_realtime:
            # 从 market_quotes 获取实时行情
            code_padded = code.zfill(6)
            realtime_quote = await market_quotes_coll.find_one(
                {"code": code_padded},
                {"_id": 0}
            )
            
            if realtime_quote:
                # 🔥 构造当天的K线数据
                today_kline = {
                    "time": today_str,
                    "open": float(realtime_quote.get("open", 0)),
                    "high": float(realtime_quote.get("high", 0)),
                    "low": float(realtime_quote.get("low", 0)),
                    "close": float(realtime_quote.get("close", 0)),
                    "volume": float(realtime_quote.get("volume", 0)),
                    "amount": float(realtime_quote.get("amount", 0)),
                }
                
                # 添加到结果中
                if has_today_data:
                    # 替换已有的当天数据
                    items = [item for item in items if item.get("time") != today_str]
                
                items.append(today_kline)
                items.sort(key=lambda x: x["time"])
                
                logger.info(f"✅ {code}: 添加当天实时K线数据")
    
    return {
        "code": code,
        "period": period,
        "limit": limit,
        "adj": adj,
        "source": "mongodb+market_quotes",
        "items": items
    }
```

**效果**：
- ✅ 交易时间内显示实时K线
- ✅ 收盘后自动补充当天数据
- ✅ 无需等待历史数据同步
- ✅ 用户体验显著提升

---

### 4. 实时行情同步状态追踪

#### 4.1 同步状态追踪和收盘后缓冲期

**提交记录**：
- `7fa9fd1af` - feat: 实时行情同步状态追踪和收盘后缓冲期
- `375a4eaca` - feat: 前端个股详情页显示实时行情同步状态
- `a7a0f5cba` - fix: 修复实时行情同步状态 API 路由冲突

**功能概述**：

添加实时行情同步状态追踪，让用户了解数据的新鲜度。

**实现方案**：

**步骤 1：后端状态追踪**

```python
# app/services/quotes_ingestion_service.py
class QuotesIngestionService:
    """实时行情同步服务"""
    
    def __init__(self):
        self.last_sync_time: Optional[datetime] = None
        self.sync_status: str = "idle"  # idle, syncing, success, error
        self.sync_error: Optional[str] = None
    
    async def sync_realtime_quotes(self):
        """同步实时行情"""
        try:
            self.sync_status = "syncing"
            self.sync_error = None
            
            # 🔥 判断是否在交易时间内（含收盘后30分钟缓冲期）
            if not self._is_sync_time():
                logger.info("⏸️ 非交易时间，跳过同步")
                self.sync_status = "idle"
                return
            
            # 同步数据
            await self._fetch_and_save_quotes()
            
            # 更新状态
            self.last_sync_time = datetime.now(ZoneInfo("Asia/Shanghai"))
            self.sync_status = "success"
            logger.info(f"✅ 实时行情同步成功: {self.last_sync_time}")
            
        except Exception as e:
            self.sync_status = "error"
            self.sync_error = str(e)
            logger.error(f"❌ 实时行情同步失败: {e}")
    
    def _is_sync_time(self) -> bool:
        """判断是否在同步时间内（交易时间 + 收盘后30分钟缓冲期）"""
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        current_time = now.time()
        
        # 周末不同步
        if now.weekday() >= 5:
            return False
        
        # 🔥 交易时间：9:30-15:00
        # 🔥 缓冲期：15:00-15:30（收盘后30分钟）
        return dtime(9, 30) <= current_time <= dtime(15, 30)
    
    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        return {
            "status": self.sync_status,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "error": self.sync_error,
            "is_trading_time": self._is_sync_time()
        }
```

**步骤 2：前端状态显示**

```vue
<!-- frontend/src/views/Stocks/Detail.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>实时行情</span>
        <!-- 🔥 同步状态指示器 -->
        <el-tag
          :type="syncStatusType"
          size="small"
          effect="plain"
        >
          <el-icon style="margin-right: 4px;">
            <component :is="syncStatusIcon" />
          </el-icon>
          {{ syncStatusText }}
        </el-tag>
      </div>
    </template>
    
    <!-- 行情数据 -->
    <div class="quote-data">
      ...
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { stockApi } from '@/api/stocks'

const syncStatus = ref<any>(null)

// 🔥 获取同步状态
const fetchSyncStatus = async () => {
  try {
    const response = await stockApi.getQuotesSyncStatus()
    syncStatus.value = response.data
  } catch (error) {
    console.error('获取同步状态失败:', error)
  }
}

// 🔥 状态显示
const syncStatusType = computed(() => {
  if (!syncStatus.value) return 'info'
  switch (syncStatus.value.status) {
    case 'success': return 'success'
    case 'syncing': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
})

const syncStatusText = computed(() => {
  if (!syncStatus.value) return '未知'
  const lastSyncTime = syncStatus.value.last_sync_time
    ? new Date(syncStatus.value.last_sync_time).toLocaleTimeString('zh-CN')
    : '从未同步'
  
  switch (syncStatus.value.status) {
    case 'success': return `已同步 (${lastSyncTime})`
    case 'syncing': return '同步中...'
    case 'error': return '同步失败'
    default: return '空闲'
  }
})

onMounted(() => {
  fetchSyncStatus()
  // 每30秒刷新一次状态
  setInterval(fetchSyncStatus, 30000)
})
</script>
```

**效果**：
- ✅ 用户可以看到数据同步状态
- ✅ 显示最后同步时间
- ✅ 收盘后30分钟缓冲期
- ✅ 自动刷新状态

---

### 5. 其他优化

#### 5.1 添加 symbol 字段

**提交记录**：
- `7bcc6d08e` - fix: 为 stock_basic_info 集合添加 symbol 字段
- `c0a3aadc2` - fix: 修复迁移脚本并验证 601899 股票信息

**功能概述**：

为 `stock_basic_info` 集合添加 `symbol` 字段（带市场前缀的完整代码）。

```python
# 示例
{
  "code": "000001",      # 6位代码
  "symbol": "sz000001",  # 带市场前缀
  "source": "tushare",
  ...
}
```

#### 5.2 基本面快照接口增强

**提交记录**：
- `41f5d7fdd` - feat: 增强基本面快照接口，添加市销率和财务指标
- `c68539e63` - feat: 基本面快照接口使用动态计算PS（市销率）

**改进内容**：

1. **添加市销率（PS）动态计算**
   ```python
   # 使用实时市值和TTM营业收入计算
   ps = total_mv / revenue_ttm if revenue_ttm else None
   ```

2. **添加更多财务指标**
   - 营业收入（TTM）
   - 净利润（TTM）
   - 净资产
   - ROE（净资产收益率）

#### 5.3 统一导出报告文件名格式

**提交记录**：
- `65c88a29f` - feat: 统一所有页面的导出报告文件名格式

**改进内容**：

```typescript
// 统一格式：TradingAgents_报告类型_股票代码_日期时间.pdf
const filename = `TradingAgents_${reportType}_${stockCode}_${timestamp}.pdf`

// 示例
// TradingAgents_分析报告_000001_20251028_143052.pdf
// TradingAgents_批量分析_20251028_143052.pdf
```

#### 5.4 股票名称获取增强

**提交记录**：
- `b7838214` - fix: 增强股票名称获取的错误处理和降级逻辑

**改进内容**：

```python
# 多层降级策略
# 1. 从 stock_basic_info 获取
# 2. 从 market_quotes 获取
# 3. 使用股票代码作为后备
```

---

## 📊 统计数据

### 提交统计（2025-10-28）
- **总提交数**: 25 个
- **修改文件数**: 60+ 个
- **新增代码**: ~3,500 行
- **删除代码**: ~500 行
- **净增代码**: ~3,000 行

### 功能分类
- **多数据源架构**: 6 项改进
- **实时数据**: 8 项增强
- **PE/PB计算**: 3 项优化
- **K线图**: 1 项新功能
- **其他优化**: 7 项改进

---

## 🔧 技术亮点

### 1. 多数据源隔离存储设计

**核心思路**：联合唯一索引 + 数据源优先级查询

```javascript
// 索引设计
db.stock_basic_info.createIndex({ "code": 1, "source": 1 }, { unique: true });

// 查询策略
source_priority = ["tushare", "multi_source", "akshare", "baostock"]
```

### 2. 实时PE/PB三层回退策略

**策略**：
1. 实时股价计算（最准确）
2. 数据库缓存值（次优）
3. 历史数据（保底）

### 3. K线图实时数据融合

**逻辑**：
- 交易时间内：从 `market_quotes` 获取实时数据
- 收盘后：补充当天数据（如果历史数据未同步）
- 非交易日：只显示历史数据

### 4. 同步状态追踪

**特性**：
- 实时状态更新
- 收盘后30分钟缓冲期
- 前端自动刷新

---

## 🎉 总结

### 今日成果

**提交统计**：
- ✅ **25 次提交**
- ✅ **60+ 个文件修改**
- ✅ **3,500+ 行新增代码**

**核心价值**：

1. **多数据源架构完善**
   - 彻底解决索引冲突
   - 支持数据源隔离存储
   - 统一数据源优先级

2. **实时数据能力提升**
   - K线图支持实时数据
   - PE/PB 实时计算优化
   - 同步状态可视化

3. **数据准确性改善**
   - 市值计算修复
   - 单位转换正确
   - 多层回退策略

4. **用户体验优化**
   - 实时数据展示
   - 同步状态追踪
   - 文件名格式统一

---

**感谢使用 TradingAgents-CN！** 🚀

如有问题或建议，欢迎在 [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues) 中反馈。

