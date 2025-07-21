#!/usr/bin/env python3
"""
报告导出工具
支持将分析结果导出为多种格式
"""

import streamlit as st
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import base64

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

# 配置日志 - 确保输出到stdout以便Docker logs可见
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到stdout
    ]
)
logger = logging.getLogger(__name__)

# 导入Docker适配器
try:
    from .docker_pdf_adapter import (
        is_docker_environment,
        get_docker_pdf_extra_args,
        setup_xvfb_display,
        get_docker_status_info
    )
    DOCKER_ADAPTER_AVAILABLE = True
except ImportError:
    DOCKER_ADAPTER_AVAILABLE = False
    logger.warning(f"⚠️ Docker适配器不可用")

# 导入导出相关库
try:
    import markdown
    import re
    import tempfile
    import os
    from pathlib import Path

    # 导入pypandoc（用于markdown转docx和pdf）
    import pypandoc

    # 检查pandoc是否可用，如果不可用则尝试下载
    try:
        pypandoc.get_pandoc_version()
        PANDOC_AVAILABLE = True
    except OSError:
        logger.warning(f"⚠️ 未找到pandoc，正在尝试自动下载...")
        try:
            pypandoc.download_pandoc()
            PANDOC_AVAILABLE = True
            logger.info(f"✅ pandoc下载成功！")
        except Exception as download_error:
            logger.error(f"❌ pandoc下载失败: {download_error}")
            PANDOC_AVAILABLE = False

    EXPORT_AVAILABLE = True

except ImportError as e:
    EXPORT_AVAILABLE = False
    PANDOC_AVAILABLE = False
    logger.info(f"导出功能依赖包缺失: {e}")
    logger.info(f"请安装: pip install pypandoc markdown")


