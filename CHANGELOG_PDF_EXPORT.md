# PDF 导出功能改进 - 更新日志

## 📅 2025-11-05

### 🎯 问题描述

用户报告了 Markdown 转 PDF/Word 时的两个严重问题：

1. **中文文本竖排显示** - 部分中文文本被错误地显示为竖排（从上到下），而不是正常的横排（从左到右）
2. **表格跨页被截断** - 表格在页面边界被切成两半，内容显示不完整

### ✅ 解决方案

实现了一个**多层级的 PDF 生成方案**，彻底解决了上述问题。

---

## 🔧 技术改进

### 1. 新增 PDF 生成工具

系统现在支持三种 PDF 生成工具，按优先级自动选择：

#### ⭐ WeasyPrint（推荐）
- **优先级**: 1（最高）
- **优点**:
  - ✅ 纯 Python 实现，跨平台
  - ✅ **完美解决中文竖排问题**
  - ✅ 表格分页控制良好
  - ✅ CSS 样式支持完善
  - ✅ 无需外部依赖（Linux/macOS）
- **安装**: `pip install weasyprint`

#### 🔧 pdfkit + wkhtmltopdf
- **优先级**: 2
- **优点**:
  - ✅ 渲染效果好
  - ✅ **完美解决中文竖排问题**
  - ✅ 支持复杂的 HTML/CSS
- **安装**: `pip install pdfkit` + 安装 wkhtmltopdf

#### 📝 Pandoc（回退）
- **优先级**: 3（最低）
- **说明**: 仅作为最后的回退方案，中文竖排问题难以完全解决

---

### 2. 核心技术实现

#### Markdown → HTML → PDF 流程

```
分析报告数据
    ↓
生成 Markdown 内容
    ↓
转换为 HTML（添加样式）
    ↓
应用 CSS 样式（强制横排 + 表格分页控制）
    ↓
选择 PDF 生成工具
    ↓
┌─────────────────────────────────┐
│ 1. WeasyPrint（优先）            │
│    ✅ 完美解决中文竖排           │
│    ✅ 表格分页控制良好           │
├─────────────────────────────────┤
│ 2. pdfkit（备选）                │
│    ✅ 完美解决中文竖排           │
│    ✅ 渲染效果好                 │
├─────────────────────────────────┤
│ 3. Pandoc（回退）                │
│    ⚠️ 中文竖排问题难以解决       │
└─────────────────────────────────┘
    ↓
生成 PDF 文件
```

#### 关键 CSS 样式

```css
/* 强制横排显示 */
* {
    writing-mode: horizontal-tb !important;
    text-orientation: mixed !important;
    direction: ltr !important;
}

/* 表格分页控制 */
table {
    page-break-inside: auto;  /* 允许表格跨页 */
}

tr {
    page-break-inside: avoid;  /* 避免行中间分页 */
}

thead {
    display: table-header-group;  /* 表头在每页重复 */
}
```

---

## 📄 新增文件

### 1. 核心代码修改

- **`app/utils/report_exporter.py`**
  - 新增 `_markdown_to_html()` - Markdown 转 HTML
  - 新增 `_generate_pdf_with_weasyprint()` - WeasyPrint PDF 生成
  - 新增 `_generate_pdf_with_pdfkit()` - pdfkit PDF 生成
  - 修改 `generate_pdf_report()` - 多层级 PDF 生成策略

### 2. 安装和配置

- **`scripts/setup/install_pdf_tools.py`**
  - 自动安装脚本
  - 检测已安装的工具
  - 提供详细的安装指导

- **`pyproject.toml`**
  - 新增 `[pdf]` 可选依赖
  - 新增 `[pdf-full]` 完整依赖
  - 新增 `python-docx` 依赖

- **`requirements.txt`**
  - 新增 `weasyprint>=60.0`
  - 新增 `pdfkit>=1.0.0`
  - 新增 `python-docx>=0.8.11`

### 3. 文档

- **`docs/guides/pdf_export_guide.md`**
  - 完整的 PDF 导出使用指南
  - 工具对比和选择建议
  - 常见问题解决方案

