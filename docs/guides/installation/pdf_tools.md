# PDF 导出工具安装指南

## 🚀 快速安装

### 方法 1: 使用 pip（推荐）

安装 PDF 导出支持（包含 WeasyPrint 和 pdfkit）：

```bash
pip install -e ".[pdf]"
```

或者安装完整的 PDF 支持：

```bash
pip install -e ".[pdf-full]"
```

### 方法 2: 单独安装 WeasyPrint（最推荐）

```bash
pip install weasyprint
```

### 方法 3: 使用自动安装脚本

```bash
python scripts/setup/install_pdf_tools.py
```

---

## 📦 安装选项说明

### 选项 1: `[pdf]` - 基础 PDF 支持

```bash
pip install -e ".[pdf]"
```

**包含**：
- ✅ `weasyprint` - 推荐的 PDF 生成工具
- ✅ `pdfkit` - 备选的 PDF 生成工具

**适用场景**：
- 大多数用户
- 需要可靠的 PDF 导出功能

---

### 选项 2: `[pdf-full]` - 完整 PDF 支持

```bash
pip install -e ".[pdf-full]"
```

**包含**：
- ✅ `weasyprint`
- ✅ `pdfkit`
- ✅ 所有 PDF 相关工具

**适用场景**：
- 需要最完整的 PDF 支持
- 开发和测试环境

---

### 选项 3: 仅安装 WeasyPrint

```bash
pip install weasyprint
```

**优点**：
- ✅ 最简单
- ✅ 纯 Python 实现
- ✅ 中文支持最好
- ✅ 无需外部依赖（Linux/macOS）

**缺点**：
- ❌ Windows 需要 GTK3 运行时

---

## 🖥️ 平台特定说明

### Windows

#### WeasyPrint 安装

1. **安装 GTK3 运行时**（必需）：
   - 下载：https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   - 安装 `gtk3-runtime-x.x.x-x-x-x-ts-win64.exe`

2. **安装 WeasyPrint**：
   ```bash
   pip install weasyprint
   ```

#### pdfkit 安装

1. **安装 pdfkit**：
   ```bash
   pip install pdfkit
   ```

2. **安装 wkhtmltopdf**：
   - 下载：https://wkhtmltopdf.org/downloads.html
   - 安装 `wkhtmltopdf-x.x.x.exe`

---

### macOS

#### WeasyPrint 安装

```bash
# 直接安装（推荐）
pip install weasyprint
```

#### pdfkit 安装

```bash
# 1. 安装 pdfkit
pip install pdfkit

# 2. 安装 wkhtmltopdf
brew install wkhtmltopdf
```

---

### Linux (Ubuntu/Debian)

#### WeasyPrint 安装

```bash
# 安装系统依赖
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

# 安装 WeasyPrint
pip install weasyprint
```

#### pdfkit 安装

```bash
# 1. 安装 pdfkit
pip install pdfkit

# 2. 安装 wkhtmltopdf
sudo apt-get install -y wkhtmltopdf
```

---

### Linux (CentOS/RHEL)

#### WeasyPrint 安装

```bash
# 安装系统依赖
sudo yum install -y \
    python3-devel \
    cairo \
    pango \
    gdk-pixbuf2

# 安装 WeasyPrint
pip install weasyprint
```

#### pdfkit 安装

```bash
# 1. 安装 pdfkit
pip install pdfkit

# 2. 安装 wkhtmltopdf
sudo yum install -y wkhtmltopdf
```

---

## ✅ 验证安装

### 方法 1: 使用 Python

```python
# 检查 WeasyPrint
try:
    import weasyprint
    print("✅ WeasyPrint 已安装")
except ImportError:
    print("❌ WeasyPrint 未安装")

# 检查 pdfkit
try:
    import pdfkit
    pdfkit.configuration()
    print("✅ pdfkit + wkhtmltopdf 已安装")
except:
    print("❌ pdfkit 或 wkhtmltopdf 未安装")

# 检查 ReportExporter
from app.utils.report_exporter import ReportExporter
exporter = ReportExporter()
print(f"WeasyPrint 可用: {exporter.weasyprint_available}")
print(f"pdfkit 可用: {exporter.pdfkit_available}")
print(f"Pandoc 可用: {exporter.pandoc_available}")
```

### 方法 2: 使用安装脚本

```bash
python scripts/setup/install_pdf_tools.py
```

---

## 🐛 常见问题

### 问题 1: WeasyPrint 安装失败（Windows）

**错误信息**：
```
OSError: cannot load library 'gobject-2.0-0'
```

**解决方案**：
1. 安装 GTK3 运行时
2. 重启终端
3. 重新安装 WeasyPrint

---

### 问题 2: pdfkit 找不到 wkhtmltopdf

**错误信息**：
```
OSError: No wkhtmltopdf executable found
```

**解决方案**：
1. 确认 wkhtmltopdf 已安装
2. 检查是否在 PATH 中：
   ```bash
   wkhtmltopdf --version
   ```
3. 如果不在 PATH 中，手动指定路径（在代码中）

---

### 问题 3: WeasyPrint 缺少系统依赖（Linux）

**错误信息**：
```
ImportError: cannot import name 'HTML' from 'weasyprint'
```

**解决方案**：
安装系统依赖（见上面的 Linux 安装说明）

---

## 📊 推荐安装方案

### 方案 A: 最简单（推荐）

```bash
# 仅安装 WeasyPrint
pip install weasyprint
```

**优点**：
- ✅ 最简单
- ✅ 中文支持最好
- ✅ 无需外部工具（Linux/macOS）

**适用**：
- 大多数用户
- 只需要基本的 PDF 导出功能

---

### 方案 B: 最完整

```bash
# 安装所有 PDF 工具
pip install -e ".[pdf-full]"

# 然后安装外部工具
# Windows: 安装 GTK3 和 wkhtmltopdf
# macOS: brew install wkhtmltopdf
# Linux: sudo apt-get install wkhtmltopdf
```

**优点**：
- ✅ 最完整的支持
- ✅ 多个备选方案

**适用**：
- 开发环境
- 需要最高可靠性

---

### 方案 C: 使用自动脚本

```bash
# 运行自动安装脚本
python scripts/setup/install_pdf_tools.py
```

**优点**：
- ✅ 自动检测和安装
- ✅ 提供详细的安装指导

**适用**：
- 不确定如何安装
- 需要检查当前环境

---

## 🔄 更新依赖

如果已经安装了旧版本，可以更新：

```bash
# 更新 WeasyPrint
pip install --upgrade weasyprint

# 更新 pdfkit
pip install --upgrade pdfkit

# 更新所有依赖
pip install --upgrade -e ".[pdf-full]"
```

---

## 📚 相关文档

- [PDF 导出功能使用指南](../pdf_export_guide.md)
- [故障排查指南](../../troubleshooting/pdf_word_export_issues.md)
- [WeasyPrint 官方文档](https://doc.courtbouillon.org/weasyprint/)
- [pdfkit 官方文档](https://github.com/JazzCore/python-pdfkit)

---

## 💡 下一步

安装完成后：

1. **重启后端服务**
2. **测试 PDF 导出功能**
3. **查看日志确认使用的工具**

```bash
# 重启后端
python -m uvicorn app.main:app --reload

# 查看日志
# 应该看到：
# ✅ WeasyPrint 可用（推荐的 PDF 生成工具）
```

