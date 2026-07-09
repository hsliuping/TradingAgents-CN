# 防止多空辩论中的幻觉和过时数据问题

## 📋 问题描述

在多空辩论（Bull vs Bear）过程中，可能出现以下问题：
1. **LLM 幻觉**：编造不存在的数据或新闻
2. **使用过时数据**：引用 LLM 训练数据中的历史信息（如2023年、2024年的数据）
3. **缺乏来源引用**：无法追溯论据的数据来源
4. **误导用户**：基于不准确信息做出投资建议

## 🎯 解决方案

### 方案1：强化提示词约束（已部分实现）

**当前状态**：
- v2.0 版本的 `bull_researcher_v2` 和 `bear_researcher_v2` 已包含基本约束
- 位置：`prompt_templates` 集合中的 `system_prompt`

**需要加强的约束**：

```markdown
**⚠️ 严格约束（违反将导致分析无效）**：

1. **数据来源约束**：
   - ✅ 只能使用用户提示词中提供的分析报告
   - ✅ 每个论据必须明确标注数据来源（如"根据基本面报告"、"根据新闻分析"）
   - ❌ 禁止使用 LLM 内部知识或训练数据
   - ❌ 禁止引用报告中未提及的数据

2. **时效性约束**：
   - ✅ 只能使用分析日期（{analysis_date}）之前的数据
   - ❌ 禁止使用"2023年"、"2024年"等历史时间标记
   - ❌ 禁止使用"去年"、"上季度"等模糊时间表述（除非报告中明确提供）

3. **数据完整性约束**：
   - ✅ 如果报告中缺少某项数据，必须明确说明"报告中未提供此数据"
   - ❌ 禁止编造、推测或补充报告中没有的数据
   - ❌ 禁止使用"据了解"、"市场传闻"等无来源表述

4. **引用格式要求**：
   - 每个关键论据后必须用【】标注来源，例如：
     - "公司营收增长30%【基本面报告】"
     - "近期发布重大利好消息【新闻分析】"
     - "市场情绪积极【情绪报告】"
   - 如果某个观点无法找到报告支持，不要提出该观点

5. **不确定性表达**：
   - 当报告数据不足时，使用"基于现有报告，无法判断..."
   - 避免使用绝对化表述（如"一定会"、"必然"）
```

### 方案2：增加来源验证机制

**实现思路**：
在 Research Manager 综合研判时，增加来源验证步骤。

**新增 Agent**：`source_validator_v2`（来源验证员）

```python
# core/agents/adapters/source_validator_v2.py

class SourceValidatorV2(AnalystAgent):
    """
    来源验证员 v2.0
    
    功能：
    - 验证多空辩论中的论据是否有报告支持
    - 标记可疑的无来源论据
    - 生成验证报告
    """
    
    def _build_system_prompt(self, state):
        return """你是一位严谨的来源验证员。
        
        任务：检查看涨和看跌论据是否都有明确的报告来源支持。
        
        验证规则：
        1. 每个关键论据必须能在提供的报告中找到对应内容
        2. 标记所有无来源支持的论据
        3. 标记所有使用历史时间标记的论据（如"2023年"、"去年"）
        4. 标记所有编造或推测的数据
        
        输出格式：
        - 有效论据列表（带来源）
        - 可疑论据列表（无来源或来源不明）
        - 验证总结
        """
```

### 方案3：报告摘要预处理

**实现思路**：
在传递给辩论 Agent 之前，先对各类报告进行结构化摘要，明确标注数据来源和时间。

**新增工具**：`report_summarizer`

```python
def summarize_reports_with_sources(reports: Dict[str, str]) -> str:
    """
    将各类报告整理为结构化摘要，明确标注来源
    
    输入：
        {
            "market_report": "...",
            "fundamentals_report": "...",
            "news_report": "...",
            ...
        }
    
    输出：
        === 数据摘要（请严格基于以下内容进行分析） ===
        
        【市场技术分析】
        - 当前价格：XX元
        - 技术指标：...
        - 数据时间：2026-02-10
        
        【基本面分析】
        - 市盈率：XX
        - 营收增长：XX%
        - 数据时间：2026-02-10
        
        【新闻事件】
        - 事件1：...（时间：2026-02-08）
        - 事件2：...（时间：2026-02-09）
        
        ⚠️ 以上是全部可用数据，请勿使用其他来源
    """
    pass
```

### 方案4：后处理过滤

**实现思路**：
在辩论结束后，使用另一个 LLM 对辩论内容进行审查，过滤掉可疑内容。

**新增步骤**：在 `research_manager_v2` 中增加审查环节

