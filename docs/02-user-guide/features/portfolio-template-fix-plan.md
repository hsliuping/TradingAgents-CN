# 持仓分析提示词模板修复计划

## 📊 问题分析总结

根据导出的模板数据分析，发现了以下问题：

### 问题1：旧版模板缺少 user_prompt
- **影响范围**：6个模板（pa_technical_v2 和 pa_fundamental_v2 各3个：aggressive/neutral/conservative）
- **当前状态**：有 system_prompt、tool_guidance、analysis_requirements、output_format、constraints
- **缺失**：user_prompt

### 问题2：新版模板结构不完整
- **影响范围**：12个模板（pa_technical_v2 和 pa_fundamental_v2 各6个：with_cache_*/without_cache_*）
- **当前状态**：只有 analysis_requirements、constraints（2个字段）
- **缺失**：system_prompt、user_prompt、tool_guidance、output_format

---

## 🔧 修复方案

### 修复步骤

#### 步骤1：修复旧版模板（补充 user_prompt）

**目标**：为 6 个旧版模板补充 `user_prompt`

**策略**：
- 使用代码中的降级提示词作为基础
- 生成通用的 `user_prompt` 模板（使用变量占位符）
- 根据 Agent 类型（技术面/基本面）生成不同的内容

**技术面分析师 user_prompt**：
```python
"""请分析以下持仓股票的技术面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}
- 持仓天数: {holding_days} 天

=== 市场数据 ===
{market_data_summary}

=== 技术指标 ===
{technical_indicators}

如果没有市场数据，请调用 get_stock_market_data_unified 工具获取K线数据和技术指标。

请撰写详细的技术面分析报告，包括：
1. 趋势判断
2. 支撑阻力位
3. 技术指标分析
4. 短期走势预判
5. 技术面评分（1-10分）"""
```

**基本面分析师 user_prompt**：
```python
"""请分析以下持仓股票的基本面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {industry}
- 成本价: {cost_price}
- 现价: {current_price}
- 持仓天数: {holding_days} 天

如果没有基本面数据，请调用 get_stock_fundamentals_unified 工具获取财务数据。

请撰写详细的基本面分析报告，包括：
1. 财务状况分析
2. 估值水平评估
3. 行业地位分析
4. 成长性判断
5. 基本面评分（1-10分）"""
```

#### 步骤2：修复新版模板（从旧版模板提取字段）

**目标**：为 12 个新版模板补充所有缺失字段

**策略**：
1. 从对应的旧版模板（aggressive/neutral/conservative）中提取：
   - `system_prompt`
   - `tool_guidance`
   - `output_format`
   - `constraints`（如果新版模板没有）

2. 根据缓存场景生成 `user_prompt`：
   - **with_cache**：包含引用缓存报告的说明
   - **without_cache**：包含调用工具的说明

**with_cache user_prompt（技术面）**：
```python
"""请基于以下单股技术面分析报告和持仓信息，进行持仓技术面分析：

=== 单股技术面分析报告（参考）===
{market_report}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}
- 持仓天数: {holding_days} 天

请结合持仓情况（成本价、盈亏等），对技术面进行持仓视角的分析：
1. 当前技术面状态与持仓成本的关系
2. 基于持仓的技术面操作建议
3. 支撑阻力位与持仓成本的关系
4. 短期走势预判（考虑持仓盈亏）
5. 技术面评分（1-10分）"""
```

**without_cache user_prompt（技术面）**：
```python
"""请分析以下持仓股票的技术面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {cost_price}
- 现价: {current_price}
- 浮动盈亏: {unrealized_pnl_pct}
- 持仓天数: {holding_days} 天

=== 市场数据 ===
{market_data_summary}

=== 技术指标 ===
{technical_indicators}

如果没有市场数据，请调用 get_stock_market_data_unified 工具获取K线数据和技术指标。

请撰写详细的技术面分析报告，包括：
1. 趋势判断
2. 支撑阻力位
3. 技术指标分析
4. 短期走势预判
5. 技术面评分（1-10分）"""
```

---

## 📝 修复脚本说明

### 脚本文件
`scripts/fix_position_analysis_templates.py`

### 功能
1. **fix_old_template()**：修复旧版模板，补充 `user_prompt`
2. **fix_single_template()**：修复新版模板，从旧版模板提取所有字段
3. **get_user_prompt_template()**：根据 Agent 类型和缓存场景生成 `user_prompt`

### 使用方法
```bash
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 运行修复脚本
python scripts/fix_position_analysis_templates.py
```

### 修复流程
```
1. 遍历所有需要修复的 Agent（pa_technical_v2, pa_fundamental_v2）
2. 第一步：修复旧版模板（补充 user_prompt）
   - 查找 aggressive/neutral/conservative 模板
   - 检查是否已有 user_prompt
   - 如果没有，生成并补充
3. 第二步：修复新版模板（从旧版模板提取字段）
   - 查找 with_cache_*/without_cache_* 模板
   - 从对应的旧版模板提取 system_prompt、tool_guidance、output_format
   - 根据缓存场景生成 user_prompt
   - 保留现有的 analysis_requirements 和 constraints
4. 更新数据库
```

---

## ✅ 修复后预期结果

### 旧版模板（6个）
- ✅ system_prompt（已有）
- ✅ **user_prompt（新增）**
- ✅ tool_guidance（已有）
- ✅ analysis_requirements（已有）
- ✅ output_format（已有）
- ✅ constraints（已有）

### 新版模板（12个）
- ✅ **system_prompt（从旧版提取）**
- ✅ **user_prompt（根据缓存场景生成）**
- ✅ **tool_guidance（从旧版提取）**
- ✅ analysis_requirements（已有）
- ✅ **output_format（从旧版提取）**
- ✅ constraints（已有）

---

## 🧪 验证步骤

### 1. 运行修复脚本
```bash
python scripts/fix_position_analysis_templates.py
```

### 2. 重新导出模板验证
```bash
python scripts/export_position_analysis_templates.py
```

### 3. 检查修复结果
- 查看导出的 JSON 文件，确认所有模板都有完整的 6 个字段
- 查看分析报告，确认没有"缺失字段"的警告

### 4. 功能测试
- 测试有缓存场景：验证 `with_cache` 模板是否正确加载
- 测试无缓存场景：验证 `without_cache` 模板是否正确加载，工具是否被调用

---

## 📊 修复统计

| 类别 | 数量 | 修复内容 |
|------|------|---------|
| 旧版模板 | 6 | 补充 user_prompt |
| 新版模板 | 12 | 补充 system_prompt、user_prompt、tool_guidance、output_format |
| **总计** | **18** | **所有模板结构完整** |

---

## 🎯 修复完成检查清单

- [x] 分析导出数据，了解问题
- [x] 设计修复方案
- [x] 编写修复脚本
- [ ] 运行修复脚本
- [ ] 验证修复结果
- [ ] 功能测试

---

**最后更新**：2026-02-02  
**修复版本**：v2.0.1
