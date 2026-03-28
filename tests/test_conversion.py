#!/usr/bin/env python3
"""
文档转换回归测试。

默认只验证本地 pandoc/docx 转换是否可用；PDF 转换会在本机存在可用引擎时才执行。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pypandoc = pytest.importorskip("pypandoc")


def _ensure_pandoc_available() -> None:
    try:
        pypandoc.get_pandoc_version()
    except OSError as exc:
        pytest.skip(f"pandoc 不可用: {exc}")


def _get_pdf_engine() -> str | None:
    for engine in ("wkhtmltopdf", "weasyprint", "xelatex", "pdflatex"):
        if shutil.which(engine):
            return engine
    return None


@pytest.fixture()
def md_content() -> str:
    """生成稳定的 Markdown 样例内容。"""
    return """# 605499 股票分析报告

**生成时间**: 2025-01-12 16:20:00
**分析状态**: 正式分析

## 投资决策摘要

| 指标 | 数值 |
|------|------|
| 投资建议 | BUY |
| 置信度 | 85.0% |
| 风险评分 | 25.0% |
| 目标价位 | ¥275.00 |

### 分析推理
基于技术分析和基本面分析，该股票显示出较强上涨趋势。市场情绪积极，建议买入。

## 分析配置信息

- LLM 提供商: gpt
- LLM 模型: gpt-5.4
- 分析师: market, fundamentals
- 研究深度: 标准分析

## 市场技术分析

### 技术指标分析
- 趋势方向: 上涨
- 支撑位: ¥250.00
- 阻力位: ¥300.00
- RSI 指标: 65

## 基本面分析

### 财务状况
- 营收增长: 15.2%
- 净利润率: 8.5%
- ROE: 12.3%

## 风险提示

1. 市场风险: 整体市场波动可能影响股价
2. 行业风险: 行业政策变化风险
3. 公司风险: 经营管理风险
"""


def test_markdown_content(md_content: str) -> None:
    assert "股票分析报告" in md_content
    assert "投资决策摘要" in md_content
    assert "风险提示" in md_content


def test_word_conversion(md_content: str, tmp_path: Path) -> None:
    _ensure_pandoc_available()

    output_file = tmp_path / "report.docx"
    pypandoc.convert_text(
        md_content,
        "docx",
        format="markdown",
        outputfile=str(output_file),
        extra_args=["--toc", "--number-sections"],
    )

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_pdf_conversion(md_content: str, tmp_path: Path) -> None:
    _ensure_pandoc_available()

    engine = _get_pdf_engine()
    if engine is None:
        pytest.skip("未检测到可用的 PDF 引擎")

    output_file = tmp_path / "report.pdf"
    pypandoc.convert_text(
        md_content,
        "pdf",
        format="markdown",
        outputfile=str(output_file),
        extra_args=[f"--pdf-engine={engine}"],
    )

    assert output_file.exists()
    assert output_file.stat().st_size > 0
