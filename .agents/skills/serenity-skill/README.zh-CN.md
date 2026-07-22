# Serenity.skill

**把你的投资 Agent 变成产业链瓶颈猎人。**

给它一个市场和方向，它会联网查资料、拆产业链、找供应链卡点、筛上市公司、给出优先研究排序，并说明这个判断最容易错在哪里。

[English README](README.en.md)

```text
市场故事 -> 系统变化 -> 必要零部件 -> 产业链层级
-> 供应链卡点 -> 上市公司 -> 证据 -> 市场可能没看清的地方
-> 什么情况说明这个判断错了
```

## 它能做什么

Serenity.skill 是一个给投资研究 Agent 用的 Skill。它的重点是让 Agent 先研究系统，再讨论股票。

它适合这些任务：

- 深度调研 AI 基建、半导体、CPO、先进封装、电力设备、机器人、材料、测试设备等产业链方向。
- 在美股、港股、A 股、台股、日股、韩股、欧股里做候选公司筛选。
- 挑战单家公司 thesis：它到底卡在哪一层，证据强度够不够，客户是否绕得开，融资和治理风险有多大。
- 像研究伙伴一样聊天：把想法从“故事”推到“证据”。
- 用本地 Python 脚本做瓶颈控制力打分。

它最适合带有联网、浏览器、财报公告、市场数据和 Python 工具的 Agent 环境。仓库里的脚本只处理本地输入。

## 快速安装

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

## 直接这样用

```text
用 serenity-skill 深度调研现在 A 股 AI 半导体产业链，
找 5 个最值得优先研究的标的，给出产业链位置、证据、排序理由和主要风险。
```

```text
用 serenity-skill 挑战这家公司“CPO 核心供应商”的说法。
它到底卡在哪一层？证据够不够？什么情况说明这个判断错了？
```

```text
我想学习 Serenity 式产业链研究方法。
每次只问我一个问题，带我从大趋势拆到供应链卡点和证据。
```

## 输出风格

它的回答应该像一个很强的研究伙伴在跟你讲判断：

```text
我会优先看三层：先进封装设备、光通信上游材料、AI 服务器电源链。
原因是它们更接近真实扩产约束，市场也更容易先定价下游故事，再回头找上游卡点。

第一优先级要查的是客户认证和产能证据。故事之外还需要订单、认证、毛利率或收入结构变化，
否则这个标的只能算线索。
```

它会尽量少用黑话。内部可以走复杂研究流程，最终回答保持正常对话。

## 本地打分脚本

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

## 仓库边界

这是一个独立的公开方法论项目，灵感来自 [Serenity / @aleabitoreddit](https://x.com/aleabitoreddit) 公开内容中可观察到的研究范式。它帮助做研究、排序和推理。仓库脚本只处理本地输入，功能范围限于研究辅助。

公司事实应以公告、交易所文件、财报、电话会、监管/项目文件、专利、标准、可信媒体和专业分析为依据。

## License

MIT
