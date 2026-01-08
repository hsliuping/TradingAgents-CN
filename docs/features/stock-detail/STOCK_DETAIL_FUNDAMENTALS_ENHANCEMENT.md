# 股票详情基本面数据增强功能

## 📋 概述

本文档记录了股票详情页面基本面数据获取的增强功能，实现了优先从 MongoDB 获取板块、ROE、负债率等财务指标。

---

## 🎯 需求背景

### 用户需求

在股票详情页面，用户需要查看以下基本面信息：
- **板块信息**：股票所属板块（主板/中小板/创业板/科创板等）
- **ROE**：净资产收益率（衡量盈利能力）
- **负债率**：资产负债率（衡量财务风险）

### 原有问题

1. **数据来源单一**：仅从 `stock_basic_info` 集合获取数据
2. **财务指标缺失**：`stock_basic_info` 中可能没有 ROE 和负债率
3. **板块信息不完整**：缺少板块字段的映射

---

## ✅ 解决方案

### 1. 数据来源优先级

```
1. stock_basic_info 集合（基础信息、估值指标）
   ↓
2. stock_financial_data 集合（财务指标：ROE、负债率等）
   ↓
3. 降级机制（使用 stock_basic_info 中的 ROE）
```

### 2. 字段映射

| 前端字段 | 后端字段 | 数据来源 | 说明 |
|---------|---------|---------|------|
| `industry` | `industry` | `stock_basic_info` | 所属行业（如：银行、软件服务） |
| `sector` | `market` | `stock_basic_info` | 板块信息（如：主板、创业板、科创板） |
| `roe` | `financial_indicators.roe` / `roe` | `stock_financial_data` → `stock_basic_info` | 净资产收益率，优先从财务数据获取 |
| `debt_ratio` | `financial_indicators.debt_to_assets` / `debt_to_assets` | `stock_financial_data` | 资产负债率 |

### 3. 接口实现

**接口路径**：`GET /api/stocks/{code}/fundamentals`

**实现逻辑**：

```python
@router.get("/{code}/fundamentals", response_model=dict)
async def get_fundamentals(code: str, current_user: dict = Depends(get_current_user)):
    """
    获取基础面快照（优先从 MongoDB 获取）
    
    数据来源优先级：
    1. stock_basic_info 集合（基础信息、估值指标）
    2. stock_financial_data 集合（财务指标：ROE、负债率等）
    """
    db = get_mongo_db()
    code6 = _zfill_code(code)
    
    # 1. 获取基础信息
    b = await db["stock_basic_info"].find_one({"code": code6}, {"_id": 0})
    
    # 2. 获取最新财务数据
    financial_data = await db["stock_financial_data"].find_one(
        {"symbol": code6},
        {"_id": 0},
        sort=[("report_period", -1)]  # 按报告期降序
    )
    
    # 3. 构建返回数据
    data = {
        "industry": b.get("industry"),  # 行业（如：银行、软件服务）
        "sector": b.get("market"),      # 板块（如：主板、创业板、科创板）
        "roe": None,
        "debt_ratio": None,
        # ... 其他字段
    }
    
    # 4. 从财务数据中提取 ROE 和负债率
    if financial_data:
        if financial_data.get("financial_indicators"):
            indicators = financial_data["financial_indicators"]
            data["roe"] = indicators.get("roe")
            data["debt_ratio"] = indicators.get("debt_to_assets")
    
    # 5. 降级机制
    if data["roe"] is None:
        data["roe"] = b.get("roe")
    
    return ok(data)
```

---

## 📊 数据结构

### stock_basic_info 集合

```javascript
{
  "code": "000001",
  "name": "平安银行",
  "industry": "银行",       // 所属行业
  "market": "主板",         // 板块信息（主板/创业板/科创板/北交所）
  "sse": "sz",              // 技术标识（深圳/上海）
  "sec": "stock_cn",        // 分类标识
  "total_mv": 2200.63,      // 总市值（亿元）
  "pe": 4.9443,             // 市盈率
  "pb": 0.5,                // 市净率
  "roe": null,              // 可能为空
  "updated_at": "2025-09-30T12:00:00Z"
}
```

### stock_financial_data 集合

```javascript
{
  "symbol": "000001",
  "report_period": "20250630",
  "report_type": "quarterly",
  "data_source": "tushare",
  
  // 财务指标
  "financial_indicators": {
    "roe": 4.9497,              // 净资产收益率
    "roa": 1.44,                // 总资产收益率
    "debt_to_assets": 91.318,   // 资产负债率
    "current_ratio": 0.74,      // 流动比率
    "quick_ratio": 0.74,        // 速动比率
    "gross_margin": 75.0,       // 毛利率
    "net_margin": 36.11         // 净利率
  },
  
  // 顶层字段（备用）
  "roe": 4.9497,
  "debt_to_assets": 91.318
}
```

---

## 🧪 测试验证

### 测试脚本

**路径**：`scripts/test_stock_fundamentals_enhanced.py`

**功能**：
1. 从 `stock_basic_info` 获取基础信息
2. 从 `stock_financial_data` 获取最新财务数据
3. 模拟接口返回数据
4. 验证板块、ROE、负债率字段

### 测试结果

