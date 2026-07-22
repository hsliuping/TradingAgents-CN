<div align="center">

# Serenity.skill

### 让 AI 用 Serenity 式投研方法，筛出上涨逻辑更清楚的股票和基金方向

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-black)](SKILL.md)
[![中文优先](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87%E4%BC%98%E5%85%88-red)](README.md)
[![English](https://img.shields.io/badge/English-README.en.md-lightgrey)](README.en.md)

</div>

看到 AI 半导体、机器人、CPO、算力、电力设备、创新药这些热点，很多人能感受到热度，却很难判断该看哪条产业链、哪类公司、哪只股票、哪个基金方向。

Serenity.skill 把 [Serenity / @aleabitoreddit](https://x.com/aleabitoreddit) 公开内容中可观察到的投研路径做成 Agent Skill。它会从热点出发，拆产业链，找供应链瓶颈，筛候选公司和基金方向，再检查公告、财报、客户、产能和风险，最后整理成一份优先研究清单。

它的工作方式很简单：先把热点拆开，看真实需求在哪里，再看哪个环节更难扩产、更难替代，最后回到股票和基金方向，判断哪些线索更值得继续深挖。

它适合面对热点信息流、希望建立系统筛选流程的投资者：让 AI 先完成第一轮深度研究，把模糊热度变成有逻辑、有证据、有风险边界的研究方向。

> Research support only. Serenity.skill 负责研究、排序和推理；最终买卖决策由你自己决定。

## 为什么是 Serenity 式方法

[Serenity / @aleabitoreddit](https://x.com/aleabitoreddit) 在公开内容中长期围绕 AI、半导体、光通信、机器人等科技主题做供应链研究。他的核心思路很清楚：大行情里真正有价值的机会，常常藏在系统扩张时最难绕开的关键环节。

Serenity.skill 复用的是这套公开方法论中的研究路径：

- 从大热点开始，先看真实需求来自哪里。
- 把主题拆成下游需求、系统集成、芯片/器件、设备、材料、封测、基础设施。
- 找低供应商数量、长验证周期、扩产困难、客户认证严格、材料纯度要求高的环节。
- 再回到股票和基金方向，判断谁更靠近真实瓶颈，谁主要只是蹭主题。
- 最后检查公告、财报、问询函、订单、产能、客户和风险，给出优先研究排序。

这个仓库做的是公开资料研究工具。它吸收 Serenity 式研究的结构化思路，同时要求所有公司判断回到公告、交易所文件、财报、电话会、监管/项目文件、专利、标准、可信媒体和专业分析。

## 它能帮你做什么

| 你现在遇到的问题 | 可以这样问 AI | Serenity.skill 会帮你看什么 |
|---|---|---|
| 刷到一个热点，感觉全网都在说，自己不知道从哪下手 | `最近 AI 半导体很火，普通人应该先研究哪些方向？` | 先拆产业链，再把更接近真实需求和扩产瓶颈的方向排出来 |
| 想买机器人方向，分不清整机、零部件、减速器、传感器谁更关键 | `机器人产业链里，哪些环节更可能先出机会？` | 比较不同环节的供需紧张度、竞争格局和证据强弱 |
| 看到别人推荐一只股票，担心它只是蹭热点 | `帮我挑战这家公司是不是 CPO 核心供应商` | 查它在产业链里的真实位置、客户证据、收入质量和主要风险 |
| 想买主题基金或 ETF，分不清哪个细分方向更值得看 | `机器人主题基金应该重点看哪些上游环节？` | 找基金背后的核心受益链条，提示需要核验的持仓方向 |
| 手里有几只候选股，想让 AI 帮你排个研究顺序 | `比较 A、B、C 三家公司，谁的上涨逻辑更清楚？` | 按产业链位置、证据强度、估值压力、风险点做优先级排序 |
| 每天刷消息很焦虑，想建立一套固定筛选流程 | `带我学 Serenity 式产业链研究，每次只问我一个问题` | 从热点、需求、卡点、证据、风险一步步建立研究框架 |

## 直接复制这个 Prompt

```text
用 serenity-skill 深度调研现在 A 股 AI 半导体产业链。
请联网查公告、财报、问询函、互动易、招投标、环评/能评、专利、客户认证和财务质量，
先排产业链层级，再找 5 个最值得优先研究的标的，
并说明卡住的环节、产业链位置、证据、排序理由和主要风险。
```

```text
用 serenity-skill 帮我研究最近机器人方向。
先拆产业链，再判断哪些环节更接近真实供需瓶颈，
最后给出股票和基金方向的优先研究清单。
```

```text
用 serenity-skill 挑战 [公司/股票代码]。
它到底卡在哪一层？证据够不够？市场可能高估了什么？
什么情况说明这个判断应该降级？
```

更多可复制模板见 [assets/research-prompt-pack.md](assets/research-prompt-pack.md)。

## 输出长什么样

```text
我会先看 [方向 A]，再看 [方向 B] 和 [方向 C]。

如果你想找股票线索，我会优先研究这几家公司：

1. [公司 A]：最接近 [关键瓶颈环节]，上涨逻辑来自 [需求增长/产能紧张/客户验证/国产替代]。
2. [公司 B]：处在 [产业链位置]，适合跟踪 [订单/毛利率/产能利用率]。
3. [公司 C]：弹性更大，但需要确认 [核心风险或缺失证据]。

如果你更想买基金或 ETF，我会先看暴露在 [细分方向 A] 和 [细分方向 B] 的产品，
再检查它们的前十大持仓里有没有 [公司 A]、[公司 B] 这类真正靠近瓶颈的公司。

我会暂时降低 [热门方向 X] 的优先级，因为它的故事很热，但现在还缺 [订单证据/利润兑现/客户认证]。

下一步先查三件事：
1. [公司 A] 最新财报里 [关键业务] 的收入和毛利率有没有变化。
2. [公司 B] 有没有新的客户认证、订单或扩产公告。
3. [相关基金/ETF] 的持仓是不是集中在真正受益的环节。
```

完整示例：

- [A 股 AI 半导体扫描](examples/a-share-ai-semiconductor-demo.md)
- [AI 基建瓶颈研究](examples/ai-infrastructure-chokepoint-demo.md)
- [研究伙伴式对话](examples/demo-conversation.md)

## 安装

### Codex / OpenAI Agent Skills / 通用 Agent Skills 客户端

用户级安装：

```bash
SKILL_DIR="$HOME/.agents/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

项目级安装：

```bash
SKILL_DIR=".agents/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

### Claude Code

用户级安装：

```bash
SKILL_DIR="$HOME/.claude/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

项目级安装：

```bash
SKILL_DIR=".claude/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

### Hermes Agent

```bash
SKILL_DIR="$HOME/.hermes/skills/research/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

### OpenClaw / 其他 AgentSkills-compatible 客户端

把 `SKILL.md`、`LICENSE`、`references/`、`assets/`、`scripts/`、`examples/`、`agents/` 放进对应客户端的 `serenity-skill/` 目录即可。README 和项目维护文档只用于 GitHub 展示，不需要安装到运行目录。

## 本地瓶颈打分

生成模板：

```bash
python scripts/serenity_scorecard.py --template > my-company.json
```

运行评分：

```bash
python scripts/serenity_scorecard.py --format md my-company.json
```

校验 Skill：

```bash
python scripts/validate_skill.py .
```

## 仓库结构

```text
serenity-skill/
├── SKILL.md
├── README.md
├── README.en.md
├── README.zh-CN.md
├── references/
│   ├── deep-research-workflow.md
│   ├── evidence-ladder.md
│   ├── market-source-playbook.md
│   ├── public-profile-and-evaluation.md
│   └── risk-and-compliance.md
├── assets/
│   ├── bottleneck-scorecard.json
│   ├── research-prompt-pack.md
│   └── thesis-template.md
├── scripts/
│   ├── serenity_scorecard.py
│   └── validate_skill.py
├── examples/
│   ├── a-share-ai-semiconductor-demo.md
│   ├── ai-infrastructure-chokepoint-demo.md
│   └── demo-conversation.md
└── evals/
    └── test-cases.md
```

## 研究边界

Serenity.skill 是独立的公开方法论项目，灵感来自 [Serenity / @aleabitoreddit](https://x.com/aleabitoreddit) 公开内容中可观察到的研究范式。它帮助做研究、排序和推理，功能范围限于研究辅助。

它提供研究优先级、证据链、风险核验和下一步检查清单。交易执行、账户操作、收益承诺和最终买卖判断始终由用户自己控制。

强结论应以公告、交易所文件、财报、电话会、监管/项目文件、专利、标准、可信媒体和专业分析为依据。社交媒体内容适合作为线索来源，最终判断要回到更强证据。

## License

MIT