class ReportExporter:
    """报告导出器"""

    def __init__(self):
        self.export_available = EXPORT_AVAILABLE
        self.pandoc_available = PANDOC_AVAILABLE
        self.is_docker = DOCKER_ADAPTER_AVAILABLE and is_docker_environment()

        # 记录初始化状态
        logger.info(f"📋 ReportExporter初始化:")
        logger.info(f"  - export_available: {self.export_available}")
        logger.info(f"  - pandoc_available: {self.pandoc_available}")
        logger.info(f"  - is_docker: {self.is_docker}")
        logger.info(f"  - docker_adapter_available: {DOCKER_ADAPTER_AVAILABLE}")

        # Docker环境初始化
        if self.is_docker:
            logger.info("🐳 检测到Docker环境，初始化PDF支持...")
            logger.info(f"🐳 检测到Docker环境，初始化PDF支持...")
            setup_xvfb_display()
    
    def _clean_text_for_markdown(self, text: str) -> str:
        """清理文本中可能导致YAML解析问题的字符"""
        if not text:
            return "N/A"

        # 转换为字符串并清理特殊字符
        text = str(text)

        # 移除可能导致YAML解析问题的字符
        text = text.replace('&', '&amp;')  # HTML转义
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')

        # 移除可能的YAML特殊字符
        text = text.replace('---', '—')  # 替换三个连字符
        text = text.replace('...', '…')  # 替换三个点

        return text

    def _clean_markdown_for_pandoc(self, content: str) -> str:
        """清理Markdown内容避免pandoc YAML解析问题"""
        if not content:
            return ""

        # 确保内容不以可能被误认为YAML的字符开头
        content = content.strip()

        # 如果第一行看起来像YAML分隔符，添加空行
        lines = content.split('\n')
        if lines and (lines[0].startswith('---') or lines[0].startswith('...')):
            content = '\n' + content

        # 替换可能导致YAML解析问题的字符序列，但保护表格分隔符
        # 先保护表格分隔符
        content = content.replace('|------|------|', '|TABLESEP|TABLESEP|')
        content = content.replace('|------|', '|TABLESEP|')

        # 然后替换其他的三连字符
        content = content.replace('---', '—')  # 替换三个连字符
        content = content.replace('...', '…')  # 替换三个点

        # 恢复表格分隔符
        content = content.replace('|TABLESEP|TABLESEP|', '|------|------|')
        content = content.replace('|TABLESEP|', '|------|')

        # 清理特殊引号
        content = content.replace('"', '"')  # 左双引号
        content = content.replace('"', '"')  # 右双引号
        content = content.replace(''', "'")  # 左单引号
        content = content.replace(''', "'")  # 右单引号

        # 确保内容以标准Markdown标题开始
        if not content.startswith('#'):
            content = '# 分析报告\n\n' + content

        return content

    def generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """生成Markdown格式的报告"""

        stock_symbol = self._clean_text_for_markdown(results.get('stock_symbol', 'N/A'))
        decision = results.get('decision', {})
        state = results.get('state', {})
        is_demo = results.get('is_demo', False)
        
        # 生成时间戳
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 清理关键数据
        action = self._clean_text_for_markdown(decision.get('action', 'N/A')).upper()
        target_price = self._clean_text_for_markdown(decision.get('target_price', 'N/A'))
        reasoning = self._clean_text_for_markdown(decision.get('reasoning', '暂无分析推理'))

        # 构建Markdown内容
        md_content = f"""# {stock_symbol} 股票分析报告

**生成时间**: {timestamp}
**分析状态**: {'演示模式' if is_demo else '正式分析'}

## 🎯 投资决策摘要

| 指标 | 数值 |
|------|------|
| **投资建议** | {action} |
| **置信度** | {decision.get('confidence', 0):.1%} |
| **风险评分** | {decision.get('risk_score', 0):.1%} |
| **目标价位** | {target_price} |

### 分析推理
{reasoning}

---

## 📋 分析配置信息

- **LLM提供商**: {results.get('llm_provider', 'N/A')}
- **AI模型**: {results.get('llm_model', 'N/A')}
- **分析师数量**: {len(results.get('analysts', []))}个
- **研究深度**: {results.get('research_depth', 'N/A')}

### 参与分析师
{', '.join(results.get('analysts', []))}

---

## 📊 详细分析报告

"""
        
        # 添加各个分析模块的内容
        analysis_modules = [
            ('market_report', '📈 市场技术分析', '技术指标、价格趋势、支撑阻力位分析'),
            ('fundamentals_report', '💰 基本面分析', '财务数据、估值水平、盈利能力分析'),
            ('sentiment_report', '💭 市场情绪分析', '投资者情绪、社交媒体情绪指标'),
            ('news_report', '📰 新闻事件分析', '相关新闻事件、市场动态影响分析'),
            ('risk_assessment', '⚠️ 风险评估', '风险因素识别、风险等级评估'),
            ('investment_plan', '📋 投资建议', '具体投资策略、仓位管理建议')
        ]
        
        for key, title, description in analysis_modules:
            md_content += f"\n### {title}\n\n"
            md_content += f"*{description}*\n\n"
            
            if key in state and state[key]:
                content = state[key]
                if isinstance(content, str):
                    md_content += f"{content}\n\n"
                elif isinstance(content, dict):
                    for sub_key, sub_value in content.items():
                        md_content += f"#### {sub_key.replace('_', ' ').title()}\n\n"
                        md_content += f"{sub_value}\n\n"
                else:
                    md_content += f"{content}\n\n"
            else:
                md_content += "暂无数据\n\n"
        
        # 添加风险提示
        md_content += f"""
---

## ⚠️ 重要风险提示

**投资风险提示**:
- **仅供参考**: 本分析结果仅供参考，不构成投资建议
- **投资风险**: 股票投资有风险，可能导致本金损失
- **理性决策**: 请结合多方信息进行理性投资决策
- **专业咨询**: 重大投资决策建议咨询专业财务顾问
- **自担风险**: 投资决策及其后果由投资者自行承担

---
*报告生成时间: {timestamp}*
"""
        
        return md_content
    
    def generate_docx_report(self, results: Dict[str, Any]) -> bytes:
        """生成Word文档格式的报告"""

        logger.info("📄 开始生成Word文档...")

        if not self.pandoc_available:
            logger.error("❌ Pandoc不可用")
            raise Exception("Pandoc不可用，无法生成Word文档。请安装pandoc或使用Markdown格式导出。")

        # 首先生成markdown内容
        logger.info("📝 生成Markdown内容...")
        md_content = self.generate_markdown_report(results)
        logger.info(f"✅ Markdown内容生成完成，长度: {len(md_content)} 字符")

        try:
            logger.info("📁 创建临时文件用于docx输出...")
            # 创建临时文件用于docx输出
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                output_file = tmp_file.name
            logger.info(f"📁 临时文件路径: {output_file}")

            # 使用强制禁用YAML的参数
            extra_args = ['--from=markdown-yaml_metadata_block']  # 禁用YAML解析
            logger.info(f"🔧 pypandoc参数: {extra_args} (禁用YAML解析)")

            logger.info("🔄 使用pypandoc将markdown转换为docx...")

            # 调试：保存实际的Markdown内容
            debug_file = '/app/debug_markdown.md'
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                logger.info(f"🔍 实际Markdown内容已保存到: {debug_file}")
                logger.info(f"📊 内容长度: {len(md_content)} 字符")

                # 显示前几行内容
                lines = md_content.split('\n')[:5]
                logger.info("🔍 前5行内容:")
                for i, line in enumerate(lines, 1):
                    logger.info(f"  {i}: {repr(line)}")
            except Exception as e:
                logger.error(f"保存调试文件失败: {e}")

            # 清理内容避免YAML解析问题
            cleaned_content = self._clean_markdown_for_pandoc(md_content)
            logger.info(f"🧹 内容清理完成，清理后长度: {len(cleaned_content)} 字符")

            # 使用测试成功的参数进行转换
            pypandoc.convert_text(
                cleaned_content,
                'docx',
                format='markdown',  # 基础markdown格式
                outputfile=output_file,
                extra_args=extra_args
            )
            logger.info("✅ pypandoc转换完成")

            logger.info("📖 读取生成的docx文件...")
            # 读取生成的docx文件
            with open(output_file, 'rb') as f:
                docx_content = f.read()
            logger.info(f"✅ 文件读取完成，大小: {len(docx_content)} 字节")

            logger.info("🗑️ 清理临时文件...")
            # 清理临时文件
            os.unlink(output_file)
            logger.info("✅ 临时文件清理完成")

            return docx_content
        except Exception as e:
            logger.error(f"❌ Word文档生成失败: {e}", exc_info=True)
            raise Exception(f"生成Word文档失败: {e}")
    
    
    def generate_pdf_report(self, results: Dict[str, Any]) -> bytes:
        """生成PDF格式的报告"""

        logger.info("📊 开始生成PDF文档...")

        if not self.pandoc_available:
            logger.error("❌ Pandoc不可用")
            raise Exception("Pandoc不可用，无法生成PDF文档。请安装pandoc或使用Markdown格式导出。")

        # 首先生成markdown内容
        logger.info("📝 生成Markdown内容...")
        md_content = self.generate_markdown_report(results)
        logger.info(f"✅ Markdown内容生成完成，长度: {len(md_content)} 字符")

        # 简化的PDF引擎列表，优先使用最可能成功的
        pdf_engines = [
            ('wkhtmltopdf', 'HTML转PDF引擎，推荐安装'),
            ('weasyprint', '现代HTML转PDF引擎'),
            (None, '使用pandoc默认引擎')  # 不指定引擎，让pandoc自己选择
        ]

        last_error = None

        for engine_info in pdf_engines:
            engine, description = engine_info
            try:
                # 创建临时文件用于PDF输出
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    output_file = tmp_file.name

                # 使用禁用YAML解析的参数（与Word导出一致）
                extra_args = ['--from=markdown-yaml_metadata_block']

                # 如果指定了引擎，添加引擎参数
                if engine:
                    extra_args.append(f'--pdf-engine={engine}')
                    logger.info(f"🔧 使用PDF引擎: {engine}")
                else:
                    logger.info(f"🔧 使用默认PDF引擎")

                logger.info(f"🔧 PDF参数: {extra_args}")

                # 清理内容避免YAML解析问题（与Word导出一致）
                cleaned_content = self._clean_markdown_for_pandoc(md_content)

                # 使用pypandoc将markdown转换为PDF - 禁用YAML解析
                pypandoc.convert_text(
                    cleaned_content,
                    'pdf',
                    format='markdown',  # 基础markdown格式
                    outputfile=output_file,
                    extra_args=extra_args
                )

                # 检查文件是否生成且有内容
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    # 读取生成的PDF文件
                    with open(output_file, 'rb') as f:
                        pdf_content = f.read()

                    # 清理临时文件
                    os.unlink(output_file)

                    logger.info(f"✅ PDF生成成功，使用引擎: {engine or '默认'}")
                    return pdf_content
                else:
                    raise Exception("PDF文件生成失败或为空")

            except Exception as e:
                last_error = str(e)
                logger.error(f"PDF引擎 {engine or '默认'} 失败: {e}")

                # 清理可能存在的临时文件
                try:
                    if 'output_file' in locals() and os.path.exists(output_file):
                        os.unlink(output_file)
                except:
                    pass

                continue

        # 如果所有引擎都失败，提供详细的错误信息和解决方案
        error_msg = f"""PDF生成失败，最后错误: {last_error}

可能的解决方案:
1. 安装wkhtmltopdf (推荐):
   Windows: choco install wkhtmltopdf
   macOS: brew install wkhtmltopdf
   Linux: sudo apt-get install wkhtmltopdf

2. 安装LaTeX:
   Windows: choco install miktex
   macOS: brew install mactex
   Linux: sudo apt-get install texlive-full

3. 使用Markdown或Word格式导出作为替代方案
"""
        raise Exception(error_msg)
    
    def export_report(self, results: Dict[str, Any], format_type: str) -> Optional[bytes]:
        """导出报告为指定格式"""

        logger.info(f"🚀 开始导出报告: format={format_type}")
        logger.info(f"📊 导出状态检查:")
        logger.info(f"  - export_available: {self.export_available}")
        logger.info(f"  - pandoc_available: {self.pandoc_available}")
        logger.info(f"  - is_docker: {self.is_docker}")

        if not self.export_available:
            logger.error("❌ 导出功能不可用")
            st.error("❌ 导出功能不可用，请安装必要的依赖包")
            return None

        try:
            logger.info(f"🔄 开始生成{format_type}格式报告...")

            if format_type == 'markdown':
                logger.info("📝 生成Markdown报告...")
                content = self.generate_markdown_report(results)
                logger.info(f"✅ Markdown报告生成成功，长度: {len(content)} 字符")
                return content.encode('utf-8')

            elif format_type == 'docx':
                logger.info("📄 生成Word文档...")
                if not self.pandoc_available:
                    logger.error("❌ pandoc不可用，无法生成Word文档")
                    st.error("❌ pandoc不可用，无法生成Word文档")
                    return None
                content = self.generate_docx_report(results)
                logger.info(f"✅ Word文档生成成功，大小: {len(content)} 字节")
                return content

            elif format_type == 'pdf':
                logger.info("📊 生成PDF文档...")
                if not self.pandoc_available:
                    logger.error("❌ pandoc不可用，无法生成PDF文档")
                    st.error("❌ pandoc不可用，无法生成PDF文档")
                    return None
                content = self.generate_pdf_report(results)
                logger.info(f"✅ PDF文档生成成功，大小: {len(content)} 字节")
                return content

            else:
                logger.error(f"❌ 不支持的导出格式: {format_type}")
                st.error(f"❌ 不支持的导出格式: {format_type}")
                return None

        except Exception as e:
            logger.error(f"❌ 导出失败: {str(e)}", exc_info=True)
            st.error(f"❌ 导出失败: {str(e)}")
            return None


