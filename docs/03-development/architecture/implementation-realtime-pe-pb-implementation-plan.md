# 实时PE/PB计算实施方案

## 背景

用户反馈：当前的PE和PB不是实时更新数据，会影响分析结果。

**问题确认**：
- PE/PB数据来自 `stock_basic_info` 集合，需要手动触发同步
- 数据使用的是前一个交易日的收盘数据
- 股价大幅波动时，PE/PB会有明显偏差

**解决方案**：
- 利用现有的 `market_quotes` 集合（每30秒更新一次）
- 基于实时价格和最新财报计算实时PE/PB
- 无需额外数据源或基础设施

## 影响范围

### 后端接口

| 接口 | 文件 | 影响 | 优先级 |
|-----|------|------|--------|
| **分析数据流** | `tradingagents/dataflows/optimized_china_data.py` | 分析报告中的PE/PB | 🔴 高 |
| **股票详情-基本面** | `app/routers/stocks.py` - `get_fundamentals()` | 详情页基本面快照 | 🔴 高 |
| **股票筛选** | `app/routers/screening.py` | 筛选结果中的PE/PB | 🔴 高 |
| **股票关注列表列表** | `app/routers/favorites.py` | 股票关注列表的PE/PB | 🟡 中 |

### 前端页面

| 页面 | 文件 | 使用场景 | 优先级 |
|-----|------|---------|--------|
| **股票详情页** | `frontend/src/views/Stocks/Detail.vue` | 基本面快照显示PE | 🔴 高 |
| **股票筛选页** | `frontend/src/views/Screening/index.vue` | 筛选条件和结果列表 | 🔴 高 |
| **股票关注列表页面** | `frontend/src/views/Favorites/index.vue` | 股票关注列表列表（如果显示PE/PB） | 🟡 中 |
| **分析报告** | 各分析相关页面 | 报告中的估值指标 | 🔴 高 |

## 实施步骤

### 第一步：创建实时计算工具函数

**文件**：`tradingagents/dataflows/realtime_metrics.py`（新建）

