# 提示词合规审计报告 (2026-01)

> **目标**：确保所有分析报告不包含目标价、买卖建议、仓位建议等可能构成投资建议的内容。

---

## 📊 审计概览

| 指标 | 数值 |
|------|------|
| **数据库模板总数** | 143 |
| **命中敏感词的模板** | 101 (70.6%) |
| **代码文件命中数** | 379 |
| **涉及 Agent 类型** | 48 |

**审计时间**: 2026-01-31  
**数据来源**: `install/database_export_config_2026-01-28.json`

---

## 🚫 敏感词清单

### 必须完全移除的词汇

| 类别 | 词汇 | 说明 |
|------|------|------|
| **目标价格** | 目标价、目标价位、目标价格、target_price | 任何形式的价格预测 |
| **交易操作** | 买入、卖出、持有、加仓、减仓、清仓、建仓 | 明确的交易指令 |
| **投资建议** | 操作建议、交易建议、投资建议 | 任何形式的建议 |
| **仓位指导** | 仓位、仓位比例、position_ratio、action_ratio | 资金配置建议 |
| **止损止盈** | 止损、止盈、stop_loss、take_profit | 价格触发点建议 |
| **交易计划** | 交易指令、trading_instruction、trading_plan | 具体交易计划 |

---

## 📁 需要修改的内容

### 一、数据库模板 (prompt_templates)

#### 1.1 高优先级 - 分析师模板 (analysts/analysts_v2)

| agent_type | agent_name | 问题字段 | 敏感词 |
|------------|------------|----------|--------|
| analysts | fundamentals_analyst | analysis_requirements | 买入、卖出、投资建议、持有、目标价、目标价位 |
| analysts | market_analyst | analysis_requirements | 买入、卖出、交易建议、投资建议、持有 |
| analysts | news_analyst | system_prompt, analysis_requirements | 交易建议、投资建议 |
| analysts | social_media_analyst | analysis_requirements | 投资建议 |
| analysts_v2 | * | 类似问题 | 同上 |

#### 1.2 高优先级 - 交易员模板 (trader/trader_v2)

| agent_type | agent_name | 问题字段 | 敏感词 |
|------------|------------|----------|--------|
| trader | trader | system_prompt, analysis_requirements | 买入、卖出、持有、目标价、交易建议、止损 |
| trader_v2 | trader_v2 | 多个字段 | 仓位、目标价、操作建议 |

#### 1.3 高优先级 - 管理者模板 (managers/managers_v2)

| agent_type | agent_name | 问题字段 | 敏感词 |
|------------|------------|----------|--------|
| managers | research_manager | system_prompt, user_prompt, output_format | target_price、position_ratio、买入、卖出、投资建议 |
| managers | risk_manager | system_prompt, output_format | 止损、仓位、目标价、投资建议 |
| managers_v2 | * | 类似问题 | 同上 |

#### 1.4 中优先级 - 持仓分析模板 (position_analysis*)

| agent_type | agent_name | 问题字段 | 敏感词 |
|------------|------------|----------|--------|
| position_analysis | pa_advisor | 多字段 | 加仓、减仓、清仓、目标价、止损 |
| position_analysis | pa_risk | 多字段 | 仓位、止损、止盈 |
| position_analysis_v2 | * | 类似问题 | 同上 |

#### 1.5 中优先级 - 复盘分析模板 (reviewers*)

| agent_type | agent_name | 问题字段 | 敏感词 |
|------------|------------|----------|--------|
| reviewers | position_analyst | 多字段 | 仓位、加仓、减仓、建仓 |
| reviewers | timing_analyst | 多字段 | 买入、卖出 |
| reviewers_v2 | * | 类似问题 | 同上 |

#### 1.6 低优先级 - 无命中的模板 ✅

以下模板**不需要修改**：
- `debators/*` - 辩论者模板（无敏感词）
- `researchers/bull_researcher` - 看涨研究员（无敏感词）
- `researchers/bear_researcher` - 看跌研究员（无敏感词）

---

### 二、代码硬编码提示词

#### 2.1 核心 Agent 适配器 (core/agents/adapters/)

| 文件 | 敏感词 | 优先级 |
|------|--------|--------|
| `trader_v2.py` | 仓位、建仓、投资建议、操作建议、目标价 | 🔴 高 |
| `research_manager_v2.py` | 买入、卖出、投资建议、操作建议、目标价 | 🔴 高 |
| `risk_manager_v2.py` | position_ratio、stop_loss、target_price、仓位、投资建议 | 🔴 高 |
| `news_analyst_v2.py` | 投资建议 | 🟡 中 |
| `social_analyst_v2.py` | 投资建议 | 🟡 中 |
| `fundamentals_analyst_v2.py` | 投资建议、持有 | 🟡 中 |

#### 2.2 持仓分析 Agent (core/agents/adapters/position/)

