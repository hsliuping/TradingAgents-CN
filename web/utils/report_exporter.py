#!/usr/bin/env python3
"""
Report exporter tool
Supports exporting analysis results in multiple formats
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

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

# Configure logging - ensure output to stdout for Docker logs visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to stdout
    ]
)
logger = logging.getLogger(__name__)

# Import Docker adapter
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
    logger.warning(f"⚠️ Docker adapter is not available")

# Import export related libraries
try:
    import markdown
    import re
    import tempfile
    import os
    from pathlib import Path

    # Import pypandoc (for markdown to docx and pdf)
    import pypandoc

    # Check if pandoc is available, try to download if not
    try:
        pypandoc.get_pandoc_version()
        PANDOC_AVAILABLE = True
    except OSError:
        logger.warning(f"⚠️ pandoc not found, attempting to download automatically...")
        try:
            pypandoc.download_pandoc()
            PANDOC_AVAILABLE = True
            logger.info(f"✅ pandoc downloaded successfully!")
        except Exception as download_error:
            logger.error(f"❌ pandoc download failed: {download_error}")
            PANDOC_AVAILABLE = False

    EXPORT_AVAILABLE = True

except ImportError as e:
    EXPORT_AVAILABLE = False
    PANDOC_AVAILABLE = False
    logger.info(f"Export functionality depends on missing packages: {e}")
    logger.info(f"Please install: pip install pypandoc markdown")


class ReportExporter:
    """Report exporter"""

    def __init__(self):
        self.export_available = EXPORT_AVAILABLE
        self.pandoc_available = PANDOC_AVAILABLE
        self.is_docker = DOCKER_ADAPTER_AVAILABLE and is_docker_environment()

        # Record initialization status
        logger.info(f"📋 ReportExporter initialization:")
        logger.info(f"  - export_available: {self.export_available}")
        logger.info(f"  - pandoc_available: {self.pandoc_available}")
        logger.info(f"  - is_docker: {self.is_docker}")
        logger.info(f"  - docker_adapter_available: {DOCKER_ADAPTER_AVAILABLE}")

        # Docker environment initialization
        if self.is_docker:
            logger.info("🐳 Detected Docker environment, initializing PDF support...")
            logger.info(f"🐳 Detected Docker environment, initializing PDF support...")
            setup_xvfb_display()
    
    def _clean_text_for_markdown(self, text: str) -> str:
        """Clean characters that might cause YAML parsing issues in text"""
        if not text:
            return "N/A"

        # Convert to string and clean special characters
        text = str(text)

        # Remove characters that might cause YAML parsing issues
        text = text.replace('&', '&amp;')  # HTML escape
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')

        # Remove potential YAML special characters
        text = text.replace('---', '—')  # Replace three hyphens
        text = text.replace('...', '…')  # Replace three dots

        return text

    def _clean_markdown_for_pandoc(self, content: str) -> str:
        """Clean Markdown content to avoid pandoc YAML parsing issues"""
        if not content:
            return ""

        # Ensure content does not start with characters that might be mistaken for YAML
        content = content.strip()

        # If the first line looks like a YAML separator, add a blank line
        lines = content.split('\n')
        if lines and (lines[0].startswith('---') or lines[0].startswith('...')):
            content = '\n' + content

        # Replace character sequences that might cause YAML parsing issues, but protect table separators
        # First protect table separators
        content = content.replace('|------|------|', '|TABLESEP|TABLESEP|')
        content = content.replace('|------|', '|TABLESEP|')

        # Then replace other three hyphens
        content = content.replace('---', '—')  # Replace three hyphens
        content = content.replace('...', '…')  # Replace three dots

        # Restore table separators
        content = content.replace('|TABLESEP|TABLESEP|', '|------|------|')
        content = content.replace('|TABLESEP|', '|------|')

        # Clean special quotes
        content = content.replace('"', '"')  # Left double quote
        content = content.replace('"', '"')  # Right double quote
        content = content.replace(''', "'")  # Left single quote
        content = content.replace(''', "'")  # Right single quote

        # Ensure content starts with a standard Markdown heading
        if not content.startswith('#'):
            content = '# Analysis Report\n\n' + content

        return content

    def generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Generate Markdown format report"""

        stock_symbol = self._clean_text_for_markdown(results.get('stock_symbol', 'N/A'))
        decision = results.get('decision', {})
        state = results.get('state', {})
        is_demo = results.get('is_demo', False)
        
        # Generate timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Clean key data
        action = self._clean_text_for_markdown(decision.get('action', 'N/A')).upper()
        target_price = self._clean_text_for_markdown(decision.get('target_price', 'N/A'))
        reasoning = self._clean_text_for_markdown(decision.get('reasoning', 'No analysis reasoning provided'))

        # Build Markdown content
        md_content = f"""# {stock_symbol} Stock Analysis Report

**Generated Time**: {timestamp}
**Analysis Status**: {'Demo Mode' if is_demo else 'Full Analysis'}

## 🎯 Investment Decision Summary

| Metric | Value |
|------|------|
| **Investment Advice** | {action} |
| **Confidence** | {decision.get('confidence', 0):.1%} |
| **Risk Score** | {decision.get('risk_score', 0):.1%} |
| **Target Price** | {target_price} |

### Analysis Reasoning
{reasoning}

---

## 📋 Analysis Configuration Information

- **LLM Provider**: {results.get('llm_provider', 'N/A')}
- **AI Model**: {results.get('llm_model', 'N/A')}
- **Analyst Count**: {len(results.get('analysts', []))} analysts
- **Research Depth**: {results.get('research_depth', 'N/A')}

### Participating Analysts
{', '.join(results.get('analysts', []))}

---

## 📊 Detailed Analysis Report

"""
        
        # Add content for each analysis module
        analysis_modules = [
            ('market_report', '📈 Market Technical Analysis', 'Technical indicators, price trends, support/resistance analysis'),
            ('fundamentals_report', '💰 Fundamental Analysis', 'Financial data, valuation levels, profitability analysis'),
            ('sentiment_report', '💭 Market Sentiment Analysis', 'Investor sentiment, social media sentiment indicators'),
            ('news_report', '📰 News Event Analysis', 'Relevant news events, market dynamics impact analysis'),
            ('risk_assessment', '⚠️ Risk Assessment', 'Risk factor identification, risk level assessment'),
            ('investment_plan', '📋 Investment Advice', 'Specific investment strategies, position management advice')
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
                md_content += "No data available\n\n"
        
        # Add risk warning
        md_content += f"""
---

## ⚠️ Important Risk Warning

**Investment Risk Warning**:
- **For Informational Purposes Only**: This analysis result is for informational purposes only and does not constitute investment advice.
- **Investment Risk**: Stock investment carries risks, which may result in loss of principal.
- **Rational Decision Making**: Please make rational investment decisions by combining multiple sources of information.
- **Professional Consultation**: Major investment decision advice should be consulted with professional financial advisors.
- **Self-Assumed Risk**: Investment decisions and their consequences are borne by the investor themselves.

---
*Report generated time: {timestamp}*
"""
        
        return md_content
    
    def generate_docx_report(self, results: Dict[str, Any]) -> bytes:
        """Generate Word document format report"""

        logger.info("📄 Starting Word document generation...")

        if not self.pandoc_available:
            logger.error("❌ Pandoc is not available")
            raise Exception("Pandoc is not available, cannot generate Word document. Please install pandoc or use Markdown format for export.")

        # First generate markdown content
        logger.info("📝 Generating Markdown content...")
        md_content = self.generate_markdown_report(results)
        logger.info(f"✅ Markdown content generated, length: {len(md_content)} characters")

        try:
            logger.info("📁 Creating temporary file for docx output...")
            # Create a temporary file for docx output
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                output_file = tmp_file.name
            logger.info(f"📁 Temporary file path: {output_file}")

            # Use parameters to force disable YAML
            extra_args = ['--from=markdown-yaml_metadata_block']  # Disable YAML parsing
            logger.info(f"🔧 pypandoc parameters: {extra_args} (Disable YAML parsing)")

            logger.info("🔄 Using pypandoc to convert markdown to docx...")

            # Debug: save actual Markdown content
            debug_file = '/app/debug_markdown.md'
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                logger.info(f"🔍 Actual Markdown content saved to: {debug_file}")
                logger.info(f"📊 Content length: {len(md_content)} characters")

                # Display first few lines of content
                lines = md_content.split('\n')[:5]
                logger.info("🔍 First 5 lines of content:")
                for i, line in enumerate(lines, 1):
                    logger.info(f"  {i}: {repr(line)}")
            except Exception as e:
                logger.error(f"Failed to save debug file: {e}")

            # Clean content to avoid YAML parsing issues
            cleaned_content = self._clean_markdown_for_pandoc(md_content)
            logger.info(f"🧹 Content cleaned, length after cleaning: {len(cleaned_content)} characters")

            # Use tested parameters for conversion
            pypandoc.convert_text(
                cleaned_content,
                'docx',
                format='markdown',  # Base markdown format
                outputfile=output_file,
                extra_args=extra_args
            )
            logger.info("✅ pypandoc conversion completed")

            logger.info("📖 Reading generated docx file...")
            # Read the generated docx file
            with open(output_file, 'rb') as f:
                docx_content = f.read()
            logger.info(f"✅ File read completed, size: {len(docx_content)} bytes")

            logger.info("🗑️ Cleaning up temporary file...")
            # Clean up temporary file
            os.unlink(output_file)
            logger.info("✅ Temporary file cleaned")

            return docx_content
        except Exception as e:
            logger.error(f"❌ Word document generation failed: {e}", exc_info=True)
            raise Exception(f"Failed to generate Word document: {e}")
    
    
    def generate_pdf_report(self, results: Dict[str, Any]) -> bytes:
        """Generate PDF format report"""

        logger.info("📊 Starting PDF document generation...")

        if not self.pandoc_available:
            logger.error("❌ Pandoc is not available")
            raise Exception("Pandoc is not available, cannot generate PDF document. Please install pandoc or use Markdown format for export.")

        # First generate markdown content
        logger.info("📝 Generating Markdown content...")
        md_content = self.generate_markdown_report(results)
        logger.info(f"✅ Markdown content generated, length: {len(md_content)} characters")

        # Simplified PDF engine list, prioritize the most likely successful one
        pdf_engines = [
            ('wkhtmltopdf', 'HTML to PDF engine, recommended installation'),
            ('weasyprint', 'Modern HTML to PDF engine'),
            (None, 'Use pandoc default engine, let pandoc choose')  # Do not specify engine, let pandoc choose
        ]

        last_error = None

        for engine_info in pdf_engines:
            engine, description = engine_info
            try:
                # Create a temporary file for PDF output
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    output_file = tmp_file.name

                # Use parameters to disable YAML parsing (consistent with Word export)
                extra_args = ['--from=markdown-yaml_metadata_block']

                # If an engine is specified, add engine parameters
                if engine:
                    extra_args.append(f'--pdf-engine={engine}')
                    logger.info(f"🔧 Using PDF engine: {engine}")
                else:
                    logger.info(f"🔧 Using default PDF engine")

                logger.info(f"🔧 PDF parameters: {extra_args}")

                # Clean content to avoid YAML parsing issues (consistent with Word export)
                cleaned_content = self._clean_markdown_for_pandoc(md_content)

                # Use pypandoc to convert markdown to PDF - disable YAML parsing
                pypandoc.convert_text(
                    cleaned_content,
                    'pdf',
                    format='markdown',  # Base markdown format
                    outputfile=output_file,
                    extra_args=extra_args
                )

                # Check if the file was generated and has content
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    # Read the generated PDF file
                    with open(output_file, 'rb') as f:
                        pdf_content = f.read()

                    # Clean up temporary file
                    os.unlink(output_file)

                    logger.info(f"✅ PDF generation successful, using engine: {engine or 'Default'}")
                    return pdf_content
                else:
                    raise Exception("PDF file generation failed or is empty")

            except Exception as e:
                last_error = str(e)
                logger.error(f"PDF engine {engine or 'Default'} failed: {e}")

                # Clean up potentially existing temporary file
                try:
                    if 'output_file' in locals() and os.path.exists(output_file):
                        os.unlink(output_file)
                except:
                    pass

                continue

        # If all engines fail, provide detailed error information and solutions
        error_msg = f"""PDF generation failed, last error: {last_error}

Possible solutions:
1. Install wkhtmltopdf (recommended):
   Windows: choco install wkhtmltopdf
   macOS: brew install wkhtmltopdf
   Linux: sudo apt-get install wkhtmltopdf

2. Install LaTeX:
   Windows: choco install miktex
   macOS: brew install mactex
   Linux: sudo apt-get install texlive-full

3. Use Markdown or Word format for export as an alternative
"""
        raise Exception(error_msg)
    
    def export_report(self, results: Dict[str, Any], format_type: str) -> Optional[bytes]:
        """Export report in specified format"""

        logger.info(f"🚀 Starting report export: format={format_type}")
        logger.info(f"📊 Export status check:")
        logger.info(f"  - export_available: {self.export_available}")
        logger.info(f"  - pandoc_available: {self.pandoc_available}")
        logger.info(f"  - is_docker: {self.is_docker}")

        if not self.export_available:
            logger.error("❌ Export functionality is not available")
            st.error("❌ Export functionality is not available, please install necessary dependencies")
            return None

        try:
            logger.info(f"🔄 Starting generation of {format_type} format report...")

            if format_type == 'markdown':
                logger.info("📝 Generating Markdown report...")
                content = self.generate_markdown_report(results)
                logger.info(f"✅ Markdown report generated successfully, length: {len(content)} characters")
                return content.encode('utf-8')

            elif format_type == 'docx':
                logger.info("📄 Generating Word document...")
                if not self.pandoc_available:
                    logger.error("❌ pandoc is not available, cannot generate Word document")
                    st.error("❌ pandoc is not available, cannot generate Word document")
                    return None
                content = self.generate_docx_report(results)
                logger.info(f"✅ Word document generated successfully, size: {len(content)} bytes")
                return content

            elif format_type == 'pdf':
                logger.info("📊 Generating PDF document...")
                if not self.pandoc_available:
                    logger.error("❌ pandoc is not available, cannot generate PDF document")
                    st.error("❌ pandoc is not available, cannot generate PDF document")
                    return None
                content = self.generate_pdf_report(results)
                logger.info(f"✅ PDF document generated successfully, size: {len(content)} bytes")
                return content

            else:
                logger.error(f"❌ Unsupported export format: {format_type}")
                st.error(f"❌ Unsupported export format: {format_type}")
                return None

        except Exception as e:
            logger.error(f"❌ Export failed: {str(e)}", exc_info=True)
            st.error(f"❌ Export failed: {str(e)}")
            return None


# Create global exporter instance
report_exporter = ReportExporter()


def render_export_buttons(results: Dict[str, Any]):
    """Render export buttons"""

    if not results:
        return

    st.markdown("---")
    st.subheader("📤 Export Report")

    # Check if export functionality is available
    if not report_exporter.export_available:
        st.warning("⚠️ Export functionality requires additional dependency packages")
        st.code("pip install pypandoc markdown")
        return

    # Check if pandoc is available
    if not report_exporter.pandoc_available:
        st.warning("⚠️ Word and PDF export requires pandoc tool")
        st.info("💡 You can still use Markdown format for export")

    # Display Docker environment status
    if report_exporter.is_docker:
        if DOCKER_ADAPTER_AVAILABLE:
            docker_status = get_docker_status_info()
            if docker_status['dependencies_ok'] and docker_status['pdf_test_ok']:
                st.success("🐳 Docker environment PDF support enabled")
            else:
                st.warning(f"🐳 Docker environment PDF support abnormal: {docker_status['dependency_message']}")
        else:
            st.warning("🐳 Docker environment detected, but adapter is not available")

        with st.expander("📖 How to install pandoc"):
            st.markdown("""
            **Windows users:**
            ```bash
            # Use Chocolatey (recommended)
            choco install pandoc

            # Or download and install
            # https://github.com/jgm/pandoc/releases
            ```

            **Or use Python to automatically download:**
            ```python
            import pypandoc

            pypandoc.download_pandoc()
            ```
            """)

        # In Docker environment, even if pandoc has issues, show all buttons for users to try
        pass
    
    # Generate filename
    stock_symbol = results.get('stock_symbol', 'analysis')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Export Markdown", help="Export as Markdown format"):
            logger.info(f"🖱️ [EXPORT] User clicked Markdown export button - Stock: {stock_symbol}")
            logger.info(f"🖱️ User clicked Markdown export button - Stock: {stock_symbol}")
            content = report_exporter.export_report(results, 'markdown')
            if content:
                filename = f"{stock_symbol}_analysis_{timestamp}.md"
                logger.info(f"✅ [EXPORT] Markdown export successful, filename: {filename}")
                logger.info(f"✅ Markdown export successful, filename: {filename}")
                st.download_button(
                    label="📥 Download Markdown",
                    data=content,
                    file_name=filename,
                    mime="text/markdown"
                )
            else:
                logger.error(f"❌ [EXPORT] Markdown export failed, content is empty")
                logger.error("❌ Markdown export failed, content is empty")
    
    with col2:
        if st.button("📝 Export Word", help="Export as Word document format"):
            logger.info(f"🖱️ [EXPORT] User clicked Word export button - Stock: {stock_symbol}")
            logger.info(f"🖱️ User clicked Word export button - Stock: {stock_symbol}")
            with st.spinner("Generating Word document, please wait..."):
                try:
                    logger.info(f"🔄 [EXPORT] Starting Word export process...")
                    logger.info("🔄 Starting Word export process...")
                    content = report_exporter.export_report(results, 'docx')
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.docx"
                        logger.info(f"✅ [EXPORT] Word export successful, filename: {filename}, size: {len(content)} bytes")
                        logger.info(f"✅ Word export successful, filename: {filename}, size: {len(content)} bytes")
                        st.success("✅ Word document generated successfully!")
                        st.download_button(
                            label="📥 Download Word",
                            data=content,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        logger.error(f"❌ [EXPORT] Word export failed, content is empty")
                        logger.error("❌ Word export failed, content is empty")
                        st.error("❌ Word document generation failed")
                except Exception as e:
                    logger.error(f"❌ [EXPORT] Word export exception: {str(e)}")
                    logger.error(f"❌ Word export exception: {str(e)}", exc_info=True)
                    st.error(f"❌ Word document generation failed: {str(e)}")

                    # Display detailed error information
                    with st.expander("🔍 View detailed error information"):
                        st.text(str(e))

                    # Provide solutions
                    with st.expander("💡 Solutions"):
                        st.markdown("""
                        **Word export requires pandoc tool, please check:**

                        1. **Docker environment**: Rebuild the image to ensure pandoc is included
                        2. **Local environment**: Install pandoc
                        ```bash
                        # Windows
                        choco install pandoc

                        # macOS
                        brew install pandoc

                        # Linux
                        sudo apt-get install pandoc
                        ```

                        3. **Alternative**: Use Markdown format for export
                        """)
    
    with col3:
        if st.button("📊 Export PDF", help="Export as PDF format (requires additional tools)"):
            logger.info(f"🖱️ User clicked PDF export button - Stock: {stock_symbol}")
            with st.spinner("Generating PDF, please wait..."):
                try:
                    logger.info("🔄 Starting PDF export process...")
                    content = report_exporter.export_report(results, 'pdf')
                    if content:
                        filename = f"{stock_symbol}_analysis_{timestamp}.pdf"
                        logger.info(f"✅ PDF export successful, filename: {filename}, size: {len(content)} bytes")
                        st.success("✅ PDF generated successfully!")
                        st.download_button(
                            label="📥 Download PDF",
                            data=content,
                            file_name=filename,
                            mime="application/pdf"
                        )
                    else:
                        logger.error("❌ PDF export failed, content is empty")
                        st.error("❌ PDF generation failed")
                except Exception as e:
                    logger.error(f"❌ PDF export exception: {str(e)}", exc_info=True)
                    st.error(f"❌ PDF generation failed")

                    # Display detailed error information
                    with st.expander("🔍 View detailed error information"):
                        st.text(str(e))

                    # Provide solutions
                    with st.expander("💡 Solutions"):
                        st.markdown("""
                        **PDF export requires additional tools, please choose one of the following options:**

                        **Option 1: Install wkhtmltopdf (recommended)**
                        ```bash
                        # Windows
                        choco install wkhtmltopdf

                        # macOS
                        brew install wkhtmltopdf

                        # Linux
                        sudo apt-get install wkhtmltopdf
                        ```

                        **Option 2: Install LaTeX**
                        ```bash
                        # Windows
                        choco install miktex

                        # macOS
                        brew install mactex

                        # Linux
                        sudo apt-get install texlive-full
                        ```

                        **Option 3: Use alternative formats**
                        - 📄 Markdown format - lightweight, high compatibility
                        - 📝 Word format - suitable for further editing
                        """)

                    # Suggest using other formats
                    st.info("💡 Suggestion: You can first export to Markdown or Word format, then use other tools to convert to PDF")
    
 