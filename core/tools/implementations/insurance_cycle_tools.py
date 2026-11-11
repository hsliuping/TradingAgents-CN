# -*- coding: utf-8 -*-
"""
保险行业 Pro —— Agent 工具守卫薄封装（共享工具层中唯一允许出现的保险行业入口）。

【铁律 / 不可违反】（与 pig_cycle_tools.py 同款，四行业统一）
1. 只读、只提示、不动手：本文件任何函数都不得下单/调仓，不得替用户做交易决策；
   输出仅为事实与数据状态，供 Agent 生成研究结论参考。
2. 数字唯一来源：所有数值直接取自 insurance_cycle 库（ingest 采集 + 人工台账，
   与 pig_cycle 同实例分库），本文件只做字段投影与组装，禁止第二套算法、
   禁止重算/改写数字；四象限/估值锚/利差等派生读数只在
   app/pro/routers/insurance.py 与前端计算，本层绝不复制派生逻辑。
3. 缺数据诚实标注（gap / error / unavailable），绝不伪造、绝不外推填充。
4. 社区版隔离：core.pro 为 Pro 专有包，社区版不存在。对它的 import 必须【延迟到
   函数体内】并用 try/except ImportError 接住，返回结构化 unavailable 结果；
   严禁在模块顶层 import core.pro —— 否则 ToolLoader 扫描本文件会整模块失败，
   污染所有工具注册。
5. 本文件是共享区（core/tools/）对 Pro 能力的"薄封装"，不含任何 Pro 业务实现。
6. 大白话输出：每个工具输出必须携带 plain_summary（给最终用户的大白话解读）、
   answer_style（措辞纪律）与 jargon_map（术语对照）；本层只翻译措辞，
   不产生任何新数字。
"""

import json
import logging
import types

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

# 每次返回都附带的纪律提示（Agent 据此约束措辞，不越界为交易指令）
_DISCIPLINE = [
    "只读参考，不自动买卖、不调仓；系统只提示，动手权在人。",
    "慢变量（负债景气/代理人趋势/预定利率政策）给方向，快变量（股价/AH溢价）给时机，"
    "不用快变量论证慢变量。",
    "所有数字为 insurance_cycle 库同源读数；缺数据处已诚实标注，禁止外推或臆造。",
]

_UNAVAILABLE_MSG = (
    "保险行业 Pro 模块在当前版本不可用（core.pro 未安装或被裁剪）。"
    "本工具为只读守卫，已自动降级，不影响其他工具；如需该能力请使用 Pro 版本。"
)

# ---------- 大白话输出层 ----------
_ANSWER_STYLE = [
    "先给大白话结论，再给数据依据：像跟不懂保险股的朋友解释那样说话。",
    "术语必须翻译后才能出现在给用户的回答里：NBV、EVPS、PEV、内含价值、继续率、"
    "偿付能力充足率、COR、预定利率、AH溢价等，一律换成日常说法，或用括号补一句大白话解释。",
    "plain_summary 是现成的大白话解读，可直接引用或改写；jargon_map 是术语对照表。",
    "只转述数据事实与口径说明，不替用户决定买卖。",
]

_JARGON_PLAIN = {
    "NBV/新业务价值": "新卖出的保单未来能赚的利润折算到今天的值，衡量卖新单赚钱的能力；"
                 "NBV同比=跟去年同期比，正=景气上行",
    "EVPS/内含价值": "保险公司'现在就解散值多少钱'折算到每股；PEV=股价÷每股内含价值，"
               "是寿险公司专用的估值尺子（类似 PB 但分母换成内含价值）",
    "继续率13/25个月": "买保险的人第 13/25 个月还在按时交费的比例；越高说明销售渠道质量越好",
    "偿付能力": "保险公司赔得起大额理赔的能力，监管有红线；充足率越低资本越紧",
    "AH溢价": "同一家公司 A 股比港股(H股)贵多少；行业级交叉估值差，不作个股选择依据",
    "原保险保费收入": "传统口径保费（保障型+储蓄型都算），行业卖保单的总收入",
    "保户投资款新增交费": "万能险等偏投资属性的钱；与原保费分开看，两栏一起才构成行业'销售温度'",
    "单月同比": "只看当月跟去年同月比，剔除累计值的基数效应，更灵敏",
    "COR/综合成本率": "财险的赔付+费用占保费的比例，低于 100% 才承保赚钱",
    "预定利率": "保单承诺给客户的回报率上限；利率下行期监管会下调上限（政策日历在跟踪触发条件）",
}

