"""把 workflow 结构化结果渲染成决策卡 markdown 与批量汇总榜。"""
import os

DISCLAIMER = "> ⚠️ 仅研究学习用途,**不构成投资建议**。数据可能滞后 T-1,结论为多智能体模型判断,未经回测。"


def render_card(res: dict) -> str:
    m = res.get("meta", {})
    f = res.get("final", {})
    sl = f.get("signal_lights", {})
    lines = [f"# {m.get('name','')}({m.get('code','')}) TradingAgents 决策卡", ""]
    lines.append(f"**信号灯**:综合 {sl.get('综合','-')} | 估值 {sl.get('估值','-')} | 资金 {sl.get('资金','-')}　"
                 f"**操作**:`{f.get('action','-')}`　**建议仓位**:{f.get('position_pct','-')}%")
    tpr = f.get("target_price_range") or []
    if len(tpr) == 2:
        lines.append(f"**目标价区间**:{tpr[0]} ~ {tpr[1]}　**数据日期**:{m.get('as_of_date','-')}")
    lines += ["", f"> **一句话**:{f.get('one_liner','')}", "", "## 四分析师要点"]
    for a in res.get("analyses", []):
        kp = "；".join(a.get("key_points", [])[:3])
        rk = "；".join(a.get("risks", [])[:2])
        lines.append(f"- **{a.get('dimension','')}**({a.get('stance','')} {a.get('score','')}分):{kp}"
                     + (f"　⚠️ {rk}" if rk else ""))
    lines += ["", "## 多空辩论摘要"]
    for d in res.get("debate", []):
        lines.append(f"- R{d.get('round','')} 多:{(d.get('bull') or {}).get('argument','')}")
        lines.append(f"- R{d.get('round','')} 空:{(d.get('bear') or {}).get('argument','')}")
    lines += ["", "## 交易员决策", str(res.get("trader", "")), "", "## 风控终裁"]
    lines.append("**催化**:" + "；".join(f.get("key_catalysts", [])))
    lines.append("**风险**:" + "；".join(f.get("key_risks", [])))
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def write_card(res: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    m = res.get("meta", {})
    path = os.path.join(out_dir, f"{m.get('code','x')}_{m.get('name','')}.md")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(render_card(res))
    return path


_LIGHT_ORDER = {"🟢": 0, "🟡": 1, "🔴": 2}
_ACTION_ORDER = {"BUY": 0, "HOLD": 1, "SELL": 2}


def render_summary(results: list) -> str:
    def key(res):
        f = res.get("final", {})
        sl = f.get("signal_lights", {})
        return (_LIGHT_ORDER.get(sl.get("综合"), 9), _ACTION_ORDER.get(f.get("action"), 9))
    rows = sorted(results, key=key)
    lines = ["# TradingAgents 决策汇总榜", "",
             "| 代码 | 名称 | 综合 | 估值 | 资金 | 操作 | 仓位 | 一句话 |",
             "|---|---|---|---|---|---|---|---|"]
    for res in rows:
        m = res.get("meta", {})
        f = res.get("final", {})
        sl = f.get("signal_lights", {})
        lines.append(f"| {m.get('code','')} | {m.get('name','')} | {sl.get('综合','-')} | "
                     f"{sl.get('估值','-')} | {sl.get('资金','-')} | {f.get('action','-')} | "
                     f"{f.get('position_pct','-')}% | {f.get('one_liner','')} |")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def write_summary(results: list, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "_汇总榜.md")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(render_summary(results))
    return path