# 创建全局导出器实例
report_exporter = ReportExporter()


def render_export_buttons(results: Dict[str, Any]):
    """渲染导出按钮"""

    if not results:
        return

    st.markdown("---")
    st.subheader("📤 导出报告")

    # 检查导出功能是否可用
    if not report_exporter.export_available:
        st.warning("⚠️ 导出功能需要安装额外依赖包")
        st.code("pip install pypandoc markdown")
        return

    # 检查pandoc是否可用
    if not report_exporter.pandoc_available:
        st.warning("⚠️ Word和PDF导出需要pandoc工具")
        st.info("💡 您仍可以使用Markdown格式导出")

    # 显示Docker环境状态
    if report_exporter.is_docker:
        if DOCKER_ADAPTER_AVAILABLE:
            docker_status = get_docker_status_info()
            if docker_status['dependencies_ok'] and docker_status['pdf_test_ok']:
                st.success("🐳 Docker环境PDF支持已启用")
            else:
                st.warning(f"🐳 Docker环境PDF支持异常: {docker_status['dependency_message']}")
        else:
            st.warning("🐳 Docker环境检测到，但适配器不可用")

        with st.expander("📖 如何安装pandoc"):
            st.markdown("""
            **Windows用户:**
            ```bash
            # 使用Chocolatey (推荐)
            choco install pandoc

            # 或下载安装包
            # https://github.com/jgm/pandoc/releases
            ```

            **或者使用Python自动下载:**
            ```python
            import pypandoc

            pypandoc.download_pandoc()
            ```
            """)

        # 在Docker环境下，即使pandoc有问题也显示所有按钮，让用户尝试
        pass
    
    # 生成文件名
    stock_symbol = results.get('stock_symbol', 'analysis')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 导出 Markdown", help="导出为Markdown格式"):
            logger.info(f"🖱️ [EXPORT] 用户点击Markdown导出按钮 - 股票: {stock_symbol}")
            logger.info(f"🖱️ 用户点击Markdown导出按钮 - 股票: {stock_symbol}")
            content = report_exporter.export_report(results, 'markdown')
            if content:
                filename = f"{stock_symbol}_analysis_{timestamp}.md"
                logger.info(f"✅ [EXPORT] Markdown导出成功，文件名: {filename}")
                logger.info(f"✅ Markdown导出成功，文件名: {filename}")
                st.download_button(
                    label="📥 下载 Markdown",
                    data=content,
                    file_name=filename,
                    mime="text/markdown"
                )
            else:
                logger.error(f"❌ [EXPORT] Markdown导出失败，content为空")
                logger.error("❌ Markdown导出失败，content为空")
    
    with col2:
        if st.button("📝 导出 Word", help="导出为Word文档格式"):
            logger.info(f"🖱️ [EXPORT] 用户点击Word导出按钮 - 股票: {stock_symbol}")
            logger.info(f"🖱️ 用户点击Word导出按钮 - 股票: {stock_symbol}")
            with st.spinner("正在生成Word文档，请稍候..."):
                try:
                    logger.info(f"🔄 [EXPORT] 开始Word导出流程...")
                    logger.info("🔄 开始Word导出流程...")
                    content = report_exporter.export_report(results, 'docx')
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.docx"
                        logger.info(f"✅ [EXPORT] Word导出成功，文件名: {filename}, 大小: {len(content)} 字节")
                        logger.info(f"✅ Word导出成功，文件名: {filename}, 大小: {len(content)} 字节")
                        st.success("✅ Word文档生成成功！")
                        st.download_button(
                            label="📥 下载 Word",
                            data=content,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        logger.error(f"❌ [EXPORT] Word导出失败，content为空")
                        logger.error("❌ Word导出失败，content为空")
                        st.error("❌ Word文档生成失败")
                except Exception as e:
                    logger.error(f"❌ [EXPORT] Word导出异常: {str(e)}")
                    logger.error(f"❌ Word导出异常: {str(e)}", exc_info=True)
                    st.error(f"❌ Word文档生成失败: {str(e)}")

                    # 显示详细错误信息
                    with st.expander("🔍 查看详细错误信息"):
                        st.text(str(e))

                    # 提供解决方案
                    with st.expander("💡 解决方案"):
                        st.markdown("""
                        **Word导出需要pandoc工具，请检查:**

                        1. **Docker环境**: 重新构建镜像确保包含pandoc
                        2. **本地环境**: 安装pandoc
                        ```bash
                        # Windows
                        choco install pandoc

                        # macOS
                        brew install pandoc

                        # Linux
                        sudo apt-get install pandoc
                        ```

                        3. **替代方案**: 使用Markdown格式导出
                        """)
    
    with col3:
        if st.button("📊 导出 PDF", help="导出为PDF格式 (需要额外工具)"):
            logger.info(f"🖱️ 用户点击PDF导出按钮 - 股票: {stock_symbol}")
            with st.spinner("正在生成PDF，请稍候..."):
                try:
                    logger.info("🔄 开始PDF导出流程...")
                    content = report_exporter.export_report(results, 'pdf')
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.pdf"
                        logger.info(f"✅ PDF导出成功，文件名: {filename}, 大小: {len(content)} 字节")
                        st.success("✅ PDF生成成功！")
                        st.download_button(
                            label="📥 下载 PDF",
                            data=content,
                            file_name=filename,
                            mime="application/pdf"
                        )
                    else:
                        logger.error("❌ PDF导出失败，content为空")
                        st.error("❌ PDF生成失败")
                except Exception as e:
                    logger.error(f"❌ PDF导出异常: {str(e)}", exc_info=True)
                    st.error(f"❌ PDF生成失败")

                    # 显示详细错误信息
                    with st.expander("🔍 查看详细错误信息"):
                        st.text(str(e))

                    # 提供解决方案
                    with st.expander("💡 解决方案"):
                        st.markdown("""
                        **PDF导出需要额外的工具，请选择以下方案之一:**

                        **方案1: 安装wkhtmltopdf (推荐)**
                        ```bash
                        # Windows
                        choco install wkhtmltopdf

                        # macOS
                        brew install wkhtmltopdf

                        # Linux
                        sudo apt-get install wkhtmltopdf
                        ```

                        **方案2: 安装LaTeX**
                        ```bash
                        # Windows
                        choco install miktex

                        # macOS
                        brew install mactex

                        # Linux
                        sudo apt-get install texlive-full
                        ```

                        **方案3: 使用替代格式**
                        - 📄 Markdown格式 - 轻量级，兼容性好
                        - 📝 Word格式 - 适合进一步编辑
                        """)

                    # 建议使用其他格式
                    st.info("💡 建议：您可以先使用Markdown或Word格式导出，然后使用其他工具转换为PDF")
    
 