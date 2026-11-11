# -*- coding: utf-8 -*-
"""
猪周期 Pro —— Agent 工具守卫薄封装（共享工具层中唯一允许出现的猪周期入口）。

【铁律 / 不可违反】
1. 只读、只提示、不动手：本文件任何函数都不得下单/撤单/调仓，不得写死建仓比例，
   不得替用户做交易决策；输出仅为事实与状态，供 Agent 生成“决策备忘录”参考。
2. 数字唯一来源：所有数值必须直接取自 core.pro 猪周期域层（L0 供给定级 / L1 标的状态 /
   期货期限结构 / 知识库），本文件只做字段投影与组装，禁止第二套算法、禁止重算/改写数字。
3. 缺数据诚实标注（degraded / gap / error / unavailable），绝不伪造、绝不外推填充。
4. 社区版隔离：core.pro 为 Pro 专有包，社区版不存在。对它的 import 必须【延迟到函数体内】
   并用 try/except ImportError 接住，返回结构化 unavailable 结果；
   严禁在模块顶层 import core.pro —— 否则 ToolLoader 扫描本文件会整模块失败，污染所有工具注册。
5. 本文件是共享区（core/tools/）对 Pro 能力的“薄封装”，不含任何 Pro 业务实现。
6. 大白话输出：每个工具输出必须携带 plain_summary（给最终用户的大白话解读）、
   answer_style（措辞纪律）与 jargon_map（术语对照）；本层只翻译措辞，不产生任何新数字。
"""

import json
import logging
import types

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

# 每次返回都附带的纪律提示（Agent 据此约束措辞，不越界为交易指令）
_DISCIPLINE = [
    "只读参考，不自动买卖、不调仓、不写死建仓比例；系统只提示，动手权在人。",
    "慢变量（供给/去化/定级）给方向，快变量（价格/期货/市值）给时机，不用快变量论证慢变量。",
    "所有数字为 core.pro 域层同源读数；缺数据处已诚实标注，禁止外推或臆造。",
]

_UNAVAILABLE_MSG = (
    "猪周期 Pro 模块在当前版本不可用（core.pro 未安装或被裁剪）。"
    "本工具为只读守卫，已自动降级，不影响其他工具；如需该能力请使用 Pro 版本。"
)

# ---------- 大白话输出层 ----------
# 面向最终用户（普通研究者，非专业交易员）：助手引用这些工具作答时必须说大白话。
# 本层只做"措辞翻译"，所有数字仍取自域层字段，不产生任何新计算。

_ANSWER_STYLE = [
    "先给大白话结论，再给数据依据：像跟不懂期货的朋友解释那样说话。",
    "术语必须翻译后才能出现在给用户的回答里：L0/L1、contango、升水/贴水、百分位、定级 A/B/C、"
    "S1/S2、KDJ、金叉死叉、头均市值等，一律换成日常说法，或用括号补一句大白话解释。",
    "plain_summary 是现成的大白话解读，可直接引用或改写；jargon_map 是术语对照表。",
    "只转述系统规则（如'这套规则在这个阶段最多放三分之一资金'），不替用户决定买卖。",
]

_JARGON_PLAIN = {
    "L0": "看猪的：数母猪、看亏了多久、看出栏多不多，判断行业大方向",
    "L1": "看股票的：用牧原/温氏等养殖股的股价当温度计，判断什么时候动手",
    "定级A/B/C": "A=反转板上钉钉（母猪减得多、还在减、亏得久，三条全中）；B=有起色苗头但没坐实；C=供给没真减过，涨价多半是情绪",
    "偏A/偏C": "B 档内部再分强弱：偏A=拐点旁证拿到多数；偏C=一张旁证都没拿到",
    "等效去化": "把母猪减少折算成最终少出多少猪（考虑养殖效率提升后的真实去化）",
    "能繁母猪": "能下崽的母猪，决定约 10 个月后的生猪供应",
    "contango/远月升水": "市场在赌以后的猪更贵：期货上未来交货的价，比最近交货的贵",
    "backwardation/远月贴水": "市场觉得以后的猪反而更便宜（常见于当下缺猪）",
    "正常保有量/政策警戒线": "正常保有量＝政府文件给全国能繁母猪定的标准数（定期修订，2026-05 最新文件起为 3750 万头左右）；"
                  "实际存栏在它的 92%~103% 之间都算绿色区间（政策不出手；2026 版上限从 105% 收窄到 103%）。"
                  "跌破正常保有量本身政府不管，跌破它的 92%（警戒线，3450 万头）政府才会出手托产能",
    "百分位": "把今天的读数放进 2021 年以来的历史里排队：第 85 百分位=比历史上 85% 的时候都高",
    "S1/S2": "两套持股规则档位：S1=周线转强就持有；S2=周线日线都转强才持有；是规则状态，不是操作指令",
    "KDJ/金叉死叉": "股价短期强弱的温度计；快线上穿慢线叫金叉（转强），下穿叫死叉（转弱）",
    "头均市值": "按每头猪产能折算出来的公司估值，用来看股票贵不贵",
    "猪粮比": "猪价除以饲料价，约低于 6 就是养一头亏一头",
}

_STYLE_DESC = (
    "【回答措辞（强制）】给用户的回答必须先给大白话结论、再给数据依据；"
    "L0/L1、contango、升水/贴水、百分位、定级 A/B/C、S1/S2、KDJ 等术语必须翻译成日常语言后才能出现"
    "（输出中的 plain_summary 是现成大白话解读，jargon_map 是术语对照表，answer_style 是措辞纪律）。"
)


def _load_backend():
    """延迟加载 Pro 猪周期域层；社区版 ImportError 时返回 None（不抛出、不炸加载器）。"""
    try:
        from core.pro.domain_models.pig_cycle import data as _data
        from core.pro.domain_models.pig_cycle import futures as _futures
        from core.pro.domain_models.pig_cycle import l0 as _l0
        from core.pro.domain_models.pig_cycle import l1_signal as _l1
        from core.pro.domain_models.pig_cycle import knowledge as _knowledge
        from core.pro.domain_models.pig_cycle import model as _model
        from core.pro.domain_models.pig_cycle import term_signal as _term_signal
        from core.pro.domain_models.pig_cycle import snapshot as _snapshot
        from core.pro.domain_models.pig_cycle import memo as _memo
        from core.pro.domain_models.pig_cycle import watchlist as _watchlist
        from core.pro.domain_models.pig_cycle import paper as _paper
        from core.pro.domain_models.pig_cycle import enterprise as _enterprise
    except ImportError as exc:  # 社区版：core.pro 不存在
        logger.info("猪周期 Pro 后端不可用，猪周期工具进入降级态: %s", exc)
        return None
    return types.SimpleNamespace(
        data=_data, futures=_futures, l0=_l0, l1=_l1, knowledge=_knowledge,
        model=_model, term_signal=_term_signal, snapshot=_snapshot, memo=_memo,
        watchlist=_watchlist, paper=_paper, enterprise=_enterprise,
    )


