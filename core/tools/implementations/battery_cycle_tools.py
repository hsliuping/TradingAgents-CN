# -*- coding: utf-8 -*-
"""
电池产业链 Pro —— Agent 工具守卫薄封装（共享工具层中唯一允许出现的电池产业链入口）。

【铁律 / 不可违反】（与 pig_cycle_tools.py 同款，四行业统一）
1. 只读、只提示、不动手：本文件任何函数都不得下单/调仓，不得替用户做交易决策；
   输出仅为事实与数据状态，供 Agent 生成研究结论参考。
2. 数字唯一来源：所有数值直接取自 battery_cycle 库（ingest 采集 + 人工核对台账，
   与 pig_cycle 同实例分库），本文件只做字段投影与组装，禁止第二套算法、
   禁止重算/改写数字；锂价档位判定（8万/12万分带）等派生读数只在
   app/pro/routers/battery_cycle.py 与前端计算，本层绝不复制派生逻辑。
3. 缺数据诚实标注（gap / error / unavailable），绝不伪造、绝不外推填充；
   两套价格源（鑫椤区间价 / 百川日均价）口径不同，禁止混算。
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
    "慢变量（材料价格带/装机景气/产能出清）给方向，快变量（锂价日线/股价）给时机，"
    "不用快变量论证慢变量。",
    "所有数字为 battery_cycle 库同源读数；缺数据处已诚实标注，禁止外推或臆造；"
    "鑫椤（区间价）与百川盈孚（日均价）两源口径不同，禁止混算、禁止互相替代。",
]

_UNAVAILABLE_MSG = (
    "电池产业链 Pro 模块在当前版本不可用（core.pro 未安装或被裁剪）。"
    "本工具为只读守卫，已自动降级，不影响其他工具；如需该能力请使用 Pro 版本。"
)

# ---------- 大白话输出层 ----------
_ANSWER_STYLE = [
    "先给大白话结论，再给数据依据：像跟不懂电池产业链的朋友解释那样说话。",
    "术语必须翻译后才能出现在给用户的回答里：GWh、电芯、正极/负极/隔膜/电解液、"
    "出清带/深亏区、staging、三元/磷酸铁锂等，一律换成日常说法，或用括号补一句大白话解释。",
    "plain_summary 是现成的大白话解读，可直接引用或改写；jargon_map 是术语对照表。",
    "只转述数据事实与口径说明，不替用户决定买卖。",
]

_JARGON_PLAIN = {
    "碳酸锂/锂价": "动力电池最核心的原料；锂价是全产业链景气的温度计（深跌=上游在亏钱出清）",
    "电芯": "电池的最小成品单元（一块电池由很多电芯组成）；电芯价格直接反映中游制造的供需",
    "鑫椤/百川盈孚": "两家第三方报价机构：鑫椤给区间价（含最高/最低），百川给日均价；"
               "两源口径不同，各自独立成序列，禁止混算",
    "装机量/GWh": "动力电池装上车用了多少电量；GWh（吉瓦时）是行业通用的电量单位",
    "staging/待核对": "机器解析后还没人工核对入库的数据；看正式结论只用正式台账，staging 仅供参考",
    "section/板块": "鑫椤报告里按产业链环节分组的板块（正极/负极/隔膜/电解液/锂电池等）",
    "spec/规格": "同一材料的不同规格档（如磷酸铁锂不同电压档）；不同规格价格不可直接平均",
    "缺报(null)": "当日该品项没报价；缺报也是信息（源没给），不是 0，禁止当 0 处理",
}

_STYLE_DESC = (
    "【回答措辞（强制）】给用户的回答必须先给大白话结论、再给数据依据；"
    "GWh、电芯、正极/负极/隔膜/电解液、出清带等术语必须翻译成日常语言后才能出现"
    "（输出中的 plain_summary 是现成大白话解读，jargon_map 是术语对照表，answer_style 是措辞纪律）。"
)


def _load_backend():
    """延迟加载 Pro ingest 框架 store（battery_cycle 库入口）；社区版 ImportError 时返回 None。"""
    try:
        from core.pro.ingest import store as _store
    except ImportError as exc:  # 社区版：core.pro 不存在
        logger.info("电池产业链 Pro 后端不可用，电池产业链工具进入降级态: %s", exc)
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
    """原始文档投影：去 _id 与下划线调试字段，datetime → ISO 字符串；不改任何数值。"""
    out = {}
    for k, v in doc.items():
        if k == "_id" or k.startswith("_"):
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
_CATALOG = [
    {"id": "material_price",
     "label": "锂电全链材料日报价快照（鑫椤，正极/负极/隔膜/电解液/锂电池等板块）",
     "unit": "元/吨 等（随行携带）", "key_field": "date", "company_aware": False,
     "source_desc": "battery_material_price 集合（ingest 每日采集鑫椤锂电数据；"
                    "本序列输出【最新一日报价快照】，键 date+section+item+spec+origin）"},
    {"id": "cell_price",
     "label": "电芯日均价（百川盈孚，逐日序列）",
     "unit": "元/Wh 等（随行携带）", "key_field": "date", "company_aware": False,
     "source_desc": "battery_cell_price 集合（ingest 每日采集百川盈孚电芯日均价，键 date+item+source；"
                    "与鑫椤区间价口径不同，禁止混算）"},
    {"id": "installation",
     "label": "动力电池月度装车量台账（中国汽车动力电池产业创新联盟口径，人工核对）",
     "unit": "GWh", "key_field": "period", "company_aware": False,
     "source_desc": "installation_monthly 集合（两步工作流：机器解析入 staging → 人工核对 → "
                    "bat-commit-installation 入库；vendors 为嵌入式厂商榜）"},
]


@register_tool(
    tool_id="query_battery_series",
    name="电池产业链原始数据序列查询（材料报价/电芯价格/装机月报）",
    description=(
        "只读查询电池产业链 Pro 库（battery_cycle）里的【原始采集与人工台账数据】，"
        "是电池工作台一切读数的底层原料，可用来独立核查页面引用的数字。"
        "不传 series 时返回序列目录（id/中文名/单位/来源/覆盖区间），"
        "可用 q 按中文标签过滤；传 series 后返回原始数据："
        "material_price 鑫椤全链材料最新一日报价快照（可按 section 过滤，含磷酸铁锂/三元等正极材料、"
        "锂价相关品项）、cell_price 百川盈孚电芯日均价逐日序列、installation 装机月报正式台账"
        "（附 staging 待核对期次）。锂价日线（akshare 现取口径）不在本工具范围，"
        "实际清单以目录返回为准。" + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["battery_cycle", "raw_series", "lithium_price",
                     "battery_material", "battery_installation", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查锂电材料报价/电芯价格/装机量原始数据",
                   "核查电池工作台页面引用的数字", "确认电池数据的来源与新旧"],
    when_to_use=(
        "当用户要看电池产业链的具体数据本身（如'碳酸锂/正极材料最新报价''电芯多少钱''"
        "这个月动力电池装了多少 GWh''材料价格从哪天开始跌的'），要核查电池工作台页面引用的数字，"
        "或要拉原始序列自己做判断时使用。先不传 series 看目录拿 id。"
    ),
    when_not_to_use=(
        "锂价日线与 8万/12万 档位判定看电池工作台页面（/api/pro/battery/series/lithium，"
        "akshare 现取口径，本工具不覆盖）；汽车需求数据走 query_auto_series；"
        "个股行情与财务三表走通用行情工具；本工具只读数，不做预测与买卖建议。"
    ),
    returns=(
        "目录模式 {mode:'catalog', matched_series:[...]}；"
        "material_price 为快照模式（最新一日报价，n 为品项数）；"
        "cell_price/installation 为逐条模式 {mode:'points', series:目录元信息, points:[原始字段...], "
        "n_points_returned}。未知 series 返回 status=error 并附全部可用 series id。"
    ),
    example="query_battery_series(series='material_price', section='正极材料')  "
            "# 先 query_battery_series(q='电芯') 找 id",
    related_tools=["query_pig_series", "query_insurance_series", "query_auto_series"],
)
def query_battery_series(series: str = "", q: str = "", section: str = "",
                         item: str = "", recent: int = 60,
                         start: str = "", end: str = "") -> str:
    """电池产业链原始序列目录/数据点。series 空=目录；material_price=最新一日快照；
    cell_price/installation=逐条；start/end 按时间键字符串比较（'YYYY-MM-DD'/'YYYY-MM'）。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_battery_series")

    by_id = {r["id"]: r for r in _CATALOG}
    sid = (series or "").strip()
    needle = (q or "").strip().lower()

    if not sid:
        rows = []
        for meta in _CATALOG:
            if needle and needle not in (meta["id"] + " " + meta["label"] + " "
                                         + meta.get("source_desc", "")).lower():
                continue
            rows.append({**meta})
        return _dump({
            "status": "ok", "scope": "pro", "mode": "catalog",
            "count": len(rows), "q": q or None,
            "matched_series": rows,
            **_plain_block("目录里每条序列都有中文名、单位和来源，都是看电池产业链用的原始数据"
                           "（装机量=电池装上车用了多少电，GWh 是电量单位）。"
                           "先用中文名找到想要的序列，再把它的 id 传进来取原始数据。"),
            "note": "material_price 输出最新一日报价快照（日频×多品全历史过大）；"
                    "cell_price/installation 输出逐条数据。",
        })

    if sid not in by_id:
        return _error("query_battery_series", "unknown_series",
                      f"未知序列 id: {sid}（不带 series 再调一次可获取完整目录）",
                      available_series=sorted(by_id))

    meta = by_id[sid]
    try:
        db = backend.store.db_domain('battery')
        if sid == "material_price":
            return _dump(_read_material_snapshot(backend, meta, section, needle))
        if sid == "cell_price":
            pts = _read_cell_price(db, item, needle, start, end, recent)
            mode_payload = {"mode": "points", "points": pts,
                            "n_points_returned": len(pts),
                            "window": {"first": pts[0].get("date") if pts else None,
                                       "last": pts[-1].get("date") if pts else None}}
        elif sid == "installation":
            pts = _read_installation(db)
            staging_pending = backend.store.pending_battery_installation_staging()
            mode_payload = {"mode": "points", "points": pts,
                            "n_points_returned": len(pts),
                            "window": {"first": pts[0].get("period") if pts else None,
                                       "last": pts[-1].get("period") if pts else None},
                            "staging_pending": staging_pending}
        else:  # pragma: no cover - 目录已穷举
            return _error("query_battery_series", "unknown_series", f"未知序列 id: {sid}")
    except Exception as exc:
        logger.warning("电池序列数据取数失败 %s: %s", sid, exc)
        return _error("query_battery_series", "fetch_failed",
                      f"序列 {sid} 数据取数失败: {exc}")

    return _dump({
        "status": "ok", "scope": "pro", "series": meta,
        **mode_payload,
        **_plain_block(_SERIES_PLAIN.get(
            sid, "原始数据点：字段为库内原始口径；来源见 series.source_desc，缺行即源缺数据，不补不插值。")),
        "note": ("points 为库内原始文档投影（字段名与口径原样保留）；"
                 "鑫椤区间价与百川日均价两源禁止混算；"
                 "锂价档位判定（出清带/深亏区分带）属于页面派生读数，本工具只给原料。"),
    })


