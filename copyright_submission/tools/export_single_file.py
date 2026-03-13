#!/usr/bin/env python3
"""
专门用于导出单个文件的PDF生成脚本
"""

import os
import sys
from typing import List

# 添加脚本路径
sys.path.insert(0, 'scripts')

try:
    from export_source_code_pdf import _export_pdf, _code_to_html
    from fpdf import FPDF
    
    # 检查 pdfkit 是否可用
    try:
        import pdfkit
        PDFKIT_AVAILABLE = True
    except ImportError:
        PDFKIT_AVAILABLE = False
        
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def export_single_file_pdf(file_path: str, output_pdf: str):
    """导出单个文件到PDF"""
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 读取文件内容
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False
    
    # 准备内容行
    lines = []
    lines.append(f"FILE: {file_path}")
    lines.append("-" * 50)
    lines.extend(content.splitlines())
    lines.append("-" * 50)
    
    # 导出PDF
    try:
        if PDFKIT_AVAILABLE:
            # 使用 pdfkit 生成
            html_content = _code_to_html(lines)
            options = {
                'encoding': 'UTF-8',
                'page-size': 'A4', 
                'margin-top': '15mm',
                'margin-bottom': '15mm',
                'margin-left': '15mm',
                'margin-right': '15mm',
                'enable-local-file-access': None,
                'quiet': ''
            }
            pdf_bytes = pdfkit.from_string(html_content, False, options=options)
            with open(output_pdf, 'wb') as f:
                f.write(pdf_bytes)
            print(f"✅ 使用 pdfkit 生成单个文件PDF成功: {output_pdf}")
        else:
            # 回退到 FPDF
            from export_source_code_pdf import CodePDF
            pdf = CodePDF()
            pdf.set_auto_page_break(True, margin=15)
            pdf.add_page()
            
            for line in lines:
                pdf.multi_cell(0, 5, line)
            
            pdf.output(output_pdf)
            print(f"✅ 使用 FPDF 生成单个文件PDF成功: {output_pdf}")
            
        return True
        
    except Exception as e:
        print(f"❌ PDF生成失败: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python export_single_file.py <源文件> <输出PDF>")
        print("示例: python export_single_file.py test_chars_sample.py single_test.pdf")
        sys.exit(1)
    
    source_file = sys.argv[1]
    output_file = sys.argv[2]
    
    success = export_single_file_pdf(source_file, output_file)
    sys.exit(0 if success else 1)