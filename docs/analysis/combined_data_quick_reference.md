# combined_data 快速参考

## 🎯 什么是 combined_data？

`combined_data` 是基本面分析师调用 `get_stock_fundamentals_unified` 工具时返回的**字符串格式**的综合数据。

## 📊 数据来源（重要！）

### ✅ MongoDB 优先策略（A股）

**系统优先从 MongoDB 获取数据，而不是直接调用 API！**

```
优先级顺序：
1️⃣ MongoDB 数据库（最高优先级）
   ├─ market_quotes        → 实时股价
   ├─ stock_financial_data → 财务指标（ROE、负债率等）
   ├─ stock_basic_info     → 基础信息（行业、PE、PB等）
   └─ stock_daily_data     → 历史交易数据

2️⃣ API 数据源（降级策略）
   ├─ AKShare API
   ├─ Tushare API
   └─ BaoStock API
```

### 为什么 MongoDB 优先？

- ⚡ **速度快**：本地查询比API快10-100倍
- 🛡️ **更稳定**：不受API限流影响
- 💰 **成本低**：减少API调用费用
- 📦 **离线可用**：API故障时仍可工作

## 📦 包含的数据内容

### 1. 头部信息
```
股票类型: 中国A股/港股/美股
货币: 人民币(¥)/港币(HK$)/美元(USD)
分析日期: 2025-11-04
数据深度级别: basic/standard/full/detailed/comprehensive
```

### 2. 价格数据（A股）
```
开盘价、最高价、最低价、收盘价
成交量、成交额
涨跌幅、换手率
```

### 3. 基础信息
```
股票代码、股票名称
所属行业、上市板块
交易所信息
```

### 4. 估值指标
```
市盈率 (PE)    - 衡量估值水平
市净率 (PB)    - 衡量资产价值
市销率 (PS)    - 衡量销售能力
总市值         - 公司总价值
流通市值       - 可交易股份市值
```

### 5. 财务指标
```
净资产收益率 (ROE)      - 盈利能力
总资产收益率 (ROA)      - 资产效率
资产负债率              - 财务风险
流动比率/速动比率        - 偿债能力
毛利率/净利率           - 盈利质量
```

### 6. 盈利能力
```
营业收入
净利润
同比增长率
每股收益 (EPS)
```

### 7. 成长性分析
```
营收增长率
利润增长率
行业地位
```

### 8. 风险评估
```
财务风险等级: 低/中/高
经营风险等级: 低/中/高
市场风险等级: 低/中/高
```

### 9. 投资建议
```
估值水平: 低估/合理/高估
合理价位区间: XX - XX 元
目标价位: XX 元
投资建议: 买入/持有/卖出
```

## 🔄 数据获取流程（A股）

```
1. 检查 MongoDB 是否可用
   ├─ 是 → 从 MongoDB 获取数据
   │      ├─ market_quotes (实时股价)
   │      ├─ stock_financial_data (财务指标)
   │      └─ stock_basic_info (基础信息)
   │
   └─ 否 → 降级到 API

2. MongoDB 数据不完整？
   └─ 降级到 API
      ├─ 尝试 AKShare API
      ├─ 失败 → 尝试 Tushare API
      └─ 失败 → 尝试 BaoStock API

3. 组合所有数据
   └─ 返回格式化的 combined_data 字符串
```

## 💡 实际示例

### 输入参数
```python
ticker = "000001"  # 平安银行
start_date = "2025-05-28"
end_date = "2025-11-04"
curr_date = "2025-11-04"
```

### 返回的 combined_data（简化版）
```markdown
# 000001 基本面分析数据

**股票类型**: 中国A股
**货币**: 人民币 (¥)
**分析日期**: 2025-11-04
**数据深度级别**: standard

## A股当前价格信息
股票代码: 000001
股票名称: 平安银行
收盘价: 13.45 元
涨跌幅: +1.2%

## A股基本面财务数据
### 估值指标
- 市盈率 (PE): 4.94
- 市净率 (PB): 0.50
- 总市值: 2200.63 亿元

### 财务指标
- 净资产收益率 (ROE): 4.95%
- 资产负债率: 91.32%

### 投资建议
- 估值水平: 低估
- 投资建议: 买入
```

## 🔑 关键要点

1. **数据格式**：字符串类型，使用 Markdown 格式
2. **MongoDB 优先**：A股数据优先从 MongoDB 获取
3. **自动降级**：MongoDB 失败时自动切换到 API
4. **数据完整性**：某些字段可能为空或"待分析"
5. **货币单位**：根据市场自动使用对应货币

## 📚 相关文档

- 详细分析：`docs/analysis/combined_data_structure_analysis.md`
- 代码位置：`tradingagents/agents/analysts/fundamentals_analyst.py` (第 422-427 行)
- 工具实现：`tradingagents/agents/utils/agent_utils.py` (第 770-1164 行)

## 🔧 环境变量

- `TA_USE_APP_CACHE=true` - 启用 MongoDB 缓存（推荐）
- `TA_USE_APP_CACHE=false` - 直接使用 API

## 📊 MongoDB 集合

| 集合名称 | 用途 | 关键字段 |
|---------|------|---------|
| `market_quotes` | 实时行情 | code, close, open, high, low |
| `stock_financial_data` | 财务数据 | code, roe, debt_to_assets |
| `stock_basic_info` | 基础信息 | code, name, industry, pe, pb |
| `stock_daily_data` | 历史数据 | code, date, close, volume |

## ⚡ 性能对比

| 数据源 | 平均响应时间 | 稳定性 | 成本 |
|--------|-------------|--------|------|
| MongoDB | 10-50ms | ⭐⭐⭐⭐⭐ | 免费 |
| AKShare API | 500-2000ms | ⭐⭐⭐⭐ | 免费 |
| Tushare API | 300-1000ms | ⭐⭐⭐⭐ | 付费 |

**结论**：MongoDB 比 API 快 10-100 倍！