```python
"""
实时估值指标计算模块
基于实时行情和财务数据计算PE/PB等指标
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def calculate_realtime_pe_pb(
    symbol: str,
    db_client=None
) -> Optional[Dict[str, Any]]:
    """
    基于实时行情和财务数据计算PE/PB
    
    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选，用于同步调用）
    
    Returns:
        {
            "pe": 22.5,              # 实时市盈率
            "pb": 3.2,               # 实时市净率
            "pe_ttm": 23.1,          # 实时市盈率（TTM）
            "price": 11.0,           # 当前价格
            "market_cap": 110.5,     # 实时市值（亿元）
            "updated_at": "2025-10-14T10:30:00",
            "source": "realtime_calculated",
            "is_realtime": True
        }
        如果计算失败返回 None
    """
    try:
        # 获取数据库连接
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                logger.warning("MongoDB不可用，无法计算实时PE/PB")
                return None
            db_client = db_manager.get_mongodb_client()
        
        db = db_client['tradingagents']
        code6 = str(symbol).zfill(6)
        
        # 1. 获取实时行情（market_quotes）
        quote = db.market_quotes.find_one({"code": code6})
        if not quote:
            logger.debug(f"未找到股票 {code6} 的实时行情")
            return None
        
        realtime_price = quote.get("close")
        if not realtime_price or realtime_price <= 0:
            logger.debug(f"股票 {code6} 的实时价格无效: {realtime_price}")
            return None
        
        # 2. 获取基础信息和财务数据（stock_basic_info）
        basic_info = db.stock_basic_info.find_one({"code": code6})
        if not basic_info:
            logger.debug(f"未找到股票 {code6} 的基础信息")
            return None
        
        # 获取财务数据
        total_shares = basic_info.get("total_share")  # 总股本（万股）
        net_profit = basic_info.get("net_profit")     # 净利润（万元）
        total_equity = basic_info.get("total_hldr_eqy_exc_min_int")  # 净资产（万元）
        
        if not total_shares or total_shares <= 0:
            logger.debug(f"股票 {code6} 的总股本无效: {total_shares}")
            return None
        
        # 3. 计算实时市值（万元）
        realtime_market_cap = realtime_price * total_shares
        
        # 4. 计算实时PE
        pe = None
        pe_ttm = None
        if net_profit and net_profit > 0:
            pe = realtime_market_cap / net_profit
            pe_ttm = pe  # 如果有TTM净利润，可以单独计算
        
        # 5. 计算实时PB
        pb = None
        if total_equity and total_equity > 0:
            pb = realtime_market_cap / total_equity
        
        # 6. 构建返回结果
        result = {
            "pe": round(pe, 2) if pe else None,
            "pb": round(pb, 2) if pb else None,
            "pe_ttm": round(pe_ttm, 2) if pe_ttm else None,
            "price": round(realtime_price, 2),
            "market_cap": round(realtime_market_cap / 10000, 2),  # 转换为亿元
            "updated_at": quote.get("updated_at"),
            "source": "realtime_calculated",
            "is_realtime": True,
            "note": "基于实时价格和最新财报计算"
        }
        
        logger.debug(f"股票 {code6} 实时PE/PB计算成功: PE={result['pe']}, PB={result['pb']}")
        return result
        
    except Exception as e:
        logger.error(f"计算股票 {symbol} 的实时PE/PB失败: {e}", exc_info=True)
        return None


def validate_pe_pb(pe: Optional[float], pb: Optional[float]) -> bool:
    """
    验证PE/PB是否在合理范围内
    
    Args:
        pe: 市盈率
        pb: 市净率
    
    Returns:
        bool: 是否合理
    """
    # PE合理范围：-100 到 1000（允许负值，因为亏损企业PE为负）
    if pe is not None and (pe < -100 or pe > 1000):
        logger.warning(f"PE异常: {pe}")
        return False
    
    # PB合理范围：0.1 到 100
    if pb is not None and (pb < 0.1 or pb > 100):
        logger.warning(f"PB异常: {pb}")
        return False
    
    return True


async def get_pe_pb_with_fallback(
    symbol: str,
    db_client=None
) -> Dict[str, Any]:
    """
    获取PE/PB，优先使用实时计算，失败时降级到静态数据
    
    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选）
    
    Returns:
        {
            "pe": 22.5,
            "pb": 3.2,
            "pe_ttm": 23.1,
            "source": "realtime_calculated" | "daily_basic",
            "is_realtime": True | False,
            "updated_at": "2025-10-14T10:30:00"
        }
    """
    # 1. 尝试实时计算
    realtime_metrics = await calculate_realtime_pe_pb(symbol, db_client)
    if realtime_metrics:
        # 验证数据合理性
        if validate_pe_pb(realtime_metrics.get('pe'), realtime_metrics.get('pb')):
            return realtime_metrics
        else:
            logger.warning(f"股票 {symbol} 的实时PE/PB数据异常，降级到静态数据")
    
    # 2. 降级到静态数据
    try:
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                return {}
            db_client = db_manager.get_mongodb_client()
        
        db = db_client['tradingagents']
        code6 = str(symbol).zfill(6)
        
        basic_info = db.stock_basic_info.find_one({"code": code6})
        if not basic_info:
            return {}
        
        return {
            "pe": basic_info.get("pe"),
            "pb": basic_info.get("pb"),
            "pe_ttm": basic_info.get("pe_ttm"),
            "pb_mrq": basic_info.get("pb_mrq"),
            "source": "daily_basic",
            "is_realtime": False,
            "updated_at": basic_info.get("updated_at"),
            "note": "使用最近一个交易日的数据"
        }
        
    except Exception as e:
        logger.error(f"获取股票 {symbol} 的静态PE/PB失败: {e}")
        return {}
```

