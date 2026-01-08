# 研究深度映射错误修复文档

## 📋 问题描述

用户报告在日志中看到 `**数据深度级别**: full`，但前端选择的是 **3级深度（标准）**。

### 问题现象

**用户选择**：
- 研究深度：3级 - 标准分析

**日志显示**：
```
**数据深度级别**: full
```

**预期显示**：
```
**数据深度级别**: standard
```

### 根本原因

**问题定位**：`tradingagents/agents/utils/agent_utils.py` 第 761-786 行

在 `get_stock_fundamentals_unified()` 方法中，`research_depth` 到 `data_depth` 的映射关系不正确：

**修复前的映射**：
```python
elif research_depth == "标准":
    # 标准分析：获取完整数据
    data_depth = "full"  # ❌ 错误：标准分析被映射到 full
    logger.info(f"🔧 [分析级别] 标准分析模式：获取完整数据")
```

**问题**：
1. 前端传递 `research_depth = "标准"`（对应3级深度）
2. 后端将 "标准" 映射到 `data_depth = "full"`
3. `data_depth = "full"` 又被映射到 `analysis_modules = "full"`
4. 最终日志显示 `**数据深度级别**: full`

**正确的映射关系应该是**：
- 1级（快速） → basic
- 2级（基础） → standard
- 3级（标准） → standard（不是 full！）
- 4级（深度） → full
- 5级（全面） → comprehensive

## ✅ 修复方案

### 修改文件

**文件**：`tradingagents/agents/utils/agent_utils.py` (第 761-786 行)

### 修改内容 1：修正 research_depth → data_depth 映射

```python
# 根据分析级别调整数据获取策略
# 🔧 修正映射关系：data_depth 应该与 research_depth 保持一致
if research_depth == "快速":
    # 快速分析：获取基础数据，减少数据源调用
    data_depth = "basic"
    logger.info(f"🔧 [分析级别] 快速分析模式：获取基础数据")
elif research_depth == "基础":
    # 基础分析：获取标准数据
    data_depth = "standard"
    logger.info(f"🔧 [分析级别] 基础分析模式：获取标准数据")
elif research_depth == "标准":
    # 标准分析：获取标准数据（不是full！）
    data_depth = "standard"  # ✅ 修正：标准分析应该映射到 standard
    logger.info(f"🔧 [分析级别] 标准分析模式：获取标准数据")
elif research_depth == "深度":
    # 深度分析：获取完整数据
    data_depth = "full"  # ✅ 修正：深度分析才映射到 full
    logger.info(f"🔧 [分析级别] 深度分析模式：获取完整数据")
elif research_depth == "全面":
    # 全面分析：获取最全面的数据，包含所有可用数据源
    data_depth = "comprehensive"
    logger.info(f"🔧 [分析级别] 全面分析模式：获取最全面数据")
else:
    # 默认使用标准分析
    data_depth = "standard"  # ✅ 修正：默认也应该是 standard
    logger.info(f"🔧 [分析级别] 未知级别，使用标准分析模式")
```

### 修改内容 2：修正 data_depth → analysis_modules 映射

**文件**：`tradingagents/agents/utils/agent_utils.py` (第 818-835 行)

```python
# 基本面分析优化：不需要大量历史数据，只需要当前价格和财务数据
# 根据数据深度级别设置不同的分析模块数量，而非历史数据范围
# 🔧 修正映射关系：analysis_modules 应该与 data_depth 保持一致
if data_depth == "basic":  # 快速分析：基础模块
    analysis_modules = "basic"
    logger.info(f"📊 [基本面策略] 快速分析模式：获取基础财务指标")
elif data_depth == "standard":  # 基础/标准分析：标准模块
    analysis_modules = "standard"
    logger.info(f"📊 [基本面策略] 标准分析模式：获取标准财务分析")
elif data_depth == "full":  # 深度分析：完整模块
    analysis_modules = "full"
    logger.info(f"📊 [基本面策略] 深度分析模式：获取完整基本面分析")
elif data_depth == "comprehensive":  # 全面分析：综合模块
    analysis_modules = "comprehensive"
    logger.info(f"📊 [基本面策略] 全面分析模式：获取综合基本面分析")
else:
    analysis_modules = "standard"  # ✅ 修正：默认标准分析
    logger.info(f"📊 [基本面策略] 默认模式：获取标准基本面分析")
```

