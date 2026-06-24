---
name: investor-panel
description: 50 位投资大佬评审团。给定一只股票的 dimensions.json 和 raw_data.json，让 50 位投资者各自按自己的方法论打分并输出 Pydantic Signal（signal/confidence/score/verdict/comment）。覆盖经典价值派、成长投资派、宏观对冲派、技术趋势派、中国价投派、A股游资派、量化系统派 7 大流派。当用户请求"评审团/50 大佬怎么看/某某会买吗/做一次大佬投票"时使用。
version: 3.8.0
author: FloatFu-true
license: MIT
metadata:
  hermes:
    tags: [finance, investor-panel, voting, role-play, a-share, value-investing, growth-investing]
    related_skills: [deep-analysis]
---

# Investor Panel · 50 贤评审团

## 调用上下文

读取以下输入：
- `.cache/{ticker}/dimensions.json` — 19 维评分
- `.cache/{ticker}/raw_data.json` — 原始数据
- `scripts/lib/investor_db.py` — 50 人元数据
- `scripts/lib/seat_db.py` — 22 位游资射程规则

输出：
- `.cache/{ticker}/panel.json` — 50 个 Signal + 投票统计

## 严格输出格式（Pydantic Signal，抄自 ai-hedge-fund）

每个投资者必须返回**严格 JSON**：

```json
{
  "investor_id": "buffett",
  "name": "巴菲特",
  "group": "A",
  "avatar": "avatars/buffett.svg",
  "signal": "bullish | neutral | bearish",
  "confidence": 87,
  "score": 82,
  "verdict": "强烈买入 | 买入 | 关注 | 观望 | 等待 | 回避 | 不达标 | 不适合",
  "reasoning": "1-3 句具体逻辑",
  "comment": "用该投资者语言风格的金句 1-2 句",
  "pass": ["..."],
  "fail": ["..."],
  "ideal_price": 16.20,
  "period": "3-5 年"
}
```

**Confidence 校准规则**：
- 85-100：核心方法论硬指标全部命中或全部不命中
- 60-84：多数命中
- 30-59：部分命中、需要等待信号
- 0-29：方法论不适用此股 / 信息不足

## 执行步骤

### Step 1: 加载元数据
```python
from lib.investor_db import INVESTORS, by_group
from lib.seat_db import SEATS, is_in_range
```

### Step 2: 对每位投资者
1. 取出 `fields` 白名单
2. 从 dimensions.json 提取相关字段
3. 读取该投资者所在 group 的 reference 文件（按需）
4. 用该投资者的方法论 + 语言样本生成 Signal（Claude 自己生成）
5. 校验 JSON 合法性

### Step 3: 游资射程预过滤（F 组特殊）
对 22 位游资，先用 `is_in_range(nickname, ticker_features)` 判断是否在射程内：
- 在射程 → 正常评分
- 不在射程 → `signal: "neutral"`, `verdict: "不适合"`, `confidence: 90`, `comment: "{nick}的射程是{style}，这只票不在风格内。"`

### Step 4: 汇总投票
```python
{
  "panel_consensus": (bullish_count / 50) * 100,
  "vote_distribution": Counter(verdict for i in investors),
  "signal_distribution": Counter(signal for i in investors),
  "investors": [...]
}
```

## 7 大流派详细方法论

按需读取下列 references：

| 组 | 文件 | 人数 |
|---|---|---|
| A 经典价值 | `references/group-a-classic-value.md` | 6 |
| B 成长投资 | `references/group-b-growth.md` | 4 |
| C 宏观对冲 | `references/group-c-macro-hedge.md` | 5 |
| D 技术趋势 | `references/group-d-technical.md` | 4 |
| E 中国价投 | `references/group-e-china-value.md` | 6 |
| F 游资 | `references/group-f-china-youzi.md` | 22 |
| G 量化系统 | `references/group-g-quant.md` | 3 |

## 📚 语料库 (必读)

**每次生成 comment 之前**必须读 `references/quotes-knowledge-base.md` 查找该投资者的真实公开原话和"风格"字段。这是知识库 single source of truth。

## 语言风格守则

每位投资者的 `comment` 字段必须**像他本人**：
- 巴菲特：温和、引用奥马哈、用"我们"
- 芒格：刻薄、反向思维、引用心理学偏误
- 索罗斯：哲学化、提"反身性"
- 章盟主：豪迈、提"格局"、不谈细节
- 赵老哥：直接、谈"题材"、谈"二板"
- 段永平：朴素、问"商业模式""人""价格"
- 陈小群：江湖气、谈"分歧""一线天""核按钮"

每组 reference 文件末尾有 3-5 句**真实公开语录**作为 few-shot。

## 完成检查

- [ ] panel.json 包含 50 个 Signal
- [ ] 每个 Signal 字段齐全
- [ ] 22 位游资里至少有 N 位返回"不适合"（除非这只票是热门题材龙头）
- [ ] panel_consensus / vote_distribution / signal_distribution 三个汇总字段已计算