### 第二步：修改后端接口

#### 2.1 修改股票详情接口

**文件**：`app/routers/stocks.py` - `get_fundamentals()`

**修改位置**：第120-124行

**修改前**：
```python
# 估值指标（来自 stock_basic_info）
"pe": b.get("pe"),
"pb": b.get("pb"),
"pe_ttm": b.get("pe_ttm"),
"pb_mrq": b.get("pb_mrq"),
```

**修改后**：
```python
# 估值指标（优先使用实时计算）
from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback
realtime_metrics = await get_pe_pb_with_fallback(code6, db.client)

"pe": realtime_metrics.get("pe") or b.get("pe"),
"pb": realtime_metrics.get("pb") or b.get("pb"),
"pe_ttm": realtime_metrics.get("pe_ttm") or b.get("pe_ttm"),
"pb_mrq": realtime_metrics.get("pb_mrq") or b.get("pb_mrq"),
"pe_source": realtime_metrics.get("source", "unknown"),
"pe_is_realtime": realtime_metrics.get("is_realtime", False),
"pe_updated_at": realtime_metrics.get("updated_at"),
```

#### 2.2 修改股票筛选服务

**文件**：`app/services/enhanced_screening_service.py`

**需要修改的地方**：
1. 在返回筛选结果时，为每个股票计算实时PE/PB
2. 批量计算以提高性能

**实现方案**：
```python
async def enrich_results_with_realtime_metrics(self, results: List[Dict]) -> List[Dict]:
    """为筛选结果添加实时PE/PB"""
    from tradingagents.dataflows.realtime_metrics import calculate_realtime_pe_pb
    
    for item in results:
        code = item.get("code") or item.get("symbol")
        if code:
            realtime_metrics = await calculate_realtime_pe_pb(code, self.db.client)
            if realtime_metrics:
                item["pe"] = realtime_metrics.get("pe") or item.get("pe")
                item["pb"] = realtime_metrics.get("pb") or item.get("pb")
                item["pe_ttm"] = realtime_metrics.get("pe_ttm") or item.get("pe_ttm")
                item["pe_is_realtime"] = True
    
    return results
```

### 第三步：修改分析数据流

**文件**：`tradingagents/dataflows/optimized_china_data.py`

**修改位置**：第948-1027行（PE/PB获取逻辑）

**修改方案**：
```python
# 优先使用实时计算的PE/PB
from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback

realtime_metrics = await get_pe_pb_with_fallback(stock_code)
if realtime_metrics and realtime_metrics.get('pe'):
    metrics["pe"] = f"{realtime_metrics['pe']:.1f}倍"
    metrics["pe_source"] = realtime_metrics.get('source')
    metrics["pe_updated_at"] = realtime_metrics.get('updated_at')
    if realtime_metrics.get('is_realtime'):
        metrics["pe"] += " (实时)"
else:
    # 降级到原有逻辑
    # ... 保持原有代码
```

### 第四步：前端显示优化

#### 4.1 股票详情页

**文件**：`frontend/src/views/Stocks/Detail.vue`

**修改位置**：第184行

**修改前**：
```vue
<div class="fact"><span>PE(TTM)</span><b>{{ Number.isFinite(basics.pe) ? basics.pe.toFixed(2) : '-' }}</b></div>
```

**修改后**：
```vue
<div class="fact">
  <span>PE(TTM)</span>
  <b>
    {{ Number.isFinite(basics.pe) ? basics.pe.toFixed(2) : '-' }}
    <el-tag v-if="basics.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
  </b>
</div>
```

#### 4.2 股票筛选页

**文件**：`frontend/src/views/Screening/index.vue`

**修改位置**：第271-283行

