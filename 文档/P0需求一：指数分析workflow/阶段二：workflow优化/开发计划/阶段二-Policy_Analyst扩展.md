# 阶段二：Policy Analyst扩展

## 📋 阶段概述

**目标**：扩展Policy Analyst，新增长期政策识别和政策分层功能，输出政策支持强度评估（❌ 不输出基础仓位）

**预计时间**：2-3天  
**优先级**：🔴 高  
**依赖**：阶段一完成，Policy Analyst v2.0已实现

---

## 🎯 本阶段交付物

### 修改文件
1. `tradingagents/agents/analysts/policy_analyst.py` - 扩展Policy Analyst
2. `tradingagents/agents/utils/analysis_schemas.py` - 扩展PolicyAnalysis Schema
3. `tests/agents/test_policy_analyst.py` - 更新测试

---

## 📝 详细开发任务

### 任务2.1：扩展PolicyAnalysis Schema

**文件**：`tradingagents/agents/utils/analysis_schemas.py`

**新增字段**：
```python
class PolicyAnalysis(BaseModel):
    """政策分析输出结构（v2.1扩展）"""
    
    # ... 原有字段保持不变
    monetary_policy: str
    fiscal_policy: str
    industry_policy: str
    
    # 🆕 新增字段
    long_term_policies: List[LongTermPolicy] = Field(
        default_factory=list,
        description="长期战略政策列表"
    )
    overall_support_strength: str = Field(
        description="整体政策支持强度: 强/中/弱"
    )
    long_term_confidence: float = Field(
        ge=0.0, le=1.0,
        description="长期政策评估置信度"
    )


class LongTermPolicy(BaseModel):
    """长期政策模型"""
    name: str = Field(description="政策名称，如'自主可控'")
    duration: str = Field(description="影响持续期，如'5-10年'")
    support_strength: str = Field(description="支持强度: 强/中/弱")
    beneficiary_sectors: List[str] = Field(description="受益板块")
    policy_continuity: float = Field(
        ge=0.0, le=1.0,
        description="政策连续性评分"
    )
```

**验收标准**：
- ✅ Schema定义完整
- ✅ **不包含base_position_recommendation字段**
- ✅ 类型约束正确

---

### 任务2.2：扩展Policy Analyst Prompt

**修改内容**：

**新增系统提示**：
```python
"""
🎯 **政策分类** (v2.1新增)

1. **长期战略政策** (重点识别)
   - 特征: 国家战略、五年规划、产业扶持
   - 示例: '自主可控'、'新质生产力'、'碳中和'
   - 影响持续期: 5-10年
   - 支持强度: 强/中/弱 (← 只评估强度,不给仓位)

2. **中期政策措施**
   - 特征: 阶段性政策、专项基金、税收优惠
   - 示例: '新能源汽车补贴延长2年'
   - 影响持续期: 1-3年

3. **短期调控政策**
   - 特征: 降息降准、临时性补贴
   - 示例: '央行降准25BP'
   - 影响持续期: 数月
   - ⚠️ 由International News Analyst处理

📊 **输出要求** (v2.1新增)
- 识别长期战略政策
- 评估政策连续性(0-1评分)
- 给出整体支持强度(强/中/弱)
- ❌ 不给出基础仓位建议
- ✅ 仓位决策由Strategy Advisor统一制定
"""
```

**验收标准**：
- ✅ 明确政策分类标准
- ✅ 强调只评估强度，不给仓位
- ✅ Prompt清晰易懂

---

### 任务2.3：实现政策分层逻辑

