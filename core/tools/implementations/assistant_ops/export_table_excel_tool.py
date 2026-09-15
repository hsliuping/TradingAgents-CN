# -*- coding: utf-8 -*-
"""通用表格 Excel 导出工具。

背景：Excel 生成能力曾被绑死在估值工具（generate_valuation_excel_tool）里，
那是一条「数据装配 → LLM 生成规格（最多3次尝试）→ 渲染」的重型管线
（heavy 层级 180 秒，实测 2-6 分钟）。用户把对话中已经算好的模型
（销量/营收预测等）导出 Excel 时被错误路由到估值工具，重新生成模型
导致 420 秒超时。

本工具与估值工具的分工：
- 本工具：**确定性导出**——LLM 把对话中已产生的 Markdown 表格原样透传，
  纯 openpyxl 渲染，零 LLM 调用，秒级完成。任何「把刚才的数据/表格
  做成 Excel」的需求都应走这里。
- 估值工具：从本地年报数据**自建**估值模型（盈利推演公式 + PE 情景），
  仅当用户明确要求"估值测算表/估值模型"时使用。

参数设计（Markdown 透传而非结构化 JSON）：
LLM 上下文里已有现成的 Markdown 表格（回复里展示过的），直接贴原文即可。
结构化 JSON 参数（sheets/columns/rows 嵌套）反而给 LLM 提供了臆造/改写
数字的机会——透传原文是对"数据不可篡改"铁律的遵守。
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Optional, Tuple

from langchain_core.tools import tool
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

_OUTPUT_DIR = "data/deliverables"

# Markdown 表格分隔行（|---|---:| 等）
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
# 单元格文本 → 数值
_INT_RE = re.compile(r"^[+-]?\d+$")
_THOUSANDS_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
_NUMBER_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_PERCENT_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*%$")


def _parse_cell(text: str) -> Tuple[object, Optional[str]]:
    """单元格文本 → (值, 数字格式)。无法解析为数值时返回 (原文本, None)。"""
    s = (text or "").strip()
    if not s:
        return "", None
    # 千分位数字：1,234 / 12,345.67
    if _THOUSANDS_RE.match(s):
        return float(s.replace(",", "")), "#,##0.##"
    if _INT_RE.match(s):
        return int(s), "#,##0"
    m = _PERCENT_RE.match(s)
    if m:
        return float(m.group(1)) / 100.0, "0.00%"
    if _NUMBER_RE.match(s):
        return float(s), "0.##"
    return s, None


def _split_row(line: str) -> List[str]:
    """Markdown 表格行 → 单元格列表（容忍首尾竖线的任意变体）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_table_row(line: str) -> bool:
    return "|" in line and not _TABLE_SEP_RE.match(line)


def _parse_markdown_tables(
    markdown: str,
) -> List[Tuple[str, List[List[str]]]]:
    """解析 Markdown 文本 → [(sheet名, 表格行列表), ...]。

    多个 sheet 用 `## 标题` 分隔；无标题时全部进单个 sheet。
    每段允许多张连续表格（自动首尾拼接为一张，列数以表头为准）。
    """
    # 按 ## 标题分段
    segments: List[Tuple[str, List[str]]] = []
    current_title = ""
    current_lines: List[str] = []
    for line in (markdown or "").splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            if any(_is_table_row(l) for l in current_lines):
                segments.append((current_title, list(current_lines)))
            current_title = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if any(_is_table_row(l) for l in current_lines):
        segments.append((current_title, list(current_lines)))

    if not segments:
        return []

    result: List[Tuple[str, List[List[str]]]] = []
    for title, lines in segments:
        rows: List[List[str]] = []
        for line in lines:
            if _is_table_row(line):
                rows.append(_split_row(line))
        if rows:
            result.append((title or f"表格{len(result) + 1}", rows))
    return result


