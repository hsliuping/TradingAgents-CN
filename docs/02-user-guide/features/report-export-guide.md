# 📄 报告导出使用指南

## 📋 概述

TradingAgents-CN v0.1.7 引入了专业级的报告导出功能，支持将股票分析结果导出为Word、PDF、Markdown三种格式。本指南将详细介绍如何使用报告导出功能。

## 🎯 导出功能特色

### 支持格式

| 格式 | 扩展名 | 适用场景 | 特点 |
|------|--------|----------|------|
| **📝 Markdown** | .md | 在线查看、版本控制、技术文档 | 轻量级、可编辑、Git友好 |
| **📄 Word** | .docx | 商业报告、编辑修改、团队协作 | 专业格式、易编辑、兼容性好 |
| **📊 PDF** | .pdf | 正式发布、打印存档、客户交付 | 固定格式、专业外观、跨平台 |

### 技术特性

- ✅ **专业排版**: 自动格式化和美化
- ✅ **中文支持**: 完整的中文字体和排版
- ✅ **图表集成**: 支持表格和数据可视化
- ✅ **模板定制**: 可自定义报告模板
- ✅ **批量导出**: 支持多个报告同时导出

## 🚀 快速开始

### 前置条件

#### Docker环境 (推荐)
```bash
# Docker环境已预配置所有依赖
docker-compose up -d
```

#### 本地环境
```bash
# 安装Pandoc (文档转换引擎)
# Windows: 下载安装包 https://pandoc.org/installing.html
# Linux: sudo apt install pandoc
# macOS: brew install pandoc

# 安装wkhtmltopdf (PDF生成引擎)
# Windows: 下载安装包 https://wkhtmltopdf.org/downloads.html
# Linux: sudo apt install wkhtmltopdf
# macOS: brew install wkhtmltopdf

# 验证安装
pandoc --version
wkhtmltopdf --version
```

### 启用导出功能

```bash
# 在.env文件中配置
EXPORT_ENABLED=true
EXPORT_DEFAULT_FORMAT=word,pdf
EXPORT_OUTPUT_PATH=./exports
```

## 📊 使用指南

### 基础导出流程

#### 1. 完成股票分析
```bash
# 访问Web界面
http://localhost:8501

# 进行股票分析
# 1. 选择LLM模型
# 2. 输入股票代码 (如: 000001, AAPL)
# 3. 选择分析深度
# 4. 点击"开始分析"
# 5. 等待分析完成
```

#### 2. 导出报告
```bash
# 在分析结果页面
# 1. 滚动到页面底部
# 2. 找到"报告导出"部分
# 3. 选择导出格式:
#    - ☑️ Markdown
#    - ☑️ Word文档
#    - ☑️ PDF文档
# 4. 点击"导出报告"按钮
# 5. 等待生成完成
# 6. 点击下载链接
```

### 导出格式详解

#### 📝 Markdown导出

**特点**:
- 轻量级文本格式
- 支持版本控制
- 易于在线查看和编辑
- 适合技术文档和协作

**使用场景**:
```bash
# 适用于:
✅ 技术团队内部分享
✅ 版本控制和历史追踪
✅ 在线文档平台发布
✅ 进一步编辑和加工
```

**示例内容**:
```markdown
# 股票分析报告: 平安银行 (000001)

## 📊 基本信息
- **股票代码**: 000001
- **股票名称**: 平安银行
- **分析时间**: 2025-07-13 14:30:00
- **当前价格**: ¥12.45

## 📈 技术分析
### 趋势分析
当前股价处于上升通道中...
```

#### 📄 Word文档导出

**特点**:
- 专业商业文档格式
- 支持复杂排版和格式
- 易于编辑和修改
- 广泛的兼容性

**使用场景**:
```bash
# 适用于:
✅ 正式商业报告
✅ 客户交付文档
✅ 团队协作编辑
✅ 演示和汇报材料
```

**格式特性**:
- 📋 标准商业文档模板
- 🎨 专业排版和字体
- 📊 表格和图表支持
- 🔖 目录和页码
- 📝 页眉页脚

#### 📊 PDF文档导出

**特点**:
- 固定格式，跨平台一致
- 专业外观和排版
- 适合打印和存档
- 不易被修改

**使用场景**:
```bash
# 适用于:
✅ 正式发布和交付
✅ 打印和存档
✅ 客户演示
✅ 监管报告
```

**质量特性**:
- 🖨️ 高质量打印输出
- 📱 移动设备友好
- 🔒 内容保护
- 📏 标准页面尺寸 (A4)

## ⚙️ 高级配置

### 自定义导出设置

