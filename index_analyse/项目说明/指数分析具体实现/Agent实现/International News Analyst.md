# Index News Analyst (综合新闻分析师)

> 原 International News Analyst (国际新闻分析师)

**职责**: 统筹分析所有影响市场的短期新闻，作为**统一的信息入口**。
*   **覆盖范围**：
    *   国际新闻（Bloomberg/Reuters/WSJ）
    *   国内政策传闻、非官方消息
    *   市场热点、突发事件（黑天鹅/灰犀牛）
*   **分析重点**：“快变量”——评估突发事件、传闻、情绪对市场的即时冲击（1-7天）和中短期影响（1-4周）。
*   **禁区**：❌ 不给出仓位调整建议。

**核心输出**: 深度综合新闻简报（Markdown）+ 结构化数据总结（JSON）。

**调用工具/接口**:
- `fetch_bloomberg_news()` - 彭博新闻
- `fetch_reuters_news()` - 路透新闻
- `fetch_google_news()` - 谷歌新闻
- `fetch_cn_international_news()` - 中国国际新闻
- `fetch_policy_news()` - 国内政策新闻（用于获取传闻和短期动态）

**数据处理与分析**:
`Index News Analyst` 会综合国内外多源信息，判断市场当前的主流叙事。它会特别关注**预期差**（外媒爆料 vs 国内现状），并对新闻进行分类（政策传闻、突发事件、情绪指标）。

**统一输出 JSON 格式**:
```json
{
  "key_news": [
    {
      "title": "新闻标题",
      "source_type": "国际媒体/国内传闻/官方吹风",
      "type": "政策传闻/行业事件/市场情绪",
      "impact": "利好/利空/中性",
      "impact_duration": "短期(1-7天)/中期(1-4周)",
      "impact_strength": "高/中/低",
      "summary": "简要摘要"
    }
  ],
  "market_sentiment": "恐慌/谨慎/乐观/狂热",
  "overall_impact": "利好/利空/中性",
  "confidence": 0.8
}
```

**降级报告 (Fallback Report) 示例**:
```json
{
  "key_news": [],
  "overall_impact": "【新闻降级】数据获取受限，无法分析新闻影响。",
  "impact_strength": "低",
  "confidence": 0.3
}
```
