"""
报告导出工具 - 支持 Markdown、Word、PDF 格式

依赖安装:
    pip install pypandoc markdown

PDF 导出需要额外工具:
    - wkhtmltopdf (推荐): https://wkhtmltopdf.org/downloads.html
    - 或 LaTeX: https://www.latex-project.org/get/
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 检查依赖是否可用
try:
    import markdown
    import pypandoc
    
    # 检查 pandoc 是否可用
    try:
        pypandoc.get_pandoc_version()
        PANDOC_AVAILABLE = True
        logger.info("✅ Pandoc 可用")
    except OSError:
        PANDOC_AVAILABLE = False
        logger.warning("⚠️ Pandoc 不可用，Word 和 PDF 导出功能将不可用")
    
    EXPORT_AVAILABLE = True
except ImportError as e:
    EXPORT_AVAILABLE = False
    PANDOC_AVAILABLE = False
    logger.warning(f"⚠️ 导出功能依赖包缺失: {e}")
    logger.info("💡 请安装: pip install pypandoc markdown")


class ReportExporter:
    """报告导出器 - 支持 Markdown、Word、PDF 格式"""
    
    def __init__(self):
        self.export_available = EXPORT_AVAILABLE
        self.pandoc_available = PANDOC_AVAILABLE
        
        logger.info(f"📋 ReportExporter 初始化:")
        logger.info(f"  - export_available: {self.export_available}")
        logger.info(f"  - pandoc_available: {self.pandoc_available}")
    
    def generate_markdown_report(self, report_doc: Dict[str, Any]) -> str:
        """生成 Markdown 格式报告"""
        logger.info("📝 生成 Markdown 报告...")
        
        stock_symbol = report_doc.get("stock_symbol", "unknown")
        analysis_date = report_doc.get("analysis_date", "")
        analysts = report_doc.get("analysts", [])
        research_depth = report_doc.get("research_depth", 1)
        reports = report_doc.get("reports", {})
        summary = report_doc.get("summary", "")
        
        content_parts = []
        
        # 标题和元信息
        content_parts.append(f"# {stock_symbol} 股票分析报告")
        content_parts.append("")
        content_parts.append(f"**分析日期**: {analysis_date}")
        if analysts:
            content_parts.append(f"**分析师**: {', '.join(analysts)}")
        content_parts.append(f"**研究深度**: {research_depth}")
        content_parts.append("")
        content_parts.append("---")
        content_parts.append("")
        
        # 执行摘要
        if summary:
            content_parts.append("## 📊 执行摘要")
            content_parts.append("")
            content_parts.append(summary)
            content_parts.append("")
            content_parts.append("---")
            content_parts.append("")
        
        # 各模块内容
        module_order = [
            "company_overview",
            "financial_analysis", 
            "technical_analysis",
            "market_analysis",
            "risk_analysis",
            "valuation_analysis",
            "investment_recommendation"
        ]
        
        module_titles = {
            "company_overview": "🏢 公司概况",
            "financial_analysis": "💰 财务分析",
            "technical_analysis": "📈 技术分析",
            "market_analysis": "🌍 市场分析",
            "risk_analysis": "⚠️ 风险分析",
            "valuation_analysis": "💎 估值分析",
            "investment_recommendation": "🎯 投资建议"
        }
        
        # 按顺序添加模块
        for module_key in module_order:
            if module_key in reports:
                module_content = reports[module_key]
                if isinstance(module_content, str) and module_content.strip():
                    title = module_titles.get(module_key, module_key)
                    content_parts.append(f"## {title}")
                    content_parts.append("")
                    content_parts.append(module_content)
                    content_parts.append("")
                    content_parts.append("---")
                    content_parts.append("")
        
        # 添加其他未列出的模块
        for module_key, module_content in reports.items():
            if module_key not in module_order:
                if isinstance(module_content, str) and module_content.strip():
                    content_parts.append(f"## {module_key}")
                    content_parts.append("")
                    content_parts.append(module_content)
                    content_parts.append("")
                    content_parts.append("---")
                    content_parts.append("")
        
        # 页脚
        content_parts.append("")
        content_parts.append("---")
        content_parts.append("")
        content_parts.append("*本报告由 TradingAgents-CN 自动生成*")
        content_parts.append("")
        
        markdown_content = "\n".join(content_parts)
        logger.info(f"✅ Markdown 报告生成完成，长度: {len(markdown_content)} 字符")
        
        return markdown_content
    
    def _clean_markdown_for_pandoc(self, md_content: str) -> str:
        """清理 Markdown 内容，避免 pandoc 解析问题"""
        import re
        
        # 移除可能导致 YAML 解析问题的内容
        # 如果开头有 "---"，在前面添加空行
        if md_content.strip().startswith("---"):
            md_content = "\n" + md_content
        
        # 转义特殊字符
        # 注意：不要过度转义，否则会影响 Markdown 格式
        
        return md_content
    
    def generate_docx_report(self, report_doc: Dict[str, Any]) -> bytes:
        """生成 Word 文档格式报告"""
        logger.info("📄 开始生成 Word 文档...")
        
        if not self.pandoc_available:
            raise Exception("Pandoc 不可用，无法生成 Word 文档。请安装 pandoc 或使用 Markdown 格式导出。")
        
        # 生成 Markdown 内容
        md_content = self.generate_markdown_report(report_doc)
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                output_file = tmp_file.name
            
            logger.info(f"📁 临时文件路径: {output_file}")
            
            # Pandoc 参数
            extra_args = [
                '--from=markdown-yaml_metadata_block',  # 禁用 YAML 元数据块解析
                '--standalone',  # 生成独立文档
            ]
            
            # 清理内容
            cleaned_content = self._clean_markdown_for_pandoc(md_content)
            
            # 转换为 Word
            pypandoc.convert_text(
                cleaned_content,
                'docx',
                format='markdown',
                outputfile=output_file,
                extra_args=extra_args
            )
            
            logger.info("✅ pypandoc 转换完成")
            
            # 读取生成的文件
            with open(output_file, 'rb') as f:
                docx_content = f.read()
            
            logger.info(f"✅ Word 文档生成成功，大小: {len(docx_content)} 字节")
            
            # 清理临时文件
            os.unlink(output_file)
            
            return docx_content
            
        except Exception as e:
            logger.error(f"❌ Word 文档生成失败: {e}", exc_info=True)
            # 清理临时文件
            try:
                if 'output_file' in locals() and os.path.exists(output_file):
                    os.unlink(output_file)
            except:
                pass
            raise Exception(f"生成 Word 文档失败: {e}")
    
    def generate_pdf_report(self, report_doc: Dict[str, Any]) -> bytes:
        """生成 PDF 格式报告"""
        logger.info("📊 开始生成 PDF 文档...")
        
        if not self.pandoc_available:
            raise Exception("Pandoc 不可用，无法生成 PDF 文档。请安装 pandoc 或使用 Markdown 格式导出。")
        
        # 生成 Markdown 内容
        md_content = self.generate_markdown_report(report_doc)
        
        # PDF 引擎列表（按优先级）
        pdf_engines = [
            ('wkhtmltopdf', 'HTML 转 PDF 引擎（推荐）'),
            ('weasyprint', '现代 HTML 转 PDF 引擎'),
            (None, 'Pandoc 默认引擎')
        ]
        
        last_error = None
        
        for engine, description in pdf_engines:
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    output_file = tmp_file.name
                
                # Pandoc 参数
                extra_args = [
                    '--from=markdown-yaml_metadata_block',  # 禁用 YAML 元数据块解析
                    '-V', 'mainfont=Noto Sans CJK SC',  # 设置中文字体（wkhtmltopdf）
                    '-V', 'sansfont=Noto Sans CJK SC',
                    '-V', 'monofont=Noto Sans Mono CJK SC',
                ]

                if engine:
                    extra_args.append(f'--pdf-engine={engine}')
                    logger.info(f"🔧 使用 PDF 引擎: {engine}")
                else:
                    logger.info(f"🔧 使用默认 PDF 引擎")
                
                # 清理内容
                cleaned_content = self._clean_markdown_for_pandoc(md_content)
                
                # 转换为 PDF
                pypandoc.convert_text(
                    cleaned_content,
                    'pdf',
                    format='markdown',
                    outputfile=output_file,
                    extra_args=extra_args
                )
                
                # 检查文件是否生成
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    # 读取生成的文件
                    with open(output_file, 'rb') as f:
                        pdf_content = f.read()
                    
                    logger.info(f"✅ PDF 生成成功，使用引擎: {engine or '默认'}，大小: {len(pdf_content)} 字节")
                    
                    # 清理临时文件
                    os.unlink(output_file)
                    
                    return pdf_content
                else:
                    raise Exception("PDF 文件生成失败或为空")
            
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ PDF 引擎 {engine or '默认'} 失败: {e}")
                
                # 清理临时文件
                try:
                    if 'output_file' in locals() and os.path.exists(output_file):
                        os.unlink(output_file)
                except:
                    pass
                
                continue
        
        # 所有引擎都失败
        error_msg = f"""PDF 生成失败，最后错误: {last_error}

可能的解决方案:
1. 安装 wkhtmltopdf (推荐):
   Windows: choco install wkhtmltopdf
   macOS: brew install wkhtmltopdf  
   Linux: sudo apt-get install wkhtmltopdf

2. 安装 LaTeX:
   Windows: choco install miktex
   macOS: brew install mactex
   Linux: sudo apt-get install texlive-full

3. 使用替代格式:
   - Markdown 格式 - 轻量级，兼容性好
   - Word 格式 - 适合进一步编辑
"""
        logger.error(error_msg)
        raise Exception(error_msg)


# 创建全局导出器实例
report_exporter = ReportExporter()