## 📈 修复效果对比

### 修复前

| 前端选择 | research_depth | data_depth | analysis_modules | 日志显示 | 正确性 |
|---------|---------------|-----------|-----------------|---------|--------|
| 1级（快速） | "快速" | basic | basic | basic | ✅ 正确 |
| 2级（基础） | "基础" | standard | standard | standard | ✅ 正确 |
| 3级（标准） | "标准" | **full** | **full** | **full** | ❌ 错误 |
| 4级（深度） | "深度" | detailed | detailed | detailed | ⚠️ 不一致 |
| 5级（全面） | "全面" | comprehensive | comprehensive | comprehensive | ✅ 正确 |

### 修复后

| 前端选择 | research_depth | data_depth | analysis_modules | 日志显示 | 正确性 |
|---------|---------------|-----------|-----------------|---------|--------|
| 1级（快速） | "快速" | basic | basic | basic | ✅ 正确 |
| 2级（基础） | "基础" | standard | standard | standard | ✅ 正确 |
| 3级（标准） | "标准" | **standard** | **standard** | **standard** | ✅ 正确 |
| 4级（深度） | "深度" | **full** | **full** | **full** | ✅ 正确 |
| 5级（全面） | "全面" | comprehensive | comprehensive | comprehensive | ✅ 正确 |

## 🔍 技术细节

### 前端映射

**文件**：`frontend/src/views/Analysis/SingleAnalysis.vue` (第 1572-1575 行)

```javascript
const getDepthDescription = (depth: number) => {
  const descriptions = ['快速', '基础', '标准', '深度', '全面']
  return descriptions[depth - 1] || '标准'
}
```

**映射关系**：
- 1 → "快速"
- 2 → "基础"
- 3 → "标准"
- 4 → "深度"
- 5 → "全面"

### 后端映射链

**完整的映射链**：
```
前端选择 → research_depth → data_depth → analysis_modules → 日志显示
```

**示例（3级标准分析）**：
```
修复前：3 → "标准" → "full" → "full" → "full" ❌
修复后：3 → "标准" → "standard" → "standard" → "standard" ✅
```

## 🎯 修复原则

1. **一致性**：`data_depth` 应该与 `research_depth` 保持语义一致
2. **清晰性**：映射关系应该清晰明确，避免歧义
3. **可维护性**：使用统一的命名规范，便于理解和维护

### 修正后的映射规则

| 级别 | 中文名称 | data_depth | analysis_modules | 说明 |
|-----|---------|-----------|-----------------|------|
| 1 | 快速 | basic | basic | 最基础的数据 |
| 2 | 基础 | standard | standard | 标准数据 |
| 3 | 标准 | standard | standard | 标准数据（与基础相同） |
| 4 | 深度 | full | full | 完整数据 |
| 5 | 全面 | comprehensive | comprehensive | 最全面的数据 |

**注意**：2级（基础）和 3级（标准）都映射到 `standard`，这是合理的，因为它们都是标准级别的分析，只是名称不同。

## 📝 修复日期

2025-10-13

## 🎉 总结

### 问题根源
- `research_depth = "标准"` 被错误地映射到 `data_depth = "full"`

### 修复方案
- 修正映射关系：`"标准" → "standard"`，`"深度" → "full"`

### 修复效果
- ✅ 日志显示与用户选择一致
- ✅ 数据获取策略与分析级别匹配
- ✅ 映射关系清晰明确

### 后续建议
1. 考虑统一前端和后端的级别命名（都使用数字或都使用中文）
2. 添加单元测试验证映射关系
3. 在文档中明确说明各级别的数据获取策略

---

**相关文档**：
- `docs/trading_date_range_fix.md` - 交易日期范围修复
- `docs/estimated_total_time_fix.md` - 预估总时长修复

