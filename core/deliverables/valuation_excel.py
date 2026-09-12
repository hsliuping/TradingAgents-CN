"""估值测算 Excel 交付物（A10-D1）

声明式可选交付物：智能助手层按用户声明调度，固定分析流程零改动。

三层架构中的确定性层：
- render_valuation_excel：模型规格 JSON → .xlsx（真实公式 + 假设输入格）
- validate_valuation_excel：重开文件，校验公式存在性 / 输入一致性 / 计算自洽

规格契约与校验规则对齐 docs/05-design/v4.0/financial-schema-examples/
（output_contract / verifier_rule / applicability_rule），
设计文档见 docs/05-design/v3.0/valuation-excel-deliverable-design.md。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

# ==================== 常量 ====================

SHEET_EARNINGS = "盈利推演"
SHEET_VALUATION = "估值情景"

SUPPORTED_METHODS = ("PE",)  # PB/PEG 需每股净资产/增长率公式，随 v4.0 Schema 落地后开放

# 假设输入格样式（浅黄底，提示可编辑）
_INPUT_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_HEADER_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
_BOLD = Font(bold=True)
_CENTER = Alignment(horizontal="center")

_EPS_TOL = 1e-9


class ValuationSpecError(ValueError):
    """模型规格不合法（阻断渲染）"""


# ==================== 规格校验 ====================

def _forecast_net_profit(spec: dict, period: str) -> Optional[float]:
    """计算某预测期间的净利润（亿元），期间不存在返回 None"""
    prev_rev: Optional[float] = None
    for h in spec["earnings_forecast"]["history"]:
        if h["period"] == period:
            return float(h["net_profit"])
        prev_rev = float(h["revenue"])
    for a in spec["earnings_forecast"]["assumptions"]:
        rev = (prev_rev or 0.0) * (1 + float(a["revenue_growth"]))
        margin = float(a["net_margin"])
        if a["period"] == period:
            return rev * margin
        prev_rev = rev
    return None


def validate_spec(spec: Dict[str, Any]) -> List[str]:
    """校验模型规格，返回错误列表（空列表 = 通过）

    规则对齐 v4.0 verifier_rule：
    - 必填字段（output_contract.required_fields）
    - 方法适用性（applicability_rule：PE 要求正盈利）
    - 假设非平凡（缺失或为零阻断）
    """
    errors: List[str] = []

    def _need(obj: dict, key: str, ctx: str):
        if key not in obj or obj[key] in (None, ""):
            errors.append(f"{ctx}缺少字段 {key}")

    # ---- 顶层必填 ----
    for key in ("ticker", "stock_name", "analysis_date", "share_count",
                "current_price", "earnings_forecast", "valuation"):
        _need(spec, key, "规格")
    if errors:
        return errors

    if float(spec["share_count"]) <= 0:
        errors.append("总股本必须为正数")
    if float(spec["current_price"]) <= 0:
        errors.append("现价必须为正数")

    # ---- 盈利推演 ----
    ef = spec["earnings_forecast"]
    history = ef.get("history") or []
    assumptions = ef.get("assumptions") or []
    if not history:
        errors.append("盈利推演缺少历史数据（history 为空）")
    if not assumptions:
        errors.append("盈利推演缺少预测假设（assumptions 为空）")

    periods = []
    for i, h in enumerate(history):
        ctx = f"历史数据第 {i + 1} 行"
        _need(h, "period", ctx)
        _need(h, "revenue", ctx)
        _need(h, "net_profit", ctx)
        if errors:
            return errors
        periods.append(h["period"])
        if float(h["revenue"]) <= 0:
            errors.append(f"{ctx}营收必须为正数")

    for i, a in enumerate(assumptions):
        ctx = f"预测假设 {a.get('period', f'第 {i + 1} 行')}"
        _need(a, "period", ctx)
        _need(a, "revenue_growth", ctx)
        _need(a, "net_margin", ctx)
        if errors:
            return errors
        periods.append(a["period"])
        growth, margin = float(a["revenue_growth"]), float(a["net_margin"])
        if growth == 0:
            errors.append(f"{ctx}营收增速为零（假设非平凡规则）")
        if margin == 0:
            errors.append(f"{ctx}净利率为零（假设非平凡规则）")
        if margin < 0 or margin > 1:
            errors.append(f"{ctx}净利率应在 (0, 1] 区间，当前 {margin}")
        if growth <= -1:
            errors.append(f"{ctx}营收增速不能 <= -100%")

    if len(set(periods)) != len(periods):
        errors.append("期间存在重复（history 与 assumptions 的 period 必须唯一）")

    # ---- 估值情景 ----
    val = spec["valuation"]
    scenarios = val.get("scenarios") or []
    if not scenarios:
        errors.append("估值情景为空（至少一个情景）")

    for i, s in enumerate(scenarios):
        ctx = f"估值情景「{s.get('name', f'第 {i + 1} 行')}」"
        _need(s, "name", ctx)
        _need(s, "method", ctx)
        _need(s, "multiple", ctx)
        _need(s, "eps_period", ctx)
        _need(s, "benchmark_basis", ctx)
        if errors:
            return errors
        method = str(s["method"]).upper()
        if method not in SUPPORTED_METHODS:
            errors.append(f"{ctx}方法 {method} 不支持（支持 {SUPPORTED_METHODS}）")
        multiple = float(s["multiple"])
        if multiple == 0:
            errors.append(f"{ctx}倍数为零（假设非平凡规则）")
        if multiple < 0:
            errors.append(f"{ctx}倍数必须为正数")
        # 适用性：PE 要求基准期净利润为正（rule.pe_requires_positive_earnings）
        if method == "PE":
            profit = _forecast_net_profit(spec, s["eps_period"])
            if profit is None:
                errors.append(f"{ctx}EPS 基准期间 {s['eps_period']} 不在盈利推演中")
            elif profit <= 0:
                errors.append(
                    f"{ctx}基准期间 {s['eps_period']} 归母净利润为 {profit:.1f} 亿元（非正），"
                    f"不满足 PE 适用条件（正盈利）；亏损场景请换用盈利期为基准，或降低该情景权重"
                )
        elif s["eps_period"] not in periods:
            errors.append(f"{ctx}EPS 基准期间 {s['eps_period']} 不在盈利推演中")

    return errors


# ==================== 渲染 ====================

def _style_header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = _BOLD
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER


def _render_earnings_sheet(ws, spec: dict) -> Dict[str, int]:
    """渲染盈利推演 Sheet，返回 {期间: 行号}"""
    ef = spec["earnings_forecast"]
    ws.title = SHEET_EARNINGS
    ws["A1"] = f"盈利推演 — {spec['stock_name']}（{spec['ticker']}）"
    ws["A1"].font = Font(bold=True, size=13)

    headers = ["期间", "营收（亿元）", "营收增速", "净利率", "归母净利润（亿元）", "假设依据"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=3, column=c, value=h)
    _style_header(ws, 3, len(headers))

    period_row: Dict[str, int] = {}
    r = 4
    for h in ef["history"]:
        ws.cell(row=r, column=1, value=h["period"])
        ws.cell(row=r, column=2, value=float(h["revenue"])).number_format = "#,##0.0"
        # 历史行：增速/净利率同样用公式，保证可审计
        if r == 4:
            ws.cell(row=r, column=3, value="—").alignment = _CENTER
        else:
            ws.cell(row=r, column=3, value=f"=B{r}/B{r - 1}-1").number_format = "0.0%"
        ws.cell(row=r, column=4, value=f"=E{r}/B{r}").number_format = "0.0%"
        ws.cell(row=r, column=5, value=float(h["net_profit"])).number_format = "#,##0.0"
        ws.cell(row=r, column=6, value="实际值（财报口径）")
        period_row[h["period"]] = r
        r += 1

    for a in ef["assumptions"]:
        ws.cell(row=r, column=1, value=a["period"])
        # 预测行：营收 = 上期 × (1 + 增速)，净利润 = 营收 × 净利率（公式格）
        ws.cell(row=r, column=2, value=f"=B{r - 1}*(1+C{r})").number_format = "#,##0.0"
        growth_cell = ws.cell(row=r, column=3, value=float(a["revenue_growth"]))
        growth_cell.number_format = "0.0%"
        growth_cell.fill = _INPUT_FILL
        margin_cell = ws.cell(row=r, column=4, value=float(a["net_margin"]))
        margin_cell.number_format = "0.0%"
        margin_cell.fill = _INPUT_FILL
        ws.cell(row=r, column=5, value=f"=B{r}*D{r}").number_format = "#,##0.0"
        ws.cell(row=r, column=6, value=a.get("rationale", ""))
        period_row[a["period"]] = r
        r += 1

    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 11
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 46
    return period_row


def _render_valuation_sheet(ws, spec: dict, period_row: Dict[str, int]) -> None:
    """渲染估值情景 Sheet（EPS 跨 Sheet 引用盈利推演）"""
    ws.title = SHEET_VALUATION
    ws["A1"] = f"估值情景 — {spec['stock_name']}"
    ws["A1"].font = Font(bold=True, size=13)

    ws["A2"] = "总股本（亿股）"
    ws["A2"].font = _BOLD
    share_cell = ws["B2"]
    share_cell.value = float(spec["share_count"])
    share_cell.number_format = "#,##0.00"
    share_cell.fill = _INPUT_FILL

    ws["A3"] = "现价（元）"
    ws["A3"].font = _BOLD
    ws["B3"] = float(spec["current_price"])
    ws["B3"].number_format = "#,##0.00"

    headers = ["情景", "方法", "倍数", "EPS 基准期间", "EPS（元）", "目标价（元）", "比较基准", "适用性检查"]
    header_row = 5
    for c, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=c, value=h)
    _style_header(ws, header_row, len(headers))

    r = header_row + 1
    for s in spec["valuation"]["scenarios"]:
        src_row = period_row[s["eps_period"]]
        ws.cell(row=r, column=1, value=s["name"])
        ws.cell(row=r, column=2, value=str(s["method"]).upper()).alignment = _CENTER
        multiple_cell = ws.cell(row=r, column=3, value=float(s["multiple"]))
        multiple_cell.number_format = "0.0"
        multiple_cell.fill = _INPUT_FILL
        ws.cell(row=r, column=4, value=s["eps_period"]).alignment = _CENTER
        # EPS = 净利润（盈利推演!E） ÷ 总股本（$B$2）；目标价 = EPS × 倍数
        ws.cell(row=r, column=5, value=f"={SHEET_EARNINGS}!E{src_row}/$B$2").number_format = "#,##0.00"
        ws.cell(row=r, column=6, value=f"=E{r}*C{r}").number_format = "#,##0.00"
        ws.cell(row=r, column=7, value=s.get("benchmark_basis", ""))
        check = s.get("applicability_check") or {}
        if check.get("passed"):
            notes = "、".join(check.get("notes") or [])
            ws.cell(row=r, column=8, value=f"通过{('：' + notes) if notes else ''}")
        else:
            ws.cell(row=r, column=8, value=f"未通过：{check.get('notes') or '见规格'}")
        r += 1

    for col, w in zip("ABCDEFGH", (8, 7, 8, 13, 10, 12, 40, 30)):
        ws.column_dimensions[col].width = w


def render_valuation_excel(spec: Dict[str, Any], output_path: str) -> str:
    """渲染模型规格为 xlsx（先校验规格，非法规格抛 ValuationSpecError）"""
    errors = validate_spec(spec)
    if errors:
        raise ValuationSpecError("规格校验未通过：\n- " + "\n- ".join(errors))

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    period_row = _render_earnings_sheet(wb.active, spec)
    _render_valuation_sheet(wb.create_sheet(), spec, period_row)
    wb.save(path)
    return str(path)


# ==================== 文件校验 ====================

def _is_formula(ws, row: int, col: int) -> bool:
    v = ws.cell(row=row, column=col).value
    return isinstance(v, str) and v.startswith("=")


def validate_valuation_excel(spec: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """重开 xlsx 校验：公式存在性 / 输入一致性 / 计算自洽 / 目标价区间

    Returns:
        {passed, errors: [...], warnings: [...], summary: {...}}
    """
    errors: List[str] = []
    warnings: List[str] = []
    period_row: Dict[str, int] = {}

    wb = load_workbook(output_path)
    if SHEET_EARNINGS not in wb.sheetnames or SHEET_VALUATION not in wb.sheetnames:
        return {"passed": False,
                "errors": [f"缺少工作表（期望 {SHEET_EARNINGS} / {SHEET_VALUATION}，实际 {wb.sheetnames}）"],
                "warnings": [], "summary": {}}
    ws_e, ws_v = wb[SHEET_EARNINGS], wb[SHEET_VALUATION]

    # ---- Sheet1：历史值 + 预测公式 ----
    r = 4
    for h in spec["earnings_forecast"]["history"]:
        if ws_e.cell(row=r, column=1).value != h["period"]:
            errors.append(f"盈利推演第 {r} 行期间与规格不一致")
            break
        if abs(float(ws_e.cell(row=r, column=2).value) - float(h["revenue"])) > _EPS_TOL:
            errors.append(f"盈利推演 {h['period']} 营收输入值与规格不一致")
        if abs(float(ws_e.cell(row=r, column=5).value) - float(h["net_profit"])) > _EPS_TOL:
            errors.append(f"盈利推演 {h['period']} 净利润输入值与规格不一致")
        period_row[h["period"]] = r
        r += 1

    prev_r = r - 1
    for a in spec["earnings_forecast"]["assumptions"]:
        if ws_e.cell(row=r, column=1).value != a["period"]:
            errors.append(f"盈利推演第 {r} 行期间与规格不一致")
            break
        # 公式存在性：营收与净利润必须是公式格
        for col, name in ((2, "营收"), (5, "净利润")):
            if not _is_formula(ws_e, r, col):
                errors.append(f"盈利推演 {a['period']} {name}不是公式格（可能被写成死值）")
        # 公式引用正确性：引用上一期营收与本期假设格
        rev_f = str(ws_e.cell(row=r, column=2).value)
        if f"B{prev_r}" not in rev_f or f"C{r}" not in rev_f:
            errors.append(f"盈利推演 {a['period']} 营收公式引用错误：{rev_f}")
        profit_f = str(ws_e.cell(row=r, column=5).value)
        if f"B{r}" not in profit_f or f"D{r}" not in profit_f:
            errors.append(f"盈利推演 {a['period']} 净利润公式引用错误：{profit_f}")
        # 输入一致性：假设格与规格一致
        if abs(float(ws_e.cell(row=r, column=3).value) - float(a["revenue_growth"])) > _EPS_TOL:
            errors.append(f"盈利推演 {a['period']} 增速输入值与规格不一致")
        if abs(float(ws_e.cell(row=r, column=4).value) - float(a["net_margin"])) > _EPS_TOL:
            errors.append(f"盈利推演 {a['period']} 净利率输入值与规格不一致")
        period_row[a["period"]] = r
        prev_r = r
        r += 1

    # ---- Sheet2：参数 + 情景公式 ----
    if abs(float(ws_v["B2"].value) - float(spec["share_count"])) > _EPS_TOL:
        errors.append("估值情景总股本输入值与规格不一致")
    if abs(float(ws_v["B3"].value) - float(spec["current_price"])) > _EPS_TOL:
        errors.append("估值情景现价输入值与规格不一致")

    # 计算自洽：Python 重算期望 EPS / 目标价（校验公式逻辑对应的数值链）
    expected: Dict[str, Tuple[float, float]] = {}
    r = 6
    for s in spec["valuation"]["scenarios"]:
        if ws_v.cell(row=r, column=1).value != s["name"]:
            errors.append(f"估值情景第 {r} 行名称与规格不一致")
            break
        if not _is_formula(ws_v, r, 5) or not _is_formula(ws_v, r, 6):
            errors.append(f"估值情景「{s['name']}」EPS 或目标价不是公式格")
        eps_f = str(ws_v.cell(row=r, column=5).value)
        src_row = period_row.get(s["eps_period"])
        if src_row is None or f"{SHEET_EARNINGS}!E{src_row}" not in eps_f or "$B$2" not in eps_f:
            errors.append(f"估值情景「{s['name']}」EPS 公式引用错误：{eps_f}")
        price_f = str(ws_v.cell(row=r, column=6).value)
        if f"E{r}" not in price_f or f"C{r}" not in price_f:
            errors.append(f"估值情景「{s['name']}」目标价公式引用错误：{price_f}")
        if abs(float(ws_v.cell(row=r, column=3).value) - float(s["multiple"])) > _EPS_TOL:
            errors.append(f"估值情景「{s['name']}」倍数输入值与规格不一致")
        # 重算
        profit = _forecast_net_profit(spec, s["eps_period"])
        if profit is not None:
            eps = profit / float(spec["share_count"])
            target = eps * float(s["multiple"])
            expected[s["name"]] = (eps, target)
            if target < 0.2 * float(spec["current_price"]) or target > 5 * float(spec["current_price"]):
                warnings.append(
                    f"情景「{s['name']}」目标价 {target:.2f} 元偏离现价 {spec['current_price']} 元 "
                    f"±80% 以上，建议复核假设"
                )
        r += 1

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "scenarios": {k: {"eps": round(v[0], 4), "target_price": round(v[1], 2)}
                          for k, v in expected.items()},
        },
    }


# ==================== 技能入口（module+function 注册用） ====================

def generate_valuation_excel(spec_json: str, output_path: str = "") -> str:
    """技能入口：规格 JSON 字符串 → 生成并校验 xlsx，返回 JSON 结果

    供 Skill 系统 module+function 方式注册调用；
    沙箱/技能调用方解析 stdout JSON 获取文件路径与校验结论。
    """
    import json

    try:
        spec = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
    except Exception as e:
        return json.dumps({"success": False, "stage": "spec_parse", "error": f"规格 JSON 解析失败: {e}"},
                          ensure_ascii=False)

    if not output_path:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(Path("data") / "deliverables" / f"valuation_{spec.get('ticker', 'unknown')}_{ts}.xlsx")

    try:
        path = render_valuation_excel(spec, output_path)
    except ValuationSpecError as e:
        return json.dumps({"success": False, "stage": "spec_validation", "error": str(e)},
                          ensure_ascii=False)

    report = validate_valuation_excel(spec, path)
    report.update({"success": report["passed"], "stage": "file_validation", "path": path})
    return json.dumps(report, ensure_ascii=False)