def _display_width(text: str) -> float:
    """估算显示宽度：中文/全角字符按 2 计。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(text))


def _sanitize_sheet_name(name: str, used: set) -> str:
    """清洗 sheet 名（Excel 限制：≤31 字符、禁用 :\\/?*[]）。"""
    clean = re.sub(r"[:\\/?*\[\]]", "_", (name or "").strip())[:31] or "Sheet"
    base, i = clean, 2
    while clean in used:
        suffix = f"_{i}"
        clean = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(clean)
    return clean


def _sanitize_filename_part(title: str) -> str:
    """标题 → 文件名安全片段（保留中文，剔除非法字符）。

    半角括号 () 必须换成全角：markdown 链接目标中的未转义半角括号
    会按 CommonMark 规则截断 URL，导致下载链接不完整。
    """
    slug = re.sub(r"[\\/:*?\"<>|\s]+", "_", (title or "").strip())
    slug = slug.replace("(", "（").replace(")", "）")
    slug = re.sub(r"_{2,}", "_", slug).strip("_")
    return slug[:40] or "table"


@tool
@register_tool(
    tool_id="export_table_excel_tool",
    name="表格Excel导出",
    description=(
        "把对话中已经产生的数据表格（Markdown 表格原文）导出为 Excel 文件（xlsx），"
        "支持多个表格分 Sheet。纯确定性渲染，不重新生成或修改任何数据，秒级完成。"
        "凡是要导出的数字已经在对话里出现过（预测结果、测算表、对比表等），"
        "无论用户说'做成Excel''生成数据表''做成模型表格'还是'导出'，都应调用本工具，"
        "严禁为此重新建模或改走其他建模工具。"
    ),
    category="utility",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "excel_export", "table_export", "deliverable_generation",
        "markdown_to_excel", "data_export",
    ],
    tool_role_hint="specialized",
    output_shape="structured_markdown",
    when_to_use=(
        "要导出的数据/表格/预测结果已经在当前对话中生成过（LLM 回复里出现过 Markdown 表格），"
        "用户现在要求把它们做成 Excel/数据表文件时调用——把表格原文逐字透传即可，"
        "多张表用 '## 表名' 分隔。用户的说法可能是'做成模型''生成数据表''导出'等，"
        "只要数据来自对话上下文而非需要重新计算，就用本工具。"
    ),
    when_not_to_use=(
        "用户明确要求'估值测算表/估值模型/盈利推演/PE 情景'（需要公式联动的"
        "财务模型）时不要调用，使用 generate_valuation_excel_tool。"
    ),
    returns=(
        "Markdown 文本：导出结果、各 Sheet 行列数摘要、文件下载链接；"
        "无可解析表格时返回明确的失败说明。"
    ),
    example=(
        "export_table_excel_tool(title='赛力斯营收预测', "
        "markdown_tables='## 月度销量预测\\n| 月份 | M9 | M7 |\\n|---|---:|---:|\\n| 2026-09 | 10500 | 8000 |')"
    ),
    related_tools=["generate_valuation_excel_tool"],
)
def export_table_excel_tool(
    title: Annotated[str, "表格主题（用于文件名与文档标题），如'赛力斯营收预测'"],
    markdown_tables: Annotated[
        str,
        "Markdown 表格原文（直接透传对话中已生成的表格，逐字复制，严禁改写任何数字）。"
        "多个表格用 '## 表名' 标题行分隔，每个标题成为 Excel 的一个 Sheet。",
    ],
    notes: Annotated[str, "可选：附加说明（数据来源、口径、假设等），写入表格底部"] = "",
) -> str:
    """把对话中的 Markdown 表格导出为 Excel 文件。

    Args:
        title: 表格主题（文件名）
        markdown_tables: Markdown 表格原文，多 sheet 用 ## 标题分隔
        notes: 可选脚注

    Returns:
        Markdown 文本（结果摘要 + 下载链接，或失败说明）
    """
    t0 = time.time()
    try:
        parsed = _parse_markdown_tables(markdown_tables or "")
        if not parsed:
            return (
                "### 表格导出失败\n\n"
                "未在传入内容中解析到 Markdown 表格（需含 `|` 分隔的表头行与数据行）。\n\n"
                "*请确认要导出的表格内容后重试。*"
            )

        wb = Workbook()
        wb.remove(wb.active)

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="4472C4")
        header_align = Alignment(horizontal="center", vertical="center")
        used_names: set = set()
        sheet_summaries: List[str] = []

        for sheet_title, rows in parsed:
            ws = wb.create_sheet(title=_sanitize_sheet_name(sheet_title, used_names))
            # 表头 = 第一行（紧随其后的分隔行已在解析时跳过）
            header = rows[0]
            data_rows = rows[1:]
            # 过滤空行
            data_rows = [r for r in data_rows if any(c for c in r)]

            for col_idx, cell_text in enumerate(header, start=1):
                cell = ws.cell(row=1, column=col_idx, value=cell_text)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align

            col_widths = [_display_width(h) + 4 for h in header]

            for row_idx, row in enumerate(data_rows, start=2):
                for col_idx in range(len(header)):
                    text = row[col_idx] if col_idx < len(row) else ""
                    value, num_fmt = _parse_cell(text)
                    cell = ws.cell(row=row_idx, column=col_idx + 1, value=value)
                    if num_fmt:
                        cell.number_format = num_fmt
                        cell.alignment = Alignment(horizontal="right")
                    if col_idx < len(row):
                        w = _display_width(text) + 2
                        if w > col_widths[col_idx]:
                            col_widths[col_idx] = w

            for col_idx, width in enumerate(col_widths, start=1):
                ws.column_dimensions[get_column_letter(col_idx)].width = min(width, 50)

            # 脚注：notes + AI 生成声明（合规要求）
            foot_row = len(data_rows) + 3
            footnotes = []
            if notes:
                footnotes.append(f"说明：{notes}")
            footnotes.append("本表格由 AI 生成，仅作研究参考，不构成投资建议。")
            for i, note in enumerate(footnotes):
                c = ws.cell(row=foot_row + i, column=1, value=note)
                c.font = Font(size=9, color="808080")

            ws.freeze_panes = "A2"
            sheet_summaries.append(f"- **{sheet_title}**：{len(header)} 列 × {len(data_rows)} 行")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"table_{_sanitize_filename_part(title)}_{stamp}.xlsx"
        output_dir = Path(_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        wb.save(str(output_path))

        # 签名下载链接：浏览器直接点击不带 JWT 头，必须用 presigned URL 鉴权
        from urllib.parse import quote

        from core.deliverables.download_links import sign_deliverable_query

        download_url = (
            f"/api/assistant/deliverables/{quote(filename)}"
            f"?{sign_deliverable_query(filename)}"
        )

        elapsed = time.time() - t0
        return (
            f"### Excel 表格已导出 ✅\n\n"
            f"**{title}** · {len(parsed)} 个 Sheet · 生成耗时 {elapsed:.1f} 秒\n\n"
            + "\n".join(sheet_summaries)
            + f"\n\n"
            f"📎 [下载 Excel 表格]({download_url})\n\n"
            f"表格数据逐字来自对话中已生成的模型结果，未做任何修改。"
            f"{'说明：' + notes if notes else ''}\n\n"
            f"*本表格由 AI 生成，仅作研究参考，不构成投资建议。*"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[ExportTableExcelTool] 导出失败: %s", exc, exc_info=True)
        return f"### 表格导出失败\n\n**执行异常**：{exc}\n\n*请重试或简化表格内容。*"