| 文件 | 敏感词 | 优先级 |
|------|--------|--------|
| `action_advisor_v2.py` | 加仓、减仓、清仓、止损、止盈、目标价、操作建议 | 🔴 高 |
| `risk_assessor_v2.py` | 仓位、止损、止盈、position_ratio | 🔴 高 |
| `action_advisor.py` | 同上 | 🟡 中 (v1.x) |
| `risk_assessor.py` | 同上 | 🟡 中 (v1.x) |
| `technical_analyst_v2.py` | 操作建议 | 🟢 低 |
| `fundamental_analyst_v2.py` | 操作建议 | 🟢 低 |

#### 2.3 复盘分析 Agent (core/agents/adapters/review/)

| 文件 | 敏感词 | 优先级 |
|------|--------|--------|
| `position_analyst_v2.py` | 仓位、减仓、建仓、trading_plan | 🟡 中 |
| `timing_analyst_v2.py` | 买入、卖出、trading_plan | 🟡 中 |
| `emotion_analyst_v2.py` | 买入、卖出、持有 | 🟡 中 |
| `attribution_analyst.py` | 买入、卖出 | 🟡 中 |
| `review_manager_v2.py` | 仓位、trading_plan | 🟡 中 |

#### 2.4 辩论者 Agent (core/agents/adapters/)

| 文件 | 敏感词 | 优先级 |
|------|--------|--------|
| `neutral_analyst_v2.py` | 仓位、操作建议、止损 | 🟡 中 |
| `risky_analyst_v2.py` | 仓位、操作建议、目标价 | 🟡 中 |
| `safe_analyst_v2.py` | 仓位、操作建议、止损 | 🟡 中 |

---

### 三、不需要修改的内容 ✅

以下内容虽然命中敏感词，但属于**数据模型定义**或**免责声明**，不影响用户报告输出：

| 类别 | 文件/模块 | 原因 |
|------|-----------|------|
| 数据模型 | `app/models/portfolio.py` | 定义持仓数据结构，非提示词 |
| 数据模型 | `app/models/trading_system.py` | 定义交易系统数据结构 |
| 数据模型 | `app/models/review.py` | 定义复盘数据结构 |
| 工具实现 | `core/tools/implementations/*` | 数据获取逻辑，非提示词 |
| 后处理器 | `core/agents/post_processors/*` | 报告保存逻辑 |
| 免责声明 | 已有 `**免责声明**` 的模板部分 | 审计时已排除 |

---

## 🔧 修改建议

### 策略一：术语替换（保守）

将敏感词替换为中性表述：

| 原词 | 替换为 | 说明 |
|------|--------|------|
| 目标价 | 价格分析区间 | 不暗示预测 |
| 买入 | 看涨 / 偏多观点 | 不暗示操作 |
| 卖出 | 看跌 / 偏空观点 | 不暗示操作 |
| 持有 | 中性 / 观望观点 | 不暗示操作 |
| 加仓 | 增持观点 | 不暗示操作 |
| 减仓 | 减持观点 | 不暗示操作 |
| 清仓 | 观望观点 | 不暗示操作 |
| 仓位 | 风险敞口分析 | 不暗示配置 |
| 止损 | 风险控制参考价位 | 仅供参考 |
| 止盈 | 收益预期参考价位 | 仅供参考 |
| 投资建议 | 分析观点 | 不暗示建议 |
| 操作建议 | 持仓分析观点 | 不暗示建议 |

### 策略二：完全删除（严格）

如果用户要求更严格的合规，可以：

1. **删除输出字段**：从 `output_format` 中移除 `target_price`、`stop_loss`、`take_profit`、`position_ratio` 等字段
2. **删除分析要求**：从 `analysis_requirements` 中移除要求输出建议的条目
3. **保留分析内容**：保留技术面、基本面、市场情绪等客观分析要求

---

## 📋 执行计划

### Phase 1：数据库模板修改（优先）

1. **备份现有模板**
   ```bash
   python scripts/compliance/export_prompts_before_compliance.py
   ```

2. **执行术语替换**
   ```bash
   python scripts/compliance/update_prompts_for_compliance.py --preview
   python scripts/compliance/update_prompts_for_compliance.py --execute
   ```

3. **验证修改结果**
   ```bash
   python scripts/compliance/audit_all_prompts.py
   ```

### Phase 2：代码硬编码提示词修改

1. 修改 `core/agents/adapters/` 下的高优先级文件
2. 修改 `core/agents/adapters/position/` 下的文件
3. 修改 `core/agents/adapters/review/` 下的文件

### Phase 3：验证与测试

1. 运行分析流程，检查报告输出
2. 确认报告中不再包含敏感词
3. 确认分析内容完整性

---

## 📎 附件

- `exports/compliance_audit/prompt_templates_audit.json` - 数据库模板审计详情
- `exports/compliance_audit/repo_terms_hitlist.json` - 代码命中清单
- `exports/compliance_audit/audit_summary.md` - 审计摘要

---

**最后更新**: 2026-01-31
**审计脚本**: `scripts/compliance/audit_all_prompts.py`