```python
def _review_debate_content(self, bull_report: str, bear_report: str, reports: Dict) -> Dict:
    """
    审查辩论内容，标记可疑论据
    
    返回：
    {
        "bull_report_reviewed": "...",  # 标记了可疑内容的看涨报告
        "bear_report_reviewed": "...",  # 标记了可疑内容的看跌报告
        "warnings": [...]  # 警告列表
    }
    """
    review_prompt = f"""
    请审查以下辩论内容，标记所有可疑的论据：
    
    可疑论据特征：
    1. 没有明确来源标注
    2. 使用了历史时间标记（如"2023年"、"去年"）
    3. 提到了报告中未出现的具体数据
    4. 使用了"据了解"、"市场传闻"等模糊表述
    
    看涨论据：
    {bull_report}
    
    看跌论据：
    {bear_report}
    
    可用报告：
    {reports}
    
    请输出：
    1. 标记后的看涨论据（在可疑内容后加 ⚠️）
    2. 标记后的看跌论据（在可疑内容后加 ⚠️）
    3. 警告列表
    """
    pass
```

### 方案5：用户界面提示

**实现思路**：
在前端显示辩论结果时，增加数据来源说明和风险提示。

**前端改进**：

```vue
<template>
  <div class="debate-section">
    <!-- 数据来源说明 -->
    <el-alert type="info" :closable="false">
      <template #title>
        📊 数据来源说明
      </template>
      本次分析基于以下数据源（截至 {{ analysisDate }}）：
      <ul>
        <li v-for="source in dataSources" :key="source.name">
          {{ source.name }}：{{ source.updateTime }}
        </li>
      </ul>
    </el-alert>
    
    <!-- 辩论内容 -->
    <div class="bull-opinion">
      <h3>🐂 看涨观点</h3>
      <div v-html="highlightSources(bullOpinion)"></div>
    </div>
    
    <div class="bear-opinion">
      <h3>🐻 看跌观点</h3>
      <div v-html="highlightSources(bearOpinion)"></div>
    </div>
    
    <!-- 风险提示 -->
    <el-alert v-if="hasWarnings" type="warning">
      <template #title>
        ⚠️ 注意事项
      </template>
      <ul>
        <li v-for="warning in warnings" :key="warning">
          {{ warning }}
        </li>
      </ul>
    </el-alert>
  </div>
</template>

<script>
function highlightSources(text) {
  // 高亮显示来源标注【】
  return text.replace(/【([^】]+)】/g, '<span class="source-tag">【$1】</span>');
}
</script>
```

## 🚀 实施建议

### ✅ 短期（已完成）

1. **更新提示词模板** ✅：
   - ✅ 在 `prompt_templates` 集合中更新 `bull_researcher_v2` 和 `bear_researcher_v2`
   - ✅ 添加更严格的约束和引用格式要求
   - ✅ 添加示例说明正确和错误的引用方式
   - ✅ 所有 preference_type（aggressive, neutral, conservative）已更新
   - ✅ 版本号从 2 升级到 3
   - **执行脚本**: `scripts/template_upgrades/enhance_researcher_anti_hallucination.py`
   - **验证脚本**: `scripts/verify_researcher_update.py`
   - **更新时间**: 2026-02-10

2. **增加前端提示** 🔄：
   - ⏳ 在辩论结果页面显示数据来源和时间
   - ⏳ 提醒用户注意无来源标注的论据
   - **建议位置**: `frontend/src/views/Analysis/components/DebateResults.vue`

### 中期（1-2周）

3. **实现报告摘要预处理** 📋：
   - 创建 `report_summarizer` 工具
   - 在传递给辩论 Agent 前进行结构化整理
   - **建议位置**: `core/tools/report_summarizer.py`

4. **增加后处理审查** 🔍：
   - 在 `research_manager_v2` 中增加审查步骤
   - 标记可疑论据
   - **建议位置**: `core/agents/adapters/research_manager_v2.py`

### 长期（1个月）

5. **实现来源验证 Agent** 🤖：
   - 创建 `source_validator_v2`
   - 集成到工作流中
   - **建议位置**: `core/agents/adapters/source_validator_v2.py`

6. **建立反馈机制** 📊：
   - 允许用户标记不准确的论据
   - 收集数据用于改进提示词
   - **建议位置**: `frontend/src/views/Analysis/components/FeedbackPanel.vue`

## 📊 效果评估

**评估指标**：
1. 论据来源标注率（目标：>90%）
2. 使用历史时间标记的比例（目标：<5%）
3. 用户反馈的准确性评分（目标：>4.0/5.0）
4. 可疑论据检出率

**监控方法**：
- 定期抽查分析报告
- 收集用户反馈
- 使用自动化脚本检测关键词（如"2023年"、"去年"、"据了解"）

---

**最后更新**: 2026-02-10  
**相关文档**: 
- `docs/design/v2.0/stock-analysis-engine-design.md`
- `scripts/template_upgrades/upgrade_researchers_v2.py`

