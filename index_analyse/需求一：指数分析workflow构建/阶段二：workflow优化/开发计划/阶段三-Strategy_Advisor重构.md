# 阶段三：Strategy Advisor重构

## 📋 阶段概述

**目标**：重构Strategy Advisor，实现统一决策逻辑，成为系统中唯一的决策节点

**预计时间**：3-4天  
**优先级**：🔴 最高（核心决策）  
**依赖**：阶段一、阶段二完成

---

## 🎯 本阶段交付物

### 修改文件
1. `tradingagents/agents/analysts/strategy_advisor.py` - 重构Strategy Advisor
2. `tradingagents/agents/utils/decision_algorithms.py` - 新增决策算法模块
3. `tests/agents/test_strategy_advisor.py` - 更新测试
4. `tests/utils/test_decision_algorithms.py` - 新增算法测试

---

## 📝 详细开发任务

### 任务3.1：创建决策算法模块

**文件**：`tradingagents/agents/utils/decision_algorithms.py`

**功能清单**：
```python
"""
决策算法模块

提供Strategy Advisor使用的各类决策算法
"""

def calculate_base_position(
    policy_strength: str,
    policy_continuity: float,
    macro_score: float
) -> float:
    """
    基础仓位决策算法
    
    Args:
        policy_strength: 政策支持强度 (强/中/弱)
        policy_continuity: 政策连续性评分 (0-1)
        macro_score: 宏观情绪评分 (0-1)
        
    Returns:
        基础仓位 (0.4-0.8)
    """
    # 决策逻辑
    if policy_strength == "强" and macro_score > 0.6:
        base = 0.65
    elif policy_strength == "强" and macro_score > 0.4:
        base = 0.60
    elif policy_strength == "中" and macro_score > 0.5:
        base = 0.50
    elif policy_strength == "中":
        base = 0.45
    else:  # 弱
        base = 0.40
    
    # 政策连续性调整
    continuity_adj = (policy_continuity - 0.5) * 0.1
    
    final = base + continuity_adj
    return max(0.40, min(0.80, final))


def calculate_short_term_adjustment(
    news_impact_strength: str,
    news_credibility: float,
    news_duration: str
) -> float:
    """
    短期调整决策算法
    
    Args:
        news_impact_strength: 新闻影响强度 (高/中/低)
        news_credibility: 新闻可信度 (0-1)
        news_duration: 影响持续期 (短期/中期/长期)
        
    Returns:
        短期调整 (-0.2 到 +0.2)
    """
    # 基础调整值
    if news_impact_strength == "高":
        if "中期" in news_duration:
            base_adj = 0.15
        else:  # 短期
            base_adj = 0.10
    elif news_impact_strength == "中":
        base_adj = 0.05
    else:  # 低
        base_adj = 0.0
    
    # 可信度调整
    credibility_factor = news_credibility
    
    final_adj = base_adj * credibility_factor
    return max(-0.20, min(0.20, final_adj))


def generate_position_breakdown(
    base_position: float,
    short_term_adjustment: float,
    final_position: float
) -> dict:
    """
    生成分层持仓策略
    
    规则:
    - 核心长期仓位 = base_position * 0.67
    - 战术配置 = short_term_adjustment + (base_position * 0.33)
    - 现金储备 = 1 - final_position
    """
    core_holding = base_position * 0.67
    tactical = short_term_adjustment + (base_position * 0.33)
    cash_reserve = 1.0 - final_position
    
    return {
        "core_holding": round(core_holding, 2),
        "tactical_allocation": round(tactical, 2),
        "cash_reserve": round(cash_reserve, 2)
    }


def generate_adjustment_triggers(
    policy_report: str,
    news_report: str
) -> dict:
    """
    生成动态调整触发条件
    """
    # 解析新闻类型
    has_policy_rumor = "政策传闻" in news_report
    
    if has_policy_rumor:
        return {
            "increase_to": 0.90,
            "increase_condition": "政策正式官宣",
            "decrease_to": 0.40,
            "decrease_condition": "传闻证伪或外部风险加剧"
        }
    else:
        return {
            "increase_to": 0.80,
            "increase_condition": "政策进一步加码",
            "decrease_to": 0.50,
            "decrease_condition": "宏观环境恶化"
        }
```

