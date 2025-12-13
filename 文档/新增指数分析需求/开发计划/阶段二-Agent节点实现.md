# 阶段二：Agent节点实现开发方案

## 📋 阶段概述

**目标**：实现4个核心分析Agent节点，每个Agent遵循现有的`create_market_analyst`模式。

**预计时间**：3-4天  
**优先级**：🔴 高（核心功能）

**前置条件**：阶段一（数据层与工具层）已完成

---

## 🎯 本阶段交付物

### 新建文件
1. `tradingagents/agents/analysts/macro_analyst.py` - 宏观经济分析师
2. `tradingagents/agents/analysts/policy_analyst.py` - 政策分析师
3. `tradingagents/agents/analysts/sector_analyst.py` - 板块轮动分析师
4. `tradingagents/agents/analysts/strategy_advisor.py` - 策略顾问
5. `tests/agents/test_macro_analyst.py` - 宏观分析师测试
6. `tests/agents/test_policy_analyst.py` - 政策分析师测试
7. `tests/agents/test_sector_analyst.py` - 板块分析师测试
8. `tests/agents/test_strategy_advisor.py` - 策略顾问测试

### 依赖项
- 阶段一的所有交付物
- LangChain ChatPromptTemplate
- 现有的 `create_market_analyst` 实现模式

---

## 📝 详细开发任务

### 任务2.1：实现Macro Analyst（宏观经济分析师）

**文件**：`tradingagents/agents/analysts/macro_analyst.py`

**核心职责**：
- 分析宏观经济环境
- 判断经济周期阶段（复苏/扩张/滞胀/衰退）
- 评估流动性状况（宽松/中性/紧缩）
- 给出情绪评分（-1.0 到 1.0）

**功能清单**：
- [ ] `create_macro_analyst()` 函数定义
- [ ] 节点函数 `macro_analyst_node(state)`
- [ ] 工具调用计数器（防止死循环）
- [ ] ChatPromptTemplate 构建
  - System prompt：角色定义、分析任务、输出格式
  - MessagesPlaceholder：消息历史
- [ ] 工具绑定：`llm.bind_tools([fetch_macro_data])`
- [ ] JSON报告提取逻辑
- [ ] 降级方案（工具调用超限时）
- [ ] 日志记录

**参考代码位置**：详细设计文档 第3.1节

**实现骨架**：
```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
from tradingagents.utils.logging_init import get_logger

logger = get_logger("agents")

def create_macro_analyst(llm, index_toolkit):
    """创建宏观经济分析师节点"""
    
    def macro_analyst_node(state):
        logger.info("🌍 [宏观分析师] 节点开始")
        
        # 1. 工具调用计数器
        tool_call_count = state.get("macro_tool_call_count", 0)
        max_tool_calls = 3
        
        # 2. 降级方案
        if tool_call_count >= max_tool_calls:
            # 返回降级报告
            pass
        
        # 3. 构建Prompt
        prompt = ChatPromptTemplate.from_messages([...])
        
        # 4. 绑定工具
        tools = [index_toolkit.fetch_macro_data]
        chain = prompt | llm.bind_tools(tools)
        
        # 5. 调用LLM
        result = chain.invoke({...})
        
        # 6. 提取JSON报告
        report = extract_json_report(result)
        
        # 7. 返回状态更新
        return {
            "messages": [result],
            "macro_report": report or "",
            "macro_tool_call_count": tool_call_count + 1
        }
    
    return macro_analyst_node
```

**分析思路**：
- **经济周期判断**：基于GDP增速、PMI走势、CPI通胀水平
- **流动性评估**：基于M2增速、LPR利率
- **情绪评分**：
  - 经济扩张 + 流动性宽松 → sentiment_score = 0.5~0.8
  - 经济衰退 + 流动性紧缩 → sentiment_score = -0.8~-0.5

**验证标准**：
- ✅ 能够调用 `fetch_macro_data` 工具
- ✅ 成功提取JSON格式的报告
- ✅ 报告包含所有必需字段（confidence, sentiment_score）
- ✅ 工具调用计数器正常工作
- ✅ 降级方案能够触发

---

### 任务2.2：实现Policy Analyst（政策分析师）

**文件**：`tradingagents/agents/analysts/policy_analyst.py`