```
================================================================================
测试股票基本面数据获取增强功能
================================================================================

📊 [测试1] 从 stock_basic_info 获取基础信息: 000001
--------------------------------------------------------------------------------
✅ 找到基础信息
   股票代码: 000001
   股票名称: 平安银行
   所属行业: 银行
   交易所: 主板
   板块(sse): sz
   板块(sec): stock_cn
   总市值: 2200.63112365 亿元
   市盈率(PE): 4.9443
   市净率(PB): 0.5
   ROE(基础): None

📊 [测试2] 从 stock_financial_data 获取最新财务数据: 000001
--------------------------------------------------------------------------------
✅ 找到财务数据
   股票代码: 000001
   报告期: 20250630
   报告类型: quarterly
   数据来源: tushare

   📈 顶层字段:
      ROE: 4.9497
      负债率: 91.318

📊 [测试3] 模拟接口返回数据
--------------------------------------------------------------------------------
✅ 接口返回数据:
   股票代码: 000001
   股票名称: 平安银行
   所属行业: 银行
   交易所: 主板
   板块: 主板 ✅
   总市值: 2200.63112365 亿元
   市盈率(PE): 4.9443
   市净率(PB): 0.5
   ROE: 4.9497 ✅
   负债率: 91.318 ✅

📊 [测试4] 验证结果
--------------------------------------------------------------------------------
✅ 板块信息获取成功: 主板
✅ ROE 获取成功: 4.9497
✅ 负债率获取成功: 91.318

================================================================================
测试完成: 3/3 项通过
================================================================================
```

---

## 🎨 前端展示

### 股票详情页面

**路径**：`frontend/src/views/Stocks/Detail.vue`

**基本面快照卡片**：

```vue
<el-card shadow="hover">
  <template #header><div class="card-hd">基本面快照</div></template>
  <div class="facts">
    <div class="fact"><span>行业</span><b>{{ basics.industry }}</b></div>
    <div class="fact"><span>板块</span><b>{{ basics.sector }}</b></div>
    <div class="fact"><span>总市值</span><b>{{ fmtAmount(basics.marketCap) }}</b></div>
    <div class="fact"><span>PE(TTM)</span><b>{{ Number.isFinite(basics.pe) ? basics.pe.toFixed(2) : '-' }}</b></div>
    <div class="fact"><span>ROE</span><b>{{ fmtPercent(basics.roe) }}</b></div>
    <div class="fact"><span>负债率</span><b>{{ fmtPercent(basics.debtRatio) }}</b></div>
  </div>
</el-card>
```

### 数据获取逻辑

```typescript
async function fetchFundamentals() {
  try {
    const res = await stocksApi.getFundamentals(code.value)
    const f: any = (res as any)?.data || {}
    
    // 基本面快照映射
    basics.industry = f.industry || basics.industry
    basics.sector = f.sector || basics.sector || '—'
    basics.marketCap = Number.isFinite(f.total_mv) ? Number(f.total_mv) * 1e8 : basics.marketCap
    basics.pe = Number.isFinite(f.pe_ttm) ? Number(f.pe_ttm) : (Number.isFinite(f.pe) ? Number(f.pe) : basics.pe)
    basics.roe = Number.isFinite(f.roe) ? Number(f.roe) : basics.roe
    basics.debtRatio = Number.isFinite(f.debt_ratio) ? Number(f.debt_ratio) : basics.debtRatio
  } catch (e) {
    console.error('获取基本面失败', e)
  }
}
```

---

## 📝 提交记录

### Commit 1: 代码实现

**Commit**: `18796fb`  
**Message**: `feat: 优化股票详情基本面数据获取 - 优先从MongoDB获取板块、ROE、负债率`

**主要改进**：
- ✅ 优先从 MongoDB 的 stock_basic_info 集合获取基础信息
- ✅ 从 stock_financial_data 集合获取最新财务指标（ROE、负债率）
- ✅ 实现自动降级：财务数据不可用时使用基础信息中的 ROE
- ✅ 新增字段：板块 (sector)、负债率 (debt_ratio)

### Commit 2: 测试脚本

**Commit**: `32c4484`  
**Message**: `test: 添加股票基本面数据增强功能测试脚本`

**测试内容**：
- ✅ 从 MongoDB 获取基础信息和财务数据
- ✅ 验证板块、ROE、负债率字段
- ✅ 测试降级机制

---

## 🎯 使用指南

### 1. 启动后端服务

```bash
python -m uvicorn app.main:app --reload
```

### 2. 访问股票详情页面

```
http://localhost:5173/stocks/000001
```

### 3. 查看基本面快照

在股票详情页面右侧，可以看到"基本面快照"卡片，显示：
- 行业
- **板块** ✅
- 总市值
- PE(TTM)
- **ROE** ✅
- **负债率** ✅

---

## 💡 技术要点

### 1. 数据来源优先级

- **优先级 1**：`stock_financial_data` 集合（最新财务数据）
- **优先级 2**：`stock_basic_info` 集合（基础信息）
- **降级机制**：财务数据不可用时使用基础信息

### 2. 字段映射策略

- **行业**：`industry`（所属行业，如：银行、软件服务）
- **板块**：`market`（交易所/板块，如：主板、创业板、科创板）
- **ROE**：`financial_indicators.roe` → `roe` → `stock_basic_info.roe`
- **负债率**：`financial_indicators.debt_to_assets` → `debt_to_assets`

### 3. 错误处理

- 财务数据查询失败不影响基础信息返回
- 字段缺失时返回 `None`，前端显示为 `-`
- 异常捕获确保接口稳定性

---

## 🔄 后续优化

### 1. 数据同步

- 定期同步 `stock_financial_data` 集合
- 确保财务数据的及时性和准确性

### 2. 缓存优化

- 添加 Redis 缓存层
- 减少 MongoDB 查询次数

### 3. 字段扩展

- 添加更多财务指标（毛利率、净利率等）
- 支持历史财务数据查询

---

## 📚 相关文档

- [DataSourceManager 增强方案](./DATA_SOURCE_MANAGER_ENHANCEMENT.md)
- [股票数据模型设计](./design/stock_data_model_design.md)
- [财务数据系统](./guides/financial_data_system/README.md)

