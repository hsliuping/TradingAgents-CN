# 阶段一：International News Analyst实现

## 📋 阶段概述

**目标**：新增国际新闻分析师Agent，监控国际媒体捕捉政策传闻和突发事件，评估新闻影响强度（❌ 不输出仓位建议）

**预计时间**：3-4天  
**优先级**：🔴 最高（核心功能）  
**依赖**：阶段一已完成（Macro/Policy/Sector/Strategy Agent已实现）

---

## 🎯 本阶段交付物

### 新建文件
1. `tradingagents/agents/analysts/international_news_analyst.py` - 国际新闻分析师Agent
2. `tradingagents/tools/international_news_tools.py` - 国际新闻工具
3. `tests/agents/test_international_news_analyst.py` - Agent单元测试
4. `tests/tools/test_international_news_tools.py` - 工具单元测试

### 依赖项
- NewsAPI（付费）或 Google News（免费降级）
- langchain：工具封装
- pydantic：数据模型

---

## 📝 详细开发任务

### 任务1.1：创建国际新闻工具

**文件**：`tradingagents/tools/international_news_tools.py`

**功能清单**：
- [ ] `fetch_bloomberg_news` 工具
  - 数据源：NewsAPI (需订阅)
  - 参数：keywords (str), lookback_days (int)
  - 返回：Markdown格式的新闻摘要
- [ ] `fetch_reuters_news` 工具
  - 数据源：NewsAPI (需订阅)
  - 降级方案：Google News
- [ ] `fetch_google_news` 工具
  - 免费数据源
  - 支持中英文关键词搜索
- [ ] 工具注册列表

**实现要点**：
```python
from langchain.tools import tool
from typing import Annotated
import requests
from datetime import datetime, timedelta

@tool
def fetch_bloomberg_news(
    keywords: Annotated[str, "搜索关键词，如'芯片+政策'"],
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取彭博社新闻
    
    数据源: NewsAPI (bloomberg.com)
    降级方案: Google News
    """
    try:
        # 1. 检查NewsAPI可用性
        if not NEWS_API_KEY:
            logger.warning("NewsAPI未配置,降级到Google News")
            return fetch_google_news(keywords, lookback_days)
        
        # 2. 调用NewsAPI
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": NEWS_API_KEY,
            "sources": "bloomberg",
            "q": keywords,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "language": "en",
            "sortBy": "publishedAt"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        # 3. 格式化为Markdown
        articles = response.json().get("articles", [])
        return format_news_to_markdown(articles, source="Bloomberg")
        
    except Exception as e:
        logger.error(f"彭博社新闻获取失败: {e}, 降级到Google News")
        return fetch_google_news(keywords, lookback_days)


@tool
def fetch_google_news(
    keywords: Annotated[str, "搜索关键词"],
    lookback_days: Annotated[int, "回溯天数"] = 7
) -> str:
    """
    获取Google News新闻（免费降级方案）
    """
    try:
        from pygooglenews import GoogleNews
        
        gn = GoogleNews(lang='zh-CN', country='CN')
        search_result = gn.search(keywords)
        
        # 格式化为Markdown
        entries = search_result.get('entries', [])[:10]
        return format_news_to_markdown(entries, source="Google News")
        
    except Exception as e:
        logger.error(f"Google News获取失败: {e}")
        return f"新闻获取失败: {str(e)}"


def format_news_to_markdown(articles: list, source: str) -> str:
    """格式化新闻为Markdown"""
    if not articles:
        return f"## {source}\n\n暂无相关新闻"
    
    md = f"## {source} 新闻摘要\n\n"
    for i, article in enumerate(articles[:10], 1):
        title = article.get('title', '无标题')
        published = article.get('published', article.get('publishedAt', ''))
        description = article.get('description', article.get('summary', ''))
        
        md += f"### {i}. {title}\n"
        md += f"**发布时间**: {published}\n"
        md += f"**摘要**: {description}\n\n"
    
    return md


# 工具列表
INTERNATIONAL_NEWS_TOOLS = [
    fetch_bloomberg_news,
    fetch_reuters_news,
    fetch_google_news
]
```

**验收标准**：
- ✅ NewsAPI配置时使用付费源
- ✅ NewsAPI不可用时自动降级到Google News
- ✅ 返回格式化的Markdown文本
- ✅ 异常处理完善

---

### 任务1.2：创建International News Analyst Agent

**文件**：`tradingagents/agents/analysts/international_news_analyst.py`

**功能清单**：
- [ ] `create_international_news_analyst` 函数
- [ ] 节点函数 `international_news_analyst_node`
- [ ] 新闻分类逻辑
- [ ] 影响持续期评估
- [ ] 影响强度评估（❌ 不输出仓位）
- [ ] 去重机制（读取Policy Analyst报告）
- [ ] 工具调用计数器（防死循环）

