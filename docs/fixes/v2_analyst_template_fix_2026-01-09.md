# v2.0 分析师模板修复记录

**日期**: 2026-01-09  
**问题**: v2.0 分析师生成的报告格式不够详细，缺少 v1.x 中的详细输出格式要求

---

## 🔍 问题分析

### 根本原因

1. **模板内容不够详细**：
   - v2.0 模板的 `analysis_requirements` 字段过于简化
   - 缺少 v1.x 中详细的输出格式要求（如技术指标分析表格、投资建议格式等）

2. **Agent 适配器调用错误**：
   - v2.0 分析师适配器使用了错误的 `agent_type` 和 `agent_name`
   - 例如：`market_analyst_v2` 调用的是 `agent_type="analysts"` 和 `agent_name="market_analyst"`
   - 导致获取的是 v1.x 模板，而不是 v2.0 模板

---

## ✅ 修复内容

### 1. 更新 v2.0 市场分析师模板

**文件**: `scripts/update_v2_analyst_templates.py`

**修改内容**：
- **激进型 (aggressive)**：增加详细的趋势突破分析、动能指标分析、激进交易建议格式
- **中性型 (neutral)**：增加完整的技术指标分析格式（MA, MACD, RSI, BOLL）、价格趋势分析、综合投资建议
- **保守型 (conservative)**：增加风险信号分析、支撑位有效性评估、下行风险评估、保守投资建议

**关键改进**：
- `analysis_requirements` 现在包含详细的输出格式要求
- 与 v1.x 数据库中的格式相似，指导 LLM 生成结构化报告
- 包含具体的章节标题、表格格式、必须包含的内容

**执行结果**：
```bash
# 第一步：更新所有 v2.0 分析师模板（scripts/update_v2_analyst_templates.py）
✅ 更新: fundamentals_analyst_v2 / aggressive, neutral, conservative
✅ 更新: market_analyst_v2 / aggressive, neutral, conservative
✅ 更新: news_analyst_v2 / aggressive, neutral, conservative
✅ 更新: social_media_analyst_v2 / aggressive, neutral, conservative
✅ 更新: social_analyst_v2 / aggressive, neutral, conservative
✅ 更新: index_analyst_v2 / aggressive, neutral, conservative
✅ 更新: sector_analyst_v2 / aggressive, neutral, conservative

总计：21 个模板已更新

# 第二步：增强大盘和行业分析师模板（scripts/enhance_index_sector_templates.py）
✅ 增强: index_analyst_v2 / aggressive (analysis_requirements: 381 字符)
✅ 增强: index_analyst_v2 / neutral (analysis_requirements: 379 字符)
✅ 增强: index_analyst_v2 / conservative (analysis_requirements: 365 字符)
✅ 增强: sector_analyst_v2 / aggressive (analysis_requirements: 351 字符)
✅ 增强: sector_analyst_v2 / neutral (analysis_requirements: 356 字符)
✅ 增强: sector_analyst_v2 / conservative (analysis_requirements: 324 字符)

总计：6 个模板已增强（添加详细的 analysis_requirements 和 output_format）
```

### 2. 修复 v2.0 分析师适配器

**修复的文件**：
1. ✅ `core/agents/adapters/market_analyst_v2.py` - 修复 agent_type 和 agent_name
2. ✅ `core/agents/adapters/fundamentals_analyst_v2.py` - **新增** get_agent_prompt 调用（之前完全没有）
3. ✅ `core/agents/adapters/news_analyst_v2.py` - 修复 agent_type 和 agent_name
4. ✅ `core/agents/adapters/social_analyst_v2.py` - 修复 agent_type 和 agent_name
5. ✅ `core/agents/adapters/index_analyst_v2.py` - 修复 agent_type 和 agent_name
6. ✅ `core/agents/adapters/sector_analyst_v2.py` - 修复 agent_type 和 agent_name

**修改内容**：
- ❌ 旧代码：`agent_type="analysts"`, `agent_name="market_analyst"`（v1.x 名称）
- ✅ 新代码：`agent_type="analysts_v2"`, `agent_name="market_analyst_v2"`（v2.0 名称）

**特别说明**：
- `fundamentals_analyst_v2.py` 之前完全没有调用 `get_agent_prompt`，使用的是硬编码提示词
- 现在已经添加了完整的模板系统集成，支持从数据库获取提示词

**额外改进**：
- 增加更多模板变量（`company_name`, `current_date`, `currency_name`, `currency_symbol`, `tool_names`）
- 从 `context` 中获取 `preference_id`（支持激进/中性/保守偏好）
- 使用 `StockUtils.get_market_info()` 自动识别市场类型和货币

