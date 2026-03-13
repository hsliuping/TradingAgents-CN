import argparse
import html
import os
import subprocess
import tempfile
from collections import deque
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

from fpdf import FPDF

# 检查 pdfkit 是否可用
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False


def _read_project_version(repo_root: str) -> str:
    try:
        version_path = os.path.join(repo_root, "VERSION")
        with open(version_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return ""


def _list_markdown_files(root_dir: str) -> List[str]:
    md_files: List[str] = []
    for base, _dirs, files in os.walk(root_dir):
        for name in files:
            if name.lower().endswith(".md"):
                full_path = os.path.join(base, name)
                rel_path = os.path.relpath(full_path, root_dir)
                md_files.append(rel_path)
    md_files.sort()
    return md_files


def _markdown_to_html_fragment(md_text: str) -> str:
    try:
        import markdown  # type: ignore

        return markdown.markdown(
            md_text,
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
            ],
        )
    except Exception:
        return "<pre>" + html.escape(md_text) + "</pre>"


def _docs_to_html(docs_root: str, md_rel_paths: Sequence[str], title: str) -> str:
    sections: List[str] = []
    for rel_path in md_rel_paths:
        abs_path = os.path.join(docs_root, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                md_text = f.read()
        except Exception:
            continue

        fragment = _markdown_to_html_fragment(md_text)
        sections.append(
            "\n".join(
                [
                    '<section class="doc">',
                    f'<div class="doc-path">{html.escape(os.path.join("docs", "architecture", rel_path)).replace(os.sep, "/")}</div>',
                    fragment,
                    "</section>",
                    '<div class="page-break"></div>',
                ]
            )
        )

    body_html = "\n".join(sections) if sections else "<div>无可导出的 Markdown 文档</div>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN" dir="ltr">
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(title)}</title>
  <style>
    html {{
      direction: ltr;
    }}
    body {{
      font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI", sans-serif;
      line-height: 1.55;
      color: #111;
      margin: 15mm;
      background: #fff;
      font-size: 11pt;
    }}
    .doc-path {{
      font-weight: 700;
      color: #2c3e50;
      background: #f8f9fa;
      border-left: 4px solid #3498db;
      padding: 8px 12px;
      margin: 0 0 14px 0;
      page-break-after: avoid;
    }}
    h1, h2, h3, h4, h5, h6 {{
      page-break-after: avoid;
    }}
    pre, code {{
      font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Consolas", "Monaco", "Courier New", monospace;
      font-size: 9.5pt;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f6f8fa;
      padding: 10px 12px;
      border-radius: 6px;
      border: 1px solid #e5e7eb;
      overflow: visible;
    }}
    code {{
      background: #f6f8fa;
      padding: 0 4px;
      border-radius: 4px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      page-break-inside: auto;
    }}
    th, td {{
      border: 1px solid #ddd;
      padding: 6px 8px;
      vertical-align: top;
    }}
    thead {{
      display: table-header-group;
    }}
    tr {{
      page-break-inside: avoid;
      page-break-after: auto;
    }}
    img {{
      max-width: 100%;
      height: auto;
    }}
    .page-break {{
      page-break-before: always;
    }}
  </style>