**修改后**：
```vue
<el-table-column prop="pe" label="市盈率" width="120" align="right">
  <template #default="{ row }">
    <span v-if="row.pe">
      {{ row.pe?.toFixed(2) }}
      <el-tag v-if="row.pe_is_realtime" type="success" size="small">实时</el-tag>
    </span>
    <span v-else class="text-gray-400">-</span>
  </template>
</el-table-column>

<el-table-column prop="pb" label="市净率" width="120" align="right">
  <template #default="{ row }">
    <span v-if="row.pb">
      {{ row.pb?.toFixed(2) }}
      <el-tag v-if="row.pe_is_realtime" type="success" size="small">实时</el-tag>
    </span>
    <span v-else class="text-gray-400">-</span>
  </template>
</el-table-column>
```

## 测试计划

### 单元测试

**文件**：`tests/dataflows/test_realtime_metrics.py`（新建）

```python
import pytest
from tradingagents.dataflows.realtime_metrics import (
    calculate_realtime_pe_pb,
    validate_pe_pb,
    get_pe_pb_with_fallback
)

def test_validate_pe_pb():
    """测试PE/PB验证"""
    assert validate_pe_pb(20.5, 3.2) == True
    assert validate_pe_pb(1500, 3.2) == False  # PE过大
    assert validate_pe_pb(20.5, 150) == False  # PB过大

@pytest.mark.asyncio
async def test_calculate_realtime_pe_pb():
    """测试实时PE/PB计算"""
    # 需要mock MongoDB数据
    pass
```

### 集成测试

1. **测试股票详情接口**
   ```bash
   curl -H "Authorization: Bearer <token>" \
        http://localhost:8000/api/stocks/000001/fundamentals
   ```
   
   验证返回数据包含：
   - `pe_is_realtime: true`
   - `pe_source: "realtime_calculated"`

2. **测试股票筛选接口**
   ```bash
   curl -X POST -H "Authorization: Bearer <token>" \
        -H "Content-Type: application/json" \
        -d '{"conditions": {"logic": "AND", "children": []}}' \
        http://localhost:8000/api/screening/screen
   ```
   
   验证返回的股票列表中PE/PB是实时计算的

3. **测试分析功能**
   - 触发单股分析
   - 检查分析报告中的PE/PB是否使用实时数据

### 性能测试

1. **单个股票计算性能**
   - 目标：< 50ms

2. **批量计算性能（100只股票）**
   - 目标：< 2s

3. **筛选接口性能**
   - 目标：与现有性能相当（增加< 20%耗时）

## 上线计划

### 第一阶段：核心功能（1天）

- [x] 创建 `realtime_metrics.py` 工具模块
- [ ] 修改股票详情接口
- [ ] 修改分析数据流
- [ ] 基本测试验证

### 第二阶段：完善功能（2天）

- [ ] 修改股票筛选服务
- [ ] 前端显示优化
- [ ] 添加数据时效性标识
- [ ] 完整测试

### 第三阶段：优化和监控（1周）

- [ ] 添加缓存机制
- [ ] 性能优化
- [ ] 监控和告警
- [ ] 文档完善

## 风险和注意事项

### 风险1：性能影响

**风险**：实时计算可能增加接口响应时间

**缓解措施**：
- 添加30秒缓存
- 批量计算优化
- 异步计算

### 风险2：数据准确性

**风险**：计算结果可能与官方数据有偏差

**缓解措施**：
- 添加数据验证
- 明确标注数据来源
- 提供降级方案

### 风险3：兼容性

**风险**：可能影响现有功能

**缓解措施**：
- 保持向后兼容
- 渐进式上线
- 充分测试

## 总结

本方案利用现有的实时行情数据（30秒更新），无需额外基础设施，即可实现PE/PB的实时计算。

**核心优势**：
- ✅ 数据实时性从"每日"提升到"30秒"
- ✅ 无需额外数据源
- ✅ 实现简单，风险可控
- ✅ 性能影响小

**预期效果**：
- 分析报告更准确
- 投资决策更可靠
- 用户体验更好