_STYLE_DESC = (
    "【回答措辞（强制）】给用户的回答必须先给大白话结论、再给数据依据；"
    "NBV、EVPS、PEV、继续率、COR、预定利率、AH溢价等术语必须翻译成日常语言后才能出现"
    "（输出中的 plain_summary 是现成大白话解读，jargon_map 是术语对照表，answer_style 是措辞纪律）。"
)


def _load_backend():
    """延迟加载 Pro ingest 框架 store（insurance_cycle 库入口）；社区版 ImportError 时返回 None。"""
    try:
        from core.pro.ingest import store as _store
    except ImportError as exc:  # 社区版：core.pro 不存在
        logger.info("保险行业 Pro 后端不可用，保险行业工具进入降级态: %s", exc)
        return None
    return types.SimpleNamespace(store=_store)


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
    """结构化业务错误（非法参数/取数失败），不抛异常给 Agent。"""
    payload = {"status": "error", "scope": "pro", "tool": tool_id,
               "code": code, "message": message}
    payload.update(extra)
    return _dump(payload)


def _clean(doc: dict) -> dict:
    """原始文档投影：去 _id，datetime → ISO 字符串；不改任何数值。"""
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _plain_block(summary: str) -> dict:
    return {
        "plain_summary": summary,
        "answer_style": _ANSWER_STYLE,
        "jargon_map": _JARGON_PLAIN,
    }


# ---------- 序列目录（人工登记；派生读数一律不做，只出原始集合文档） ----------
# id → {label 中文名, unit 单位, key_field 时间键字段, company_aware 是否公司维度}
_CATALOG = [
    {"id": "industry_monthly",
     "label": "行业月度两栏（原保险保费收入 / 保户投资款新增交费，单月同比）",
     "unit": "%", "key_field": "period", "company_aware": False,
     "source_desc": "insurance_industry_monthly 集合（ingest 采集，月频，m2 口径）"},
    {"id": "nbv_quarterly",
     "label": "上市险企 NBV 季度矩阵（新业务价值及同比、累计保费）",
     "unit": "亿元 / %", "key_field": "period", "company_aware": True,
     "source_desc": "insurance_nbv_quarterly 集合（人工台账，逐条留痕，period 形如 2026Q1/H1）"},
    {"id": "agent_count",
     "label": "代理人数量（万人）",
     "unit": "万人", "key_field": "period", "company_aware": True,
     "source_desc": "insurance_agent_count 集合（人工台账，各家披露频率不一，disclosure_freq 字段标明）"},
    {"id": "persistency",
     "label": "继续率（13 个月 / 25 个月）",
     "unit": "%", "key_field": "year", "company_aware": True,
     "source_desc": "insurance_persistency 集合（人工台账，年报口径，按年）"},
    {"id": "solvency",
     "label": "偿付能力（充足率等，季度）",
     "unit": "%", "key_field": "quarter", "company_aware": True,
     "source_desc": "insurance_solvency 集合（人工台账，偿付能力季度报告口径）"},
    {"id": "valuation_inputs",
     "label": "估值输入（EVPS / DPS / 财险 BPS、ROE、COR）",
     "unit": "元 / %", "key_field": "period", "company_aware": True,
     "source_desc": "insurance_valuation_inputs 集合（kind=evps/dps 为寿险轨，kind=pc 为财险轨；"
                    "人工台账）"},
    {"id": "ah_premium",
     "label": "AH 溢价（A/H 交叉估值差，日频）",
     "unit": "%", "key_field": "date", "company_aware": False,
     "source_desc": "insurance_ah_premium 集合（每 pair 一文档含 bars 数组；"
                    "2026-10-22 起停采，历史读数仍可查）"},
]

_AH_PER_PAIR_DEFAULT = 8  # ah_premium 每 pair 输出的最近 bar 数