**验收标准**：
- ✅ 决策逻辑清晰
- ✅ 边界值处理正确
- ✅ 单元测试覆盖

---

### 任务3.2：重构Strategy Advisor节点

**核心实现**：
```python
def create_strategy_advisor(llm, toolkit):
    """
    创建策略顾问节点（v2.1重构版）
    
    职责: 唯一的决策节点，整合所有上游信息给出最终仓位建议
    """
    
    def strategy_advisor_node(state):
        """策略顾问节点"""
        logger.info("🎯 [策略顾问] 节点开始 - 统一决策")
        
        # 1. 读取上游报告（只包含信息，不包含决策）
        macro_report = state.get("macro_report", "")
        policy_report = state.get("policy_report", "")
        international_news_report = state.get("international_news_report", "")
        sector_report = state.get("sector_report", "")
        
        # 2. 提取各项分析指标
        ## 从 Macro Analyst
        macro_score = extract_macro_sentiment_score(macro_report)
        economic_cycle = extract_economic_cycle(macro_report)
        
        ## 从 Policy Analyst
        policy_strength = extract_policy_support_strength(policy_report)
        policy_continuity = extract_policy_continuity(policy_report)
        
        ## 从 International News Analyst
        news_impact_strength = extract_news_impact_strength(
            international_news_report
        )
        news_credibility = extract_news_credibility(
            international_news_report
        )
        news_duration = extract_news_duration(
            international_news_report
        )
        
        ## 从 Sector Analyst
        sector_heat = extract_sector_heat_score(sector_report)
        
        logger.info(f"📊 提取指标: policy={policy_strength}, news={news_impact_strength}, macro={macro_score}")
        
        # 3. 决策算法 - 基础仓位
        base_position = calculate_base_position(
            policy_strength=policy_strength,
            policy_continuity=policy_continuity,
            macro_score=macro_score
        )
        logger.info(f"💼 基础仓位决策: {base_position:.2%}")
        
        # 4. 决策算法 - 短期调整
        short_term_adjustment = calculate_short_term_adjustment(
            news_impact_strength=news_impact_strength,
            news_credibility=news_credibility,
            news_duration=news_duration
        )
        logger.info(f"⚡ 短期调整决策: {short_term_adjustment:+.2%}")
        
        # 5. 计算最终仓位
        final_position = base_position + short_term_adjustment
        final_position = max(0.0, min(1.0, final_position))
        logger.info(f"🎯 最终仓位: {final_position:.2%}")
        
        # 6. 生成分层策略
        position_breakdown = generate_position_breakdown(
            base_position,
            short_term_adjustment,
            final_position
        )
        
        # 7. 生成动态调整触发条件
        adjustment_triggers = generate_adjustment_triggers(
            policy_report,
            international_news_report
        )
        
        # 8. 调用LLM生成综合报告
        system_prompt = """你是一位投资策略顾问。

请基于以下分析指标，生成最终的投资策略建议：

**分析指标**:
- 基础仓位: {base_position:.2%} (基于政策支持强度和宏观环境)
- 短期调整: {short_term_adjustment:+.2%} (基于国际新闻影响)
- 最终仓位: {final_position:.2%}

**分层持仓**:
- 核心长期: {core_holding:.2%}
- 战术配置: {tactical:.2%}
- 现金储备: {cash_reserve:.2%}

**动态调整触发**:
- 提升至{increase_to:.2%}: {increase_condition}
- 降至{decrease_to:.2%}: {decrease_condition}

请生成详细的策略报告，包括：
1. 市场outlook
2. 仓位建议理由
3. 关键风险
4. 机会板块
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        prompt = prompt.partial(
            base_position=base_position,
            short_term_adjustment=short_term_adjustment,
            final_position=final_position,
            core_holding=position_breakdown["core_holding"],
            tactical=position_breakdown["tactical_allocation"],
            cash_reserve=position_breakdown["cash_reserve"],
            increase_to=adjustment_triggers["increase_to"],
            increase_condition=adjustment_triggers["increase_condition"],
            decrease_to=adjustment_triggers["decrease_to"],
            decrease_condition=adjustment_triggers["decrease_condition"]
        )
        
        chain = prompt | llm
        result = chain.invoke({"messages": state["messages"]})
        
        # 9. 构建输出
        strategy_output = {
            "final_position": final_position,
            "position_breakdown": position_breakdown,
            "adjustment_triggers": adjustment_triggers,
            "decision_rationale": f"基于{policy_strength}政策支持({base_position:.2%})+{news_impact_strength}新闻影响({short_term_adjustment:+.2%})={final_position:.2%}"
        }
        
        from langchain_core.messages import AIMessage
        clean_message = AIMessage(content=result.content)
        
        logger.info("🎯 [策略顾问] ✅ 决策完成")
        
        return {
            "messages": [clean_message],
            "strategy_report": strategy_output
        }
    
    return strategy_advisor_node
```

