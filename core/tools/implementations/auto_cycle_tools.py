# -*- coding: utf-8 -*-
"""
汽车产业链 Pro —— Agent 工具守卫薄封装（共享工具层中唯一允许出现的汽车产业链入口）。

【铁律 / 不可违反】（与 pig_cycle_tools.py 同款，四行业统一）
1. 只读、只提示、不动手：本文件任何函数都不得下单/调仓，不得替用户做交易决策；
   输出仅为事实与数据状态，供 Agent 生成研究结论参考。
2. 数字唯一来源：所有数值直接复用 app/pro/routers/auto_cycle.py 的取数函数
   （_demand / _brand_sales / _capacity_utilization，含离线库优先读取、缺数回落实时、
   TTL 缓存、口径说明与懂车帝回落识别），本文件只做字段投影/截断与组装，禁止第二套算法；
   产能利用率是路由层自算口径（当月销量×12÷年产能台账），台账只在那一份。
3. 缺数据诚实标注：源失败如实返回 error，绝不伪造、绝不外推填充；
   年产能未核实的公司由路由层标 gap，本层不补数。
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
    "慢变量（需求大盘/渗透率/产能出清）给方向，快变量（月度销量/股价）给时机，"
    "不用快变量论证慢变量。",
    "所有数字为月频离线采集口径（auto_cycle 库，缺数时回落实时取数）：乘联会（狭义乘用车）"
    "与懂车帝（终端零售）来源不同，禁止混算；缺数据处已诚实标注，禁止外推或臆造。",
]

_UNAVAILABLE_MSG = (
    "汽车产业链 Pro 模块在当前版本不可用（app.pro 路由未安装或被裁剪）。"
    "本工具为只读守卫，已自动降级，不影响其他工具；如需该能力请使用 Pro 版本。"
)

# ---------- 大白话输出层 ----------
_ANSWER_STYLE = [
    "先给大白话结论，再给数据依据：像跟不懂汽车行业的朋友解释那样说话。",
    "术语必须翻译后才能出现在给用户的回答里：NEV/渗透率、狭义乘用车、批发/零售、"
    "批零差、产能利用率、子品牌等，一律换成日常说法，或用括号补一句大白话解释。",
    "plain_summary 是现成的大白话解读，可直接引用或改写；jargon_map 是术语对照表。",
    "只转述数据事实与口径说明，不替用户决定买卖。",
]

_JARGON_PLAIN = {
    "NEV/渗透率": "新能源车（电动+插混）卖出的占比；渗透率越高说明电动化转型越快",
    "狭义乘用车": "家用小客车（轿车+SUV+MPV）；乘联会口径，不含卡车客车等商用车，"
             "与中汽协'汽车总产量'不是一回事",
    "产量/零售": "产量=工厂造了多少；零售=卖到用户手上的车（终端销量）；两者差异近似库存变动",
    "批发 vs 零售": "批发=厂商卖给经销商的车（含出口与压库）；零售=终端上险/交付；"
              "出口占比高的公司批发会明显高于零售",
    "批零差": "当月批发−当月零售：正值=在压库或出口，负值=经销商在去库存；"
           "是渠道库存方向的代理指标，不是官方库存系数",
    "产能利用率（自算）": "系统自己估算的：当月销量×12÷年产能，不是官方数；"
                 "零售口径为主（与国内工厂产能可比），批发口径含出口仅作参照",
    "子品牌口径": "懂车帝按子品牌聚合：腾势/方程豹/仰望独立于'比亚迪'、银河独立于'吉利'，"
             "加总不等于集团口径",
    "同比/份额": "同比=跟去年同月比；份额=该品牌销量占全市场的比例",
}

_STYLE_DESC = (
    "【回答措辞（强制）】给用户的回答必须先给大白话结论、再给数据依据；"
    "NEV 渗透率、狭义乘用车、批发/零售、批零差等术语必须翻译成日常语言后才能出现"
    "（输出中的 plain_summary 是现成大白话解读，jargon_map 是术语对照表，answer_style 是措辞纪律）。"
)


def _load_backend():
    """延迟加载汽车路由取数层（含缓存与口径）；社区版 ImportError 时返回 None。"""
    try:
        from app.pro.routers import auto_cycle as _mod
    except ImportError as exc:  # 社区版：app.pro 不存在
        logger.info("汽车产业链 Pro 后端不可用，汽车产业链工具进入降级态: %s", exc)
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
    {"id": "demand",
     "label": "乘用车需求侧月度数据（乘联会：产量/零售/NEV 销量/官方渗透率）",
     "unit": "万辆", "key_field": "period",
     "source_desc": "akshare 乘联会接口月频采集落 auto_cycle.auto_demand_monthly"
                    "（任务 auto_demand，每月 12 日；缺数时端点回落实时取数），series 输出近 36 个月"},
    {"id": "brand_sales",
     "label": "分品牌月度终端零售量（懂车帝，按子品牌聚合，含份额与同比）",
     "unit": "辆", "key_field": "month",
     "source_desc": "懂车帝销量榜月频采集落 auto_cycle.auto_brand_sales_monthly"
                    "（任务 auto_brand_sales，每月 10 日，自算回补窗口 25 个月，覆盖近 12 个月同月同比"
                    "与年初至今累计；窗口外月份回落实时取数；同比月份静默回落已识别，识别到回落则同比置空）；"
                    "month 传 YYYYMM，缺省取最新已发布月"},
    {"id": "capacity",
     "label": "厂商产能利用率（自算口径：当月销量×12÷年产能台账，零售主口径/批发辅口径）",
     "unit": "%", "key_field": "company",
     "source_desc": "乘联会厂商榜（零售/批发 Top10）÷ 人工维护年产能台账，月频采集落 "
                    "auto_cycle.auto_capacity_monthly（任务 auto_capacity，每月 12 日，保留最新一期）；"
                    "年产能未核实的公司标 gap，不填估算"},
]


@register_tool(
    tool_id="query_auto_series",
    name="汽车产业链行业数据（乘联会需求侧/懂车帝分品牌销量/自算产能利用率）",
    description=(
        "只读查询汽车产业链 Pro 的行业面数据，是汽车工作台一切读数的唯一统一入口"
        "（月频离线采集落 auto_cycle 库，缺数时回落实时取数），"
        "可用来独立核查页面引用的数字。data=demand 乘联会狭义乘用车月度"
        "产量/零售/NEV 销量/官方渗透率（近 36 个月）；data=brand_sales 懂车帝月度"
        "终端零售量按子品牌聚合（腾势/方程豹/仰望独立计数），含份额与同比，"
        "month 传 YYYYMM（缺省最新已发布月），输出 Top20 品牌；"
        "data=capacity 自算产能利用率（当月销量×12÷年产能，零售主口径），"
        "年产能未核实的公司如实标 gap。" + _STYLE_DESC
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    data_source_handling="self_contained",
    capability_tags=["auto_cycle", "auto_demand", "auto_brand_sales",
                     "auto_capacity", "read_only"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查乘用车需求大盘/NEV 渗透率", "查分品牌月度销量与同比",
                   "查厂商产能利用率与批零差"],
    when_to_use=(
        "当用户要看汽车行业的具体数据本身（如'这个月乘用车卖了多少''新能源渗透率到多少了'"
        "'各家品牌销量排名''谁家产能利用得最满''批零差说明在压库还是去库'），"
        "要核查汽车工作台页面引用的数字，或要拉行业序列自己做判断时使用。"
        "先不传 data 看目录拿 id。"
    ),
    when_not_to_use=(
        "单个品牌旗下车型明细走 get_auto_brand_monthly_sales（懂车帝车型榜，本工具是"
        "子品牌聚合口径）；个股行情与财务三表走通用行情工具；本工具为狭义乘用车口径，"
        "不覆盖商用车；只读数，不做预测与买卖建议。"
    ),
    returns=(
        "目录模式 {mode:'catalog', data_kinds:[...]}；"
        "demand 返回 {latest, series[近36月], sources, note}；"
        "brand_sales 返回 {month, months, total, brands[Top20], hidden_brands, "
        "yoy_available, note}；capacity 返回 {month_label, rows, summary, "
        "gap_companies, note}。取数失败返回 status=error 并附源侧错误信息。"
    ),
    example="query_auto_series(data='brand_sales', month=202609)  "
            "# 先 query_auto_series() 看目录",
    related_tools=["get_auto_brand_monthly_sales", "query_pig_series",
                   "query_insurance_series", "query_battery_series"],
)
def query_auto_series(data: str = "", month: int = 0) -> str:
    """汽车行业面数据目录/读数。data 空=目录；demand/brand_sales/capacity=读数
    （复用 app/pro/routers/auto_cycle 取数函数：离线库优先、缺数回落实时，本层不重算）。"""
    backend = _load_backend()
    if backend is None:
        return _unavailable("query_auto_series")

    kind = (data or "").strip().lower()
    if not kind:
        return _dump({
            "status": "ok", "scope": "pro", "mode": "catalog",
            "count": len(_DATA_CATALOG),
            "data_kinds": [dict(m) for m in _DATA_CATALOG],
            **_plain_block("目录里每种数据都有中文名和来源：需求大盘（乘联会）、"
                           "分品牌销量（懂车帝）、产能利用率（系统自算）。"
                           "先用中文名找到想要的，再把它的 id 传进 data 取数。"),
            "note": "demand/brand_sales/capacity 均为月频离线采集读数（库内未覆盖应已发布月时"
                    "回落实时取数）；懂车帝车型明细另有 get_auto_brand_monthly_sales 工具。",
        })
    if kind not in {m["id"] for m in _DATA_CATALOG}:
        return _error("query_auto_series", "unknown_data_kind",
                      f"未知数据种类: {kind}（不带 data 再调一次可获取完整目录）",
                      available_kinds=sorted(m["id"] for m in _DATA_CATALOG))

    try:
        if kind == "demand":
            payload, err = backend.mod._demand()
            summary = ("这是乘联会发布的乘用车市场月度数据：产量、零售量、新能源销量和官方渗透率，"
                       "用来看整车需求大盘是热是冷、电动化跑到哪一步了。")
        elif kind == "brand_sales":
            payload, err = backend.mod._brand_sales(int(month) if month else None)
            summary = ("这是懂车帝的月度终端销量榜，按子品牌聚合（腾势、方程豹、仰望单独计数，"
                       "加总不等于比亚迪集团），带份额和同比，用来看各家卖得好不好、谁在掉队。")
        else:
            payload, err = backend.mod._capacity_utilization()
            summary = ("这是系统自算的产能利用率：当月销量×12÷年产能，看各家工厂是满负荷还是闲置；"
                       "年产能没核实到的公司如实标 gap 不填估算，批零差可看渠道是在压库还是去库。")
    except Exception as e:  # 路由层兜底之外的意外异常，如实报错不造数
        logger.warning("汽车行业数据 %s 取数异常: %s", kind, e)
        return _error("query_auto_series", "fetch_failed",
                      f"取数异常: {e}", data_kind=kind)

    if not payload:
        return _error("query_auto_series", "fetch_failed",
                      err or "数据源暂不可用（源侧无响应或返回空），已如实返回，未造数",
                      data_kind=kind)

    if kind == "brand_sales" and isinstance(payload.get("brands"), list):
        top = 20
        payload = {**payload,
                   "brands": payload["brands"][:top],
                   "hidden_brands": max(0, payload.get("brand_count", 0) - top)}

    return _dump({
        "status": "ok", "scope": "pro", "tool": "query_auto_series",
        "data_kind": kind,
        **payload,
        **_plain_block(summary),
        "discipline": _DISCIPLINE,
    })