- **`docs/guides/installation/pdf_tools.md`**
  - 详细的安装指南
  - 平台特定说明（Windows/macOS/Linux）
  - 验证和测试方法

- **`docs/troubleshooting/pdf_word_export_issues.md`**
  - 问题分析和解决方案
  - 测试方法
  - 故障排查步骤

---

## 🚀 使用方法

### 快速开始

1. **安装 WeasyPrint**（推荐）:
   ```bash
   pip install weasyprint
   ```

   或使用 pyproject.toml:
   ```bash
   pip install -e ".[pdf]"
   ```

2. **重启后端服务**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

3. **测试导出功能**:
   - 打开分析报告详情页
   - 点击"导出" → "PDF"
   - 系统会自动使用 WeasyPrint 生成 PDF
   - **不会再出现中文竖排问题！**

### 查看日志

成功安装后，日志会显示：

```
✅ WeasyPrint 可用（推荐的 PDF 生成工具）
✅ pdfkit + wkhtmltopdf 可用
✅ Pandoc 可用
📋 ReportExporter 初始化:
  - export_available: True
  - pandoc_available: True
  - weasyprint_available: True
  - pdfkit_available: True
```

导出时会显示：

```
📊 开始生成 PDF 文档...
🔧 使用 WeasyPrint 生成 PDF...
✅ WeasyPrint PDF 生成成功，大小: 123456 字节
```

---

## 📊 效果对比

| 问题 | Pandoc（旧方案） | WeasyPrint（新方案） |
|------|-----------------|---------------------|
| 中文竖排 | ❌ 经常出现 | ✅ 完全解决 |
| 表格分页 | ⚠️ 控制不佳 | ✅ 完美控制 |
| 安装难度 | ⚠️ 需要外部工具 | ✅ 纯 Python（Linux/macOS） |
| 中文字体 | ⚠️ 需要配置 | ✅ 自动支持 |
| 样式控制 | ⚠️ 有限 | ✅ 完全控制 |
| 推荐度 | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🔄 向后兼容性

- ✅ 完全向后兼容
- ✅ 如果没有安装新的 PDF 工具，会自动回退到 Pandoc
- ✅ 不影响现有的 Markdown 和 Word 导出功能
- ✅ 不需要修改前端代码

---

## 📚 相关文档

- [PDF 导出功能使用指南](docs/guides/pdf_export_guide.md)
- [PDF 工具安装指南](docs/guides/installation/pdf_tools.md)
- [故障排查指南](docs/troubleshooting/pdf_word_export_issues.md)
- [自动安装脚本](scripts/setup/install_pdf_tools.py)

---

## 💡 最佳实践

1. **优先使用 WeasyPrint**
   - 最可靠，中文支持最好
   - 无需外部依赖（Linux/macOS）

2. **备选 pdfkit**
   - 如果 WeasyPrint 不可用
   - 渲染效果好

3. **避免使用 Pandoc**
   - 仅作为最后的回退方案
   - 中文竖排问题难以解决

4. **测试导出功能**
   - 安装后立即测试
   - 检查中文显示是否正常
   - 检查表格分页是否正确

---

## 🐛 已知问题

### Windows 平台

- WeasyPrint 需要安装 GTK3 运行时
- 安装步骤见：[PDF 工具安装指南](docs/guides/installation/pdf_tools.md)

### 解决方案

如果 WeasyPrint 安装困难，可以使用 pdfkit 作为替代方案。

---

## 🎯 下一步计划

- [ ] 添加 PDF 导出的更多自定义选项（页眉、页脚、水印等）
- [ ] 支持批量导出多个报告
- [ ] 添加 PDF 导出的进度显示
- [ ] 优化大型报告的导出性能

---

## 🙏 致谢

感谢用户反馈的问题，帮助我们改进了 PDF 导出功能！

---

## 📞 获取帮助

如果遇到问题：

1. 查看[故障排查指南](docs/troubleshooting/pdf_word_export_issues.md)
2. 运行安装脚本检查依赖：`python scripts/setup/install_pdf_tools.py`
3. 查看日志输出
4. 在 GitHub 提交 Issue