**验收标准**：
- ✅ 提取所有上游指标
- ✅ 实现完整决策算法
- ✅ 输出分层策略
- ✅ 输出触发条件
- ✅ **不直接读取上游的仓位值**

---

### 任务3.3：编写单元测试

**核心测试**：
```python
def test_decision_algorithm():
    """测试决策算法正确性"""
    # 场景1: 强政策 + 高新闻影响
    base = calculate_base_position("强", 0.9, 0.7)
    assert 0.60 <= base <= 0.70
    
    adj = calculate_short_term_adjustment("高", 0.8, "中期")
    assert 0.10 <= adj <= 0.15
    
    # 场景2: 弱政策 + 低新闻影响
    base = calculate_base_position("弱", 0.5, 0.4)
    assert 0.35 <= base <= 0.45


def test_strategy_advisor_integration():
    """测试Strategy Advisor完整决策流程"""
    # 模拟上游输出（只包含指标，不包含仓位）
    state = {
        "macro_report": json.dumps({
            "sentiment_score": 0.7,
            "economic_cycle": "复苏期"
        }),
        "policy_report": json.dumps({
            "overall_support_strength": "强",
            "long_term_confidence": 0.9
        }),
        "international_news_report": json.dumps({
            "impact_strength": "高",
            "confidence": 0.8,
            "impact_duration": "中期"
        }),
        "sector_report": json.dumps({
            "sentiment_score": 0.85
        }),
        "messages": []
    }
    
    result = strategy_advisor_node(state)
    strategy = result["strategy_report"]
    
    # 验证输出
    assert "final_position" in strategy
    assert 0.6 <= strategy["final_position"] <= 0.85
    assert "position_breakdown" in strategy
    assert "adjustment_triggers" in strategy
```

---

## 📊 进度跟踪

- [ ] **任务3.1**: 创建决策算法模块 (1天)
- [ ] **任务3.2**: 重构Strategy Advisor (1.5天)
- [ ] **任务3.3**: 编写单元测试 (1天)

### 验收标准

✅ **决策逻辑验收**：
- 实现完整决策算法
- 不直接读取上游仓位
- 决策结果合理

✅ **质量验收**：
- 算法测试覆盖≥90%
- 集成测试通过

---

## ⚠️ 注意事项

1. **决策算法**: 充分测试各种场景
2. **边界处理**: 仓位限制在0-1之间
3. **日志记录**: 记录决策过程

---

**阶段负责人**: ___________  
**预计完成日期**: ___________  
**实际完成日期**: ___________