**核心职责**：
- 分析货币政策、财政政策、产业政策
- 识别关键政策事件
- 判断政策对市场的影响（正面/中性/负面）
- 识别政策受益板块

**功能清单**：
- [ ] `create_policy_analyst()` 函数定义
- [ ] 节点函数 `policy_analyst_node(state)`
- [ ] 工具调用计数器
- [ ] ChatPromptTemplate 构建
  - 货币政策识别（降息/降准）
  - 财政政策识别（减税降费、基建投资）
  - 产业政策映射（自主可控、新能源）
- [ ] 工具绑定：`llm.bind_tools([fetch_policy_news])`
- [ ] JSON报告提取逻辑
- [ ] 降级方案
- [ ] 日志记录

**参考代码位置**：详细设计文档 第3.2节

**分析思路**：
- **货币政策**：降息/降准 → 宽松 → 利好股市
- **财政政策**：减税降费 → 积极 → 企业盈利改善
- **产业政策**：自主可控 → 半导体、国防军工受益
- **情绪评分**：
  - 多项宽松政策叠加 → sentiment_score = 0.6~0.9
  - 政策真空期 → sentiment_score = -0.1~0.1
  - 紧缩政策出台 → sentiment_score = -0.7~-0.3

**验证标准**：
- ✅ 能够调用 `fetch_policy_news` 工具
- ✅ 成功识别货币、财政、产业政策
- ✅ JSON报告包含 key_events 和 market_impact
- ✅ 降级方案能够触发

---

### 任务2.3：实现Sector Analyst（板块轮动分析师）

**文件**：`tradingagents/agents/analysts/sector_analyst.py`

**核心职责**：
- 分析板块资金流向和涨跌幅
- 识别领涨/领跌板块
- 判断板块轮动特征
- 结合政策分析识别热点主题

**功能清单**：
- [ ] `create_sector_analyst()` 函数定义
- [ ] 节点函数 `sector_analyst_node(state)`
- [ ] 工具调用计数器
- [ ] 读取上游 `policy_report`（交叉验证）
- [ ] ChatPromptTemplate 构建
  - 领涨/领跌板块识别
  - 轮动特征判断（成长→价值、大盘→小盘）
  - 热点主题挖掘
- [ ] 工具绑定：`llm.bind_tools([fetch_sector_rotation])`
- [ ] JSON报告提取逻辑
- [ ] 降级方案
- [ ] 日志记录

**参考代码位置**：详细设计文档 第3.3节

**分析思路**：
- **领涨板块**：Top 5 涨幅板块 → 资金流入方向
- **轮动特征**：成长→价值、大盘→小盘
- **热点主题**：结合政策报告，识别受益板块
  - 政策提到"自主可控" → 关注半导体、国防军工
  - 政策提到"新能源" → 关注光伏、储能、新能源车
- **情绪评分**：
  - 普涨（多板块上涨）→ sentiment_score = 0.5~0.8
  - 结构性行情 → sentiment_score = 0.2~0.5
  - 普跌 → sentiment_score = -0.8~-0.5

**验证标准**：
- ✅ 能够调用 `fetch_sector_rotation` 工具
- ✅ 成功解析上游 `policy_report`
- ✅ JSON报告包含 top_sectors、hot_themes
- ✅ 热点主题与政策支持方向一致

---

### 任务2.4：实现Strategy Advisor（策略顾问）

**文件**：`tradingagents/agents/analysts/strategy_advisor.py`

**核心职责**：
- 综合宏观、政策、板块三个维度的分析
- 计算加权情绪得分
- 给出仓位建议
- 识别关键风险和机会板块

**功能清单**：
- [ ] `create_strategy_advisor()` 函数定义
- [ ] 节点函数 `strategy_advisor_node(state)`
- [ ] 读取上游报告（macro_report, policy_report, sector_report）
- [ ] 验证上游报告完整性
- [ ] ChatPromptTemplate 构建
  - 加权情绪计算公式（宏观30%、政策40%、板块30%）
  - 仓位建议映射逻辑
  - 风险识别
  - 机会板块推荐
- [ ] **不绑定工具**（直接分析上游报告）
- [ ] JSON报告提取逻辑
- [ ] 降级方案（上游报告缺失时）
- [ ] 日志记录