def _read_series(backend, sid: str, recent: int):
    """按序列 id 读取原始文档列表（原样投影，不做派生计算）；未知 id 返回 None。"""
    db = backend.store.db_domain('insurance')
    if sid == "industry_monthly":
        return list(db['insurance_industry_monthly'].find(
            {}, {'_id': 0}).sort('period', 1))
    if sid == "nbv_quarterly":
        return list(db['insurance_nbv_quarterly'].find(
            {}, {'_id': 0}).sort([('company', 1), ('period', 1)]))
    if sid == "agent_count":
        return list(db['insurance_agent_count'].find(
            {}, {'_id': 0}).sort([('company', 1), ('period', 1)]))
    if sid == "persistency":
        return list(db['insurance_persistency'].find(
            {}, {'_id': 0}).sort([('company', 1), ('year', 1)]))
    if sid == "solvency":
        return list(db['insurance_solvency'].find(
            {}, {'_id': 0}).sort([('company', 1), ('quarter', 1)]))
    if sid == "valuation_inputs":
        return list(db['insurance_valuation_inputs'].find(
            {}, {'_id': 0}).sort([('kind', 1), ('company', 1), ('period', 1)]))
    if sid == "ah_premium":
        out = []
        for p in db['insurance_ah_premium'].find({}, {'_id': 0}).sort('pair', 1):
            bars = p.get('bars') or []
            tail = bars[-recent:] if (recent and recent > 0) else bars
            for b in tail:
                row = {"pair": p.get("pair"), "name": p.get("name")}
                row.update(b)
                out.append(row)
        return out
    return None


def _filter_points(docs: list, meta: dict, company: str,
                   start: str, end: str, recent: int) -> list:
    """时间键字典序窗口 + 公司过滤 + 尾部截取；只筛选，不改数值。"""
    kf = meta.get("key_field")
    needle = (company or "").strip().lower()
    if needle:
        docs = [d for d in docs
                if needle in str(d.get("company", "")).lower()
                or needle in str(d.get("name", "")).lower()]
    if (start or "").strip() or (end or "").strip():
        lo, hi = start.strip(), end.strip()

        def _in(d):
            k = d.get(kf)
            if k is None:
                return False
            s = str(k)
            return (not lo or s >= lo) and (not hi or s <= hi)
        docs = [d for d in docs if _in(d)]
    elif recent and recent > 0 and len(docs) > recent:
        docs = docs[-recent:]
    return [_clean(d) for d in docs]


_SERIES_PLAIN = {
    "industry_monthly": "两栏一起看行业的'销售温度'：原保费增速是卖保障型保单的温度计，"
                        "保户投资款是万能险等偏投资的钱；单月同比比累计同比更灵敏。",
    "nbv_quarterly": "NBV 是新卖保单未来利润的现值，四家寿险龙头同比均值是负债景气方向的核心读数。",
    "agent_count": "代理人数量是行业出清的慢变量：队伍止跌回稳往往领先负债端改善。",
    "persistency": "继续率高说明当年卖的单子质量好、退保少；是渠道质量的体检表。",
    "solvency": "偿付能力充足率是'赔得起'的安全垫，监管红线附近的公司扩张会受限。",
    "valuation_inputs": "EVPS/DPS 是估值锚的原料（PEV=股价÷每股内含价值、股息率=DPS÷股价）；"
                        "财险轨看 BPS/ROE/COR。派生的 PEV/股息率/利差请看工作台页面，本工具只给原料。",
    "ah_premium": "AH 溢价=同一家公司 A 股比 H 股贵多少，行业级交叉估值差，不作个股选择依据；"
                  "该序列 2026-10-22 起停采，返回的是停采前的历史读数。",
}