</head>
<body>
{body_html}
</body>
</html>
"""


def _export_markdown_docs_pdf(output_path: str, docs_root: str) -> None:
    md_files = _list_markdown_files(docs_root)
    html_content = _docs_to_html(docs_root=docs_root, md_rel_paths=md_files, title="TradingAgentsCN 架构文档")

    if not PDFKIT_AVAILABLE:
        raise RuntimeError("pdfkit 不可用，无法生成文档 PDF。")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".html",
            delete=False,
            dir=docs_root,
        ) as f:
            tmp_path = f.name
            f.write(html_content)

        options = {
            "encoding": "UTF-8",
            "enable-local-file-access": None,
            "page-size": "A4",
            "margin-top": "15mm",
            "margin-right": "15mm",
            "margin-bottom": "15mm",
            "margin-left": "15mm",
            "quiet": "",
        }
        pdf_bytes = pdfkit.from_file(tmp_path, False, options=options)
        with open(output_path, "wb") as out_f:
            out_f.write(pdf_bytes)
        print(f"✅ 架构文档 PDF 生成成功: {output_path}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _run_git(args: Sequence[str], cwd: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout


def _list_files(repo_root: str, rev: str) -> List[str]:
    out = _run_git(["ls-tree", "-r", "--name-only", rev], cwd=repo_root)
    return [line.strip() for line in out.decode("utf-8", errors="replace").splitlines() if line.strip()]


def _read_file_at_rev(repo_root: str, rev: str, path: str) -> Optional[bytes]:
    spec = f"{rev}:{path}"
    proc = subprocess.run(
        ["git", "show", spec],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None
    data = proc.stdout
    if b"\x00" in data:
        return None
    return data


def _should_include_path(
    path: str,
    include_prefixes: Tuple[str, ...],
    include_root_files: Tuple[str, ...],
    exclude_prefixes: Tuple[str, ...],
    include_exts: Tuple[str, ...],
) -> bool:
    norm = path.replace("\\", "/")
    if any(norm.startswith(p) for p in exclude_prefixes):
        return False
    if norm in include_root_files:
        return True
    if not any(norm.startswith(p) for p in include_prefixes):
        return False
    _, ext = os.path.splitext(norm)
    if not ext:
        return False
    return ext.lower() in include_exts


def _iter_code_lines_for_file(path: str, content_text: str) -> Iterable[str]:
    yield f"FILE: {path}"
    yield "-" * 120
    for line in content_text.splitlines():
        yield line.rstrip("\n\r")
    yield ""


def _has_non_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def _is_emoji_char(ch: str) -> bool:
    o = ord(ch)
    if o in (0x200D, 0xFE0E, 0xFE0F):
        return True
    if 0x1F000 <= o <= 0x1FAFF:
        return True
    if 0x2600 <= o <= 0x27BF:
        return True
    if 0x2300 <= o <= 0x23FF:
        return True
    if 0x2B00 <= o <= 0x2BFF:
        return True
    return False


def _font_key_for_char(ch: str) -> str:
    if ord(ch) < 128:
        return "ascii"
    o = ord(ch)
    if _is_emoji_char(ch):
        return "emoji"
    if 0x2000 <= o <= 0x2BFF:
        return "symbol"
    return "unicode"


def _split_by_font(s: str) -> List[Tuple[str, str]]:
    if not s:
        return [("ascii", "")]
    parts: List[Tuple[str, str]] = []
    current_key = _font_key_for_char(s[0])
    buf = [s[0]]
    for ch in s[1:]:
        key = _font_key_for_char(ch)
        if key == current_key:
            buf.append(ch)
        else:
            parts.append((current_key, "".join(buf)))
            current_key = key
            buf = [ch]
    parts.append((current_key, "".join(buf)))
    return parts


class CodePDF(FPDF):
    def __init__(
        self,
        title: str,
        subtitle: str,
        font_ascii: str,
        font_unicode: Optional[str],
        font_emoji: Optional[str],
        font_symbol: Optional[str],
        font_size: int,
    ):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.title = title
        self.subtitle = subtitle
        self.font_ascii = font_ascii
        self.font_unicode = font_unicode
        self.font_emoji = font_emoji
        self.font_symbol = font_symbol
        self.font_size = font_size
        self.set_auto_page_break(auto=False)

    def header(self):
        self.set_font(self.font_ascii, size=10)
        self.cell(0, 6, self.title, new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.font_ascii, size=9)
        self.cell(0, 5, self.subtitle, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def footer(self):
        self.set_y(-12)
        self.set_font(self.font_ascii, size=9)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def write_code_line(self, line: str, max_chars: int, line_height: float):
        chunks = _wrap_line(line, max_chars=max_chars)
        for chunk in chunks:
            if self.get_y() + line_height > (self.h - self.b_margin):
                self.add_page()
            self.set_x(self.l_margin)
            for key, text in _split_by_font(chunk):
                if key == "emoji" and self.font_emoji:
                    self.set_font(self.font_emoji, size=self.font_size)
                elif key == "symbol" and self.font_symbol:
                    self.set_font(self.font_symbol, size=self.font_size)
                elif key == "unicode" and self.font_unicode:
                    self.set_font(self.font_unicode, size=self.font_size)
                else:
                    self.set_font(self.font_ascii, size=self.font_size)
                self.write(line_height, text)
            self.ln(line_height)


def _wrap_line(line: str, max_chars: int) -> List[str]:
    if not line:
        return [""]
    if len(line) <= max_chars:
        return [line]
    parts: List[str] = []
    start = 0
    while start < len(line):
        parts.append(line[start : start + max_chars])
        start += max_chars
    return parts


def _build_excerpt_lines(
    repo_root: str,
    rev: str,
    files: List[str],
    include_prefixes: Tuple[str, ...],
    include_root_files: Tuple[str, ...],
    exclude_prefixes: Tuple[str, ...],
    include_exts: Tuple[str, ...],
    excerpt_total_lines: int,
) -> Tuple[List[str], int]:
    head_count = excerpt_total_lines // 2
    tail_count = excerpt_total_lines - head_count

    first_lines: List[str] = []
    last_lines: deque[str] = deque(maxlen=tail_count)
    all_lines: Optional[List[str]] = []
    total = 0

    for path in files:
        if not _should_include_path(
            path,
            include_prefixes=include_prefixes,
            include_root_files=include_root_files,
            exclude_prefixes=exclude_prefixes,
            include_exts=include_exts,
        ):
            continue

        raw = _read_file_at_rev(repo_root, rev, path)
        if raw is None:
            continue

        text = raw.decode("utf-8", errors="replace")
        for line in _iter_code_lines_for_file(path, text):
            total += 1
            if all_lines is not None:
                all_lines.append(line)
                if len(all_lines) > excerpt_total_lines:
                    all_lines = None
            if len(first_lines) < head_count:
                first_lines.append(line)
            last_lines.append(line)

    if total <= excerpt_total_lines:
        return all_lines or first_lines, total

    overlap = max(0, head_count + tail_count - total)
    last_part = list(last_lines)
    if overlap:
        last_part = last_part[overlap:]

    combined = first_lines + ["", "…（中间省略）…", ""] + last_part
    return combined, total


def _code_to_html(lines: Iterable[str]) -> str:
    """将代码行转换为 HTML 格式，参考 report_exporter.py 的样式"""
    html_lines = []
    
    for line in lines:
        # 转义 HTML 特殊字符
        escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        # 检查是否是文件标题行
        if line.startswith("FILE:"):
            html_lines.append(f'<div class="file-header">{escaped_line}</div>')
        # 检查是否是分隔线
        elif line.startswith("-" * 10):
            html_lines.append(f'<div class="separator">{escaped_line}</div>')
        # 检查是否是省略提示
        elif "…（中间省略）…" in line:
            html_lines.append(f'<div class="omission">{escaped_line}</div>')
        else:
            html_lines.append(f'<div class="code-line">{escaped_line}</div>')
    
    html_content = "\n".join(html_lines)
    
    # 使用 report_exporter.py 的 HTML 模板和样式
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN" dir="ltr">
<head>
    <meta charset="UTF-8">
    <title>源代码导出</title>
    <style>
        /* 基础样式 - 确保文本方向正确 */
        html {{
            direction: ltr;
        }}

        body {{
            font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Apple Color Emoji", "Noto Color Emoji", "Consolas", "Monaco", "Courier New", monospace;
            line-height: 1.4;
            color: #333;
            margin: 15mm;
            padding: 0;
            background: white;
            direction: ltr;
            font-size: 9pt;
        }}

        /* 文件标题样式 */
        .file-header {{
            font-weight: bold;
            color: #2c3e50;
            background-color: #f8f9fa;
            padding: 8px 12px;
            margin: 15px 0 5px 0;
            border-left: 4px solid #3498db;
            page-break-after: avoid;
        }}

        /* 代码行样式 */
        .code-line {{
            white-space: pre;
            font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Apple Color Emoji", "Noto Color Emoji", "Consolas", "Monaco", "Courier New", monospace;
            margin: 1px 0;
            padding: 1px 5px;
            direction: ltr;
        }}

        /* 分隔线样式 */
        .separator {{
            border-top: 1px solid #ddd;
            margin: 8px 0;
            padding: 2px 0;
            color: #999;
            font-size: 8pt;
        }}

        /* 省略提示样式 */
        .omission {{
            text-align: center;
            color: #999;
            font-style: italic;
            margin: 10px 0;
            padding: 5px;
            background-color: #f8f9fa;
        }}

        /* 分页控制 */
        @page {{
            size: A4;
            margin: 15mm;

            @top-center {{
                content: "TradingAgentsCN 源代码";
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 10pt;
                color: #666;
            }}

            @bottom-center {{
                content: "第 " counter(page) " 页";
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 9pt;
                color: #666;
            }}
        }}

        /* 确保所有元素都正确显示 */
        * {{
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""
    
    return html_template


def _export_pdf(
    output_path: str,
    title: str,
    subtitle: str,
    lines: Iterable[str],
    max_chars: int,
    font_ascii: str,
    font_unicode: Optional[str],
    font_emoji: Optional[str],
    font_symbol: Optional[str],
    font_size: int,
):
    # 优先使用 pdfkit + wkhtmltopdf（参考 report_exporter.py 的实现）
    if PDFKIT_AVAILABLE:
        try:
            html_content = _code_to_html(lines)
            
            # pdfkit 配置选项（参考 report_exporter.py）
            options = {
                'encoding': 'UTF-8',
                'enable-local-file-access': None,
                'page-size': 'A4',
                'margin-top': '15mm',
                'margin-right': '15mm',
                'margin-bottom': '15mm',
                'margin-left': '15mm',
                'quiet': '',
            }
            
            # 生成 PDF
            pdf_bytes = pdfkit.from_string(html_content, False, options=options)
            
            # 保存到文件
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            
            print(f"✅ 使用 pdfkit 生成 PDF 成功: {output_path}")
            return
            
        except Exception as e:
            print(f"⚠️ pdfkit 生成失败，回退到 FPDF: {e}")
    
    # 回退到 FPDF 方式
    pdf = CodePDF(
        title=title,
        subtitle=subtitle,
        font_ascii=font_ascii,
        font_unicode=font_unicode,
        font_emoji=font_emoji,
        font_symbol=font_symbol,
        font_size=font_size,
    )

    if font_unicode:
        pdf.add_font(font_unicode, "", r"C:\Windows\Fonts\msyh.ttc")
    if font_emoji:
        pdf.add_font(font_emoji, "", r"C:\Windows\Fonts\seguiemj.ttf")
    if font_symbol:
        pdf.add_font(font_symbol, "", r"C:\Windows\Fonts\seguisym.ttf")

    pdf.add_page()
    line_height = (font_size * 0.42) + 1.8

    for line in lines:
        pdf.write_code_line(line, max_chars=max_chars, line_height=line_height)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    pdf.output(output_path)
    print(f"✅ 使用 FPDF 生成 PDF 成功: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rev", default="v1.0.0-preview")
    parser.add_argument("--out", default="")
    parser.add_argument("--mode", choices=["excerpt", "full"], default="excerpt")
    parser.add_argument("--pages", type=int, default=60)
    parser.add_argument("--lines-per-page", type=int, default=50)
    parser.add_argument("--max-chars", type=int, default=95)
    parser.add_argument("--font-size", type=int, default=8)
    parser.add_argument("--docs-architecture", action="store_true")
    parser.add_argument("--docs-dir", default="docs/architecture")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    version = _read_project_version(repo_root) or "unknown"

    if args.docs_architecture:
        if not args.out:
            now = datetime.now().strftime("%Y-%m-%d")
            args.out = os.path.join(repo_root, f"TradingAgentsCN_architecture_docs_{version}_{now}.pdf")
        docs_root = os.path.join(repo_root, args.docs_dir)
        _export_markdown_docs_pdf(output_path=args.out, docs_root=docs_root)
        return

    files = _list_files(repo_root, args.rev)

    include_prefixes = (
        "app/",
        "core/",
        "cli/",
        "tradingagents/",
        "frontend/src/",
        "scripts/",
    )
    include_root_files = (
        "main.py",
        "pyproject.toml",
        "requirements.txt",
        "requirements-lock.txt",
        "docker-compose.yml",
        "Dockerfile.backend",
        "Dockerfile.frontend",
        "VERSION",
    )
    exclude_prefixes = (
        "data/",
        "logs/",
        "release/",
        "frontend/dist/",
        "frontend/public/assets/",
        "assets/",
        "images/",
        "docs/",
        ".github/",
        ".streamlit/",
        "reports/",
    )
    include_exts = (
        ".py",
        ".ts",
        ".tsx",
        ".vue",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
        ".ps1",
        ".bat",
        ".html",
        ".css",
        ".scss",
        ".sql",
    )

    now = datetime.now().strftime("%Y-%m-%d")
    if not args.out:
        suffix = "60p" if args.mode == "excerpt" else "full"
        args.out = os.path.join(repo_root, f"TradingAgentsCN_source_code_{version}_{args.rev}_{suffix}_{now}.pdf")

    title = f"TradingAgentsCN Source Code Listing ({version})"
    subtitle = f"Version: {version} | Revision: {args.rev} | Generated: {now}"

    font_ascii = "Courier"
    font_unicode = "MSYH"
    font_emoji = "SEGOE_EMJ"
    font_symbol = "SEGOE_SYM"

    if args.mode == "full":
        def line_iter():
            for path in files:
                if not _should_include_path(
                    path,
                    include_prefixes=include_prefixes,
                    include_root_files=include_root_files,
                    exclude_prefixes=exclude_prefixes,
                    include_exts=include_exts,
                ):
                    continue
                raw = _read_file_at_rev(repo_root, args.rev, path)
                if raw is None:
                    continue
                text = raw.decode("utf-8", errors="replace")
                for line in _iter_code_lines_for_file(path, text):
                    yield line

        _export_pdf(
            output_path=args.out,
            title=title,
            subtitle=subtitle,
            lines=line_iter(),
            max_chars=args.max_chars,
            font_ascii=font_ascii,
            font_unicode=font_unicode,
            font_emoji=font_emoji,
            font_symbol=font_symbol,
            font_size=args.font_size,
        )
        return

    excerpt_total_lines = max(1, args.pages) * max(1, args.lines_per_page)
    lines, _total = _build_excerpt_lines(
        repo_root=repo_root,
        rev=args.rev,
        files=files,
        include_prefixes=include_prefixes,
        include_root_files=include_root_files,
        exclude_prefixes=exclude_prefixes,
        include_exts=include_exts,
        excerpt_total_lines=excerpt_total_lines,
    )

    _export_pdf(
        output_path=args.out,
        title=title,
        subtitle=subtitle,
        lines=lines,
        max_chars=args.max_chars,
        font_ascii=font_ascii,
        font_unicode=font_unicode,
        font_emoji=font_emoji,
        font_symbol=font_symbol,
        font_size=args.font_size,
    )


if __name__ == "__main__":
    main()