**核心代码**：
```python
def classify_policy_type(policy_name: str, duration: str) -> str:
    """
    政策分层分类
    
    Args:
        policy_name: 政策名称
        duration: 影响持续期
        
    Returns:
        "长期战略政策" | "中期政策措施" | "短期调控政策"
    """
    # 长期关键词
    long_term_keywords = [
        "战略", "五年规划", "产业扶持", "自主可控",
        "新质生产力", "碳中和", "双循环"
    ]
    
    # 中期关键词
    mid_term_keywords = [
        "补贴", "税收优惠", "专项基金", "试点"
    ]
    
    # 短期关键词
    short_term_keywords = [
        "降准", "降息", "临时", "紧急"
    ]
    
    # 1. 关键词匹配
    if any(kw in policy_name for kw in long_term_keywords):
        return "长期战略政策"
    elif any(kw in policy_name for kw in mid_term_keywords):
        return "中期政策措施"
    elif any(kw in policy_name for kw in short_term_keywords):
        return "短期调控政策"
    
    # 2. 持续期判断
    if "5年" in duration or "10年" in duration:
        return "长期战略政策"
    elif "1年" in duration or "2年" in duration or "3年" in duration:
        return "中期政策措施"
    else:
        return "短期调控政策"


def assess_policy_support_strength(
    policies: List[Dict],
    policy_continuity_avg: float
) -> str:
    """
    评估整体政策支持强度
    
    Args:
        policies: 长期政策列表
        policy_continuity_avg: 平均政策连续性评分
        
    Returns:
        "强" | "中" | "弱"
    """
    if not policies:
        return "弱"
    
    # 统计强支持政策数量
    strong_count = sum(1 for p in policies if p.get("support_strength") == "强")
    
    # 综合评估
    if strong_count >= 2 and policy_continuity_avg > 0.7:
        return "强"
    elif strong_count >= 1 or policy_continuity_avg > 0.5:
        return "中"
    else:
        return "弱"
```

**验收标准**：
- ✅ 政策分类逻辑清晰
- ✅ 支持强度评估合理
- ✅ 边界情况处理完善

---

### 任务2.4：编写单元测试

**测试用例**：
```python
def test_no_base_position_output(mock_llm, mock_toolkit):
    """验证Policy Analyst不输出基础仓位"""
    # Arrange
    analyst_node = create_policy_analyst(mock_llm, mock_toolkit)
    state = {
        "company_of_interest": "sh931865",
        "trade_date": "2025-12-14",
        "messages": []
    }
    
    # Act
    result = analyst_node(state)
    
    # Assert
    report = result.get("policy_report", "")
    
    if isinstance(report, str):
        import json
        try:
            report_json = json.loads(report)
            
            # 验证不包含基础仓位字段
            assert "base_position_recommendation" not in report_json, \
                "❌ Policy Analyst不应输出base_position_recommendation"
            
            # 验证包含支持强度评估
            assert "overall_support_strength" in report_json, \
                "✅ 应输出overall_support_strength"
            assert report_json["overall_support_strength"] in ["强", "中", "弱"], \
                "✅ support_strength应为强/中/弱"
                
        except json.JSONDecodeError:
            pytest.skip("报告非JSON格式")


def test_long_term_policy_identification():
    """测试长期政策识别"""
    # 测试能够正确识别"自主可控"等长期战略政策
    pass


def test_policy_classification():
    """测试政策分层分类"""
    assert classify_policy_type("自主可控战略", "5-10年") == "长期战略政策"
    assert classify_policy_type("新能源补贴", "1-3年") == "中期政策措施"
    assert classify_policy_type("央行降准", "数月") == "短期调控政策"
```

---

## 📊 进度跟踪

### 任务清单

- [ ] **任务2.1**: 扩展PolicyAnalysis Schema (0.5天)
- [ ] **任务2.2**: 扩展Prompt (0.5天)
- [ ] **任务2.3**: 实现政策分层逻辑 (1天)
- [ ] **任务2.4**: 编写单元测试 (1天)

### 验收标准

✅ **功能验收**：
- 识别长期政策
- 评估政策连续性
- 输出支持强度

✅ **职责分离验收** ⭐：
- **不输出base_position_recommendation字段**
- 只输出overall_support_strength

✅ **质量验收**：
- 测试覆盖率≥80%
- 向后兼容v2.0

---

## ⚠️ 注意事项

1. **向后兼容**: 保持原有字段不变
2. **职责分离**: 严禁输出仓位建议
3. **Prompt优化**: 明确说明只评估强度

---

**阶段负责人**: ___________  
**预计完成日期**: ___________  
**实际完成日期**: ___________