**参考代码位置**：详细设计文档 第3.4节

**实现要点**：
```python
def create_strategy_advisor(llm):
    """创建策略顾问节点（不需要工具）"""
    
    def strategy_advisor_node(state):
        # 1. 获取上游报告
        macro_report = state.get("macro_report", "")
        policy_report = state.get("policy_report", "")
        sector_report = state.get("sector_report", "")
        
        # 2. 验证完整性
        if not (macro_report and policy_report and sector_report):
            # 返回降级报告
            pass
        
        # 3. 构建Prompt（包含加权计算公式）
        prompt = ChatPromptTemplate.from_messages([...])
        
        # 4. 直接调用LLM（不绑定工具）
        chain = prompt | llm
        result = chain.invoke({...})
        
        # 5. 提取JSON报告
        return {
            "messages": [result],
            "strategy_report": report or ""
        }
    
    return strategy_advisor_node
```

**加权情绪计算**：
```python
# Prompt中的公式说明
final_sentiment = (
    macro_sentiment * 0.3 * macro_confidence +
    policy_sentiment * 0.4 * policy_confidence +
    sector_sentiment * 0.3 * sector_confidence
) / (0.3 * macro_confidence + 0.4 * policy_confidence + 0.3 * sector_confidence)
```

**仓位建议映射**：
- 情绪 > 0.5 → 仓位 0.7~1.0（激进）
- 情绪 0.2~0.5 → 仓位 0.5~0.7（稳健）
- 情绪 -0.2~0.2 → 仓位 0.3~0.5（谨慎）
- 情绪 < -0.2 → 仓位 0.0~0.3（防御）

**验证标准**：
- ✅ 能够正确解析上游三个报告
- ✅ JSON报告包含所有必需字段
- ✅ recommended_position 与 final_sentiment_score 映射合理
- ✅ 上游报告缺失时降级方案生效

---

### 任务2.5：编写单元测试

**测试文件**：
- `tests/agents/test_macro_analyst.py`
- `tests/agents/test_policy_analyst.py`
- `tests/agents/test_sector_analyst.py`
- `tests/agents/test_strategy_advisor.py`

**测试用例清单**：

#### test_macro_analyst.py
- [ ] `test_macro_analyst_node()` - 测试基本功能
- [ ] `test_macro_analyst_tool_call()` - 测试工具调用
- [ ] `test_macro_analyst_json_output()` - 测试JSON输出
- [ ] `test_macro_analyst_fallback()` - 测试降级方案
- [ ] `test_macro_analyst_tool_counter()` - 测试计数器

#### test_policy_analyst.py
- [ ] `test_policy_analyst_node()` - 测试基本功能
- [ ] `test_policy_analyst_tool_call()` - 测试工具调用
- [ ] `test_policy_analyst_json_output()` - 测试JSON输出
- [ ] `test_policy_analyst_fallback()` - 测试降级方案

#### test_sector_analyst.py
- [ ] `test_sector_analyst_node()` - 测试基本功能
- [ ] `test_sector_analyst_with_policy()` - 测试与政策分析联动
- [ ] `test_sector_analyst_json_output()` - 测试JSON输出
- [ ] `test_sector_analyst_fallback()` - 测试降级方案

#### test_strategy_advisor.py
- [ ] `test_strategy_advisor_node()` - 测试基本功能
- [ ] `test_strategy_advisor_aggregation()` - 测试加权聚合
- [ ] `test_strategy_advisor_position_mapping()` - 测试仓位映射
- [ ] `test_strategy_advisor_incomplete_reports()` - 测试报告缺失

**参考代码位置**：测试计划与总结补充.md 第6.2节

---

## 🔄 开发流程

### Day 1: Macro Analyst
1. **上午**
   - 创建 `macro_analyst.py` 文件
   - 实现 `create_macro_analyst()` 函数
   - 构建Prompt模板
   
2. **下午**
   - 实现工具绑定和调用逻辑
   - 实现JSON提取逻辑
   - 编写单元测试

3. **验收**
   - 单元测试通过
   - 能够成功调用工具并生成报告

### Day 2: Policy Analyst 和 Sector Analyst
1. **上午**
   - 实现 `policy_analyst.py`
   - 编写单元测试
   
