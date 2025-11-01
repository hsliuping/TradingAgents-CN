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
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

# 尝试加载项目根目录下的 .env 环境变量文件（若存在）
try:
    from dotenv import load_dotenv  # type: ignore
    _this_file = Path(__file__).resolve()
    _project_root = _this_file.parents[2]  # app/utils/report_exporter.py -> app -> 项目根目录
    _dotenv_path = _project_root / '.env'
    if _dotenv_path.exists():
        load_dotenv(dotenv_path=str(_dotenv_path))
        logger.info(f"🧩 已加载 .env: {_dotenv_path}")
    else:
        # 回退默认搜索（当前工作目录）
        load_dotenv()
        logger.info("🧩 已尝试加载 .env（默认搜索路径）")
except Exception:
    pass

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
                '--standalone',  # 生成独立文档
            ]
            
            # 清理内容
            cleaned_content = self._clean_markdown_for_pandoc(md_content)
            
            # 转换为 Word
            pypandoc.convert_text(
                cleaned_content,
                'docx',
                format='markdown-yaml_metadata_block',  # 禁用 YAML 元数据块解析
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

        # 可选：显式补充 TeX 可执行目录到 PATH（解决 GUI/服务进程 PATH 丢失问题）
        texbin_val = os.getenv('TRADINGAGENTS_TEXBIN')
        if texbin_val:
            parts = []
            # 支持多目录（以系统分隔符、逗号或分号分隔）
            for raw in re.split(r"[" + re.escape(os.pathsep) + r",;]", texbin_val):
                p = raw.strip()
                if p and os.path.isdir(p):
                    parts.append(p)
            if parts:
                current_path = os.environ.get('PATH', '')
                new_path = current_path
                # 将有效目录按顺序前置
                for p in reversed(parts):  # 保持原次序，逐个前置
                    if p not in new_path.split(os.pathsep):
                        new_path = p + os.pathsep + new_path
                os.environ['PATH'] = new_path
                logger.info(f"🛠️ 已将 TRADINGAGENTS_TEXBIN 目录前置到 PATH: {parts}")
                try:
                    import shutil as _sh
                    logger.info(
                        "🔎 预检查 which: pdflatex=%s, xelatex=%s, lualatex=%s",
                        _sh.which('pdflatex'), _sh.which('xelatex'), _sh.which('lualatex')
                    )
                except Exception:
                    pass
        
        # 可选：环境变量强制指定引擎（pdflatex/xelatex/lualatex/tectonic/weasyprint/wkhtmltopdf）
        preferred_engine = os.getenv('TRADINGAGENTS_PDF_ENGINE')
        if preferred_engine:
            preferred_engine = preferred_engine.strip().lower()
            logger.info(f"🎛️ 指定首选PDF引擎(来自环境变量): {preferred_engine}")

        # 按可用性动态选择 PDF 引擎，尽量避免触发缺失报错
        detected = {
            'pdflatex': shutil.which('pdflatex'),
            'xelatex': shutil.which('xelatex'),
            'lualatex': shutil.which('lualatex'),
            'wkhtmltopdf': shutil.which('wkhtmltopdf'),
            'weasyprint': shutil.which('weasyprint'),
            'tectonic': shutil.which('tectonic'),
            # 只要本机安装了 docker 客户端，即认为可尝试 docker-wkhtmltopdf
            'docker-wkhtmltopdf': shutil.which('docker')
        }
        logger.info(
            "🔎 引擎可用性: "
            f"pdflatex={detected['pdflatex']}, xelatex={detected['xelatex']}, lualatex={detected['lualatex']}, "
            f"tectonic={detected['tectonic']}, wkhtmltopdf={detected['wkhtmltopdf']}, weasyprint={detected['weasyprint']}"
        )

        # 构建候选引擎顺序（去重，避免重复添加）
        pdf_engines = []
        added = set()
        valid_names = {'pdflatex', 'xelatex', 'lualatex', 'tectonic', 'wkhtmltopdf', 'weasyprint', 'docker-wkhtmltopdf'}

        # 内容是否包含中文（CJK）和 Emoji
        contains_cjk = bool(re.search(r"[\u4e00-\u9fff]", md_content))
        contains_emoji = bool(re.search(r"[\U0001F000-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\U0001F1E6-\U0001F1FF]", md_content))

        # 先考虑环境变量指定的引擎（若可用）
        if preferred_engine and preferred_engine in valid_names:
            if preferred_engine in {'pdflatex', 'xelatex', 'lualatex', 'tectonic'}:
                if detected.get(preferred_engine):
                    # 如果内容包含中文且用户偏好 pdflatex，则延后作为回退
                    if preferred_engine == 'pdflatex' and contains_cjk:
                        logger.warning("⚠️ 检测到报告包含中文，pdflatex 对 CJK 支持较差，将优先尝试 tectonic/xelatex/lualatex，再回退到 pdflatex")
                    else:
                        pdf_engines.append((preferred_engine, '首选引擎（环境变量）'))
                        added.add(preferred_engine)
                else:
                    logger.warning(f"⚠️ 已指定首选引擎 {preferred_engine} 但未检测到可执行文件，已跳过该引擎")
            else:  # HTML 引擎
                if detected.get(preferred_engine):
                    pdf_engines.append((preferred_engine, '首选引擎（环境变量）'))
                    added.add(preferred_engine)
                else:
                    logger.warning(f"⚠️ 已指定首选引擎 {preferred_engine} 但未检测到可执行文件，已跳过该引擎")

        # 按可用性构建候选顺序
        if detected['tectonic'] and 'tectonic' not in added:
            pdf_engines.append(('tectonic', '轻量级 LaTeX 引擎（conda 可安装）'))
            added.add('tectonic')

        for latex_engine in ['xelatex', 'lualatex', 'pdflatex']:
            if detected[latex_engine]:
                # 若用户显式选择 pdflatex 且包含中文，则将其放在回退位置，不在此处加入
                if latex_engine == 'pdflatex' and preferred_engine == 'pdflatex' and contains_cjk:
                    continue
                if latex_engine not in added:
                    pdf_engines.append((latex_engine, 'LaTeX 引擎'))
                    added.add(latex_engine)

        # 优先尝试 docker-wkhtmltopdf（跨平台稳定的 HTML→PDF 渲染）
        if detected.get('docker-wkhtmltopdf') and 'docker-wkhtmltopdf' not in added:
            pdf_engines.append(('docker-wkhtmltopdf', 'Docker 封装的 wkhtmltopdf'))
            added.add('docker-wkhtmltopdf')

        for html_engine in ['weasyprint', 'wkhtmltopdf']:
            if detected[html_engine] and html_engine not in added:
                pdf_engines.append((html_engine, 'HTML 转 PDF 引擎'))
                added.add(html_engine)

        # 如果用户偏好 pdflatex 且内容包含中文，同时系统存在 pdflatex，则将 pdflatex 作为回退追加到队尾
        if preferred_engine == 'pdflatex' and contains_cjk and detected.get('pdflatex') and 'pdflatex' not in added:
            pdf_engines.append(('pdflatex', 'LaTeX 引擎（CJK 回退）'))
            added.add('pdflatex')

        # 如果完全未检测到引擎，提供提示性候选顺序（不添加 None，避免触发默认 pdflatex）
        if not pdf_engines:
            pdf_engines = [
                ('tectonic', '轻量级 LaTeX 引擎（conda 可安装）'),
                ('weasyprint', '现代 HTML 转 PDF 引擎'),
                ('wkhtmltopdf', 'HTML 转 PDF 引擎（推荐）')
            ]

        # 仅在系统存在任一 LaTeX 引擎时，才允许使用 pandoc 默认引擎
        if any(detected[k] for k in ['pdflatex', 'xelatex', 'lualatex']):
            pdf_engines.append((None, 'Pandoc 默认引擎'))

        logger.info("🧭 引擎候选顺序: " + ", ".join([str(e[0] or '默认') for e in pdf_engines]))
        
        last_error = None
        
        for engine, description in pdf_engines:
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    output_file = tmp_file.name
                
                # Pandoc 参数
                extra_args = []

                if engine:
                    extra_args.append(f'--pdf-engine={engine}')
                    logger.info(f"🔧 使用 PDF 引擎: {engine}")
                else:
                    logger.info(f"🔧 使用默认 PDF 引擎")

                # LaTeX 系（tectonic/xelatex/lualatex）下为中文选择系统字体（可选添加 Emoji 回退）
                if engine in ('tectonic', 'xelatex', 'lualatex'):
                    mainfont = 'PingFang SC' if sys.platform == 'darwin' else 'Noto Sans CJK SC'
                    extra_args += ['-V', f'mainfont={mainfont}', '-V', f'CJKmainfont={mainfont}']
                    emoji_mode = os.getenv('TRADINGAGENTS_PDF_EMOJI_MODE', 'auto').lower()
                    if emoji_mode == 'font' and contains_emoji:
                        if sys.platform == 'darwin':
                            emoji_fonts = ['Apple Color Emoji', 'Noto Emoji']
                        elif sys.platform.startswith('linux'):
                            emoji_fonts = ['Noto Color Emoji', 'Noto Emoji', 'Twemoji Mozilla']
                        elif sys.platform.startswith('win'):
                            emoji_fonts = ['Segoe UI Emoji']
                        else:
                            emoji_fonts = ['Noto Emoji']

                        fallback_opt = '{' + ', '.join(emoji_fonts) + '}'
                        extra_args += [
                            '-V', 'mainfontoptions=Renderer=Harfbuzz',
                            '-V', f'mainfontoptions=Fallback={fallback_opt}',
                            # 同步为无衬线字体设置相同的回退，改进标题等处的 Emoji 呈现
                            '-V', f'sansfont={mainfont}',
                            '-V', 'sansfontoptions=Renderer=Harfbuzz',
                            '-V', f'sansfontoptions=Fallback={fallback_opt}'
                        ]
                        logger.info(f"🈶 为中文渲染设置字体: {mainfont}，Emoji 回退(font): {', '.join(emoji_fonts)}")
                    else:
                        logger.info(f"🈶 为中文渲染设置字体: {mainfont}")

                # HTML 转 PDF 引擎（weasyprint / wkhtmltopdf / docker-wkhtmltopdf）：注入 CSS 以保证 CJK/Emoji 字体
                if engine in ('weasyprint', 'wkhtmltopdf', 'docker-wkhtmltopdf'):
                    try:
                        # 根据平台构建字体族
                        if sys.platform == 'darwin':
                            font_stack = (
                                '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", '
                                '"Noto Sans CJK SC", "Microsoft YaHei", "Helvetica Neue", Arial, '
                                '"Apple Color Emoji", "Noto Color Emoji", "Noto Emoji", sans-serif'
                            )
                            mono_stack = 'Menlo, Monaco, "Fira Code", "Noto Sans Mono CJK SC", monospace'
                        elif sys.platform.startswith('linux'):
                            font_stack = (
                                'system-ui, "Noto Sans CJK SC", "WenQuanYi Micro Hei", Arial, '
                                '"Noto Color Emoji", "Noto Emoji", sans-serif'
                            )
                            mono_stack = '"DejaVu Sans Mono", "Fira Code", "Noto Sans Mono CJK SC", monospace'
                        elif sys.platform.startswith('win'):
                            font_stack = (
                                '"Segoe UI", "Microsoft YaHei", Arial, '
                                '"Segoe UI Emoji", "Noto Color Emoji", "Noto Emoji", sans-serif'
                            )
                            mono_stack = 'Consolas, "Courier New", "Fira Code", monospace'
                        else:
                            font_stack = (
                                'system-ui, "Noto Sans CJK SC", Arial, '
                                '"Noto Color Emoji", "Noto Emoji", sans-serif'
                            )
                            mono_stack = 'monospace'

                        css_content = f"""
                        body {{
                          font-family: {font_stack};
                          -webkit-font-smoothing: antialiased;
                          -moz-osx-font-smoothing: grayscale;
                          line-height: 1.6;
                          font-size: 14px;
                        }}
                        h1, h2, h3, h4, h5, h6 {{
                          font-family: {font_stack};
                          font-weight: 600;
                        }}
                        code, pre {{
                          font-family: {mono_stack};
                          font-size: 12px;
                        }}
                        table {{
                          border-collapse: collapse;
                          width: 100%;
                        }}
                        th, td {{
                          border: 1px solid #ddd;
                          padding: 6px 8px;
                        }}
                        """

                        with tempfile.NamedTemporaryFile(suffix='.css', delete=False, mode='w', encoding='utf-8') as css_tmp:
                            css_tmp.write(css_content)
                            css_file = css_tmp.name

                        logger.info(f"🎨 已为 HTML 引擎准备 CSS: {css_file}")

                        if engine in ('weasyprint', 'wkhtmltopdf'):
                            # 走 pandoc HTML 引擎路径
                            extra_args += ['--css', css_file]
                            if engine == 'wkhtmltopdf':
                                extra_args += ['--pdf-engine-opt=--enable-local-file-access']
                    except Exception as _:
                        logger.warning("⚠️ 注入 HTML CSS 失败（忽略，继续转换）")
                
                # 清理内容
                cleaned_content = self._clean_markdown_for_pandoc(md_content)
                
                # 分三类处理：LaTeX / 原生 HTML 引擎 / docker-wkhtmltopdf
                if engine in (None, 'tectonic', 'xelatex', 'lualatex', 'pdflatex', 'weasyprint', 'wkhtmltopdf'):
                    # 交给 pandoc 正常处理
                    pypandoc.convert_text(
                        cleaned_content,
                        'pdf',
                        format='markdown-yaml_metadata_block',  # 禁用 YAML 元数据块解析
                        outputfile=output_file,
                        extra_args=extra_args
                    )
                elif engine == 'docker-wkhtmltopdf':
                    # 1) 先把 Markdown 转为 HTML
                    html_body = pypandoc.convert_text(
                        cleaned_content,
                        'html',
                        format='markdown-yaml_metadata_block',  # 禁用 YAML 元数据块解析
                        extra_args=['--standalone']
                    )

                    # 2) 注入 CSS 到 HTML <head>
                    try:
                        css_text = ''
                        if 'css_file' in locals() and os.path.exists(css_file):
                            with open(css_file, 'r', encoding='utf-8') as _cf:
                                css_text = _cf.read()
                    except Exception:
                        css_text = ''

                    if '<head>' in html_body:
                        html = html_body.replace('<head>', f'<head>\n<meta charset="utf-8">\n<style>\n{css_text}\n</style>\n', 1)
                    else:
                        html = f'<!doctype html><html><head><meta charset="utf-8"><style>{css_text}</style></head><body>{html_body}</body></html>'

                    # 3) 写入临时目录，并用 docker 运行 wkhtmltopdf
                    with tempfile.TemporaryDirectory() as tmpdir:
                        in_html = os.path.join(tmpdir, 'input.html')
                        out_pdf = os.path.join(tmpdir, 'output.pdf')
                        with open(in_html, 'w', encoding='utf-8') as _hf:
                            _hf.write(html)

                        image = os.getenv('TRADINGAGENTS_WKHTML_IMAGE', 'surnet/alpine-wkhtmltopdf:3.20-0.12.6-full')
                        platform = os.getenv('TRADINGAGENTS_DOCKER_PLATFORM')  # 例如: linux/arm64 (可选)
                        docker_cmd = [
                            'docker', 'run', '--rm',
                            '-v', f'{tmpdir}:/work',
                            '-w', '/work',
                        ]
                        if platform:
                            docker_cmd += ['--platform', platform]
                        docker_cmd += [
                            image,
                            '--enable-local-file-access', 'input.html', 'output.pdf'
                        ]
                        logger.info(f"🐳 调用 docker-wkhtmltopdf: {' '.join(docker_cmd)}")
                        result = subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if result.returncode != 0:
                            raise Exception(f"docker-wkhtmltopdf 失败: {result.stderr.strip()}")

                        if not os.path.exists(out_pdf) or os.path.getsize(out_pdf) == 0:
                            raise Exception('docker-wkhtmltopdf 未生成有效 PDF')

                        # 拷贝到 output_file
                        shutil.copyfile(out_pdf, output_file)
                
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
                    if 'css_file' in locals() and os.path.exists(css_file):
                        os.unlink(css_file)
                except:
                    pass
                
                continue
        
        # 所有引擎都失败
        error_msg = f"""PDF 生成失败，最后错误: {last_error}

可能的解决方案:
1. 通过 Conda 安装轻量 PDF 引擎（推荐，无需 Homebrew）:
    conda install -n trading -c conda-forge tectonic

2. 安装 wkhtmltopdf（HTML 转 PDF 引擎）:
    Windows: choco install wkhtmltopdf
    macOS: brew install wkhtmltopdf  
    Linux: sudo apt-get install wkhtmltopdf

3. 安装完整 LaTeX（体积较大）:
    Windows: choco install miktex
    macOS: brew install mactex
    Linux: sudo apt-get install texlive-full

4. 使用替代格式:
   - Markdown 格式 - 轻量级，兼容性好
   - Word 格式 - 适合进一步编辑
"""
        logger.error(error_msg)
        raise Exception(error_msg)


# 创建全局导出器实例
report_exporter = ReportExporter()