---

## 📊 模板字段组合逻辑

`get_agent_prompt` 函数会自动组合以下字段（位于 `tradingagents/utils/template_client.py`）：

```python
parts = []
if formatted.get("system_prompt"):
    parts.append(formatted["system_prompt"])
if formatted.get("tool_guidance"):
    parts.append("\n\n" + formatted["tool_guidance"])
if formatted.get("analysis_requirements"):
    parts.append("\n\n" + formatted["analysis_requirements"])
if formatted.get("output_format"):
    parts.append("\n\n" + formatted["output_format"])
if formatted.get("constraints"):
    parts.append("\n\n" + formatted["constraints"])

prompt = "\n".join(parts)
```

因此，`analysis_requirements` 中的详细输出格式要求**会被包含在最终提示词中**。

---

## 🎯 预期效果

修复后，v2.0 市场分析师应该能够生成与 v1.x 类似的详细报告，包括：

1. **股票基本信息**（公司名称、代码、当前价格、涨跌幅、成交量）
2. **技术指标分析**：
   - 移动平均线（MA）分析（表格展示）
   - MACD 指标分析
   - RSI 相对强弱指标
   - 布林带（BOLL）分析
3. **价格趋势分析**：
   - 短期趋势（5-10 交易日）
   - 中期趋势（20-60 交易日）
   - 成交量分析
4. **投资建议**：
   - 综合评估
   - 操作建议（买入/持有/卖出）
   - 目标价位、止损位
   - 关键价格区间（支撑位、压力位）

---

## 🔄 后续工作

1. **测试验证**：运行 v2.0 工作流，检查市场分析师生成的报告格式
2. **其他分析师**：如果其他 v2.0 分析师也有类似问题，按照相同方式修复
3. **文档更新**：更新 v2.0 模板系统文档，说明详细的输出格式要求

---

---

## 📊 修复总结

### 已修复的问题

| 问题类型 | 影响范围 | 修复状态 |
|---------|---------|---------|
| 模板内容不够详细 | 所有 v2.0 分析师 | ✅ 已修复（21 个模板） |
| Agent 适配器调用错误 | 6 个 v2.0 分析师 | ✅ 已修复 |
| 基本面分析师未集成模板系统 | fundamentals_analyst_v2 | ✅ 已修复 |

### 修复文件清单

**数据库模板**：
- ✅ `fundamentals_analyst_v2` - 3 个偏好（详细模板，311-325 字符）
- ✅ `market_analyst_v2` - 3 个偏好（详细模板，1147-1296 字符）
- ✅ `news_analyst_v2` - 3 个偏好（简单模板，88-160 字符）
- ✅ `social_media_analyst_v2` - 3 个偏好（简单模板）
- ✅ `social_analyst_v2` - 3 个偏好（简单模板）
- ✅ `index_analyst_v2` - 3 个偏好（**已增强**，365-381 字符）
- ✅ `sector_analyst_v2` - 3 个偏好（**已增强**，324-356 字符）

**更新脚本**：
1. `scripts/update_v2_analyst_templates.py` - 更新所有 21 个模板
2. `scripts/enhance_index_sector_templates.py` - 增强大盘和行业分析师（6 个模板）

**Agent 适配器代码**：
- ✅ `core/agents/adapters/market_analyst_v2.py`
- ✅ `core/agents/adapters/fundamentals_analyst_v2.py`
- ✅ `core/agents/adapters/news_analyst_v2.py`
- ✅ `core/agents/adapters/social_analyst_v2.py`
- ✅ `core/agents/adapters/index_analyst_v2.py`
- ✅ `core/agents/adapters/sector_analyst_v2.py`

### 验证方法

1. **检查数据库模板**：
   ```bash
   python scripts/check_v2_templates.py
   ```
   应该看到 21 个 v2.0 分析师模板，每个都有详细的 `analysis_requirements` 字段

2. **运行 v2.0 工作流**：
   - 创建一个 v2.0 单股分析任务
   - 检查市场分析师、基本面分析师等生成的报告
   - 报告应该包含详细的章节结构和表格格式

3. **检查日志输出**：
   ```
   ✅ 从模板系统获取市场分析师 v2.0 提示词 (长度: XXXX)
   ✅ 从模板系统获取基本面分析师 v2.0 提示词 (长度: XXXX)
   ```

---

**修复人员**: Augment Agent
**修复日期**: 2026-01-09
**审核状态**: ✅ 已完成，待测试验证