def _unavailable(tool_id: str) -> str:
    return json.dumps(
        {
            "status": "unavailable",
            "scope": "pro",
            "tool": tool_id,
            "message": _UNAVAILABLE_MSG,
            "discipline": _DISCIPLINE,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _error(tool_id: str, code: str, message: str, **extra) -> str:
    """结构化业务错误（非法参数/域层 ValueError），不抛异常给 Agent。"""
    payload = {"status": "error", "scope": "pro", "tool": tool_id,
               "code": code, "message": message}
    payload.update(extra)
    return _dump(payload)


def _series_point(d: dict, month_str) -> dict:
    """monthly_series 原始点做呈现层序列化：月索引->'YYYY-MM'、时间->ISO；不改数值。"""
    out = dict(d)
    if isinstance(out.get("month"), int):
        out["month"] = month_str(out["month"])
    ts = out.get("collected_at")
    if hasattr(ts, "isoformat"):
        out["collected_at"] = ts.isoformat()
    return out


def _plain_block(summary: str) -> dict:
    """统一的大白话输出段：plain_summary + 措辞纪律 + 术语对照。"""
    return {"plain_summary": summary,
            "answer_style": _ANSWER_STYLE,
            "jargon_map": _JARGON_PLAIN}


def _plain_l0(summary) -> str:
    """L0 摘要 → 大白话（只翻译措辞，不改数字）。"""
    if not isinstance(summary, dict) or not summary or summary.get("status") == "error":
        return "供给面（母猪/亏损/出栏）数据暂时取不到，无法下判断。"
    grade = str(summary.get("grade") or "")
    if not grade:
        return "供给面数据暂缺（未拿到定级读数）。"
    head = {
        "A": "行业反转基本坐实：母猪减得多、还在减、亏损够久，三条判据全中。",
        "B": "行业有起色苗头，但还没坐实：母猪开始少了、也亏了很久，只是减得还不够。",
        "C": "供给并没有真正减过，之前的价格上涨更像情绪起哄。",
    }.get(grade[:1])
    if head is None:
        head = f"当前行业状态读数：{grade}。"
    elif "偏C" in grade:
        head += "但拐点的旁证（出栏变少、仔猪价回升、母猪止跌）一张都没拿到，属于苗头里偏弱的。"
    elif "偏A" in grade:
        head += "且拐点旁证已拿到多数，属于苗头里偏强的。"
    facts = []
    dd = summary.get("equiv_drawdown_pct")
    if dd is not None:
        facts.append(f"母猪减产折算到最终出栏，比峰值少约 {dd}%（'减得够多'的及格线是 8%）")
    sow, sd = summary.get("sow_now_wan"), summary.get("sow_direction")
    if sow is not None:
        d = {"down": "仍在减少",
             "up": "已开始回升（回升=反弹在自杀，是离场警戒线）"}.get(sd, f"方向：{sd}")
        facts.append(f"能下崽的母猪约 {sow} 万头，{d}")
    if summary.get("loss_months") is not None:
        facts.append(f"全行业已连亏约 {summary['loss_months']} 个月")
    price, pctl = summary.get("price_now"), summary.get("price_pctl_24m")
    if price is not None:
        seg = f"当前猪价约 {price} 元/公斤"
        if pctl is not None:
            seg += f"（比近两年里 {pctl:.0%} 的时候都贵）"
        facts.append(seg)
    out = head
    if facts:
        out += "｜依据：" + "；".join(facts) + "。"
    pa, pp = summary.get("policy_anchor_wan"), summary.get("policy_pct_of_anchor")
    if pa is not None and pp is not None:
        zone = summary.get("policy_zone") or ""
        seg = (f"和政府定的正常保有量（{pa} 万头）比：现在的母猪存栏是它的 {pp}%"
               f"（{'高于' if pp and pp >= 100 else '低于'}这个标准数）")
        if zone:
            seg += ("，处于绿色区间（政策不用出手，市场自己调节）" if zone.startswith("绿色")
                    else f"，已走出绿色区间（{zone}，政策会出手调节）")
        gap, floor = (summary.get("policy_gap_to_floor_wan"),
                      summary.get("policy_green_floor_wan"))
        if gap is not None and floor is not None:
            if gap > 0:
                seg += (f"；距政策警戒线（正常保有量的 92%，约 {floor} 万头）还差 {gap} 万头——"
                        "跌破正常保有量本身政府不管，跌到警戒线以下才会启动调控")
            else:
                seg += (f"；已跌破政策警戒线（正常保有量的 92%，约 {floor} 万头）{abs(gap)} 万头，"
                        "政策托底、督促补栏的概率大增")
        out += seg + "。"
    rule = summary.get("position_rule")
    if rule:
        out += f"系统规则的态度：{rule}——这是给想提前蹲点的人立的纪律，不是叫你买。"
    if summary.get("fuses_triggered"):
        out += "另有估值/情绪过热的预警灯亮着（详见 fuses 字段）。"
    return out


def _plain_l1(l1_state) -> str:
    """L1 状态 → 大白话。"""
    targets = (l1_state or {}).get("targets") or {}
    if not targets:
        return "养殖股股价温度计数据暂缺。"
    display = {"牧原": "牧原", "温氏": "温氏", "新希望": "新希望", "组合": "四家等权组合"}
    segs = []
    for name, t in targets.items():
        if not isinstance(t, dict):
            continue
        wk = t.get("weekly") or {}
        pos = t.get("position") or {}
        bull = str(wk.get("state_cn") or "").startswith("多头")
        seg = f"{display.get(name, name)}股价" + ("周线已转强" if bull else "周线还在跌势里")
        if wk.get("top_warn"):
            seg += "，且短期涨得太急有回调预警"
        s1 = pos.get("s1")
        if s1 is not None:
            seg += "；按系统规则当前是" + ("持有档" if s1 == 1 else "空仓等待档")
        segs.append(seg)
    if not segs:
        return "养殖股股价温度计数据暂缺。"
    return ("养殖股温度计：" + "；".join(segs) + "。"
            "持有/等待是这套规则所处的档位，不是操作指令。")


def _plain_paper(st) -> str:
    """模拟盘状态 → 大白话。"""
    if not isinstance(st, dict) or not st.get("meta"):
        return "模拟盘还没启动（尚未落过初始快照）。"
    nav = st.get("latest_nav") or {}
    meta = st.get("meta") or {}
    nav_v = nav.get("nav")
    asof = nav.get("date") or meta.get("last_signal_date")
    exposure = nav.get("exposure")
    pending = meta.get("pending_fills") or {}
    n_pending = sum(1 for v in pending.values() if v) if isinstance(pending, dict) else 0
    head = f"模拟盘（零费用、T收盘确认、次日收盘价成交的纸面记录，不是实盘、也不是操作建议）：截至 {asof}，组合净值 {nav_v}"
    if exposure is not None:
        head += f"，当前总仓位约 {round(float(exposure) * 100, 1)}%"
    n_trades = (st.get("counts") or {}).get("paper_trades", 0)
    head += f"，累计成交 {n_trades} 笔"
    if n_pending:
        head += f"，另有 {n_pending} 笔挂单待下一交易日成交"
    head += "。这是按规则 v1.1（定级上限×G1梯度）跑出来的纸面跟踪结果。"
    return head


def _plain_curve(cv) -> str:
    """期货曲线 → 大白话。"""
    if not isinstance(cv, dict) or cv.get("status") != "live":
        return "生猪期货数据暂时不齐，市场对远期猪价的态度无法判断（缺数据不猜）。"
    sp = cv.get("spread") or {}
    pct, abs_v, shape = sp.get("pct"), sp.get("abs_yuan_ton"), sp.get("shape")
    if shape == "contango":
        head = (f"市场在赌以后的猪更贵：期货上最远月份交货的猪，"
                f"比最近交货的贵 {pct}%（每吨贵 {abs_v} 元）。")
    elif shape == "backwardation":
        head = (f"市场觉得以后的猪反而更便宜：远期交货价比最近交货的低 "
                f"{abs_v} 元/吨（约 {pct}%）。")
    else:
        head = "期货远近月价格基本持平：市场对远期猪价没有明显倾向。"
    main = cv.get("main") or {}
    if main.get("close_per_kg") is not None:
        head += (f"当前成交最活跃的合约折合每公斤 {main['close_per_kg']} 元，"
                 "相当于市场给那段时间猪价的'预报价'。")
    return head


def _plain_term(tw) -> str:
    """期限结构警示位 → 大白话。"""
    if not isinstance(tw, dict) or tw.get("status") != "live":
        return "期货历史对比数据暂缺，看涨情绪是否过热暂时无法判断。"
    parts = []
    pct, pctl = tw.get("spread_pct"), tw.get("spread_percentile")
    if pct is not None:
        head = f"现在期货市场一致看涨远期猪价：远期比近期贵 {pct}%。"
        if pctl is not None:
            head += f"这个看涨程度放进 2021 年以来的历史里排队，比其中 {pctl}% 的时候都高。"
        parts.append(head)
    for w in tw.get("warnings") or []:
        code = w.get("code")
        if code == "deep_contango_overpriced":
            parts.append("预警：看涨已经买得很满——这么一致看涨在近几年很少见，涨价预期基本被买满，"
                         "此时追高容易站岗（历史实证见 warnings[].evidence）。")
        elif code == "curve_steepening_overheat":
            ch = tw.get("change_4w") or {}
            parts.append(f"预警：最近一个月看涨情绪升温太快——约一个月内远期价被抬高 "
                         f"{ch.get('value_pp')} 个百分点，历史上升温这么快之后行情常要歇一歇。")
    if tw.get("all_clear"):
        parts.append("两个过热预警灯都没亮：看涨情绪不算极端，处于历史常态区间。")
    ch = tw.get("change_4w") or {}
    if ch.get("state") == "warming_up":
        parts.append("'一个月内升温速度'的对比因历史样本还在积累，暂不下结论。")
    return " ".join(parts)


_SERIES_PLAIN = {
    "sow_stock_wan": "能繁母猪＝能下崽的母猪（万头），决定约 10 个月后的生猪供应："
                     "母猪少→10 个月后出栏少→猪价容易涨。",
    "hog_price_yuan_kg": "生猪出场价（元/公斤）：养殖场把猪卖给屠宰场的价格，猪周期的核心读数。",
    "hog_grain_ratio": "猪粮比：猪价÷饲料价，约低于 6 就是养一头亏一头，是衡量全行业亏损的标尺。",
    "slaughter_head_wan": "规模屠宰量（万头）：进了屠宰场的猪≈市场真实猪肉供应。",
    "slaughter_yoy": "屠宰量同比（%）：比去年同期宰得多还是少，供过于求/供不应求的旁证。",
    "scale_profit_yuan_head": "规模养殖养一头猪平均赚（正）/亏（负）多少钱。",
}


def _plain_inference(inf) -> str:
    """调控下限情景推演 → 大白话。"""
    if not isinstance(inf, dict) or inf.get("status") != "live":
        return "能繁母猪数据暂缺，推演做不了（缺数据不猜）。"
    b = inf.get("basis") or {}
    lag = inf.get("lag_months") or 0
    floor = inf.get("floor_wan")
    anchor = inf.get("normal_level_wan")
    parts = []
    if lag > 0:
        parts.append(f"官方最后一次报数是 {b.get('sow_month')}（{b.get('sow_now_wan'):.0f} 万头），"
                     f"之后 {lag} 个月还没披露。世界模型按三种速度把这几个月推出来：")
    else:
        parts.append(f"官方最新读数就是本月：{b.get('sow_month')}＝{b.get('sow_now_wan'):.0f} 万头。")
    for s in inf.get("scenarios") or []:
        speed = s.get("speed_wan_per_month") or 0
        if speed < 0:
            speed_txt = f"每月减 {abs(speed):.1f} 万头"
        else:
            speed_txt = f"每月变化 {speed:+.1f} 万头"
        vs_normal = ("已经跌破标准数" if s.get("below_normal_level") else "还在标准数之上")
        if s.get("hits_floor"):
            vs_floor = "、已碰到政府要出手的警戒线"
        else:
            gap = s.get("gap_to_floor_wan")
            vs_floor = f"、离警戒线还差约 {gap:.0f} 万头"
        parts.append(f"按最近 {s.get('window_months')} 个月的速度（{speed_txt}）："
                     f"现在约 {s.get('inferred_wan'):.0f} 万头，{vs_normal}{vs_floor}。")
    hits = [s for s in inf.get("scenarios") or [] if s.get("hits_floor")]
    n = len(inf.get("scenarios") or [])
    if n and not hits:
        parts.append(f"结论：三种速度推下来都没到政府要出手的线（{floor} 万头）——"
                     "『已经触及调控下限』这个推定按现有证据不成立。")
    elif hits and len(hits) < n:
        parts.append(f"结论：只有按去化最快的情景才碰到 {floor} 万头这条线，"
                     "别的情景还差着——能不能推定『已触及』要看你信哪种速度。")
    elif hits:
        parts.append(f"结论：三种速度都推到 {floor} 万头以下了，『已触及调控下限』的推定基本成立。")
    hp = inf.get("history_prior") or {}
    if hp.get("total"):
        parts.append(f"别急着按匀速外推：历史上 {hp['total']} 段'连续仨月每月减 35 万头以上'的急速去化，"
                     f"有 {hp.get('stabilized_after', 0)} 段随后三个月就止跌回稳——"
                     "杀母猪多半是一阵一阵的，不是匀速滑坡。")
    pc = inf.get("price_check") or {}
    if pc.get("rebounding"):
        parts.append("而且猪价最近在反弹：猪价一回暖、亏损收窄，杀母猪的动力就小了。")
    pol = inf.get("policy_check") or {}
    evs = pol.get("recent_6m_events") or []
    if evs:
        ev_txt = "、".join(f"{e['month']}{e['type']}" for e in evs[:4])
        parts.append(f"政策旁证：近 6 个月有政策动作（{ev_txt}"
                     f"{' 等' if len(evs) > 4 else ''}）——收储是政策托底的位置信号，"
                     "但历史实证它扭不动供需（事件后 1 个月猪价仅 +0.7%），"
                     "去化会不会被托住最终看价格与扛亏能力。")
    else:
        parts.append("政策旁证：近 6 个月没有收储/放储类政策动作，去化没被政策托底。")
    parts.append("验证信号：下次官方披露值若明显高于最快情景的推算，说明去化确实在减速。")
    return "".join(parts)


@register_tool(
    tool_id="get_pig_cycle_state",
    name="猪周期六环节状态总览",
    description=(
        "只读获取生猪养殖板块“猪周期”当前状态的同源事实快照，供撰写决策备忘录使用："
        "L0 供给侧定级摘要（反弹级别/仓位规则/能繁母猪方向与去化/头均市值分位/熔断与断档序列）、"
        "L1 四个标的（牧原/温氏/新希望/组合）的周线状态与 S1/S2 仓位信号及 G1 参考梯度（仅仪表盘参考列）、"
        "生猪期货期限结构（live/degraded、近远月升贴水、主力合约、曲线形态），以及基于 2021 年以来全交割合约"
        "冻结阈值的两条【风险警示位】：深升水透支（近远月升水处历史第85百分位及以上，复苏预期已被较充分定价）、"
        "曲线4周骤升过热（升水4周变化处历史第90百分位及以上）；附当前百分位、阈值、触发详情与历史实证。"
        "警示位只是风险/赔率位置提示，不是方向或买卖信号。工具只返回域层既有数字，不给买卖点、不替用户决策。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "hog_cycle", "l0_supply", "l1_timing", "livestock_futures", "term_structure", "contango_warning", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["猪周期位置判断", "生猪养殖板块决策备忘录", "能繁去化/猪价/期货状态速览"],
    when_to_use=(
        "当用户询问当前猪周期处于什么阶段、能繁母猪去化/猪粮比/猪价、牧原温氏等养殖股的 S1/S2 信号、"
        "生猪期货升贴水，或追问“期货升水是不是已经透支/太贵”“近一个月曲线是不是骤升过热”、"
        "或问“能繁数据滞后两个月/还没出，能不能推算现在到没到政府调控下限（红线）”“去化速度怎么算/会不会停”、"
        "“政策会不会托底/收储”时必须先用本工具拿调控锚/占锚比/离下限差值，不要用网络搜索替代；"
        "或要为生猪养殖板块写决策备忘录、需要一份同源事实底稿时使用。"
    ),
    when_not_to_use=(
        "不用于普通股票行情/财务（请用 get_stock_market_data_unified / get_stock_fundamentals_unified）；"
        "不会也不能下单、调仓或给出具体建仓比例；不检索研究框架知识卡（请用 query_pig_knowledge）。"
    ),
    returns=(
        "返回 JSON 字符串：status(ok/partial/unavailable)、rules_version、as_of、"
        "l0_summary（L0 定级摘要）、l1_targets（四标的 close/weekly_state/s1/s2/g1_ref 等）、"
        "futures_curve（status/trade_date/shape/spread/main/n_contracts）、"
        "term_warnings（期限结构风险警示位：status/trade_date/spread_pct/spread_percentile/zone/"
        "change_4w{state,value_pp,percentile,lookback_days,threshold_pp}/warnings[code,title,detail,evidence]/"
        "all_clear/baseline{version,spread_q85,dspread4_q90,period}；骤升历史不足时 change_4w.state=warming_up，"
        "整体无数据 status=degraded）、discipline。"
        "某一分段取数失败时该分段为 {status:error}，整体 status=partial，不影响其它分段。"
    ),
    example="get_pig_cycle_state()",
    related_tools=["query_pig_knowledge"],
)
def get_pig_cycle_state() -> str:
    """获取猪周期 L0 定级 + L1 四标的信号 + 期货期限结构的只读同源快照（无参数）。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_cycle_state")

    section_errors: list[str] = []

    # ---- L0 供给定级（只取 summary 子集，数字一律原样投影） ----
    l0_summary = None
    rules_version = None
    l0_as_of = None
    try:
        l0_state = backend.l0.get_l0_state(None)
        l0_summary = l0_state.get("summary")
        rules_version = l0_state.get("rules_version")
        l0_as_of = l0_state.get("as_of")
    except Exception as exc:  # 诚实降级，不炸整工具
        logger.warning("猪周期 L0 取数失败: %s", exc)
        l0_summary = {"status": "error", "error": str(exc)}
        section_errors.append("l0")

    # ---- L1 四标的：仅投影周线状态与仓位信号字段 ----
    l1_targets = None
    l1_as_of = None
    l1_state = None
    try:
        l1_state = backend.l1.get_l1_state(None)
        l1_as_of = l1_state.get("as_of")
        projected: dict = {}
        for name, t in (l1_state.get("targets") or {}).items():
            weekly = t.get("weekly") or {}
            pos = t.get("position") or {}
            projected[name] = {
                "close": t.get("close"),
                "weekly_state": weekly.get("state_cn"),
                "weekly_zone": weekly.get("zone"),
                "weekly_top_warn": weekly.get("top_warn"),
                "s1": pos.get("s1"),
                "s2": pos.get("s2"),
                "s1_last_switch": pos.get("s1_last_switch"),
                "g1_ref": pos.get("g1_ref"),
                "g1_streak_days": pos.get("g1_streak_days"),
                "g1_ref_note": pos.get("g1_ref_note"),
            }
        l1_targets = projected
    except Exception as exc:
        logger.warning("猪周期 L1 取数失败: %s", exc)
        l1_targets = {"status": "error", "error": str(exc)}
        section_errors.append("l1")

    # ---- 生猪期货期限结构（build_curve_view 纯读库，缺数据自报 degraded） ----
    fut_view = None
    cv = None
    try:
        cv = backend.futures.build_curve_view()
        main = cv.get("main")
        spread = cv.get("spread")
        # live 时形态在 spread.shape；degraded 时 spread=None、顶层 shape=None
        shape = spread.get("shape") if isinstance(spread, dict) else cv.get("shape")
        fut_view = {
            "status": cv.get("status"),
            "trade_date": cv.get("trade_date"),
            "last_success": cv.get("last_success"),
            "shape": shape,
            "spread": spread,
            "main": main.get("code") if isinstance(main, dict) else main,
            "n_contracts": len(cv.get("contracts") or []),
        }
        if cv.get("reason"):
            fut_view["reason"] = cv["reason"]
    except Exception as exc:
        logger.warning("猪周期期货视图取数失败: %s", exc)
        fut_view = {"status": "error", "error": str(exc)}
        section_errors.append("futures")

    # ---- 期限结构风险警示位（term_signal；冻结阈值，纯读库。仅供风险/赔率提示，非方向信号）----
    term_view = None
    try:
        tw = backend.term_signal.build_term_warnings()
        bl = tw.get("baseline") or {}
        term_view = {
            "status": tw.get("status"),
            "trade_date": tw.get("trade_date"),
            "shape": tw.get("shape"),
            "spread_pct": tw.get("spread_pct"),
            "spread_percentile": tw.get("spread_percentile"),
            "zone": tw.get("zone"),
            "change_4w": tw.get("change_4w"),
            "warnings": tw.get("warnings"),
            "all_clear": tw.get("all_clear"),
            "disclaimer": tw.get("disclaimer"),
            "baseline": {
                "version": bl.get("version"),
                "period_start": bl.get("period_start"),
                "period_end": bl.get("period_end"),
                "n_weeks": bl.get("n_weeks"),
                "spread_q85": bl.get("spread_q85"),
                "dspread4_q90": bl.get("dspread4_q90"),
            },
        }
        if tw.get("reason"):
            term_view["reason"] = tw["reason"]
        if tw.get("last_success"):
            term_view["last_success"] = tw["last_success"]
    except Exception as exc:
        logger.warning("猪周期期限结构警示位取数失败: %s", exc)
        term_view = {"status": "error", "error": str(exc)}
        section_errors.append("term")

    plain = "｜".join([
        _plain_l0(l0_summary),
        _plain_l1(l1_state),
        _plain_curve(cv),
        _plain_term(term_view),
    ])

    payload = {
        "status": "partial" if section_errors else "ok",
        "scope": "pro",
        "rules_version": rules_version,
        "as_of": {"l0": l0_as_of, "l1": l1_as_of,
                  "futures_trade_date": (fut_view or {}).get("trade_date")},
        "l0_summary": l0_summary,
        "l1_targets": l1_targets,
        "futures_curve": fut_view,
        "term_warnings": term_view,
        **_plain_block(plain),
        "discipline": _DISCIPLINE,
        "note": "数字唯一来源 core.pro 域层；本工具只读，不产生任何交易动作。"
                "term_warnings 为历史统计风险提示，不构成方向或买卖建议。",
    }
    if section_errors:
        payload["section_errors"] = section_errors
    return _dump(payload)


@register_tool(
    tool_id="query_pig_knowledge",
    name="猪周期辩手弹药库、风险知识卡与用户情报卡",
    description=(
        "检索猪周期知识库："
        "debate_ammo 辩手弹药库（四条断层线的多空论据+收场判据、五条攻击路径、证据权重排序）、"
        "risk_transmission 七条风险传导链及其监测哨 live/gap/manual 状态、"
        "source_stance 信源制度性立场与甄别要点——以上为框架静态知识卡（源自项目框架文档）；"
        "user_intel 用户情报卡（当前用户上传资料经大模型提炼的要点结论，带信源等级 tier_rank，"
        "仅登录用户本人可见）。支持按分类与关键字检索，供多空辩论与备忘录引用。"
        + _STYLE_DESC
    ),
    category="knowledge",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "debate_ammo", "risk_transmission", "source_stance", "user_intel", "framework", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["猪周期多空辩论", "风险传导链与监测哨查询", "信源立场甄别", "用户自有资料要点引用", "备忘录引用框架论据"],
    when_to_use=(
        "当需要猪周期的多空辩论弹药（去化/成本/政策/预期差断层线）、证据可信度排序、"
        "七条风险传导链与监测哨状态、信源立场甄别要点，"
        "或引用用户自己上传资料提炼的结论要点（category='user_intel'）时使用。"
    ),
    when_not_to_use=(
        "不返回实时行情/定级数值（请用 get_pig_cycle_state）；知识卡是框架提炼与用户资料要点，"
        "引用时必须保留 source_ref 出处，不得把多空任一方论据当作确定性结论或买卖建议。"
    ),
    returns=(
        "返回 JSON 字符串：status(ok/error/unavailable)、count、categories（合法分类）、"
        "cards（id/category/title/body/tag/source_ref 全字段；user_intel 卡 body 含 source_tier/tier_rank）。"
        "非法分类返回 status=error 与可选值，不抛异常。"
    ),
    example="query_pig_knowledge(category='debate_ammo', q='去化')",
    related_tools=["get_pig_cycle_state"],
)
def query_pig_knowledge(category: str = "", q: str = "") -> str:
    """检索猪周期知识卡（框架卡 + 当前用户情报卡）。

    Args:
        category: 可选分类，debate_ammo / risk_transmission / source_stance / user_intel；
            留空返回全部（框架卡 + 当前用户情报卡）。
        q: 可选关键字（匹配标题/标签/正文/出处，大小写不敏感）。
    """
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_pig_knowledge")

    cat = (category or "").strip() or None
    needle = (q or "").strip() or None
    allowed = list(backend.knowledge.CATEGORIES)
    if cat is not None and cat not in allowed:
        return _dump({
            "status": "error",
            "scope": "pro",
            "code": "bad_category",
            "message": f"未知知识分类: {cat}",
            "categories": allowed,
        })

    # 用户上下文由 app 层在调用 LLM 前写入 ContextVar；无上下文时 user_intel 返回空（绝不跨用户泄露）
    try:
        from core.pro.domain_models.pig_cycle.knowledge import current_user_id, CATEGORY_INTEL
    except ImportError:  # 社区版：core.pro 不存在（上方 backend 检查已降级，此处兼顾发布断链自检）
        return _unavailable("query_pig_knowledge")
    user_id = (current_user_id.get() or "").strip()

    try:
        cards: list[dict] = []
        intel_note = ""
        if cat == CATEGORY_INTEL:
            if not user_id:
                intel_note = "当前无用户上下文，用户情报卡不可检索（仅登录用户本人可见）。"
            else:
                cards = backend.knowledge.list_intel_cards(user_id, q=needle)
        else:
            cards = backend.knowledge.list_cards(cat, needle)
            if cat is None and user_id:
                # 全库检索时并入当前用户的情报卡（开放检索：框架知识 + 用户自有情报）
                cards = backend.knowledge.list_intel_cards(user_id, q=needle) + cards
    except ValueError as exc:  # 域层兜底，转结构化错误而非抛给 Agent
        return _dump({
            "status": "error",
            "scope": "pro",
            "code": "bad_category",
            "message": str(exc),
            "categories": allowed,
        })

    return _dump({
        "status": "ok",
        "scope": "pro",
        "count": len(cards),
        "category": cat,
        "q": needle,
        "cards": cards,
        **_plain_block("知识卡是多空辩论的素材库（正反两方论据都有）。引用给用户时："
                       "请把框架术语翻译成大白话，保留 source_ref 出处，并说明这是论据不是结论。"),
        "discipline": _DISCIPLINE,
        "note": "知识卡为研究框架静态提炼与用户资料要点；引用须保留 source_ref，且不构成买卖建议。"
                "user_intel 卡冲突分层评估：多张用户情报卡结论不一致时，按 body.tier_rank 采信"
                "（内部一手4 > 官方披露3 > 机构研报2 > 公开资讯1 > 自媒体0），"
                "同等级再比时效（更新者优）与多卡一致性，并在回答中说明冲突与取舍依据。"
                + (f" {intel_note}" if intel_note else ""),
    })


# 用户私有资料检索：原文匹配字段与命中片段上下文长度
_MATERIAL_TEXT_FIELDS = ("title", "content", "extracted_text", "remark", "source_note")
_MATERIAL_SNIPPET_CONTEXT = 80


@register_tool(
    tool_id="query_user_materials",
    name="用户私有资料原文检索（我的资料）",
    description=(
        "按关键字检索当前用户在「我的资料」中存档的资料【原文】：标题、笔记正文、"
        "上传文件的提取文本、备注、信源说明，返回命中片段（关键词上下文）与元信息"
        "（类别/信源等级/股票）。与 query_pig_knowledge 的 user_intel 知识卡互补："
        "知识卡是提炼要点，本工具是原文细节来源——资料尚未提炼成知识卡也能查到。"
        + _STYLE_DESC
    ),
    category="knowledge",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["user_materials", "stock_materials", "user_intel", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["用户上传资料原文引用", "私有资料细节与数字核对", "知识卡溯源到原文"],
    when_to_use=(
        "当需要引用用户自己上传/收藏资料的原文细节（知识卡要点之外的数字、段落、上下文），"
        "或资料尚未提炼成知识卡时使用；可先查 query_pig_knowledge(category='user_intel') 取要点，"
        "再用本工具取原文佐证。"
    ),
    when_not_to_use=(
        "不返回实时行情；不检索公共互联网（那是搜索工具职责）；"
        "只能看到当前登录用户本人的资料，无用户上下文时不可用。"
    ),
    returns=(
        "返回 JSON 字符串：status(ok/error)、count、q、stock_code、"
        "materials（id/title/kind/category/source_tier/stock_code/updated_at/text_len/"
        "snippet 命中片段）。无关键字时返回最近更新的资料清单（正文前 200 字预览）。"
    ),
    example="query_user_materials(q='能繁母猪')",
    related_tools=["query_pig_knowledge"],
)
def query_user_materials(q: str = "", stock_code: str = "", limit: int = 5) -> str:
    """检索当前用户「我的资料」原文（标题/笔记正文/文件提取文本/备注）。

    Args:
        q: 可选关键字（原文片段匹配，大小写不敏感）；留空返回最近更新的资料清单。
        stock_code: 可选股票代码过滤（如 002714）；留空跨全部股票检索。
        limit: 返回条数上限，默认 5，最大 10。
    """
    try:
        from core.pro.domain_models.pig_cycle.knowledge import current_user_id
    except ImportError:  # 社区版：core.pro 不存在，资料库为 Pro 能力
        return _unavailable("query_user_materials")

    user_id = (current_user_id.get() or "").strip()
    if not user_id:
        return _dump({
            "status": "error",
            "scope": "pro",
            "code": "no_user_context",
            "message": "当前无用户上下文，私有资料不可检索（仅登录用户本人可见）。",
        })

    needle = (q or "").strip()
    stock = (stock_code or "").strip()
    try:
        lim = max(1, min(int(limit or 5), 10))
    except (TypeError, ValueError):
        lim = 5

    import re as _re
    from datetime import datetime as _dt

    query: dict = {"user_id": user_id}
    if stock:
        query["stock_code"] = stock
    if needle:
        pattern = {"$regex": _re.escape(needle), "$options": "i"}
        query["$or"] = [{field: pattern} for field in _MATERIAL_TEXT_FIELDS]

    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        docs = list(
            db["stock_materials"]
            .find(query)
            .sort("updated_at", -1)
            .limit(lim)
        )
    except Exception as exc:
        return _dump({
            "status": "error",
            "scope": "pro",
            "code": "db_error",
            "message": f"私有资料检索失败: {exc}",
        })

    def _snippet(doc: dict) -> str:
        text = str(doc.get("content") or "") or str(doc.get("extracted_text") or "")
        if not text:
            return ""
        if not needle:
            return text[:200] + ("…" if len(text) > 200 else "")
        pos = text.lower().find(needle.lower())
        if pos < 0:
            return text[:200] + ("…" if len(text) > 200 else "")
        start = max(0, pos - _MATERIAL_SNIPPET_CONTEXT)
        end = min(len(text), pos + len(needle) + _MATERIAL_SNIPPET_CONTEXT)
        return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")

    materials = []
    for doc in docs:
        body_text = str(doc.get("content") or "") or str(doc.get("extracted_text") or "")
        updated = doc.get("updated_at")
        materials.append({
            "id": str(doc["_id"]),
            "title": str(doc.get("title") or "未命名资料"),
            "kind": str(doc.get("kind") or ""),
            "stock_code": str(doc.get("stock_code") or ""),
            "category": str(doc.get("category") or "other"),
            "source_tier": str(doc.get("source_tier") or ""),
            "source_note": str(doc.get("source_note") or "")[:120],
            "remark": str(doc.get("remark") or "")[:200],
            "updated_at": updated.isoformat() if isinstance(updated, _dt) else "",
            "text_len": len(body_text),
            "snippet": _snippet(doc),
        })

    no_hit_note = ""
    if needle and not materials:
        no_hit_note = f"未命中关键词「{needle}」，可换关键词（如资料中的专有名词、数字）或留空 q 列出最近资料。"

    return _dump({
        "status": "ok",
        "scope": "pro",
        "count": len(materials),
        "q": needle or None,
        "stock_code": stock or None,
        "materials": materials,
        **_plain_block("这是用户自己上传/收藏的私有资料原文检索，仅本人可见；"
                       "引用时说明资料标题与信源等级，原文细节以 snippet 片段为准。"),
        "discipline": _DISCIPLINE,
        "note": "私有资料为用户本人存档，与网络搜索冲突时按信源等级采信"
                "（内部一手4 > 官方披露3 > 机构研报2 > 公开资讯1 > 自媒体0）并说明取舍。"
                "需要资料提炼要点可配合 query_pig_knowledge(category='user_intel')；"
                "snippet 仅为片段，更多上下文可提示用户在「我的资料」页查看原文。"
                + (f" {no_hit_note}" if no_hit_note else ""),
    })


@register_tool(
    tool_id="get_pig_l0_evidence",
    name="猪周期L0供给定级·完整判定底稿",
    description=(
        "只读返回 L0 供给侧定级【为什么是这个级别】的完整证据底稿（不只是结论）："
        "grade 反弹级别与 sub_tag、position_rule 仓位规则、conditions 全部判据（亏损月数/猪价分位/"
        "能繁方向与去化等每一条的实测值与阈值）、drawdown 等效去化计算、sow 能繁存栏明细与质量标记、"
        "supply 供给投影（MSY 假设/回测误差/未来逐月预测）、scenario 多空情景矩阵（各情景猪价/概率/触发条件）、"
        "fuses 三类行为熔断面板（空间/时间/行为，含头均市值历史分位序列与触发状态）、"
        "freshness 每条序列的数据截止与陈旧标记。供助手与用户逐条核查定级是否成立。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "l0_supply", "rebound_grade", "fuse", "evidence", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["核查L0定级依据", "反弹级别判据逐条验证", "供给投影与情景矩阵", "熔断/断档状态审查"],
    when_to_use=(
        "当用户不满足于‘现在是B偏C/轻仓’这个结论，想知道定级用了哪些数据、每条判据实测值是多少、"
        "供给投影怎么推、哪些熔断触发了、哪些序列数据已陈旧、"
        "或要核对“离政府调控下限还差多少/调控锚是多少”的完整政策层（policy 字段）时使用。"
        "get_pig_cycle_state 只给摘要，本工具给全部底稿。"
    ),
    when_not_to_use=(
        "只要一句话结论用 get_pig_cycle_state；要个股周线择时明细用 get_pig_l1_evidence；"
        "要能繁/猪价等单条历史序列原始数据点用 query_pig_series；本工具同样不给买卖指令。"
    ),
    returns=(
        "get_l0_state 全量 JSON：rules_version/as_of/summary/supply(含 projection.forecast)/finance/"
        "scenario/grade(含 conditions 每条判据实测与阈值)/fuses(space/time/behavior 全面板)/freshness/note。"
        "取数失败 status=error。"
    ),
    example="get_pig_l0_evidence()  # 或 date='2026-09' 回看历史月份",
    related_tools=["get_pig_cycle_state", "query_pig_series", "get_pig_l1_evidence"],
)
def get_pig_l0_evidence(date: str = "") -> str:
    """L0 完整定级底稿（慢变量）。date 可空=最新；月频，'YYYY-MM' 或 'YYYY-MM-DD' 均可。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_l0_evidence")
    try:
        full = backend.l0.get_l0_state(date or None)
    except Exception as exc:
        logger.warning("L0 底稿取数失败: %s", exc)
        return _error("get_pig_l0_evidence", "fetch_failed", f"L0 底稿取数失败: {exc}")
    return _dump({
        "status": "ok", "scope": "pro",
        "as_of": full.get("as_of"), "rules_version": full.get("rules_version"),
        "l0": full,
        **_plain_block(_plain_l0(full.get("summary"))),
        "read_guide": (
            "核查顺序建议：①grade.conditions 每条判据是否满足 → ②fuses 有无 triggered/broken → "
            "③freshness 有无 stale 序列影响判断 → ④supply.projection 与 scenario 的假设是否认同。"
        ),
        "discipline": _DISCIPLINE,
    })


@register_tool(
    tool_id="get_pig_sow_floor_inference",
    name="能繁母猪调控下限·情景推演（数据滞后期间）",
    description=(
        "只读推演：官方能繁母猪读数按季度披露、天然滞后，本工具在披露空窗期用已知条件做合理推论——"
        "①三速度情景外推（按最近3/6/12个月的去化速度把官方读数外推到当前月，给出推算存栏、"
        "是否跌破正常保有量、离调控下限（警戒线）还差多少、最快何时触及）；"
        "②历史同类加速去化段基率（连续仨月每月减≥35万头的历史段落，之后三个月是止跌回稳还是延续去化——"
        "检验'按原速度匀速外推'这个假设本身靠不靠谱）；"
        "③猪价旁证（猪价反弹→亏损收窄→削弱淘汰动力）。"
        "所有推算值显式标注假设窗口，结论按情景给，不下单一路断言。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "l0_supply", "inference", "scenario", "policy_floor", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["能繁数据滞后期间推定当前存栏", "是否触及调控下限/警戒线", "去化速度外推与触及时间", "去化会不会一直加速"],
    when_to_use=(
        "当用户问『能繁数据还是 N 个月前的/最近几个月还没披露，能不能推定现在已经达到（触及）政府限定的数量』"
        "『按原来的去化速度推算现在到没到调控下限（红线/警戒线）』『去化应该没停吧，这个推定成立吗』"
        "『还要去化多久才到政策要出手的水平』时使用——这类问题不许以『官方数据未出、等披露』拒答，"
        "世界模型的职责就是用已知条件做情景推论。也适用于检验『按匀速外推』假设本身"
        "（历史基率段）。要当下政策区域读数用 get_pig_cycle_state/policy 字段，本工具专做滞后空窗推演。"
    ),
    when_not_to_use=(
        "不要用它查原始序列数据点（用 query_pig_series）；不要用它判断买卖时点（不给交易指令）；"
        "推算是情景推演不是预测承诺，回答时必须保留假设与验证信号。"
    ),
    returns=(
        "JSON：status/as_of_month/lag_months（官方读数距查询月的空窗月数）、"
        "basis（policy_at 全量：官方读数月与值/锚/占锚比/区域/下限/差值）、"
        "scenarios[]（window_months/speed_wan_per_month/inferred_wan/below_normal_level/hits_floor/"
        "gap_to_floor_wan/months_to_floor/eta_floor_month）、"
        "history_prior（criterion/episodes[]/total/stabilized_after/stabilized_share_pct）、"
        "price_check（recent_6m_yuan_kg/rebounding/note）、assumptions[]，"
        "以及 plain_summary 大白话结论（含验证信号）。"
    ),
    example="get_pig_sow_floor_inference()  # date='2026-10-06' 可推演历史任一时点",
    related_tools=["get_pig_cycle_state", "get_pig_l0_evidence", "query_pig_series"],
)
def get_pig_sow_floor_inference(date: str = "") -> str:
    """调控下限情景推演（披露空窗期）。date 可空=最新；'YYYY-MM' 或 'YYYY-MM-DD' 均可。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_sow_floor_inference")
    try:
        inf = backend.model.sow_floor_inference(date or None)
    except Exception as exc:
        logger.warning("下限推演取数失败: %s", exc)
        return _error("get_pig_sow_floor_inference", "fetch_failed", f"下限推演取数失败: {exc}")
    payload = dict(inf)
    inner_status = payload.pop("status", "live")   # 域层 live → 工具层 ok 惯例
    return _dump({
        "status": "ok" if inner_status == "live" else inner_status,
        "scope": "pro",
        "tool": "get_pig_sow_floor_inference",
        **payload,
        **_plain_block(_plain_inference(inf)),
        "discipline": _DISCIPLINE,
    })


def _plain_verification(panel) -> str:
    """三验证信号面板 → 大白话。"""
    if not isinstance(panel, dict) or panel.get("status") != "live":
        return "三验证信号面板暂缺数据（缺数据不猜）。"
    parts = []

    s1 = panel.get("signal_1_disclosure_band") or {}
    if s1.get("status") == "live":
        sc = s1.get("scenarios") or []
        lo = (s1.get("last_official") or {})
        if len(sc) >= 2 and s1.get("verdict") == "pending_disclosure":
            parts.append(
                f"信号①产能落档：官方最后一次报数 {lo.get('month')}（{lo.get('value_wan'):.0f} 万头），"
                f"之后 {lo.get('lag_months')} 个月还没披露。三档推算：快档 {sc[0]['inferred_wan']} / "
                f"中档 {sc[1]['inferred_wan']} / 慢档 {sc[-1]['inferred_wan']} 万头。"
                f"下份披露值落在哪个区间，直接裁决反转剧本：低于快档=去化还在加速；"
                f"高于慢档=去化明显减速，期货按快剧本定价就透支了。")
        else:
            parts.append("信号①产能落档：本月已有官方读数，无外推空窗，暂不需要判档。")

    s2 = panel.get("signal_2_breakeven") or {}
    if s2.get("status") == "live":
        spot = (s2.get("spot") or {})
        comps = s2.get("companies") or []
        comp_txt = "、".join(
            f"{c['name']}（成本 {c['cost_yuan_kg']}，差 {c['gap_yuan_kg']:+.2f} 元/kg）"
            for c in comps)
        winners = s2.get("winners") or []
        verdict = f"{'、'.join(winners)} 已站上转正线" if winners else "还没有龙头站上转正线"
        parts.append(
            f"信号②转正线：现货 {spot.get('month')} {spot.get('price_yuan_kg')} 元/kg——{verdict}。"
            f"各家对照：{comp_txt}。头均口径即（现货−成本）×120kg。")

    s3 = panel.get("signal_3_futures_expectation") or {}
    if s3.get("status") == "live":
        contracts = s3.get("contracts") or []
        main_c = next((c for c in contracts if c.get("is_main")), None)
        far_c = contracts[-1] if contracts else None
        pctl = s3.get("spread_percentile")
        warns = s3.get("term_warnings") or []
        warn_txt = "；".join(w["title"] for w in warns) if warns else "警示灯未触发"
        lines = [f"信号③期货定价：{s3.get('trade_date')} 曲线形态 {s3.get('shape')}，"
                 f"近-远月升水 {s3.get('spread_pct'):.2f}%（历史分位 P{pctl}）——{warn_txt}。"]
        if main_c:
            winners_txt = "、".join(main_c.get("implied_winners") or []) or "无人转正"
            lines.append(f"主力 {main_c['code']}（{main_c['delivery_month']} 交割）"
                         f"{main_c['yuan_kg']} 元/kg（较现货 {main_c['vs_spot_pct']:+.1f}%）："
                         f"这个价上 {winners_txt} 能转正。")
        if far_c and far_c is not main_c:
            winners_txt = "、".join(far_c.get("implied_winners") or []) or "无人转正"
            lines.append(f"最远 {far_c['code']}（{far_c['delivery_month']} 交割）"
                         f"{far_c['yuan_kg']} 元/kg（较现货 {far_c['vs_spot_pct']:+.1f}%）："
                         f"市场把最足的涨价押在这里——这个价上 {winners_txt} 转正。")
        parts.append("".join(lines))
    else:
        parts.append("信号③期货定价：期货曲线取不到（通达信客户端未运行或库内无数据），该信号降级。")

    parts.append("三个信号合起来读：①定剧本、②定开关、③定温度——预期差的方向由它们共同裁决。")
    return "\n".join(parts)


@register_tool(
    tool_id="get_pig_verification_signals",
    name="猪周期三验证信号面板（产能落档/转正线/期货定价温度）",
    description=(
        "只读返回三个验证信号的即时读数（与观察哨到期回查互补的『现在亮什么灯』）："
        "①产能落档——官方能繁披露滞后期间，三速度情景推算给出判档区间，下份披露值落在快/中/慢"
        "哪一档即裁决反转剧本（复用 get_pig_sow_floor_inference 的推演）；"
        "②转正线——现货猪价 vs 牧原/温氏/新希望最新完全成本锚，谁先单月头均转正；"
        "③期货定价温度——期货曲线逐合约折元/kg 对照成本光谱（隐含谁转正），"
        "叠加近-远月升水历史分位与透支警示灯。"
        "预期差研究闭环『深潜定锚→期货定天花板→股价对刻度→三信号裁决』的最后一环。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "verification", "expectation_gap", "l0_supply",
                     "livestock_futures", "watchlist", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["三个验证信号现在什么状态", "下次能繁披露怎么判读", "现货破没破牧原成本线",
                   "期货透支没透支", "反弹高度是否超出预期该盯什么"],
    when_to_use=(
        "当用户问『三个验证信号现在什么状态』『下次官方能繁披露出来怎么判读（落在哪一档说明什么）』"
        "『现货站上牧原成本线了吗/谁先转正』『期货把反转定价到哪一档、透支了吗』"
        "『反弹高度超没超预期，接下来盯什么』时使用——这是每月例行检查的仪表盘，"
        "也是判断『市场定价的剧本该升档还是降档』的裁判。"
    ),
    when_not_to_use=(
        "不要用它做买卖决策（只读描述不给指令）；要下限推演全量细节（历史基率/猪价旁证/触及 ETA）"
        "用 get_pig_sow_floor_inference；要期货逐合约全字段与警示实证用 get_pig_futures_evidence；"
        "要查原始序列用 query_pig_series。"
    ),
    returns=(
        "JSON：as_of_month、signal_1_disclosure_band（last_official/scenarios 三档/bands 四档判定带/"
        "verdict=pending_disclosure|fresh）、signal_2_breakeven（spot/companies 逐家成本锚与头均盈亏/"
        "winners）、signal_3_futures_expectation（contracts 逐合约折元/kg 与 implied_winners/"
        "spread_percentile/term_warnings，期货缺失时 status=degraded）、assumptions[]，"
        "以及 plain_summary 大白话结论。"
    ),
    example="get_pig_verification_signals()  # date='2026-10' 可回看历史任一月",
    related_tools=["get_pig_sow_floor_inference", "get_pig_futures_evidence",
                   "get_pig_cycle_state", "query_pig_series"],
)
def get_pig_verification_signals(date: str = "") -> str:
    """三验证信号即时读数。date 可空=最新；'YYYY-MM' 或 'YYYY-MM-DD' 均可。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_verification_signals")
    try:
        panel = backend.model.verification_panel(date or None)
    except Exception as exc:
        logger.warning("三验证信号面板取数失败: %s", exc)
        return _error("get_pig_verification_signals", "fetch_failed",
                      f"三验证信号面板取数失败: {exc}")
    payload = dict(panel)
    inner_status = payload.pop("status", "live")
    return _dump({
        "status": "ok" if inner_status == "live" else inner_status,
        "scope": "pro",
        "tool": "get_pig_verification_signals",
        **payload,
        **_plain_block(_plain_verification(panel)),
        "discipline": _DISCIPLINE,
    })


def _plain_fin_check(chk) -> str:
    """财报 vs 市场口径对账 → 大白话。"""
    if not isinstance(chk, dict) or chk.get("status") != "live":
        reason = (chk or {}).get("reason") or "财报锚点数据暂缺"
        return f"财报对账做不了：{reason}（缺数据不猜）。"
    parts = []
    for name, blk in (chk.get("companies") or {}).items():
        latest = blk.get("latest") or {}
        if latest.get("market_estimate_yi") is None:
            parts.append(f"{name}：最新锚点（{latest.get('period')}，{latest.get('month_str')}）"
                         "缺出栏量或净利，本期只记锚不对账。")
            continue
        np_ = latest.get("net_profit_yi")
        est = latest.get("market_estimate_yi")
        gap = latest.get("gap_yi")
        sub = latest.get("subsidy_per_head_yuan")
        sub_txt = f"，补贴摊到每头猪约 {sub} 元" if sub is not None else ""
        parts.append(
            f"{name}（{latest.get('period')}，截至 {latest.get('month_str')}）："
            f"财报净利 {np_} 亿 vs 市场口径推算 {est} 亿"
            f"（期均猪价 {latest.get('avg_price_yuan_kg')} − 期均成本 "
            f"{latest.get('avg_cost_yuan_kg')} 元/kg，×120kg×出栏 {latest.get('hogs_wan')} 万头）"
            f"——差额 {gap:+.1f} 亿（补贴+套保+非养殖业务等）{sub_txt}。")
    parts.append("读法：常态下差额是零头（补贴量级远小于头均亏损）；差额突然变大才需要细查"
                 "（如事件性大额补助）。市场口径不含补贴是对的——去化由市场亏损驱动。")
    return "\n".join(parts)


@register_tool(
    tool_id="get_pig_company_fin_check",
    name="猪企财报 vs 市场口径对账（补贴/套保差额）",
    description=(
        "只读对账：把公司财报净利润与市场口径推算（期均猪价−期均成本）×120kg×期内出栏 "
        "逐期对照，差额即补贴（其他收益）+套保+非养殖业务+口径差；并给出补贴摊到每头猪的"
        "读数（subsidy_per_head_yuan），回答『算亏损有没有把政府补贴算进去』『财报转正了吗』"
        "『补贴力度多大』。财报锚点为季度稀疏序列（company_fin，含净利润/其他收益/出栏量），"
        "由 seed CSV 维护、--only company_fin 入库。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "company_fin", "subsidy", "reconciliation",
                     "evidence", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["牧原财报亏多少、补贴占多少", "算亏损有没有把补贴算进去",
                   "财报口径和市场口径差在哪", "财报是否已转正"],
    when_to_use=(
        "当用户问『财报里有没有补贴的部分』『算亏损时政府补贴算进去了吗』"
        "『牧原按现在的猪价财报能转正吗、补贴能不能填上亏损』『财报净利和按猪价推算的"
        "利润差多少』时使用——财报净利本来就是含补贴之后的数，本工具把含与不含拆开对账。"
    ),
    when_not_to_use=(
        "不要用它看转正线实时距离（用 get_pig_verification_signals 信号②）；"
        "不要据此给买卖指令；锚点未入库时诚实降级并给出补数指引，不编数。"
    ),
    returns=(
        "JSON：companies.{name}.anchors[]（period/month_str/net_profit_yi/other_income_yi/"
        "hogs_wan/avg_price_yuan_kg/avg_cost_yuan_kg/market_estimate_yi/gap_yi/"
        "subsidy_per_head_yuan）+ latest + methodology，以及 plain_summary 大白话。"
    ),
    example="get_pig_company_fin_check()  # date 可空=最新",
    related_tools=["get_pig_verification_signals", "get_pig_sow_floor_inference",
                   "get_pig_l0_evidence"],
)
def get_pig_company_fin_check(date: str = "") -> str:
    """财报 vs 市场口径对账。date 可空=最新；'YYYY-MM' 或 'YYYY-MM-DD' 均可。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_company_fin_check")
    try:
        chk = backend.model.company_fin_check(date or None)
    except Exception as exc:
        logger.warning("财报对账取数失败: %s", exc)
        return _error("get_pig_company_fin_check", "fetch_failed", f"财报对账取数失败: {exc}")
    payload = dict(chk)
    inner_status = payload.pop("status", "live")
    return _dump({
        "status": "ok" if inner_status == "live" else inner_status,
        "scope": "pro",
        "tool": "get_pig_company_fin_check",
        **payload,
        **_plain_block(_plain_fin_check(chk)),
        "discipline": _DISCIPLINE,
    })


@register_tool(
    tool_id="get_pig_l1_evidence",
    name="猪周期L1择时信号·完整计算底稿",
    description=(
        "只读返回 L1 四个标的（牧原002714/温氏300498/新希望000876/等权组合）择时信号的【完整计算底稿】："
        "每个标的最新收盘、周线 K/D/J 原值与多空状态、超买超卖 zone、见顶预警 top_warn、最近一次金叉/死叉日期、"
        "日线 K/D/J 与最近交叉、position 段 S1（周线K>D持有）/S2（双周期）当前仓位、上次切换日期与动作、"
        "G1 梯度参考与连续天数；另含 "
        "event 猪价急跌次日反弹规律的近期事件与全样本胜率、chip 牧原筹码获利比例/平均成本（自算参照通道）、"
        "main_force 北向/大宗/股东户数/融资融券行为数据（缺失时 status=pending 诚实标注）。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "l1_timing", "kdj_weekly", "chip", "evidence", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["核查S1/S2信号怎么来的", "周线KDJ原值与交叉日期", "筹码/资金参照通道"],
    when_to_use=(
        "当用户想自己判断‘牧原/温氏现在能不能跟’而不是只听一句空头/多头，需要 KDJ 原值、金叉死叉日期、"
        "筹码与资金佐证时使用。"
    ),
    when_not_to_use=(
        "要供给慢变量定级用 get_pig_l0_evidence；要期货曲线用 get_pig_futures_evidence；"
        "S1/S2 信号是状态判读参照，不是胜率保证，也不是买卖建议。"
    ),
    returns=(
        "get_l1_state 全量 JSON：rules_version/as_of/panel_range/signal_from/targets(周/日KDJ+position全字段)/"
        "event/chip/main_force/discipline。参照通道数据缺失时其自身 status=pending，不补造。"
    ),
    example="get_pig_l1_evidence()  # date='2026-09-30' 可截断面板回看历史任一天",
    related_tools=["get_pig_l0_evidence", "get_pig_futures_evidence"],
)
def get_pig_l1_evidence(date: str = "") -> str:
    """L1 完整择时底稿（快变量）。date 可空=最新，日频 'YYYY-MM-DD' 截断面板。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_l1_evidence")
    try:
        full = backend.l1.get_l1_state(date or None)
    except Exception as exc:
        logger.warning("L1 底稿取数失败: %s", exc)
        return _error("get_pig_l1_evidence", "fetch_failed", f"L1 底稿取数失败: {exc}")
    return _dump({
        "status": "ok", "scope": "pro",
        "as_of": full.get("as_of"), "rules_version": full.get("rules_version"),
        "l1": full,
        **_plain_block(_plain_l1(full)),
        "read_guide": (
            "核查顺序建议：①周线 K/D 谁在上、距金叉死叉几天 → ②position.s1/s2 与上次切换 → "
            "③chip/main_force 是佐证还是背离（缺失会标 pending）。"
        ),
        "discipline": _DISCIPLINE,
    })


@register_tool(
    tool_id="get_pig_futures_evidence",
    name="生猪期货曲线与期限结构警示·完整明细",
    description=(
        "只读返回生猪期货的两层完整明细：(1) curve 当日全部在交易真实交割合约（合约号/交割月/收盘/结算/持仓量/"
        "是否主力）、主力合约、近月 far/near、近远月升贴水绝对值与百分比、曲线形态；"
        "(2) term_warnings 期限结构风险警示位完整字段：当前升水与 2021 年以来历史百分位、Q1-Q4 分区、"
        "4 周升水变化值/基准日/百分位、触发的每条警示（code/title/detail/evidence 历史实证）、"
        "冻结基线版本/区间/样本周数/两条阈值。供助手与用户自行核查‘深升水透支/曲线骤升’是否成立。"
        "历史不足时 change_4w.state=warming_up，整体无数据 status=degraded，均为真实状态而非估算。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "livestock_futures", "term_structure", "contango", "evidence", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["核查升贴水怎么算的", "逐合约看曲线", "深升水/骤升警示依据核查", "期货数据缺口确认"],
    when_to_use=(
        "当用户问期货升水/贴水具体数字、近月远月是哪些合约、持仓结构、深升水警示的阈值与实证、"
        "或要亲自验算曲线形态时使用。"
    ),
    when_not_to_use=(
        "不要据此给买卖指令；只要摘要可用 get_pig_cycle_state；要主力连续历史日线请走研究脚本而非本工具。"
    ),
    returns=(
        "JSON：curve（build_curve_view 全量，含 contracts 逐合约）+ term_warnings（build_term_warnings 全量，"
        "含 warnings[detail,evidence]、change_4w、baseline）。两任一段独立可降级。"
    ),
    example="get_pig_futures_evidence()  # trade_date='2026-09-30' 可指定行情日",
    related_tools=["get_pig_cycle_state", "get_pig_l1_evidence"],
)
def get_pig_futures_evidence(trade_date: str = "") -> str:
    """期货全合约曲线 + 期限结构警示完整明细。trade_date 可空=最新行情日。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_futures_evidence")
    td = trade_date or None
    section_errors: list[str] = []
    try:
        curve = backend.futures.build_curve_view(td)
    except Exception as exc:
        logger.warning("期货曲线底稿取数失败: %s", exc)
        curve = {"status": "error", "error": str(exc)}
        section_errors.append("curve")
    try:
        warnings_view = backend.term_signal.build_term_warnings(td)
    except Exception as exc:
        logger.warning("期限结构警示底稿取数失败: %s", exc)
        warnings_view = {"status": "error", "error": str(exc)}
        section_errors.append("term_warnings")
    return _dump({
        "status": "partial" if section_errors else "ok",
        "scope": "pro", "curve": curve, "term_warnings": warnings_view,
        **_plain_block(_plain_curve(curve) + " " + _plain_term(warnings_view)),
        "read_guide": (
            "验算方式：spread_pct=(far.close-near.close)/near.close×100；与历史百分位（基线已冻结）"
            "对照判断所处分区；4 周变化为与约 28 天前同口径 spread 之差。"
        ),
        "discipline": _DISCIPLINE,
    })


@register_tool(
    tool_id="query_pig_series",
    name="猪周期原始数据序列查询（带出生证明）",
    description=(
        "只读查询 pig_cycle 库 monthly_series 里的【原始月度数据点】，这是 L0/L1 一切结论的底层原料，"
        "可用来独立核查任何定级数字。不传 series 时返回序列目录（id/中文名/单位/来源/点数/覆盖区间/"
        "滞后月数/ok|stale|discontinued 状态），可用 q 按中文标签或来源过滤；传 series 后返回该序列的"
        "逐月数据点，每点含 month/value/source/note/collected_at（即每个数的出处与采集时间）。"
        "典型序列：sow_stock_wan 能繁母猪存栏(万头)、hog_price_yuan_kg 生猪出场价(元/kg)、"
        "hog_grain_ratio 猪粮比价、slaughter_head_wan 规上屠宰量(万头)、slaughter_yoy 屠宰同比、"
        "scale_profit_yuan_head 规模养殖头均利润(元/头) 等，实际清单以目录返回为准（含官方/插值质量标记）。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "raw_series", "data_lineage", "sow_stock", "hog_price", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["核查能繁/猪价/猪粮比/屠宰量等原始数据", "拉一条序列的历史数据自行判断", "确认数据来源与新旧"],
    when_to_use=(
        "当用户要看具体数据本身（如‘把近24个月能繁存栏给我’‘猪价这轮涨跌的原始月度数据’‘"
        "这个数从哪来、什么时候采的’），要验证 L0 报告引用的数字，"
        "或要自己算历史去化速度（逐月环比变化分布，验证‘去化是匀速还是时快时慢’）时使用。"
        "先不传 series 看目录拿 id。"
    ),
    when_not_to_use=(
        "要加工好的定级/信号用 get_pig_l0_evidence/get_pig_l1_evidence；日频个股与期货不在本月频库；"
        "本工具只读数，不做预测与买卖建议。"
    ),
    returns=(
        "目录模式 {mode:'catalog', matched_series:[...]}；数据点模式 {mode:'points', series:目录元信息, "
        "points:[{month,value,source,note,collected_at}...], n_points_returned}。"
        "未知 series 返回 status=error 并附全部可用 series id。"
    ),
    example="query_pig_series(series='sow_stock_wan', recent=24)  # 先 query_pig_series(q='能繁') 找 id",
    related_tools=["get_pig_l0_evidence", "get_pig_l1_evidence"],
)
def query_pig_series(series: str = "", q: str = "", recent: int = 36,
                     start: str = "", end: str = "") -> str:
    """原始月频序列目录/数据点。series 空=目录；recent 取最近 N 点（<=0 全部）；start/end='YYYY-MM'。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_pig_series")
    try:
        catalog = backend.data.load_series_catalog()
    except Exception as exc:
        logger.warning("序列目录取数失败: %s", exc)
        return _error("query_pig_series", "fetch_failed", f"序列目录取数失败: {exc}")

    by_id = {r["series"]: r for r in catalog}
    sid = (series or "").strip()
    needle = (q or "").strip().lower()

    if not sid:
        rows = catalog
        if needle:
            rows = [r for r in rows
                    if needle in (r["series"] + " " + r.get("label", "") + " "
                                  + r.get("source", "")).lower()]
        return _dump({
            "status": "ok", "scope": "pro", "mode": "catalog",
            "count": len(rows), "q": q or None,
            "matched_series": rows,
            **_plain_block("目录里每条序列都有中文名、单位和来源，都是判断猪周期用的原始数据"
                           "（比如能繁母猪=能下崽的母猪数量）。先用中文名找到想要的序列，"
                           "再把它的 id 传进来取逐月原始数据。"),
            "note": "把 series id 传入本工具即可取该序列逐月原始数据点。",
        })

    if sid not in by_id:
        return _error("query_pig_series", "unknown_series",
                      f"未知序列 id: {sid}（不带 series 再调一次可获取完整目录）",
                      available_series=sorted(by_id))

    try:
        lo = backend.data.month_index(start) if start.strip() else None
        hi = backend.data.month_index(end) if end.strip() else None
    except Exception:
        return _error("query_pig_series", "bad_month",
                      "start/end 需为 'YYYY-MM' 格式", start=start, end=end)

    try:
        docs = backend.data.load_series_anchors(sid)
    except Exception as exc:
        logger.warning("序列数据点取数失败: %s", exc)
        return _error("query_pig_series", "fetch_failed", f"序列 {sid} 数据点取数失败: {exc}")

    pts = [_series_point(d, backend.data.month_str) for d in docs
           if (lo is None or d.get("month", -1) >= lo)
           and (hi is None or d.get("month", -1) <= hi)]
    if not (start or end) and recent and recent > 0 and len(pts) > recent:
        pts = pts[-recent:]
    return _dump({
        "status": "ok", "scope": "pro", "mode": "points",
        "series": by_id[sid], "n_points_returned": len(pts),
        "window": {"first": pts[0]["month"] if pts else None,
                   "last": pts[-1]["month"] if pts else None},
        "points": pts,
        **_plain_block(_SERIES_PLAIN.get(
            sid, "原始数据点：value 是数值本身；source/note/collected_at 标明每个数的出处与采集时间。")),
        "note": ("value 为原始入库值；source/note/collected_at 为其出处；"
                 "能繁等序列另有质量标记（official/anchor/interpolated），插值点不等于新官方数据。"),
    })


@register_tool(
    tool_id="list_pig_journal",
    name="猪周期历史快照与研判备忘录",
    description=(
        "只读回看猪周期的历史留证材料：(1) snapshots 每日信号快照台账（日期/L0摘要/L1四标的信号/"
        "规则版本/备注），用于复盘‘系统当时怎么看、后来对不对’；(2) memos 人工或LLM生成并经数字校验的"
        "研判备忘录清单（日期/是否用了LLM/挂了几个观察哨/保存时间），给 memo_id 可取备忘录全文"
        "（多空辩论、可证伪条件、观察哨等段落）。用于把今天的判断放到时间轴上核对，而不是只看当下结论。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "snapshots", "memo", "journal", "review", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["回看历史每日信号", "读往期研判备忘录", "复盘当时判断对错"],
    when_to_use=(
        "当用户想看‘上周/上月系统给的信号和研判是什么’‘有没有存档的决策备忘录全文’、"
        "或要对比信号随时间变化时使用。"
    ),
    when_not_to_use=(
        "要当前结论用 get_pig_cycle_state；要观察哨兑现/证伪明细用 list_pig_watch；本工具只读，不新建备忘录。"
    ),
    returns=(
        "JSON：snapshots 列表和/或 memos 列表；kind='memo' 且给 memo_id 时返回 memo_full 全文。"
        "空库时对应列表为空数组，不造假材料。"
    ),
    example="list_pig_journal(kind='all', limit=20)  # kind='memo', memo_id='...' 取全文",
    related_tools=["list_pig_watch", "get_pig_cycle_state"],
)
def list_pig_journal(kind: str = "all", memo_id: str = "", limit: int = 30) -> str:
    """历史快照/备忘录只读查询。kind: all|snapshots|memos|memo。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("list_pig_journal")
    kind = (kind or "all").strip()
    if kind not in ("all", "snapshots", "memos", "memo"):
        return _error("list_pig_journal", "bad_kind",
                      f"未知 kind: {kind}", allowed=["all", "snapshots", "memos", "memo"])
    limit = max(1, min(int(limit or 30), 100))
    payload: dict = {"status": "ok", "scope": "pro"}

    if kind == "memo":
        if not memo_id:
            return _error("list_pig_journal", "missing_memo_id",
                          "kind='memo' 取全文时必须提供 memo_id（先 kind='memos' 拿 id）")
        try:
            doc = backend.memo.get_memo(memo_id)
        except Exception as exc:
            logger.warning("备忘录全文取数失败: %s", exc)
            return _error("list_pig_journal", "fetch_failed", f"备忘录取数失败: {exc}")
        if doc is None:
            return _error("list_pig_journal", "not_found", f"备忘录不存在: {memo_id}")
        payload["memo_full"] = doc
        payload.update(_plain_block(
            "这是一期研判备忘录的全文：当时怎么判断、依据是什么、错了认什么（可证伪条件）。"
            "引用给用户时请把框架术语翻译成大白话。"))
        return _dump(payload)

    try:
        if kind in ("all", "snapshots"):
            payload["snapshots"] = backend.snapshot.list_snapshots(limit)
        if kind in ("all", "memos"):
            payload["memos"] = backend.memo.list_memos(limit)
    except Exception as exc:
        logger.warning("历史留证取数失败: %s", exc)
        return _error("list_pig_journal", "fetch_failed", f"快照/备忘录取数失败: {exc}")
    payload.update(_plain_block(
        "快照=系统每天的'体检表'存档（当天看到什么、给什么档位）；"
        "备忘录=当时的完整研判。用来复盘'系统当时怎么看、后来对不对'。"))
    return _dump(payload)


@register_tool(
    tool_id="list_pig_watch",
    name="猪周期观察哨（待验证假设与兑现结果）",
    description=(
        "只读返回猪周期‘观察哨’清单与统计：每条是一个可证伪的量化假设（指标/方向≥≤/阈值/到期日/"
        "关联标的/状态 pending待回查·won兑现·lost证伪·void作废/实际值/判定结果/来源备忘录）。"
        "stats 给总体兑现率、按指标与按月份的 won/lost 分布——即这套研判框架历史预测的真实命中率底稿。"
        "可按状态过滤。只做查询：不会新增、判定或修改任何观察哨。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "watchlist", "falsifiable", "hit_rate", "review", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查看待验证假设", "统计历史预测兑现率", "复盘证伪记录"],
    when_to_use=(
        "当用户问‘当前有哪些待验证的判断条件’‘以前挂的观察哨兑现了多少/哪些被证伪’、"
        "或要评估这套研判方法的实战命中率时使用。"
    ),
    when_not_to_use=(
        "本工具严格只读，不能替用户挂观察哨或回查（那是写操作）；要备忘录全文用 list_pig_journal。"
    ),
    returns=(
        "JSON：items 观察哨数组（可按 status 过滤）+ stats 兑现率与分组统计。"
        "非法 status 返回 status=error 与可选值。"
    ),
    example="list_pig_watch(status='', with_stats=True)",
    related_tools=["list_pig_journal", "get_pig_cycle_state"],
)
def list_pig_watch(status: str = "", with_stats: bool = True, limit: int = 100) -> str:
    """观察哨清单+兑现统计（只读）。status: 空=全部 / pending / won / lost / void。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("list_pig_watch")
    st = (status or "").strip() or None
    limit = max(1, min(int(limit or 100), 500))
    try:
        items = backend.watchlist.list_items(st, limit)
        stats_view = backend.watchlist.stats() if with_stats else None
    except ValueError as exc:
        return _error("list_pig_watch", "bad_status", str(exc))
    except Exception as exc:
        logger.warning("观察哨取数失败: %s", exc)
        return _error("list_pig_watch", "fetch_failed", f"观察哨取数失败: {exc}")
    return _dump({
        "status": "ok", "scope": "pro", "status_filter": st,
        "count": len(items), "items": items, "stats": stats_view,
        **_plain_block("观察哨=系统提前立下的'对账单'：每条是一个可验证的判断（比如'下月出栏量环比下降'），"
                       "到期拿真实数据对答案。won=猜中，lost=猜错，pending=还没到期；"
                       "兑现率就是历史猜中比例，用来看这套方法靠不靠谱。"),
        "note": "won/lost 是到期按真实数据自动或人工判定的结果；兑现率=won/(won+lost)，pending 不进分母。",
    })


@register_tool(
    tool_id="get_pig_paper_status",
    name="猪周期模拟盘状态（持仓/净值/成交，只读纸面跟踪）",
    description=(
        "只读返回猪周期模拟盘的当前状态（纸面跟踪，非实盘）：meta（初始日期/最近信号日/待成交挂单）、"
        "latest_nav（组合最新净值、三家分仓净值、当前持仓 units、总暴露）、latest_signal（最近一日信号快照，"
        "各标的 G1 梯度/期望仓位/待成交差）、recent_trades（最近 10 笔成交：T收盘确认→T+1收盘价、买卖方向/"
        "成交价/成交后仓位）、counts（信号/成交/净值文档数）以及规则口径说明。撮合口径零费用、无前视。"
        "本工具严格只读：不能触发补跑、不能改仓位、不下单；数字直接来自域层 paper 落库结果。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "paper_trading", "nav", "positions", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查看模拟盘净值与持仓", "核对模拟成交", "跟踪规则 v1.1 纸面表现"],
    when_to_use=(
        "当用户问‘模拟盘现在赚了还是亏了/净值多少/现在几成仓/有没有成交/挂单成交了吗’、"
        "或要看这套规则纸面跑出来的真实表现时使用。"
    ),
    when_not_to_use=(
        "本工具只读，不能手动补跑模拟盘（补跑走后端 POST /paper/run，不在 Agent 工具内）；"
        "要看信号怎么来的用 get_pig_l1_evidence / get_pig_l0_evidence。模拟盘结果不构成投资建议。"
    ),
    returns=(
        "JSON：meta/latest_nav/latest_signal/recent_trades/counts/note + plain_summary。"
        "模拟盘未初始化时 meta 为 null，plain_summary 提示尚未启动。"
    ),
    example="get_pig_paper_status()",
    related_tools=["get_pig_cycle_state", "get_pig_l1_evidence", "list_pig_watch"],
)
def get_pig_paper_status() -> str:
    """模拟盘持仓/净值/成交只读快照（无参数）。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_paper_status")
    try:
        st = backend.paper.paper_status()
    except Exception as exc:
        logger.warning("模拟盘状态取数失败: %s", exc)
        return _error("get_pig_paper_status", "fetch_failed", f"模拟盘状态取数失败: {exc}")
    rv = (st.get("latest_signal") or {}).get("rules_version")
    if not rv:
        rv = backend.paper.C.RULES_VERSION
    return _dump({
        "status": "ok", "scope": "pro", "rules_version": rv,
        **st,
        **_plain_block(_plain_paper(st)),
        "discipline": _DISCIPLINE,
    })


def _plain_monthly_sales(data, company: str, product: str, months: int) -> str:
    """月度销售简报 -> 大白话（只翻译措辞，不改数字）。"""
    if not data:
        return "月度销售简报暂时取不到（缺数据不猜）。"
    names = [company] if company else list(data)
    segs = []
    for name in names:
        products = data.get(name) or {}
        pkeys = [product] if product else list(products)
        for pk in pkeys:
            rows = products.get(pk) or []
            tail = rows[-months:] if months and months > 0 else rows
            if not tail:
                continue
            last = tail[-1]
            unit = last.get("volume_unit") or ""
            seg = f"{name}·{pk}：{last['period']} 卖了 {last['volume']} {unit}"
            if last.get("revenue_yi") is not None:
                seg += f"、销售收入 {last['revenue_yi']} 亿"
            if last.get("price") is not None:
                seg += f"、均价 {last['price']} {last.get('price_unit') or '元/公斤'}"
            if len(tail) >= 2:
                prev = tail[-2]
                dvol = (last["volume"] - prev["volume"]) if last.get("volume") is not None and prev.get("volume") is not None else None
                if dvol is not None:
                    seg += f"（环比{'多' if dvol >= 0 else '少'}卖 {abs(dvol):.1f} {unit}）"
            segs.append(seg)
    if not segs:
        return "没有匹配的公司或品类月度简报。"
    return ("月度销售简报（公司自愿披露、未经审计，只看经营节奏别当精确财报）："
            + "；".join(segs) + "。注意猪按万头、鸡按万只，单位不同不能直接相加。")


@register_tool(
    tool_id="get_pig_monthly_sales",
    name="猪企月度销售简报查询（销量/收入/均价，月频经营节奏）",
    description=(
        "只读查询三家头部猪企自愿披露的月度销售简报（巨潮 cninfo PDF，未审计阶段值）："
        "牧原股份 商品猪(万头)+屠宰生猪、温氏股份 肉鸡(万只)+肉猪(万头)+白羽鸡苗、新希望 商品猪(万头)。"
        "每行给出该月销量、销售收入(亿元)、均价(元/公斤)，以及年初至今累计销量/累计收入。"
        "用来在两份季度财报之间按月份跟踪经营过程——出栏节奏是放量还是收缩、均价环比涨跌、收入变化，"
        "补上企业模型只有季报、看不到月度经营状态的缺口。"
        "口径：1-2月常发合并简报(牧原)，合并数归入2月、1月缺行；简报为未审计数据，与定期报告或有差异。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "monthly_sales", "company_operation", "volume", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查牧原/温氏/新希望月度卖了多少猪、均价收入", "看出栏节奏环比放量收缩", "跟踪财报之间的月度经营状态"],
    when_to_use=(
        "当用户问‘牧原/温氏/新希望这个月（或最近几个月）卖了多少头猪/鸡、销售收入多少、均价多少’、"
        "‘最近出栏是在放量还是收缩’、‘月度销售简报怎么样’、‘屠宰量多少’，"
        "或要按月份而非季度了解公司经营节奏时使用。"
    ),
    when_not_to_use=(
        "不要用于季度财报利润/资产负债（用 get_pig_company_fin_check / get_pig_l0_evidence）；"
        "不要把猪(万头)和鸡(万只)直接相加；本工具只读，不给买卖指令。"
    ),
    returns=(
        "JSON：companies.{name}.{product}[]（period/volume/volume_unit/revenue_yi/price/"
        "price_unit/cum_volume/cum_revenue_yi/published，按期升序）、coverage（每公司每品月份数与区间）。"
        "空库时公司为空，不造假数据。"
    ),
    example="get_pig_monthly_sales(company='牧原股份', months=6)",
    related_tools=["get_pig_company_fin_check", "get_pig_cycle_state", "query_pig_series"],
)
def get_pig_monthly_sales(company: str = "", product: str = "", months: int = 12) -> str:
    """月度销售简报查询。company/product 留空=全部；months 控制大白话摘要展示的最近月数。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_monthly_sales")
    try:
        data = backend.data.load_company_monthly_sales()
    except Exception as exc:
        logger.warning("月度销售简报取数失败: %s", exc)
        return _error("get_pig_monthly_sales", "fetch_failed",
                      f"月度销售简报取数失败: {exc}")

    coverage = {}
    for name, products in data.items():
        coverage[name] = {pk: {"n": len(rows),
                               "first": rows[0]["period"] if rows else None,
                               "last": rows[-1]["period"] if rows else None}
                          for pk, rows in products.items()}
    return _dump({
        "status": "ok", "scope": "pro",
        "companies": data, "coverage": coverage,
        **_plain_block(_plain_monthly_sales(data, company, product, months)),
        "discipline": _DISCIPLINE,
        "note": ("数据为公司自愿披露、未审计月报；1-2月合并简报归入2月(1月缺行)；"
                 "猪=万头、鸡/鸡苗=万只，单位不同勿直接相加。"),
    })


_BASIS_CN = {
    "pig": "纯猪养殖口径",
    "mixed": "养殖混业口径（含禽苗/外购仔猪等苗种成本）",
    "segment_total": "板块总成本（未按成本项拆分）",
}
_ITEM_CN = {
    "feed": "饲料", "labor": "职工薪酬", "depreciation": "折旧",
    "medicine": "兽药疫苗", "energy": "燃料动力", "materials": "物料消耗",
    "other": "其他", "seedling": "苗种成本",
}


def _plain_cost_structure(data, company: str, year, latest_only: bool) -> str:
    """年报成本构成 -> 大白话（只翻译措辞，不改数字）。"""
    if not data:
        return "年报成本构成暂时取不到（缺数据不猜）。"
    names = [company] if company else list(data)
    segs = []
    for name in names:
        rows = data.get(name) or []
        years = sorted({r["fiscal_year"] for r in rows})
        if latest_only and years:
            years = [years[-1]]
        if year:
            years = [y for y in years if y == year]
        for fy in years:
            yr_rows = [r for r in rows if r["fiscal_year"] == fy]
            basis = yr_rows[0].get("basis") if yr_rows else ""
            item_txt = "、".join(
                f"{_ITEM_CN.get(r['item_std'], r['item_raw'])} {r['pct']}%"
                for r in yr_rows if r.get("pct") is not None
                and r["item_std"] != "__total__")
            seg = f"{name} {fy}年（{_BASIS_CN.get(basis, basis)}）：{item_txt}"
            total = next((r for r in yr_rows if r["item_std"] == "__total__"), None)
            if total is not None and total.get("amount_yi") is not None:
                seg += f"；肉猪类板块总成本 {total['amount_yi']} 亿"
            segs.append(seg)
    if not segs:
        return "没有匹配的公司或年度成本构成。"
    return ("年报营业成本构成（年度披露、经审计，看每一块钱成本花在哪）："
            + "；".join(segs) + "。注意三家口径不同（纯猪/混业/仅板块总额），"
            "不同口径之间不能直接比占比。")


@register_tool(
    tool_id="get_pig_cost_structure",
    name="猪企年报营业成本构成查询（饲料/人工/折旧等分项，年度）",
    description=(
        "只读查询三家头部猪企年度报告中的「营业成本构成」明细（巨潮 cninfo 年报 PDF，经审计）："
        "每个成本项给出当年金额(亿元)和占营业成本比重(%)。用于看公司每一块钱养殖成本花在哪——"
        "饲料占多少、人工占多少、折旧（重资产）占多少、其他占多少，以及这些结构怎么随年度变化，"
        "补上企业模型只有总成本标量、看不到成本内部结构的缺口。"
        "口径差异（强制保留、勿强行拉齐）：牧原股份为纯猪口径，2021-2023按7项明细披露、"
        "2024年起合并为4项(其他项口径变大)；新希望2021-2023为养殖混业口径(含苗种成本)、"
        "2024年起改为纯猪养殖口径；温氏股份年报只给肉猪类板块总成本，不按成本项拆分。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "cost_structure", "company_operation", "cost", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查牧原/温氏/新希望成本由什么构成", "对比饲料人工折旧占比及年度变化", "分析重资产折旧在成本中的份量"],
    when_to_use=(
        "当用户问‘牧原/温氏/新希望成本构成是什么’、‘饲料/人工/折旧各占多少成本’、"
        "‘成本结构怎么变化’、‘完全成本里哪块最贵’，或要从年报角度拆解公司成本内部结构时使用。"
    ),
    when_not_to_use=(
        "不要用于每公斤完全成本水平本身（用 get_pig_cycle_state / query_pig_series 的 company_cost）；"
        "不要把混业口径(mixed)占比和纯猪口径(pig)直接相比；不要跨牧原2023/2024的other口径直接比；"
        "本工具只读，不给买卖指令。"
    ),
    returns=(
        "JSON：companies.{name}[]（fiscal_year/segment/basis/item_raw/item_std/amount_yi/pct/"
        "source_pdf/published，按年与项升序）、coverage（每公司年度数与区间）。空库时公司为空，不造假数据。"
    ),
    example="get_pig_cost_structure(company='牧原股份', latest_only=True)",
    related_tools=["get_pig_cycle_state", "query_pig_series", "get_pig_company_fin_check", "get_pig_monthly_sales"],
)
def get_pig_cost_structure(company: str = "", year: int = 0, latest_only: bool = False) -> str:
    """年报营业成本构成查询。company 留空=全部；year 指定会计年度；latest_only=只看最新年度。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_cost_structure")
    try:
        data = backend.data.load_company_cost_structure()
    except Exception as exc:
        logger.warning("年报成本构成取数失败: %s", exc)
        return _error("get_pig_cost_structure", "fetch_failed",
                      f"年报成本构成取数失败: {exc}")

    coverage = {}
    for name, rows in data.items():
        ys = sorted({r["fiscal_year"] for r in rows})
        coverage[name] = {"n_years": len(ys), "years": ys,
                          "first": ys[0] if ys else None,
                          "last": ys[-1] if ys else None}
    return _dump({
        "status": "ok", "scope": "pro",
        "companies": data, "coverage": coverage,
        **_plain_block(_plain_cost_structure(data, company, year, latest_only)),
        "discipline": _DISCIPLINE,
        "basis_note": _BASIS_CN,
        "note": ("数据取自经审计年报；三家口径不同(pig纯猪/mixed混业/segment_total仅板块总额)，"
                 "勿跨口径直接比占比；牧原2024起明细合并、other口径变化。"),
    })


_METRIC_CN = {
    "psy": "PSY（每头能繁年提供断奶仔猪）",
    "fcr": "料肉比",
    "market_rate": "上市率/成活率",
    "litter_weaned": "窝均断奶数",
}
_PERIOD_CN = {
    "annual": "全年平均",
    "Q4": "四季度时点",
    "year_end": "年末时点",
    "H1": "上半年时点",
    "H2": "下半年水平",
    "Q3-Q4": "三四季度区间",
}


def _plain_efficiency(data, company: str, year, latest_only: bool) -> str:
    """年报效率指标 -> 大白话（只翻译措辞，不改数字）。"""
    if not data:
        return "养殖效率指标暂时取不到（缺数据不猜）。"
    names = [company] if company else list(data)
    segs = []
    for name in names:
        rows = data.get(name) or []
        years = sorted({r["fiscal_year"] for r in rows})
        if latest_only and years:
            years = [years[-1]]
        if year:
            years = [y for y in years if y == year]
        for fy in years:
            yr_rows = [r for r in rows if r["fiscal_year"] == fy]
            parts = []
            for r in yr_rows:
                per = _PERIOD_CN.get(r.get("period"), r.get("period"))
                parts.append(f"{_METRIC_CN.get(r['metric'], r['metric'])}"
                             f"{r['value']}{r.get('unit') or ''}（{per}）")
            segs.append(f"{name} {fy}年：" + "、".join(parts))
    if not segs:
        return "没有匹配的公司或年度效率指标。"
    return ("养殖效率指标（PSY/料肉比/上市率/窝均断奶，年报及半年报/投关锚点）："
            + "；".join(segs) + "。注意时点值（Q4/年末/上半年）不是全年平均，"
              "勿当全年值平推；各家披露年份不齐，缺数据处不猜。")


def _plain_segment_profit(data, company: str, year, latest_only: bool) -> str:
    """年报主营业务分产品盈亏 -> 大白话（只翻译措辞，不改数字）。"""
    if not data:
        return "分部盈亏数据暂时取不到（缺数据不猜）。"
    names = [company] if company else list(data)
    segs = []
    for name in names:
        rows = data.get(name) or []
        years = sorted({r["fiscal_year"] for r in rows})
        if latest_only and years:
            years = [years[-1]]
        if year:
            years = [y for y in years if y == year]
        for fy in years:
            yr_rows = sorted((r for r in rows if r["fiscal_year"] == fy),
                             key=lambda r: (not r.get("is_pig"), r["segment_raw"]))
            parts = [f"{r['segment_raw']}收入{r['revenue_yi']}亿、毛利率{r['gross_margin_pct']}%"
                     for r in yr_rows]
            segs.append(f"{name} {fy}年：" + "、".join(parts))
    if not segs:
        return "没有匹配的公司或年度分部盈亏数据。"
    return ("主营业务分产品盈亏（巨潮年报 MD&A，亿元）：" + "；".join(segs)
            + "。注意这是**毛利**不是净利（不含期间费用/资产减值/财务费用）；"
              "“主营业务”口径剔其他业务，与总营收有少量差异；新希望2024年起处置禽与食品、"
              "分部由四个变两个（公司已重述可比期），勿跨年直接比业务结构。")


@register_tool(
    tool_id="get_pig_efficiency",
    name="猪企养殖效率指标查询（PSY/料肉比/上市率/窝均断奶）",
    description=(
        "只读查询三家头部猪企的养殖效率指标（巨潮 cninfo 年报 PDF，及半年报/投关锚点）："
        "PSY=每头能繁母猪一年提供的断奶仔猪数（头/年，越高繁殖效率越高）、"
        "料肉比=长一公斤肉吃多少公斤饲料（越低越省料）、肉猪上市率/育肥成活率（%）、"
        "窝均断奶/健仔数（头/窝）。用于比较牧原/温氏/新希望谁养得更省、繁殖效率谁更高，"
        "以及效率怎么随年度改善，补上企业模型只有成本标量、看不到养殖效率的缺口。"
        "口径差异（强制保留、勿当全年值平推）：新希望2024年起给全年平均值，2022-2023多为"
        "四季度/年末时点值；温氏2023-2024给全年PSY与上市率，2021上市率为下半年回升水平、"
        "窝均健仔取区间下限，2022与2025年报不报PSY；牧原年报不披露效率数值，仅有2026上半年"
        "锚点（PSY约29、料肉比约2.46、成活率约92%）。出栏均重三家年报均不披露，本工具无此指标。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "efficiency", "psy", "fcr", "company_operation", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查牧原/温氏/新希望PSY或料肉比", "对比三家养殖效率及年度改善", "分析成活率/窝均断奶数"],
    when_to_use=(
        "当用户问‘牧原/温氏/新希望PSY/料肉比/成活率/窝均断奶是多少’、‘谁养殖效率更高’、"
        "‘效率指标怎么变化’，或要从年报角度比较公司养殖效率时使用。"
    ),
    when_not_to_use=(
        "不要把时点值(Q4/年末/H1)当全年平均；不要在三家/各年间无视口径直接排名；"
        "出栏均重年报不披露、不要向本工具索要；本工具只读，不给买卖指令。"
    ),
    returns=(
        "JSON：companies.{name}[]（fiscal_year/metric/value/unit/period/period_note/source/"
        "source_pdf/published，按年与指标升序）、coverage（每公司年度数与区间）。空库时公司为空，不造假数据。"
    ),
    example="get_pig_efficiency(company='新希望', latest_only=True)",
    related_tools=["get_pig_cost_structure", "get_pig_cycle_state", "query_pig_series", "get_pig_monthly_sales"],
)
def get_pig_efficiency(company: str = "", year: int = 0, latest_only: bool = False) -> str:
    """养殖效率指标查询。company 留空=全部；year 指定会计年度；latest_only=只看最新年度。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_efficiency")
    try:
        data = backend.data.load_company_efficiency()
    except Exception as exc:
        logger.warning("养殖效率指标取数失败: %s", exc)
        return _error("get_pig_efficiency", "fetch_failed",
                      f"养殖效率指标取数失败: {exc}")

    coverage = {}
    for name, rows in data.items():
        ys = sorted({r["fiscal_year"] for r in rows})
        coverage[name] = {"n_years": len(ys), "years": ys,
                          "first": ys[0] if ys else None,
                          "last": ys[-1] if ys else None}
    return _dump({
        "status": "ok", "scope": "pro",
        "companies": data, "coverage": coverage,
        **_plain_block(_plain_efficiency(data, company, year, latest_only)),
        "discipline": _DISCIPLINE,
        "period_note_cn": _PERIOD_CN,
        "note": ("数据取自年报及半年报/投关锚点；时点值(Q4/年末/H1)非全年平均，"
                 "勿平推；各家披露年份不齐，缺数据处不猜；出栏均重年报不披露。"),
    })


@register_tool(
    tool_id="get_pig_segment_profit",
    name="猪企年报主营业务分产品盈亏查询（分业务收入/成本/毛利率）",
    description=(
        "只读查询三家头部猪企年报 MD&A「主营业务分产品」明细（巨潮 cninfo 年报 PDF，年度口径）："
        "每个分产品分部给主营业务口径的营业收入、营业成本、毛利、毛利率，用于新希望 SOTP 分部估值、"
        "温氏猪/鸡拆分、牧原生猪与屠宰肉食拆分，修正只看集团合并口径被其他业务摊薄的问题。"
        "分部口径：牧原2021仅生猪、2022起为生猪+屠宰肉食；温氏2021起为肉猪类+肉鸡类双主业；"
        "新希望2021-2023为饲料/禽产业/猪产业/食品四分部，2024年起处置禽与食品仅留饲料/猪产业。"
        "口径纪律（强制保留）：这是**毛利**不是净利，不含期间费用/资产减值/财务费用，勿当分部净利润；"
        "“主营业务”口径剔其他业务，与财报总营收有少量差异；新希望2024分部结构变更（公司已重述可比期），"
        "勿跨年把四分部与两分部直接比业务结构。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "segment", "sotp", "gross_margin", "company_operation", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "查某公司某年度各业务收入/毛利率",
        "SOTP分部估值取分部收入与毛利",
        "温氏猪鸡拆分、牧原生猪与屠宰拆分",
        "比较各业务盈利能力而非集团合并摊薄值",
    ],
    when_to_use=(
        "当用户问‘牧原/温氏/新希望各业务（生猪/饲料/屠宰/禽/食品）收入或毛利率是多少’、"
        "‘猪业务和鸡业务分别赚不赚钱’、‘做分部/SOTP估值要分部收入成本’，"
        "或要看分产品而非集团合并口径的盈亏时使用。"
    ),
    when_not_to_use=(
        "不要把毛利当净利润（未扣费用/减值/财务费用）；不要跨年直接比新希望2023四分部与2024两分部结构；"
        "不要与财报总营收强行对账（主营业务口径有差异）；本工具为年度数据、无季度值，只读不给买卖指令。"
    ),
    returns=(
        "JSON：companies.{name}[]（fiscal_year/segment_raw/segment_std/is_pig/revenue_yi/cost_yi/"
        "gross_profit_yi/gross_margin_pct/source_pdf/published，按年度与分部排序）、"
        "coverage（每公司年度数与区间）。空库时公司为空，不造假数据。"
    ),
    example="get_pig_segment_profit(company='温氏股份', latest_only=True)",
    related_tools=["get_pig_cost_structure", "get_pig_efficiency", "get_pig_company_fin_check", "get_pig_cycle_state"],
)
def get_pig_segment_profit(company: str = "", year: int = 0, latest_only: bool = False) -> str:
    """主营业务分产品盈亏查询。company 留空=全部；year 指定会计年度；latest_only=只看最新年度。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_segment_profit")
    try:
        data = backend.data.load_company_segment_profit()
    except Exception as exc:
        logger.warning("分部盈亏取数失败: %s", exc)
        return _error("get_pig_segment_profit", "fetch_failed",
                      f"分部盈亏取数失败: {exc}")

    coverage = {}
    for name, rows in data.items():
        ys = sorted({r["fiscal_year"] for r in rows})
        coverage[name] = {"n_years": len(ys), "years": ys,
                          "first": ys[0] if ys else None,
                          "last": ys[-1] if ys else None}
    return _dump({
        "status": "ok", "scope": "pro",
        "companies": data, "coverage": coverage,
        **_plain_block(_plain_segment_profit(data, company, year, latest_only)),
        "discipline": _DISCIPLINE,
        "note": ("这是毛利不是净利（不含期间费用/资产减值/财务费用）；主营业务口径剔其他业务，"
                 "与总营收有少量差异；新希望2024起处置禽与食品、分部口径变更（公司已重述可比期），"
                 "勿跨年直接比业务结构；年度数据无季度值，缺数据处不猜。"),
    })


def _plain_solvency(bs_data, cf_data, company: str, quarters: int) -> str:
    """偿债+产能 -> 大白话（只翻译措辞，不改数字）。"""
    if not bs_data:
        return "资产负债数据暂时取不到（缺数据不猜）。"
    names = [company] if company else list(bs_data)
    segs = []
    for name in names:
        rows = bs_data.get(name) or []
        if not rows:
            continue
        last = rows[-1]
        tail = rows[-(max(1, quarters)):]
        seg = (f"{name} {last['month_str']}：账上货币资金 {last.get('monetary_cap_yi')} 亿，"
               f"短期有息债务 {last.get('short_int_debt_yi')} 亿、有息负债总额 "
               f"{last.get('total_int_debt_yi')} 亿，现金短债比 {last.get('cash_short_debt_ratio')}"
               f"（<1 表示账上现金不够一次还完短债）；固定资产 {last.get('fix_assets_yi')} 亿、"
               f"在建工程 {last.get('cip_yi')} 亿（在建工程是已开工还没转固的猪场/产线），"
               f"资产负债率 {last.get('debt_ratio_pct')}%")
        cf_rows = (cf_data.get(name) or [])[-2:]
        for c in cf_rows:
            seg += (f"；{c['month_str']} 经营现金流 {c.get('ocf_q_yi')} 亿、资本开支 "
                    f"{c.get('capex_q_yi')} 亿、自由现金流 {c.get('fcf_q_yi')} 亿")
        segs.append(seg)
    if not segs:
        return "没有匹配的公司偿债/产能数据。"
    return ("偿债与产能（季末时点值，单位亿元）：" + "；".join(segs)
            + "。短期有息债务=短期借款+一年内到期非流动负债+短期应付债券，不含应付账款等经营负债；"
              "自由现金流=经营现金流净额−购建固定资产支出，连续为负说明在靠融资/耗现金扩张。")


@register_tool(
    tool_id="get_pig_solvency_capacity",
    name="猪企偿债与产能查询（有息负债/现金短债比/在建工程/自由现金流）",
    description=(
        "只读返回三家头部猪企的偿债安全与产能扩张数据（Tushare 资产负债表/现金流量表，2021Q1 起逐季）："
        "货币资金、短期有息债务（短期借款+一年内到期非流动负债+短期应付债券）、有息负债总额（再加长期借款+应付债券）、"
        "现金短债比（货币资金/短期有息债务，<1 即账上现金不足以一次偿还短债）、资产负债率；"
        "固定资产、在建工程（已开工尚未转固的猪场产线，看未来产能投放）；"
        "单季经营现金流、资本开支、自由现金流（经营现金流净额−购建固定资产支出）、筹资活动净额。"
        "应付账款/合同负债作为经营性无息负债单列，不计入有息债务。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "solvency", "debt", "capacity", "cip", "free_cashflow", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查牧原/温氏/新希望短债压力与现金安全", "查在建工程与未来产能投放", "查真实自由现金流"],
    when_to_use=(
        "当用户问‘牧原/温氏/新希望短期债务/有息负债多少、现金够不够还’、‘在建工程多少、还在不在扩产’、"
        "‘资产负债率/现金短债比’、‘资本开支/自由现金流’、‘偿债压力大不大’时使用。"
    ),
    when_not_to_use=(
        "不要用于利润对账（用 get_pig_company_fin_check）、成本构成（get_pig_cost_structure）；"
        "不要把应付账款等无息经营负债算作有息债务；本工具只读，不给买卖指令。"
    ),
    returns=(
        "JSON：balance_sheet.{name}[] 与 cashflow.{name}[]（逐季，字段同源透传）、coverage；"
        "空库时公司为空，不造假数据。"
    ),
    example="get_pig_solvency_capacity(company='牧原股份', quarters=4)",
    related_tools=["get_pig_company_fin_check", "get_pig_cost_structure", "get_pig_monthly_sales"],
)
def get_pig_solvency_capacity(company: str = "", quarters: int = 2) -> str:
    """偿债与产能查询。company 留空=全部；quarters 控制大白话摘要回看的季数。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_solvency_capacity")
    try:
        bs_data = backend.data.load_company_bs()
        cf_data = backend.data.load_company_cashflow()
    except Exception as exc:
        logger.warning("偿债/产能取数失败: %s", exc)
        return _error("get_pig_solvency_capacity", "fetch_failed",
                      f"偿债/产能取数失败: {exc}")

    coverage = {}
    for name, rows in bs_data.items():
        coverage[name] = {"n": len(rows),
                          "first": rows[0]["month_str"] if rows else None,
                          "last": rows[-1]["month_str"] if rows else None}
    return _dump({
        "status": "ok", "scope": "pro",
        "balance_sheet": bs_data, "cashflow": cf_data, "coverage": coverage,
        **_plain_block(_plain_solvency(bs_data, cf_data, company, quarters)),
        "discipline": _DISCIPLINE,
        "note": ("短期有息债务=短期借款+一年内到期非流动负债+短期应付债券（不含应付账款/合同负债）；"
                 "有息负债总额再加长期借款+应付债券；自由现金流=经营现金流净额−购建固定资产支出；"
                 "时点值随季末披露，缺数据处不猜。"),
    })


def _plain_forecast(res: dict) -> str:
    """预测三表 -> 大白话（只翻译措辞，不改数字）。"""
    comp = res['company']
    sc = res['scenario_prices']
    fc = res['forecast']
    neutral = fc['neutral']
    p = neutral['params']
    parts = []
    ih = [r for r in res['interest_history']
          if r.get('interest_expense_yi') is not None]
    if ih:
        tot = sum(r['interest_expense_yi'] for r in ih)
        parts.append(f"{comp} 近4季利息费用（利润表准确口径）合计 {round(tot, 1)} 亿"
                     f"（{ih[0]['month_str']}~{ih[-1]['month_str']}），"
                     f"综合融资成本约 {p['interest_rate_pct']}%（利息/有息负债）")
    for key, label in (('pessimistic', '悲观'), ('neutral', '中性'),
                       ('optimistic', '乐观')):
        s = fc[key]['summary']
        last = s[-1]
        cum = sum(x['net_profit_attr_yi'] for x in s)
        parts.append(f"{label}情景（首4季猪价 {sc[key]} 元/kg）：8季累计归母净利约 {cum:.0f} 亿，"
                     f"期末货币资金 {last['cash_yi']} 亿、有息负债 {last['debt_yi']} 亿、"
                     f"资产负债率 {last['debt_ratio_pct']}%")
    parts.append(f"模型口径：出栏平推，毛差=基准毛差 {p['gross_margin_base_q_yi']} 亿/季"
                 f"+(猪价−基准价 {p['price_base_4q_yuan_kg']} 元/kg)×弹性"
                 f"{p['margin_sens_yi_per_yuan']} 亿/元（近8季对猪价回归标定），"
                 f"非猪收入平推 {p['nonpig_rev_q_yi']} 亿/季（混业口径）、"
                 f"每季折旧摊销 {p['da_q_yi']} 亿、维护性资本开支≈折旧摊销、"
                 f"税率 {p['tax_rate_pct']}%、归母比 {p['attr_ratio_pct']}%，"
                 "全部按近4季实际值标定；这是情景推演不是事实，猪价/成本偏离假设时结论随之变化"
                 + ("；负债率>100% 表示推演下资不抵债（净资产亏穿），现实中会先发生融资/重组等，模型未含"
                    if any(s[-1]['debt_ratio_pct'] > 100 for s in
                           (fc[k]['summary'] for k in fc)) else ""))
    return "；".join(parts) + "。"


@register_tool(
    tool_id="get_pig_forecast_statements",
    name="猪企预测三表查询（利息费用/综合融资成本/8季利润表现金负债率推演）",
    description=(
        "只读返回头部猪企的预测三大报表（利润表/现金流量表/资产负债表，逐季滚动 8 个季度，悲观/中性/乐观三情景）："
        "情景价由近 N 月猪价分位确定；每季按'利润表逐项（一次性损益按 off/avg 开关计入 EBT）→ "
        "间接法经营现金流（净利+折旧摊销−一次性+营运资金变动，营运资金系数按季度类型季节性标定）"
        "→ 维护性资本开支 → 筹资平项（保最低现金）→ 货币资金与有息负债滚动 → 资产负债率'勾稽生成，三表可对账。"
        "同时返回：近4季利息费用（利润表 fin_exp_int_exp 准确口径，逐季披露）、"
        "综合融资成本（近4季利息/最新有息负债）、历史勾稽桥（近6季'净利+D&A 隐含 OCF'vs 实际 OCF 的残差）。"
        "模型参数（单位现金成本/每季折旧摊销/融资成本/税率/归母比/营运资金系数）全部从近4季实际值标定，无硬编码。"
        + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["pig_cycle", "forecast", "three_statements", "interest",
                     "debt_ratio", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查牧原/温氏/新希望利息费用与综合融资成本",
                   "推演未来几个季度利润/经营现金流/货币资金/资产负债率",
                   "按猪价情景做三表压力测试"],
    when_to_use=(
        "当用户问'利息费用多少、综合融资成本多少、未来几季利润/经营现金流/货币资金/资产负债率怎么走、"
        "预测三表、按猪价 X 元压力测试、现金撑不撑得住、负债率会不会破线'等前瞻推演问题时使用。"
    ),
    when_not_to_use=(
        "不要用于历史实际值查询（偿债用 get_pig_solvency_capacity、利润对账用 get_pig_company_fin_check）；"
        "输出是模型推演不是既成事实，引用时必须标明情景与假设；本工具只读，不给买卖指令。"
    ),
    returns=(
        "JSON：company/vol_base_wan/weight_kg/scenario_prices（含分位窗口）/"
        "interest_history（近4季利息费用）/forecast.{pessimistic|neutral|optimistic}"
        "（base_month/params/assumptions/summary 8季，detail=true 时附选中情景 quarters 逐季三表）/"
        "bridge（历史勾稽桥）；三表勾稽差异≤0.1亿（舍入量级）。"
    ),
    example="get_pig_forecast_statements(company='牧原股份', scenario='neutral', detail=True)",
    related_tools=["get_pig_solvency_capacity", "get_pig_company_fin_check",
                   "get_pig_cycle_state"],
)
def get_pig_forecast_statements(company: str = "牧原股份",
                                scenario: str = "neutral",
                                detail: bool = False) -> str:
    """预测三表查询。scenario 选 pessimistic/neutral/optimistic；detail=true 附逐季三表明细。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("get_pig_forecast_statements")
    if scenario not in ("pessimistic", "neutral", "optimistic"):
        return _error("get_pig_forecast_statements", "bad_scenario",
                      f"scenario 只支持 pessimistic/neutral/optimistic，收到 {scenario!r}")
    try:
        res = backend.enterprise.forecast_with_defaults(company)
    except ValueError as exc:
        return _error("get_pig_forecast_statements", "no_such_company", str(exc))
    except Exception as exc:
        logger.warning("预测三表取数失败: %s", exc)
        return _error("get_pig_forecast_statements", "fetch_failed",
                      f"预测三表取数失败: {exc}")

    fc = res['forecast']
    forecast_out = {}
    for key, block in fc.items():
        forecast_out[key] = {'base_month': block['base_month'],
                             'params': block['params'],
                             'assumptions': block['assumptions'],
                             'summary': block['summary']}
        if key == scenario and detail:
            forecast_out[key]['quarters'] = block['quarters']
    return _dump({
        "status": "ok", "scope": "pro",
        "company": res['company'],
        "vol_base_wan": res['vol_base_wan'], "weight_kg": res['weight_kg'],
        "scenario_prices": res['scenario_prices'],
        "interest_history": res['interest_history'],
        "forecast": forecast_out,
        "bridge": res['bridge'],
        **_plain_block(_plain_forecast(res)),
        "discipline": _DISCIPLINE,
        "note": ("利息费用=利润表 fin_exp_int_exp 逐季口径（准确），区别于现金流量表补充资料的财务费用；"
                 "综合融资成本=近4季利息费用合计/最新有息负债；"
                 "预测路径：首4季用情景价、后4季回归中性价；参数近4季标定；"
                 "一次性损益预测期默认 off（可切 avg 计入 EBT），间接法恒剔除；资产减值未单列（数据缺口）；"
                 "筹资为保最低现金（0.5季经营支出）的平项，"
                 "缺口增债、富余还债；资产负债表含显式其他经营负债项与残差平衡项 other_liab_plug_yi（透明单列）。"),
    })


__all__ = [
    "get_pig_cycle_state",
    "query_pig_knowledge",
    "get_pig_l0_evidence",
    "get_pig_l1_evidence",
    "get_pig_futures_evidence",
    "query_pig_series",
    "list_pig_journal",
    "list_pig_watch",
    "get_pig_paper_status",
    "get_pig_monthly_sales",
    "get_pig_cost_structure",
    "get_pig_efficiency",
    "get_pig_segment_profit",
    "get_pig_solvency_capacity",
    "get_pig_forecast_statements",
]