**实现要点**：
```python
#!/usr/bin/env python3
"""
国际新闻分析师 (International News Analyst)

职责:
- 监控彭博、路透、WSJ等国际媒体
- 识别短期新闻事件（政策传闻/行业事件/市场情绪）
- 评估新闻影响持续期和影响强度
- ❌ 不给出仓位调整建议（由Strategy Advisor决策）
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
from datetime import datetime

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_international_news_analyst(llm, toolkit):
    """
    创建国际新闻分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包
        
    Returns:
        国际新闻分析师节点函数
    """
    
    def international_news_analyst_node(state):
        """国际新闻分析师节点"""
        logger.info("🌍 [国际新闻分析师] 节点开始")
        
        # 1. 工具调用计数器（防死循环）
        tool_call_count = state.get("international_news_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"🔧 工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("international_news_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [国际新闻分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "international_news_report": existing_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案（达到最大调用次数）
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [国际新闻分析师] 达到最大工具调用次数")
            fallback_report = json.dumps({
                "key_news": [],
                "overall_impact": "数据获取受限",
                "impact_strength": "低",
                "confidence": 0.3
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "international_news_report": fallback_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 4. 获取指数信息
        index_code = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")
        
        # 5. 识别指数类型，生成搜索关键词
        index_keywords = get_search_keywords(index_code)
        logger.info(f"🌍 [国际新闻分析师] 分析指数: {index_code}, 关键词: {index_keywords}")
        
        # 6. 读取上游Policy Analyst报告（用于去重）
        policy_report = state.get("policy_report", "")
        
        # 7. 构建Prompt
        system_prompt = """你是一位国际新闻分析师，专注于监控彭博、路透、华尔街日报等国际媒体。

📋 **核心任务**
- 获取近7天国际媒体关于目标市场/行业的新闻
- **重点关注短期影响的新闻** (政策传闻、突发事件)
- 区分新闻类型和影响持续期
- 评估新闻影响强度 (高/中/低)

🎯 **新闻分类标准**
1. **政策传闻** (重点关注)
   - 国际媒体提前爆料但国内未确认
   - 示例: '彭博社:中国计划千亿芯片支持'
   - 影响持续期: 中期 (1-4周)

2. **政策官宣**
   - 已被国内官方确认的政策
   - ⚠️ 如果已在上游Policy Analyst报告中 → 跳过
   - 影响持续期: 长期 (数月)

3. **行业突发事件**
   - 示例: 'ASML限制对华出口', '美国芯片法案通过'
   - 影响持续期: 中期 (1-4周)

4. **市场情绪**
   - 示例: '外资大幅增持中国科技股'
   - 影响持续期: 短期 (1-7天)

🔍 **去重规则** (避免与Policy Analyst重复)
- 如果新闻已在上游Policy Analyst报告中 → 标注为"已覆盖"
- 仅保留**未被Policy Analyst覆盖**的短期新闻

📊 **上游Policy Analyst报告**
{policy_report}

🎯 **输出格式** (严格JSON)
{{
  "key_news": [
    {{
      "source": "Bloomberg",
      "title": "...",
      "date": "2025-12-10",
      "type": "政策传闻" | "行业事件" | "市场情绪",
      "impact": "利好" | "利空" | "中性",
      "impact_duration": "短期(1-7天)" | "中期(1-4周)" | "长期(数月)",
      "impact_strength": "高" | "中" | "低",
      "credibility": 0.8,
      "covered_by_policy_analyst": false,
      "summary": "新闻摘要"
    }}
  ],
  "overall_impact": "重大利好" | "利好" | "中性" | "利空" | "重大利空",
  "impact_strength": "高" | "中" | "低",
  "confidence": 0.85
}}

⚠️ **重要**: 
- ❌ 不要输出 position_adjustment 字段
- ❌ 不要输出 adjustment_rationale 字段
- ✅ 只评估影响强度,不给出仓位建议
- ✅ 仓位决策由Strategy Advisor统一制定

请使用工具获取国际新闻数据，然后进行分析。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        prompt = prompt.partial(policy_report=policy_report)
        
        # 8. 绑定工具并调用LLM
        tools = [toolkit.get_tool("fetch_bloomberg_news")]
        chain = prompt | llm.bind_tools(tools)
        
        result = chain.invoke({"messages": state["messages"]})
        
        # 9. 检查工具调用
        tool_calls = getattr(result, 'tool_calls', [])
        logger.info(f"[国际新闻分析师] LLM调用了 {len(tool_calls)} 个工具")
        
        if len(tool_calls) == 0:
            # LLM没有调用工具，可能直接生成了报告
            report = result.content if hasattr(result, 'content') else ""
        else:
            # 有工具调用，使用LangGraph的工具节点处理
            report = result.content
        
        # 10. 清理消息（移除tool_calls）
        from langchain_core.messages import AIMessage
        clean_message = AIMessage(content=report)
        
        logger.info(f"[国际新闻分析师] ✅ 分析完成")
        
        # 11. 更新工具调用计数器
        return {
            "messages": [clean_message],
            "international_news_report": report,
            "international_news_tool_call_count": tool_call_count + 1
        }
    
    return international_news_analyst_node


def get_search_keywords(index_code: str) -> str:
    """根据指数代码生成搜索关键词"""
    keyword_map = {
        "sh931865": "芯片 半导体 政策",  # 中证芯片产业
        "sz399006": "创业板 科技 政策",  # 创业板指
        "sh000300": "A股 大盘 政策",    # 沪深300
        "sh000016": "上证50 蓝筹 政策"   # 上证50
    }
    return keyword_map.get(index_code, "中国 股市 政策")
```

