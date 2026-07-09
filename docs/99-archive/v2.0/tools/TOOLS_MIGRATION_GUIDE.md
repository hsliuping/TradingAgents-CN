# Tools迁移指南

**版本**: v2.0  
**日期**: 2025-12-15  
**状态**: 🚧 进行中

---

## 📋 概述

TradingAgentsCN v2.0引入了新的工具系统，提供：

1. ✅ 统一的工具注册机制
2. ✅ 自动化的工具发现
3. ✅ 更好的类型提示
4. ✅ 更简洁的代码（减少60-76%）

---

## 🔄 迁移映射表

### 1. 新闻工具

| 旧路径 | 新路径 | 状态 |
|--------|--------|------|
| `tradingagents.tools.unified_news_tool.UnifiedNewsAnalyzer` | `core.tools.implementations.news.get_stock_news_unified` | ⚠️ 废弃 |

**迁移步骤**：

**旧代码**：
```python
from tradingagents.tools.unified_news_tool import UnifiedNewsAnalyzer

analyzer = UnifiedNewsAnalyzer(toolkit)
news = analyzer.get_stock_news_unified(stock_code="000001", max_news=10)
```

**新代码（方式1 - 直接导入）**：
```python
from core.tools.implementations.news import get_stock_news_unified

news = get_stock_news_unified(ticker="000001", curr_date="2025-12-15")
```

**新代码（方式2 - 通过注册表）**：
```python
from core.tools import get_tool

tool = get_tool("get_stock_news_unified")
news = tool.invoke({"ticker": "000001", "curr_date": "2025-12-15"})
```

**注意事项**：
- ⚠️ 新工具目前**不支持MongoDB缓存**
- ⚠️ 新工具目前**不支持复杂的同步机制**
- ✅ 新工具代码更简洁（140行 vs 596行）

### 2. 技术指标计算库

| 旧路径 | 新路径 | 状态 |
|--------|--------|------|
| `tradingagents.tools.analysis.indicators` | `core.tools.implementations.technical.indicators` | ⚠️ 废弃 |

**迁移步骤**：

**旧代码**：
```python
from tradingagents.tools.analysis.indicators import ma, rsi, macd, add_all_indicators

# 计算MA
ma_values = ma(df['close'], n=20)

# 计算RSI（中国风格）
rsi_values = rsi(df['close'], n=14, method='china')

# 添加所有指标
df = add_all_indicators(df, rsi_style='china')
```

**新代码**：
```python
from core.tools.implementations.technical import ma, rsi, macd, add_all_indicators

# 完全相同的API，无需修改
ma_values = ma(df['close'], n=20)
rsi_values = rsi(df['close'], n=14, method='china')
df = add_all_indicators(df, rsi_style='china')
```

**注意事项**：
- ✅ API完全兼容，无需修改代码逻辑
- ✅ 支持所有3种RSI计算风格（ema/sma/china）
- ✅ 这是纯计算库，不注册为LangChain工具

### 3. 技术指标工具（LangChain工具）

| 旧路径 | 新路径 | 状态 |
|--------|--------|------|
| - | `core.tools.implementations.market.get_technical_indicators` | 🆕 新增 |

**使用方式**：

```python
from core.tools.implementations.market import get_technical_indicators

# 获取技术指标
indicators = get_technical_indicators(
    ticker="000001",
    indicators="macd,rsi_14,boll,kdj",
    start_date="2024-01-01",
    end_date="2025-12-15"
)
```

**特点**：
- ✅ 自动识别股票类型（A股/港股/美股）
- ✅ 自动获取历史数据
- ✅ 使用stockstats库计算指标
- ✅ 注册为LangChain工具，可被Agent调用

---

## 📝 完整迁移清单

### 阶段1: 更新导入语句 ✅

- [x] 更新新闻工具导入
- [x] 更新技术指标库导入
- [x] 测试导入是否正常

### 阶段2: 功能验证 🚧

- [ ] 测试新闻工具功能
- [ ] 测试技术指标计算
- [ ] 对比新旧工具输出结果

### 阶段3: 补充缺失功能 📋

**新闻工具需要补充**：
- [ ] MongoDB数据库缓存机制
- [ ] 同步机制（避免事件循环冲突）
- [ ] 更详细的日志记录

**技术指标工具需要确认**：
- [ ] 确认stockstats是否支持中国式RSI
- [ ] 如不支持，集成indicators.py的计算函数

### 阶段4: 清理旧代码 ⏰

**计划时间**: 2026-06-15（6个月后）

- [ ] 删除`tradingagents/tools/unified_news_tool.py`
- [ ] 删除`tradingagents/tools/analysis/indicators.py`
- [ ] 更新所有引用

---

## 🎯 推荐实践

### 1. 渐进式迁移

不要一次性迁移所有代码，建议：

1. 先迁移新功能
2. 逐步迁移现有功能
3. 保留旧代码3-6个月

### 2. 测试驱动

每次迁移后：

1. 运行单元测试
2. 对比新旧输出
3. 确认功能一致

### 3. 文档更新

迁移后及时更新：

1. API文档
2. 使用示例
3. 迁移记录

---

## ❓ 常见问题

### Q1: 新工具是否支持MongoDB缓存？

**A**: 目前不支持。如果需要缓存功能，可以：
1. 在应用层实现缓存
2. 等待后续版本支持
3. 暂时继续使用旧工具

### Q2: 技术指标计算结果是否一致？

**A**: 是的。新的indicators.py是旧文件的直接复制，API和计算逻辑完全一致。

### Q3: 何时删除旧工具？

**A**: 计划在2026-06-15（6个月后）删除。在此之前，旧工具会继续工作，但会发出废弃警告。

---

## 📞 获取帮助

如有问题，请：

1. 查看详细分析报告：`docs/design/v2.0/tools/TOOLS_MIGRATION_ANALYSIS.md`
2. 查看工具实现：`core/tools/implementations/`
3. 提交Issue或联系开发团队

---

**最后更新**: 2025-12-15