@register_tool(
    tool_id="query_insurance_series",
    name="保险行业原始数据序列查询（保费/NBV/代理人/继续率/偿付能力/AH溢价/估值输入）",
    description=(
        "只读查询保险行业 Pro 库（insurance_cycle）里的【原始采集与人工台账数据】，"
        "是保险工作台一切读数的底层原料，可用来独立核查页面引用的数字。"
        "不传 series 时返回序列目录（id/中文名/单位/来源/点数/覆盖区间），"
        "可用 q 按中文标签或来源过滤；传 series 后返回该序列的逐条原始数据。"
        "典型序列：industry_monthly 行业月度两栏（原保费/保户投资款单月同比）、"
        "nbv_quarterly 上市险企NBV季度矩阵、agent_count 代理人数量、persistency 继续率、"
        "solvency 偿付能力、valuation_inputs 估值输入(EVPS/DPS/BPS/ROE/COR)、"
        "ah_premium AH溢价，实际清单以目录返回为准。" + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["insurance_cycle", "raw_series", "insurance_nbv",
                     "insurance_premium", "insurance_solvency", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查保险行业保费/NBV/代理人/继续率/偿付能力原始数据",
                   "核查保险工作台页面引用的数字", "确认保险数据的来源与新旧"],
    when_to_use=(
        "当用户要看保险行业的具体数据本身（如'保险行业保费增速怎么样''上市险企 NBV 同比多少'"
        "'代理人还在减少吗''各公司偿付能力充足率''AH溢价多少'），"
        "要核查保险工作台页面引用的数字，或要拉原始序列自己做判断时使用。"
        "先不传 series 看目录拿 id。"
    ),
    when_not_to_use=(
        "四象限/估值锚（PEV/股息率/利差）等加工好的派生读数看保险工作台页面（本工具只给原料，"
        "不做派生计算）；预定利率触发器状态属于政策日历（/api/pro/insurance/policy-calendar）；"
        "个股行情与财务三表走通用行情工具；本工具只读数，不做预测与买卖建议。"
    ),
    returns=(
        "目录模式 {mode:'catalog', matched_series:[...]}；数据模式 {mode:'points', series:目录元信息, "
        "points:[原始字段...], n_points_returned}。每点均携带来源集合说明；"
        "未知 series 返回 status=error 并附全部可用 series id。"
    ),
    example="query_insurance_series(series='nbv_quarterly', company='中国平安')  "
            "# 先 query_insurance_series(q='保费') 找 id",
    related_tools=["query_pig_series", "query_battery_series", "query_auto_series"],
)
def query_insurance_series(series: str = "", q: str = "", company: str = "",
                           recent: int = 36, start: str = "", end: str = "") -> str:
    """保险行业原始序列目录/数据点。series 空=目录；recent 取最近 N 条（<=0 全部）；
    start/end 按时间键字符串比较（'YYYY-MM'/'YYYYQ1'/'YYYY'）；company 子串过滤公司维度序列。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_insurance_series")

    by_id = {r["id"]: r for r in _CATALOG}
    sid = (series or "").strip()
    needle = (q or "").strip().lower()

    if not sid:
        rows = []
        for meta in _CATALOG:
            if needle and needle not in (meta["id"] + " " + meta["label"] + " "
                                         + meta.get("source_desc", "")).lower():
                continue
            try:
                # 目录统计：ah_premium 只取每 pair 尾 1 根估覆盖区间，其余全量计数
                probe_recent = 1 if meta["id"] == "ah_premium" else 0
                docs = _read_series(backend, meta["id"], probe_recent)
            except Exception as exc:
                logger.warning("保险序列目录统计失败 %s: %s", meta["id"], exc)
                rows.append({**meta, "n_points": None, "first": None, "last": None,
                             "catalog_error": f"统计失败: {exc}"})
                continue
            keys = sorted({str(d.get(meta["key_field"])) for d in docs
                           if d.get(meta["key_field"]) is not None})
            n = len({d.get("pair") for d in docs}) if meta["id"] == "ah_premium" else len(docs)
            rows.append({**meta, "n_points": n,
                         "first": keys[0] if keys else None,
                         "last": keys[-1] if keys else None})
        return _dump({
            "status": "ok", "scope": "pro", "mode": "catalog",
            "count": len(rows), "q": q or None,
            "matched_series": rows,
            **_plain_block("目录里每条序列都有中文名、单位和来源，都是看保险行业用的原始数据"
                           "（NBV=新卖保单未来利润的现值，继续率=客户第二年还交钱的比例）。"
                           "先用中文名找到想要的序列，再把它的 id 传进来取原始数据。"),
            "note": "把 series id 传入本工具即可取该序列原始数据；start/end 为字符串窗口过滤。",
        })

    if sid not in by_id:
        return _error("query_insurance_series", "unknown_series",
                      f"未知序列 id: {sid}（不带 series 再调一次可获取完整目录）",
                      available_series=sorted(by_id))

    meta = by_id[sid]
    try:
        docs = _read_series(backend, sid, recent)
    except Exception as exc:
        logger.warning("保险序列数据取数失败 %s: %s", sid, exc)
        return _error("query_insurance_series", "fetch_failed",
                      f"序列 {sid} 数据取数失败: {exc}")

    pts = _filter_points(docs or [], meta, company, start, end,
                         recent if meta["id"] != "ah_premium" else recent)
    return _dump({
        "status": "ok", "scope": "pro", "mode": "points",
        "series": meta, "n_points_returned": len(pts),
        "window": {"first": (pts[0].get(meta["key_field"]) if pts else None),
                   "last": (pts[-1].get(meta["key_field"]) if pts else None)},
        "points": pts,
        **_plain_block(_SERIES_PLAIN.get(
            sid, "原始数据点：字段为库内原始口径；来源见 series.source_desc，缺行即源缺数据，不补不插值。")),
        "note": ("points 为库内原始文档投影（字段名与口径原样保留）；"
                 "company/start/end 仅做筛选，不改数值；派生读数（四象限/估值锚）不在本工具范围。"),
    })
