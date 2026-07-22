# Serenity.skill

**Turn your investment agent into a supply-chain bottleneck hunter.**

Give it a market theme. It investigates live sources, maps the value chain, finds scarce constraints, ranks public-company research priorities, and writes the strongest reasons the idea could fail before you chase the story.

[中文 README](README.md)

```text
market story -> system change -> required parts -> supply-chain layers
-> scarce constraints -> public companies -> evidence -> repricing path
-> what could prove the idea wrong
```

## What It Does

Serenity.skill is an Agent Skill for tool-using investment research agents.

It helps an agent move from broad market narratives to evidence-backed research priorities:

- Deep theme research across AI infrastructure, semiconductors, CPO, advanced packaging, power equipment, robotics, materials, testing, and other supply-chain-heavy sectors.
- Cross-market candidate discovery for US, Hong Kong, A-share, Taiwan, Japan, Korea, and Europe.
- Single-company thesis challenges: exact chain position, evidence quality, customer dependence, substitution risk, financing risk, and what the market may be missing.
- Research partner conversations that push ideas from story to proof.
- Local scoring through a standard-library Python scorecard.

The Skill works best when the host agent has web search, browser, filings, market-data, and Python access. Local scripts use only local inputs.

## Quick Start

### Codex / OpenAI Agent Skills / Generic Agent Skills Clients

User-level install:

```bash
SKILL_DIR="$HOME/.agents/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

Project-level install:

```bash
SKILL_DIR=".agents/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

### Claude Code

User-level install:

```bash
SKILL_DIR="$HOME/.claude/skills/serenity-skill"
mkdir -p "$SKILL_DIR"
cp -R SKILL.md LICENSE references assets scripts examples agents "$SKILL_DIR"/
```

Project-level install:

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

### OpenClaw / Other AgentSkills-Compatible Clients

Place `SKILL.md`, `LICENSE`, `references/`, `assets/`, `scripts/`, `examples/`, and `agents/` in the client's `serenity-skill/` directory. README and project-maintenance docs are for the GitHub repository and do not need to be installed into the runtime skill directory.

## Try It

```text
Use serenity-skill to deeply research A-share AI semiconductor opportunities.
Map the value chain, investigate current sources, rank the top research priorities,
explain the evidence, and say what could prove each idea wrong.
```

```text
Use serenity-skill to challenge this company's CPO supplier thesis.
Where does it sit in the chain, what evidence supports it, and what would weaken the idea?
```

```text
用 serenity-skill 深度调研现在 A 股 AI 半导体产业链，
找 5 个最值得优先研究的标的，给出产业链位置、证据、排序理由和主要风险。
```

## Example Output Style

The Skill aims for normal research-partner language:

```text
I would prioritize advanced packaging equipment, optical-interconnect upstream materials,
and AI server power components. They sit closer to real expansion constraints than the
obvious AI ticker basket.

The first group ranks higher because capacity qualification and customer validation
can take time, and public markets often recognize the downstream demand before they
price the upstream constraint.

The main thing that would weaken this view is simple: if customers can qualify alternate
suppliers faster than expected, the scarce-layer logic fades.
```

Chinese outputs use the same style:

```text
我会优先看三层：先进封装设备、光通信上游材料、AI 服务器电源链。
原因是它们更接近真实扩产约束，市场也更容易先定价下游故事，再回头找上游卡点。

第一优先级要查的是客户认证和产能证据。故事之外还需要订单、认证、毛利率或收入结构变化，
否则这个标的只能算线索。
```

## Local Scorecard

Generate a template:

```bash
python scripts/serenity_scorecard.py --template > my-company.json
```

Run a score:

```bash
python scripts/serenity_scorecard.py --format md my-company.json
```

Validate the Skill package:

```bash
python scripts/validate_skill.py .
```

## Repository Layout

```text
serenity-skill/
├── SKILL.md
├── README.md
├── README.en.md
├── README.zh-CN.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   ├── deep-research-workflow.md
│   ├── evidence-ladder.md
│   ├── market-source-playbook.md
│   ├── serenity-dialogue-protocol.md
│   ├── output-style-and-language.md
│   ├── public-profile-and-evaluation.md
│   ├── research-sources.md
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

## Boundary

This is an independent public-methodology project inspired by public [Serenity / @aleabitoreddit](https://x.com/aleabitoreddit) research patterns. It supports research, ranking, and reasoning. It has zero broker access, zero wallet access, and zero trade execution.

Company facts should come from filings, exchange documents, company announcements, transcripts, regulatory/project records, patents, standards, reputable media, and specialist analysis.

## License

MIT
