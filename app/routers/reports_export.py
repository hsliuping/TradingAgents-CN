"""
研究报告导出 API 路由（Pro 专属）

v3.6.0 社区版开源分离（M1 收敛改造）：
- 本文件为付费功能（export_reports）的代码载体，社区版发布时整体剔除
- 社区版的报告查看/列表/详情/删除在 reports.py（社区版保留）
- 见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §5.2
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .auth_db import get_current_user
from ..core.permissions import require_feature
from ..core.database import get_mongo_db
from .reports import _build_report_query

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    format: str = Query("markdown", description="下载格式: markdown, json, pdf, docx"),
    user: dict = Depends(get_current_user),
    _license=Depends(require_feature("export_reports"))
):
    """下载报告

    支持的格式:
    - markdown: Markdown 格式（默认）
    - json: JSON 格式（包含完整数据）
    - docx: Word 文档格式（需要 pandoc）
    - pdf: PDF 格式（需要 WeasyPrint 或 pdfkit，不再需要 pandoc）
    """
    try:
        logger.info(f"📥 下载报告: {report_id}, 格式: {format}")

        db = get_mongo_db()

        # 查询报告（支持多种ID）
        query = _build_report_query(report_id)
        doc = await db.analysis_reports.find_one(query)

        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        stock_symbol = doc.get("stock_symbol", "unknown")
        analysis_date = doc.get("analysis_date", datetime.now().strftime("%Y-%m-%d"))

        if format == "json":
            # JSON格式下载
            content = json.dumps(doc, ensure_ascii=False, indent=2, default=str)
            filename = f"{stock_symbol}_{analysis_date}_report.json"
            media_type = "application/json"

            # 返回文件流
            def generate():
                yield content.encode('utf-8')

            return StreamingResponse(
                generate(),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        elif format == "markdown":
            # Markdown格式下载
            from app.utils.report_exporter import report_exporter

            content = report_exporter.generate_markdown_report(doc)
            filename = f"{stock_symbol}_{analysis_date}_report.md"
            media_type = "text/markdown"

            # 返回文件流
            def generate():
                yield content.encode('utf-8')

            return StreamingResponse(
                generate(),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        elif format == "docx":
            # Word 文档格式下载
            from app.utils.report_exporter import report_exporter

            if not report_exporter.pandoc_available:
                raise HTTPException(
                    status_code=400,
                    detail="Word 导出功能不可用。请安装 pandoc: pip install pypandoc"
                )

            try:
                # 生成 Word 文档
                docx_content = report_exporter.generate_docx_report(doc)
                filename = f"{stock_symbol}_{analysis_date}_report.docx"

                # 返回文件流
                def generate():
                    yield docx_content

                return StreamingResponse(
                    generate(),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except Exception as e:
                logger.error(f"❌ Word 文档生成失败: {e}")
                raise HTTPException(status_code=500, detail=f"Word 文档生成失败: {str(e)}")

        elif format == "pdf":
            # PDF 格式下载（不再需要 pandoc，使用 WeasyPrint 或 pdfkit）
            from app.utils.report_exporter import report_exporter

            if not report_exporter.weasyprint_available and not report_exporter.pdfkit_available:
                raise HTTPException(
                    status_code=400,
                    detail="PDF 导出功能不可用。请安装 PDF 引擎：pip install weasyprint（推荐）或安装 pdfkit + wkhtmltopdf"
                )

            try:
                # 生成 PDF 文档
                pdf_content = report_exporter.generate_pdf_report(doc)
                filename = f"{stock_symbol}_{analysis_date}_report.pdf"

                # 返回文件流
                def generate():
                    yield pdf_content

                return StreamingResponse(
                    generate(),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except Exception as e:
                logger.error(f"❌ PDF 文档生成失败: {e}")
                raise HTTPException(status_code=500, detail=f"PDF 文档生成失败: {str(e)}")

        else:
            raise HTTPException(status_code=400, detail=f"不支持的下载格式: {format}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 下载报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