```bash
# .env 高级配置
# === 导出功能详细配置 ===
EXPORT_ENABLED=true
EXPORT_DEFAULT_FORMAT=word,pdf,markdown
EXPORT_OUTPUT_PATH=./exports
EXPORT_FILENAME_FORMAT={symbol}_analysis_{timestamp}

# === 格式转换配置 ===
PANDOC_PATH=/usr/bin/pandoc
WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf

# === 质量配置 ===
EXPORT_INCLUDE_DEBUG=false
EXPORT_WATERMARK=false
EXPORT_COMPRESS_PDF=true

# === Word导出配置 ===
WORD_TEMPLATE_PATH=./templates/report_template.docx
WORD_REFERENCE_DOC=./templates/reference.docx

# === PDF导出配置 ===
PDF_PAGE_SIZE=A4
PDF_MARGIN_TOP=2cm
PDF_MARGIN_BOTTOM=2cm
PDF_MARGIN_LEFT=2cm
PDF_MARGIN_RIGHT=2cm
```

### 自定义模板

#### Word模板定制
```bash
# 1. 创建模板目录
mkdir -p templates

# 2. 创建Word模板文件
# templates/report_template.docx
# - 设置标准样式
# - 定义页眉页脚
# - 配置字体和颜色

# 3. 配置模板路径
WORD_TEMPLATE_PATH=./templates/report_template.docx
```

#### PDF样式定制
```bash
# 创建CSS样式文件
# templates/pdf_style.css

body {
    font-family: "SimSun", serif;
    font-size: 12pt;
    line-height: 1.6;
    margin: 2cm;
}

h1 {
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 10px;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 20px 0;
}
```

## 🔧 故障排除

### 常见问题

#### 1. 导出按钮不显示

**原因**: 导出功能未启用

**解决方案**:
```bash
# 检查.env配置
EXPORT_ENABLED=true

# 重启应用
docker-compose restart web
# 或
streamlit run web/app.py
```

#### 2. Word导出失败

**原因**: Pandoc未安装或YAML冲突

**解决方案**:
```bash
# Docker环境 (自动修复)
docker-compose restart web

# 本地环境
# 1. 安装Pandoc
sudo apt install pandoc  # Linux
brew install pandoc      # macOS

# 2. 检查Pandoc版本
pandoc --version
```

#### 3. PDF导出失败

**原因**: wkhtmltopdf未安装或中文字体问题

**解决方案**:
```bash
# Docker环境 (已预配置)
docker logs TradingAgents-web

# 本地环境
# 1. 安装wkhtmltopdf
sudo apt install wkhtmltopdf  # Linux
brew install wkhtmltopdf      # macOS

# 2. 安装中文字体
sudo apt install fonts-wqy-zenhei  # Linux
```

#### 4. 文件下载失败

**原因**: 浏览器阻止下载或文件权限问题

**解决方案**:
```bash
# 1. 检查浏览器下载设置
# 2. 检查文件权限
chmod 755 exports/
chmod 644 exports/*.pdf

# 3. 手动下载
# 文件保存在 exports/ 目录中
```

### 性能优化

```bash
# 1. 启用并行导出
EXPORT_PARALLEL=true
EXPORT_MAX_WORKERS=3

# 2. 启用缓存
EXPORT_CACHE_ENABLED=true
EXPORT_CACHE_TTL=3600

# 3. 压缩输出
EXPORT_COMPRESS_PDF=true
EXPORT_OPTIMIZE_IMAGES=true
```

## 📊 批量导出

### 批量导出多个分析

```python
# 使用Python脚本批量导出
import os
from tradingagents.export.report_exporter import ReportExporter

# 初始化导出器
exporter = ReportExporter()

# 批量导出
symbols = ['000001', '600519', '000858', 'AAPL', 'TSLA']
for symbol in symbols:
    # 获取分析结果
    analysis_result = get_analysis_result(symbol)
    
    # 导出所有格式
    exporter.export_all_formats(
        analysis_result, 
        output_dir=f'exports/{symbol}'
    )
```

### 定时导出

```bash
# 创建定时任务
crontab -e

# 每日导出重要股票分析
0 18 * * 1-5 cd /path/to/TradingAgents-CN && python scripts/daily_export.py
```

## 📈 最佳实践

### 1. 文件命名规范
```bash
# 推荐命名格式
{股票代码}_{分析类型}_{日期}.{格式}

# 示例
000001_comprehensive_20250713.pdf
AAPL_technical_20250713.docx
600519_fundamental_20250713.md
```

### 2. 存储管理
```bash
# 定期清理旧文件
find exports/ -name "*.pdf" -mtime +30 -delete
find exports/ -name "*.docx" -mtime +30 -delete

# 压缩存档
tar -czf exports_archive_$(date +%Y%m).tar.gz exports/
```

### 3. 质量控制
```bash
# 导出前检查
✅ 分析结果完整性
✅ 数据准确性
✅ 格式配置正确
✅ 模板文件存在

# 导出后验证
✅ 文件生成成功
✅ 文件大小合理
✅ 内容格式正确
✅ 中文显示正常
```

---

## 📞 获取帮助

如果在使用报告导出功能时遇到问题：

- 🐛 [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)
- 💬 [GitHub Discussions](https://github.com/hsliuping/TradingAgents-CN/discussions)
- 📚 [Pandoc文档](https://pandoc.org/MANUAL.html)

---

*最后更新: 2025-07-13*  
*版本: cn-0.1.7*  
*贡献者: [@baiyuxiong](https://github.com/baiyuxiong)*
