# -*- coding: utf-8 -*-
"""
银行业 Pro —— Agent 工具守卫薄封装（共享工具层中唯一允许出现的银行业入口）。

【铁律 / 不可违反】（与 pig/insurance/battery/auto_cycle_tools.py 同款，五行业统一）
1. 只读、只提示、不动手：本文件任何函数都不得下单/调仓，不得替用户做交易决策；
   输出仅为事实与数据状态，供 Agent 生成研究结论参考。
2. 数字唯一来源：所有数值直接复用 app/pro/routers/bank_cycle.py 的取数函数
   （_overview / _rates / _macro，含离线库优先读取、缺数回落实时、TTL 缓存、
   口径说明与 gap 标注），本文件只做字段投影/截断与组装，禁止第二套算法；
   中位数/区间由路由层现算，本层不重算。
3. 缺数据诚实标注：源失败如实返回 error，绝不伪造、绝不外推填充；
   季报 NIM/核心一级 CAR 制度性不披露的银行由路由层如实留空，本层不补数。
4. import 纪律：对 app.pro 的 import 必须【延迟到函数体内】并用
   try/except ImportError 接住，返回结构化 unavailable 结果；严禁模块顶层 import
   —— 否则 ToolLoader 扫描本文件会整模块失败，污染所有工具注册。
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
    "慢变量（净息差趋势/资产质量/资本充足）给方向，快变量（利率锚/股价）给时机，"
    "不用快变量论证慢变量。",
    "所有数字为离线采集口径（bank_cycle 库，缺数时回落实时取数）：央行货政报告"
    "（官方加权利率）与东财财报指标（上市行横截面）来源不同，禁止混算；"
    "缺数据处已诚实标注，禁止外推或臆造。",
]

_UNAVAILABLE_MSG = (
    "银行业 Pro 模块在当前版本不可用（app.pro 路由未安装或被裁剪）。"
    "本工具为只读守卫，已自动降级，不影响其他工具；如需该能力请使用 Pro 版本。"
)

# ---------- 大白话输出层 ----------
_ANSWER_STYLE = [
    "先给大白话结论，再给数据依据：像跟不懂银行业的朋友解释那样说话。",
    "术语必须翻译后才能出现在给用户的回答里：净息差(NIM)、不良率、拨备覆盖率、"
    "核心一级资本充足率、LPR、10Y 国债收益率、报告期等，一律换成日常说法，"
    "或用括号补一句大白话解释。",
    "plain_summary 是现成的大白话解读，可直接引用或改写；jargon_map 是术语对照表。",
    "只转述数据事实与口径说明，不替用户决定买卖。",
]

_JARGON_PLAIN = {
    "净息差（NIM）": "银行拿存款放贷款赚的利差，用生息资产平均余额摊出来的百分比；"
                 "息差越低说明靠吃利差赚钱越来越难，是银行最核心的赚钱能力指标",
    "不良率": "贷款里已经还不上的那部分占比；越高说明资产质量越差",
    "拨备覆盖率": "银行为坏账预先计提的准备金是坏账的几倍；越高越安全（监管一般要求 ≥150%）",
    "核心一级资本充足率": "银行自己最硬的自有资本占风险资产的比例，是抗风险底线"
                    "（监管要求约 7.5%+缓冲）；越高越能扛亏损和扩表",
    "报告期（period）": "数据对应的报表截止日，如 2026-09-30 是三季报；季报口径，非实时值",
    "中位数/区间": "把 42 家银行按指标从小到大排队，取中间那家（中位）和最差最好两家（区间）；"
              "看行业整体水平比看平均数更抗极端值干扰",
    "存款利率/贷款利率（新发放）": "央行货政报告表 4 披露的当月新发放贷款加权平均利率，"
                          "是官方口径的『银行放贷收多少利息』；季频发布且滞后约两个月",
    "LPR（贷款市场报价利率）": "每月 20 日公布的贷款定价基准利率（1年期/5年期），"
                        "房贷和企业贷款都参考它；降 LPR = 贷款端收益被压",
    "10Y 国债收益率": "市场给国家借 10 年钱的利率，是全社会无风险利率的锚；"
                  "银行持有的债券估值、保险再投资收益率都跟着它走",
    "中证银行指数（399986）": "42 家上市银行股价打包成的指数，看板块整体涨跌用",
    "季频/月频/日频": "分别指季度、每月、每个交易日更新一次，不是实时数据",
}

_STYLE_DESC = (
    "【回答措辞（强制）】给用户的回答必须先给大白话结论、再给数据依据；"
    "净息差、不良率、拨备覆盖率、核心一级资本充足率、LPR 等术语必须翻译成日常语言后才能出现"
    "（输出中的 plain_summary 是现成大白话解读，jargon_map 是术语对照表，answer_style 是措辞纪律）。"
)


def _load_backend():
    """延迟加载银行路由取数层（含缓存与口径）；社区版 ImportError 时返回 None。"""
    try:
        from app.pro.routers import bank_cycle as _mod
    except ImportError as exc:  # 社区版：app.pro 不存在
        logger.info("银行业 Pro 后端不可用，银行业工具进入降级态: %s", exc)
        return None
    return types.SimpleNamespace(mod=_mod)


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


def _plain_block(summary: str) -> dict:
    return {
        "plain_summary": summary,
        "answer_style": _ANSWER_STYLE,
        "jargon_map": _JARGON_PLAIN,
    }


# ---------- 数据种类目录（人工登记；派生计算一律不做，只转发路由层现成读数） ----------
_DATA_CATALOG = [
    {"id": "em_metrics",
     "label": "上市银行横截面四字段（东财财报指标：净息差/不良率/拨备覆盖率/核心一级 CAR，含中位与区间）",
     "unit": "%", "key_field": "period",
     "source_desc": "akshare 东财财报指标按报告期逐家采集落 bank_cycle.bank_em_metrics"
                    "（任务 bank_em_metrics，每月 5 日全量刷新；覆盖 42 家 A 股上市银行）；"
                    "period 传 YYYY-MM-DD，缺省取四字段覆盖最全的最近一期；"
                    "季报净息差/核心一级 CAR 部分银行不披露，空值如实留空"},
    {"id": "pbc_rates",
     "label": "央行新发放贷款利率（货政报告表 4，官方加权口径，季频 5 个利率键）",
     "unit": "%", "key_field": "month",
     "source_desc": "央行货币政策执行报告表 4 PDF 解析，落 bank_cycle.bank_pbc_rates"
                    "（任务 bank_pbc_rates，每月 20 日扫描；季频、报告滞后约 2 个月，"
                    "无新期次时幂等覆盖旧值），series 输出近 12 期"},
    {"id": "macro",
     "label": "利率锚（中债 10Y 国债收益率 + 中证银行 399986 收盘，日频）与 LPR 1Y/5Y（月度）",
     "unit": "% / 点", "key_field": "date",
     "source_desc": "日频采集落 bank_cycle.bank_macro_daily（任务 bank_macro_daily，每日 19:55），"
                    "LPR 落 bank_lpr_monthly（同任务，每月 20 日报价日更新）；"
                    "日频输出近 260 个交易日，LPR 输出近 24 期；两源分字段 upsert，"
                    "单源缺当日值不会覆盖另一源"},
]


@register_tool(
    tool_id="query_bank_series",
    name="银行业行业数据（上市银行四字段横截面/央行新发放贷款利率/利率锚与 LPR）",
    description=(
        "只读查询银行业 Pro 的行业面数据，是银行工作台一切读数的唯一统一入口"
        "（离线采集落 bank_cycle 库，缺数时回落实时取数），"
        "可用来独立核查页面引用的数字。data=em_metrics 42 家上市银行单报告期"
        "净息差/不良率/拨备覆盖率/核心一级 CAR 横截面含中位与区间"
        "（period 传 YYYY-MM-DD，缺省覆盖最全的最近一期）；"
        "data=pbc_rates 央行货政报告表 4 新发放贷款利率官方加权口径（季频 5 个利率键，"
        "输出近 12 期）；data=macro 10Y 国债收益率 + 中证银行指数日频（近 260 个交易日）"
        "与 LPR 1Y/5Y 月度（近 24 期）。" + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    data_source_handling="self_contained",
    capability_tags=["bank_cycle", "bank_em_metrics", "bank_pbc_rates",
                     "bank_macro_daily", "bank_lpr", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查上市银行净息差/不良率/拨备覆盖率横向对比",
                   "查央行新发放贷款利率官方口径",
                   "查 10Y 国债收益率/LPR/银行指数"],
    when_to_use=(
        "当用户要看银行业的具体数据本身（如'这个季度银行净息差多少''哪家不良率最高'"
        "'央行新发放贷款利率降到多少了''LPR 最近降了没''10Y 国债收益率现在多少'），"
        "要核查银行工作台页面引用的数字，或要拉行业序列自己做判断时使用。"
        "先不传 data 看目录拿 id。"
    ),
    when_not_to_use=(
        "单家银行个股行情/财务三表/估值走通用行情与财报工具（本工具是 42 家横截面口径，"
        "只出行业层面读数）；银行股持仓复盘走持仓分析工具；"
        "本工具不覆盖信贷投放社融总量等央行其他表，只读数据，不做预测与买卖建议。"
    ),
    returns=(
        "目录模式 {mode:'catalog', data_kinds:[...]}；"
        "em_metrics 返回 {period, period_name, rows[42], summary{四字段 中位/区间/家数}, "
        "coverage, gap_note, note}；pbc_rates 返回 {latest, series[近12期], sources, note}；"
        "macro 返回 {latest, series[近260交易日], lpr{latest, series}, sources, note}。"
        "取数失败返回 status=error 并附源侧错误信息。"
    ),
    example="query_bank_series(data='em_metrics', period='2026-09-30')  "
            "# 先 query_bank_series() 看目录",
    related_tools=["query_pig_series", "query_insurance_series",
                   "query_battery_series", "query_auto_series"],
)
def query_bank_series(data: str = "", period: str = "") -> str:
    """银行业行业面数据目录/读数。data 空=目录；em_metrics/pbc_rates/macro=读数
    （复用 app/pro/routers/bank_cycle 取数函数：离线库优先、缺数回落实时，本层不重算）。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_bank_series")

    kind = (data or "").strip().lower()
    if not kind:
        return _dump({
            "status": "ok", "scope": "pro", "mode": "catalog",
            "count": len(_DATA_CATALOG),
            "data_kinds": [dict(m) for m in _DATA_CATALOG],
            **_plain_block("目录里每种数据都有中文名和来源：42 家上市银行的四个关键指标"
                           "（净息差、不良率、拨备覆盖率、核心一级资本充足率）、"
                           "央行公布的新发放贷款利率、以及 10 年期国债收益率和 LPR 这些利率锚。"
                           "先用中文名找到想要的，再把它的 id 传进 data 取数。"),
            "note": "em_metrics 为季报口径横截面（库内最新报告期）；pbc_rates 季频滞后约两个月；"
                    "macro 为日频。三者来源不同，禁止混算。",
        })
    if kind not in {m["id"] for m in _DATA_CATALOG}:
        return _error("query_bank_series", "unknown_data_kind",
                      f"未知数据种类: {kind}（不带 data 再调一次可获取完整目录）",
                      available_kinds=sorted(m["id"] for m in _DATA_CATALOG))

    try:
        if kind == "em_metrics":
            payload = backend.mod._overview(period or None)
            summary = ("这是同一报告期 42 家 A 股上市银行的横向对比：净息差（吃利差的能力）、"
                       "不良率（贷款还不上占比）、拨备覆盖率（坏账准备金厚不厚）、"
                       "核心一级资本充足率（自有资本底线），并给出中位和最差最好值，"
                       "用来看银行业整体日子好不好过、谁在掉队。")
        elif kind == "pbc_rates":
            payload, err = backend.mod._rates()
            summary = ("这是央行货币政策执行报告里公布的『新发放贷款加权平均利率』，"
                       "属于官方口径，看银行放贷到底收多少利息、贷款端收益被压到什么程度；"
                       "一个季度才更新一次，而且报告要滞后两个月左右。")
            if not payload:
                return _error("query_bank_series", "fetch_failed",
                              err or "数据源暂不可用（源侧无响应或返回空），已如实返回，未造数",
                              data_kind=kind)
            if isinstance(payload.get("series"), list):
                payload = {**payload, "series": payload["series"][-12:]}
        else:
            payload, err = backend.mod._macro()
            summary = ("这是利率锚：10 年期国债收益率（全社会无风险利率的锚，银行债券估值和"
                       "保险再投资都跟它走）、中证银行指数（板块整体涨跌）、以及 LPR 贷款基准利率；"
                       "用来看资金价格大环境在往哪个方向走。")
            if not payload:
                return _error("query_bank_series", "fetch_failed",
                              err or "数据源暂不可用（源侧无响应或返回空），已如实返回，未造数",
                              data_kind=kind)
            lpr = payload.get("lpr") or {}
            if isinstance(lpr.get("series"), list):
                payload = {**payload,
                           "lpr": {**lpr, "series": lpr["series"][-24:]}}
    except Exception as e:  # 路由层兜底之外的意外异常，如实报错不造数
        logger.warning("银行业数据 %s 取数异常: %s", kind, e)
        return _error("query_bank_series", "fetch_failed",
                      f"取数异常: {e}", data_kind=kind)

    if not payload:
        return _error("query_bank_series", "fetch_failed",
                      "数据源暂不可用（返回空），已如实返回，未造数", data_kind=kind)

    return _dump({
        "status": "ok", "scope": "pro", "tool": "query_bank_series",
        "data_kind": kind,
        **payload,
        **_plain_block(summary),
        "discipline": _DISCIPLINE,
    })
