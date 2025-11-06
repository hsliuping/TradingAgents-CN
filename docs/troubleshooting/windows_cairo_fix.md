# Windows Cairo 库缺失问题修复指南

## 🐛 问题描述

在 Windows 上使用 WeasyPrint 导出 PDF 时，出现以下错误：

```
no library called "cairo-2" was found
no library called "cairo" was found
no library called "libcairo-2" was found
cannot load library 'libcairo.so.2': error 0x7e
cannot load library 'libcairo.2.dylib': error 0x7e
cannot load library 'libcairo-2.dll': error 0x7e
```

## 🔍 原因分析

WeasyPrint 依赖 Cairo 图形库来渲染 PDF。在 Windows 上，Cairo 库不会自动安装，需要手动安装 GTK3 运行时。

---

## ✅ 解决方案

### 方案 1: 安装 GTK3 运行时（推荐）

这是最彻底的解决方案，安装后 WeasyPrint 就能正常工作。

#### 步骤 1: 下载 GTK3 运行时

访问以下地址下载最新版本：

**下载地址**: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

选择文件：`gtk3-runtime-x.x.x-x-x-x-ts-win64.exe`

例如：`gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe`

#### 步骤 2: 安装 GTK3 运行时

1. 双击下载的 `.exe` 文件
2. 按照安装向导进行安装
3. **重要**: 选择"Add to PATH"选项（添加到系统路径）
4. 完成安装

#### 步骤 3: 重启终端

关闭所有终端窗口，重新打开一个新的终端。

#### 步骤 4: 验证安装

```bash
# 重启后端服务
python -m uvicorn app.main:app --reload
```

查看日志，应该看到：

```
✅ WeasyPrint 可用（推荐的 PDF 生成工具）
```

#### 步骤 5: 测试 PDF 导出

1. 打开前端界面
2. 生成一份分析报告
3. 点击"导出" → "PDF"
4. 应该能成功下载 PDF 文件

---

### 方案 2: 使用 pdfkit（替代方案）

如果不想安装 GTK3，可以使用 pdfkit 作为替代方案。

#### 步骤 1: 安装 pdfkit

```bash
pip install pdfkit
```

#### 步骤 2: 下载并安装 wkhtmltopdf

**下载地址**: https://wkhtmltopdf.org/downloads.html

选择 Windows 版本：`wkhtmltox-x.x.x_msvc2015-win64.exe`

#### 步骤 3: 安装 wkhtmltopdf

1. 双击下载的 `.exe` 文件
2. 按照安装向导进行安装
3. 默认安装路径：`C:\Program Files\wkhtmltopdf`
4. 完成安装

#### 步骤 4: 重启后端服务

```bash
python -m uvicorn app.main:app --reload
```

查看日志，应该看到：

```
✅ pdfkit + wkhtmltopdf 可用
```

#### 步骤 5: 测试 PDF 导出

系统会自动使用 pdfkit 生成 PDF。

---

### 方案 3: 使用 Pandoc（最后的回退方案）

如果上述两个方案都不可行，可以使用 Pandoc。

#### 步骤 1: 下载并安装 Pandoc

**下载地址**: https://pandoc.org/installing.html

选择 Windows 版本：`pandoc-x.x.x-windows-x86_64.msi`

#### 步骤 2: 安装 Pandoc

1. 双击下载的 `.msi` 文件
2. 按照安装向导进行安装
3. 完成安装

#### 步骤 3: 重启后端服务

```bash
python -m uvicorn app.main:app --reload
```

**注意**: Pandoc 方案可能仍然存在中文竖排问题，不推荐作为首选方案。

---

## 🎯 推荐方案对比

| 方案 | 安装难度 | 中文支持 | 表格分页 | 推荐度 |
|------|---------|---------|---------|--------|
| GTK3 + WeasyPrint | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| wkhtmltopdf + pdfkit | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Pandoc | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ |

---

## 🔍 验证当前可用的工具

在 Python 中运行以下代码：

```python
from app.utils.report_exporter import ReportExporter

exporter = ReportExporter()
print(f"WeasyPrint 可用: {exporter.weasyprint_available}")
print(f"pdfkit 可用: {exporter.pdfkit_available}")
print(f"Pandoc 可用: {exporter.pandoc_available}")
```

或查看后端启动日志：

```
✅ WeasyPrint 可用（推荐的 PDF 生成工具）
✅ pdfkit + wkhtmltopdf 可用
✅ Pandoc 可用
```

---

## 🐛 常见问题

### 问题 1: 安装 GTK3 后仍然报错

**解决方案**:
1. 确认 GTK3 已添加到系统 PATH
2. 重启所有终端窗口
3. 重启后端服务
4. 如果仍然不行，重启电脑

### 问题 2: wkhtmltopdf 找不到

**解决方案**:
1. 确认 wkhtmltopdf 已安装
2. 检查是否在 PATH 中：
   ```bash
   wkhtmltopdf --version
   ```
3. 如果不在 PATH 中，手动添加到系统环境变量

### 问题 3: 所有方案都不可用

**解决方案**:
1. 运行自动安装脚本：
   ```bash
   python scripts/setup/install_pdf_tools.py
   ```
2. 按照脚本提示进行安装
3. 查看详细的错误信息

---

## 📊 快速决策流程图

```
需要导出 PDF
    ↓
是否愿意安装 GTK3？
    ↓
是 → 安装 GTK3 + 使用 WeasyPrint（推荐）
    ↓
    ✅ 最佳效果
    
否 → 是否愿意安装 wkhtmltopdf？
    ↓
    是 → 安装 wkhtmltopdf + 使用 pdfkit
        ↓
        ✅ 良好效果
    
    否 → 使用 Pandoc（回退方案）
        ↓
        ⚠️ 可能有中文竖排问题
```

---

## 💡 最佳实践

1. **优先选择 GTK3 + WeasyPrint**
   - 效果最好
   - 中文支持最完善
   - 表格分页控制最好

2. **备选 wkhtmltopdf + pdfkit**
   - 如果不想安装 GTK3
   - 效果也很好

3. **避免使用 Pandoc**
   - 仅作为最后的回退方案
   - 中文竖排问题难以解决

---

## 🆘 获取更多帮助

如果以上方案都无法解决问题：

1. 查看完整的[PDF 导出指南](../guides/pdf_export_guide.md)
2. 查看[安装指南](../guides/installation/pdf_tools.md)
3. 运行诊断脚本：
   ```bash
   python scripts/setup/install_pdf_tools.py
   ```
4. 在 GitHub 提交 Issue，附上：
   - 错误日志
   - 操作系统版本
   - Python 版本
   - 已安装的工具列表

---

## 📚 相关链接

- [GTK3 运行时下载](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)
- [wkhtmltopdf 下载](https://wkhtmltopdf.org/downloads.html)
- [Pandoc 下载](https://pandoc.org/installing.html)
- [WeasyPrint 官方文档](https://doc.courtbouillon.org/weasyprint/)
- [pdfkit 官方文档](https://github.com/JazzCore/python-pdfkit)

---

## ✅ 总结

**最简单的解决方案**：

1. 下载并安装 GTK3 运行时
2. 重启终端
3. 重启后端服务
4. 测试 PDF 导出

**如果不想安装 GTK3**：

1. 安装 pdfkit: `pip install pdfkit`
2. 下载并安装 wkhtmltopdf
3. 重启后端服务
4. 测试 PDF 导出

现在就试试吧！🚀