2. **下午**
   - 实现 `sector_analyst.py`
   - 实现与政策分析的联动
   - 编写单元测试

3. **验收**
   - 两个Agent的单元测试通过
   - Sector Analyst能够正确解析policy_report

### Day 3: Strategy Advisor
1. **上午**
   - 实现 `strategy_advisor.py`
   - 实现加权聚合逻辑
   
2. **下午**
   - 完善Prompt中的计算公式说明
   - 编写单元测试
   - 测试不同情绪区间的仓位映射

3. **验收**
   - 单元测试通过
   - 加权计算逻辑正确

### Day 4: 集成测试和优化
1. **上午**
   - 串联测试（Macro → Policy → Sector → Strategy）
   - 验证数据流转
   
2. **下午**
   - 优化Prompt
   - 完善错误处理
   - Code Review

3. **验收**
   - 所有Agent串联运行正常
   - JSON输出格式统一
   - 测试覆盖率 ≥ 80%

---

## ✅ 验收标准

### 功能验收
- [ ] 4个Agent节点全部实现
- [ ] 每个Agent能够调用对应的工具
- [ ] 每个Agent能够输出JSON格式的报告
- [ ] Strategy Advisor能够综合上游报告
- [ ] 工具调用计数器在所有Agent中正常工作

### 质量验收
- [ ] 所有单元测试通过
- [ ] 测试覆盖率 ≥ 80%
- [ ] 代码符合现有风格（参考market_analyst.py）
- [ ] 所有函数有完整的docstring
- [ ] 日志记录清晰

### 输出验收
- [ ] 所有JSON报告包含 confidence 和 sentiment_score
- [ ] sentiment_score 范围在 -1.0 到 1.0
- [ ] confidence 范围在 0.0 到 1.0
- [ ] JSON格式可以被正确解析

---

## 📊 进度跟踪

| 任务 | 负责人 | 开始时间 | 预计完成 | 实际完成 | 状态 |
|------|--------|----------|----------|----------|------|
| 任务2.1 Macro Analyst | - | - | Day 1 | - | 📋 待开始 |
| 任务2.2 Policy Analyst | - | - | Day 2 上午 | - | 📋 待开始 |
| 任务2.3 Sector Analyst | - | - | Day 2 下午 | - | 📋 待开始 |
| 任务2.4 Strategy Advisor | - | - | Day 3 | - | 📋 待开始 |
| 任务2.5 单元测试 | - | - | 各任务同步 | - | 📋 待开始 |
| 集成测试和优化 | - | - | Day 4 | - | 📋 待开始 |

---

## ⚠️ 注意事项

### Prompt工程
1. **明确角色定义**：在System Prompt中清晰定义Agent的职责
2. **强制JSON格式**：在Prompt中嵌入JSON Schema示例
3. **评分指南**：提供情绪评分的具体规则
4. **示例输出**：给出完整的JSON输出示例

### 工具调用
1. **防止死循环**：每个Agent都要有工具调用计数器
2. **降级方案**：达到最大次数时返回有意义的降级报告
3. **工具描述**：使用 `Annotated` 提供清晰的参数说明

### 状态管理
1. **字段命名**：遵循现有规范（如 `macro_report`）
2. **计数器命名**：`macro_tool_call_count` 格式
3. **返回值**：必须返回字典，包含 messages 和相关字段

### 最佳实践
1. **参考现有实现**：`market_analyst.py` 是最好的模板
2. **日志记录**：记录节点开始、工具调用、报告提取等关键步骤
3. **异常处理**：所有外部调用都要有try-except

---

## 🔗 相关资源

- **参考实现**：`tradingagents/agents/analysts/market_analyst.py`
- **Prompt模板示例**：详细设计文档 第2.5节
- **LangChain文档**：https://python.langchain.com/docs/modules/prompts/
- **JSON提取技巧**：使用 `content.index('{')` 和 `content.rindex('}')`

---

**上一阶段**：[阶段一-数据层与工具层](./阶段一-数据层与工具层.md)  
**下一阶段**：[阶段三-状态与路由扩展](./阶段三-状态与路由扩展.md)

---

**版本**: v1.0  
**创建日期**: 2024-12-11  
**最后更新**: 2024-12-11
