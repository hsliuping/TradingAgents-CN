# claude_native — TradingAgents 原生化(Claude Code + Workflow)

把 TradingAgents 多智能体分析,用 **quant_db + a-stock-data skill 数据** + **Workflow 编排** + **Claude(无需任何 LLM API key)** 原生重建。

> ⚠️ 仅研究学习用途,**不构成投资建议**。数据可能滞后 T-1,结论为多智能体模型判断,未经回测。

## 为什么不用原项目的 LLM 链路

原项目每个分析师依赖 LLM 的 function-calling 工具调用;而本地 Claude Code 模型服务不是标准带工具调用的 API 端点。本模块改为「主控预取数据 → JSON → Workflow 多智能体只读定性」,LLM 即 Claude subagent,零 key、零额外进程。原项目 FastAPI/Vue/CLI 链路保持不变,本模块是并存的轻量替代路径。

## 架构(三层)

```
① 预取层(主控 Bash)    quant_db + a-stock-data → _tmp/<code>_data.json
② 编排层(Workflow)     只读 JSON → 4分析师+多空辩论+风控终裁 → 结构化决策
③ 渲染层(主控)         决策卡 + 批量汇总榜 → reports/<YYMMDD>/
```

## 前置

- Claude Code(提供 Workflow 与 subagent)
- a-stock-data skill 及其 venv(mootdx/pg8000/requests/pandas/numpy)
- quant_db 访问:`cp .env.example .env` 后填入凭据(`.env` 已 gitignored)

约定 `PY` = a-stock-data venv 的 python 绝对路径,例如:
`~/.../.claude/skills/a-stock-data/.venv/bin/python`

## 三步(在 Claude Code 中由主控执行)

1. **预取**(单只或逗号分隔批量):
   ```bash
   set -a; source .env; set +a
   $PY tradingagents_fetch.py 600845
   $PY tradingagents_fetch.py 600845,000938,300442
   ```
   → 产出 `_tmp/<code>_data.json`

2. **跑 workflow**(主控用 Workflow 工具,逐只):
   读 `_tmp/<code>_data.json` 为对象 →
   `Workflow({scriptPath:"claude_native/tradingagents.mjs", args:<对象>})`
   → 把返回对象写入 `_tmp/<code>_result.json`

3. **渲染**:
   ```bash
   $PY -c "import json,tradingagents_render as r; \
     res=json.load(open('_tmp/600845_result.json',encoding='utf-8')); \
     print(r.write_card(res,'reports/<YYMMDD>'))"
   ```
   批量汇总:`r.write_summary([res1,res2,...], 'reports/<YYMMDD>')`

## 文件

| 文件 | 职责 |
|---|---|
| `tradingagents_db.py` | quant_db:K线/估值/名称(凭据 env-only) |
| `tradingagents_astock.py` | a-stock-data:研报/资金/财务快照(从 SKILL.md lift) |
| `tradingagents_indicators.py` | MA/RSI/MACD/BOLL 纯函数 |
| `tradingagents_fetch.py` | 组装 `_data.json` |
| `tradingagents.mjs` | Workflow:4分析师+多空辩论+风控终裁(只读 JSON) |
| `tradingagents_render.py` | 决策卡 + 汇总榜 |

## 调参

- 辩论轮数:传给 workflow 的 args 里加 `debate_rounds: 2`(默认 1)。

## 数据源连通性备注

- `push2.eastmoney.com` / `push2his.eastmoney.com`(个股资金流 moneyflow)在部分网络不可达,已优雅降级为 null;资金情绪面仍由龙虎榜/融资融券/股东户数支撑。
- quant_db 为公网 PostgreSQL,沙箱默认放行。

## 测试

```bash
$PY -m pytest test_indicators.py test_render.py -q
```