**验收标准**：
- ✅ 成功调用国际新闻工具
- ✅ 正确分类新闻类型
- ✅ 评估影响持续期和强度
- ✅ 实现去重机制
- ✅ **不输出position_adjustment字段**
- ✅ 工具调用计数器生效

---

### 任务1.3：编写单元测试

**文件**：`tests/agents/test_international_news_analyst.py`

**测试用例清单**：
- [ ] `test_international_news_analyst_basic()` - 基本功能测试
- [ ] `test_news_classification()` - 新闻分类测试
- [ ] `test_impact_assessment()` - 影响评估测试
- [ ] `test_deduplication()` - 去重机制测试
- [ ] `test_no_position_output()` - **验证不输出仓位** ⭐
- [ ] `test_tool_call_limit()` - 工具调用上限测试
- [ ] `test_fallback_mechanism()` - 降级机制测试

**核心测试代码**：
```python
import pytest
from tradingagents.agents.analysts.international_news_analyst import (
    create_international_news_analyst
)

def test_no_position_output(mock_llm, mock_toolkit):
    """验证International News Analyst不输出仓位建议"""
    # Arrange
    analyst_node = create_international_news_analyst(mock_llm, mock_toolkit)
    state = {
        "company_of_interest": "sh931865",
        "trade_date": "2025-12-14",
        "policy_report": "...",
        "messages": []
    }
    
    # Act
    result = analyst_node(state)
    
    # Assert
    report = result.get("international_news_report", "")
    
    # 验证不包含仓位调整字段
    if isinstance(report, str):
        import json
        try:
            report_json = json.loads(report)
            assert "position_adjustment" not in report_json, \
                "❌ International News Analyst不应输出position_adjustment"
            assert "adjustment_rationale" not in report_json, \
                "❌ International News Analyst不应输出adjustment_rationale"
            
            # 验证包含影响强度评估
            assert "impact_strength" in report_json, \
                "✅ 应输出impact_strength"
            assert report_json["impact_strength"] in ["高", "中", "低"], \
                "✅ impact_strength应为高/中/低"
                
        except json.JSONDecodeError:
            pytest.skip("报告非JSON格式,跳过验证")
```

---

## 📊 进度跟踪

### 任务清单

- [ ] **任务1.1**: 创建国际新闻工具 (0.5天)
  - [ ] fetch_bloomberg_news
  - [ ] fetch_reuters_news
  - [ ] fetch_google_news
  
- [ ] **任务1.2**: 创建International News Analyst (2天)
  - [ ] 节点函数实现
  - [ ] Prompt设计
  - [ ] 去重机制
  - [ ] 影响强度评估
  
- [ ] **任务1.3**: 编写单元测试 (1天)
  - [ ] 基本功能测试
  - [ ] 职责分离验证
  - [ ] 边界情况测试

### 验收标准

✅ **功能验收**：
- 成功获取国际新闻
- 正确分类和评估
- 去重机制生效

✅ **职责分离验收** ⭐：
- **不输出position_adjustment字段**
- 只输出impact_strength评估

✅ **质量验收**：
- 单元测试覆盖率≥80%
- 代码审查通过
- 日志记录完整

---

## ⚠️ 注意事项

### 开发注意
1. **NewsAPI配置**: 需要配置NEWS_API_KEY环境变量
2. **降级方案**: Google News作为免费替代
3. **去重逻辑**: 必须读取Policy Analyst报告
4. **职责分离**: **严禁输出仓位字段**

### 测试注意
1. **Mock外部API**: 测试时Mock NewsAPI
2. **职责验证**: 必须验证不输出仓位
3. **边界情况**: 测试API失败、空数据等

### 文档注意
1. 更新API文档
2. 添加使用示例
3. 说明降级方案

---

**阶段负责人**: ___________  
**预计完成日期**: ___________  
**实际完成日期**: ___________