_SERIES_PLAIN = {
    "material_price": "鑫椤每日给全产业链材料报价，按板块分组（正极/负极/隔膜/电解液/锂电池等）；"
                      "价格单位随行携带，缺报行 price 为 null（缺报也是信息，不是 0）。",
    "cell_price": "百川盈孚每天给各规格电芯的日均价，是中游制造环节供需的直观读数；"
                  "与鑫椤区间价口径不同，两源各自独立，禁止混算。",
    "installation": "装机月报来自动力电池联盟，按月公布；机器解析后必须人工核对才入正式台账，"
                    "staging_pending 里列的是还没核对完的期次，引用时注意区分。",
}


def _read_material_snapshot(backend, meta: dict, section: str, needle: str) -> dict:
    """鑫椤最新一日报价快照（复用 store.latest_battery_material_price_date，同 /materials 接口口径）。"""
    latest = backend.store.latest_battery_material_price_date()
    if not latest:
        return {"status": "ok", "scope": "pro", "mode": "snapshot", "series": meta,
                "date": None, "points": [],
                "plain_note": "库中暂无材料报价（采集任务未跑或源无数据），如实返回空。"}
    db = backend.store.db_domain('battery')
    query = {'date': latest}
    sec = (section or "").strip()
    if sec:
        query['section'] = sec
    docs = list(db.battery_material_price.find(query, {'_id': 0, 'collected_at': 0})
                .sort([('section', 1), ('item', 1), ('spec', 1), ('origin', 1)]))
    if needle:
        docs = [d for d in docs
                if needle in json.dumps(d, ensure_ascii=False).lower()]
    pts = [_clean(d) for d in docs]
    sections = sorted({d.get("section") for d in pts if d.get("section")})
    return {
        "status": "ok", "scope": "pro", "mode": "snapshot", "series": meta,
        "date": latest, "n_items": len(pts),
        "sections": sections, "points": pts,
    }


def _read_cell_price(db, item: str, needle: str,
                     start: str, end: str, recent: int) -> list:
    """百川电芯逐日点位：item/关键词过滤 + date 字典序窗口 + 尾部截取。"""
    query = {}
    it = (item or "").strip()
    if it:
        query['item'] = {'$regex': _escape_regex(it), '$options': 'i'}
    docs = list(db.battery_cell_price.find(query, {'_id': 0, 'collected_at': 0})
                .sort([('date', 1), ('item', 1)]))
    if needle:
        docs = [d for d in docs
                if needle in json.dumps(d, ensure_ascii=False).lower()]
    lo, hi = (start or "").strip(), (end or "").strip()
    if lo or hi:
        docs = [d for d in docs
                if (not lo or str(d.get("date", "")) >= lo)
                and (not hi or str(d.get("date", "")) <= hi)]
    elif recent and recent > 0 and len(docs) > recent:
        docs = docs[-recent:]
    return [_clean(d) for d in docs]


def _read_installation(db) -> list:
    """装机月报正式台账全量（去 _id/_candidates/collected_at，period 升序）。"""
    docs = list(db.installation_monthly.find(
        {}, {'_id': 0, 'collected_at': 0, '_candidates': 0}).sort('period', 1))
    return [_clean(d) for d in docs]


def _escape_regex(s: str) -> str:
    import re
    return re.escape(s)
