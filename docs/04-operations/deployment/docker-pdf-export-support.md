# Docker 环境 PDF 导出支持

## 📋 概述

TradingAgents-CN 的 Docker 镜像已经内置了完整的 PDF 导出支持，包括：

- ✅ **WeasyPrint** - 推荐的 PDF 生成工具（纯 Python 实现）
- ✅ **pdfkit + wkhtmltopdf** - 备选的 PDF 生成工具
- ✅ **Pandoc** - 回退方案
- ✅ **中文字体支持** - Noto Sans CJK

---

## 🚀 快速开始

### 方法 1: 使用预构建镜像（推荐）

如果你使用的是官方发布的 Docker 镜像，PDF 导出功能已经内置，无需额外配置。

```bash
# 拉取镜像
docker pull tradingagents/tradingagents-cn:latest

# 启动服务
docker-compose up -d

# 查看日志，确认 PDF 工具可用
docker-compose logs backend | grep -E "WeasyPrint|pdfkit|Pandoc"
```

应该看到：

```
✅ WeasyPrint 可用（推荐的 PDF 生成工具）
✅ pdfkit + wkhtmltopdf 可用
✅ Pandoc 可用
```

---

### 方法 2: 自己构建镜像

如果你需要自己构建镜像：

#### Linux/macOS

```bash
# 使用构建脚本（推荐）
chmod +x scripts/build_docker_with_pdf.sh
./scripts/build_docker_with_pdf.sh --build

# 或手动构建
docker build -f Dockerfile.backend -t tradingagents-backend:latest .
```

#### Windows

```powershell
# 使用构建脚本（推荐）
.\scripts\build_docker_with_pdf.ps1 -Build

# 或手动构建
docker build -f Dockerfile.backend -t tradingagents-backend:latest .
```

---

## 🔧 技术实现

### Dockerfile 配置

`Dockerfile.backend` 中已经包含了所有必需的依赖：

#### 1. 系统依赖

```dockerfile
# WeasyPrint 依赖
libcairo2
libpango-1.0-0
libpangocairo-1.0-0
libgdk-pixbuf2.0-0
libffi-dev
shared-mime-info

# wkhtmltopdf（从官方下载）
wkhtmltox_0.12.6.1-3.bookworm_${ARCH}.deb

# Pandoc（从 GitHub 下载）
pandoc-3.8.2.1-1-${ARCH}.deb

# 中文字体
fonts-noto-cjk
```

#### 2. Python 依赖

```dockerfile
RUN pip install --prefer-binary weasyprint pdfkit -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## ✅ 验证 PDF 导出功能

### 方法 1: 使用测试脚本

#### Linux/macOS

```bash
./scripts/build_docker_with_pdf.sh --test
```

#### Windows

```powershell
.\scripts\build_docker_with_pdf.ps1 -Test
```

---

### 方法 2: 手动验证

#### 1. 启动容器

```bash
docker run --rm -d \
    --name tradingagents-test \
    -p 8000:8000 \
    tradingagents-backend:latest
```

#### 2. 检查 WeasyPrint

```bash
docker exec tradingagents-test python -c "
import weasyprint
print('✅ WeasyPrint 已安装')
weasyprint.HTML(string='<html><body>测试中文</body></html>').write_pdf()
print('✅ WeasyPrint 可用')
"
```

#### 3. 检查 pdfkit

```bash
docker exec tradingagents-test python -c "
import pdfkit
print('✅ pdfkit 已安装')
pdfkit.configuration()
print('✅ pdfkit + wkhtmltopdf 可用')
"
```

#### 4. 检查 Pandoc

```bash
docker exec tradingagents-test pandoc --version
```

#### 5. 检查 wkhtmltopdf

```bash
docker exec tradingagents-test wkhtmltopdf --version
```

#### 6. 停止容器

```bash
docker stop tradingagents-test
```

---

## 📊 PDF 生成工具优先级

在 Docker 环境中，系统会按以下优先级自动选择 PDF 生成工具：

1. **WeasyPrint**（优先）
   - ✅ 纯 Python 实现
   - ✅ 中文支持最好
   - ✅ 表格分页控制最好
   - ✅ 无需外部依赖

2. **pdfkit + wkhtmltopdf**（备选）
   - ✅ 渲染效果好
   - ✅ 中文支持良好
   - ✅ 支持复杂的 HTML/CSS

3. **Pandoc**（回退）
   - ⚠️ 仅作为最后的回退方案
   - ⚠️ 中文竖排问题难以解决

---

## 🐛 常见问题

### 问题 1: WeasyPrint 不可用

**现象**：
```
❌ WeasyPrint 不可用: cannot load library 'libcairo.so.2'
```

**原因**：缺少 Cairo 库

**解决方案**：
确保 Dockerfile 中包含以下依赖：
```dockerfile
libcairo2 \
libpango-1.0-0 \
libpangocairo-1.0-0 \
libgdk-pixbuf2.0-0
```

---

### 问题 2: pdfkit 找不到 wkhtmltopdf

**现象**：
```
❌ pdfkit 不可用: No wkhtmltopdf executable found
```

**原因**：wkhtmltopdf 未安装或不在 PATH 中

**解决方案**：
确保 Dockerfile 中正确安装了 wkhtmltopdf：
```dockerfile
wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_${ARCH}.deb && \
apt-get install -y --no-install-recommends ./wkhtmltox_0.12.6.1-3.bookworm_${ARCH}.deb
```

---

### 问题 3: 中文字体显示为方框

**现象**：PDF 中的中文显示为方框 □□□

**原因**：缺少中文字体

**解决方案**：
确保 Dockerfile 中安装了中文字体：
```dockerfile
fonts-noto-cjk
```

并更新字体缓存：
```dockerfile
fc-cache -fv
```

---

### 问题 4: 镜像构建失败

**现象**：
```
ERROR: failed to solve: process "/bin/sh -c ..." did not complete successfully
```

**可能原因**：
1. 网络问题（无法下载 pandoc 或 wkhtmltopdf）
2. 架构不匹配
3. 依赖冲突

**解决方案**：

1. **检查网络连接**：
   ```bash
   # 测试是否能访问 GitHub
   curl -I https://github.com
   ```

2. **使用国内镜像**：
   Dockerfile 已经配置了清华镜像：
   ```dockerfile
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

3. **检查架构**：
   ```bash
   # 查看当前架构
   uname -m
   
   # 确保 TARGETARCH 正确传递
   docker build --build-arg TARGETARCH=amd64 ...
   ```

4. **清理缓存重新构建**：
   ```bash
   docker build --no-cache -f Dockerfile.backend -t tradingagents-backend:latest .
   ```

---

## 📈 性能优化

### 1. 使用多阶段构建（可选）

如果镜像太大，可以考虑使用多阶段构建：

```dockerfile
# 构建阶段
FROM python:3.10-slim as builder
# ... 安装依赖 ...

# 运行阶段
FROM python:3.10-slim
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# ... 复制必需文件 ...
```

### 2. 减小镜像大小

当前优化措施：
- ✅ 使用 `python:3.10-slim` 基础镜像
- ✅ 使用 `--no-install-recommends` 减少不必要的依赖
- ✅ 清理 apt 缓存：`rm -rf /var/lib/apt/lists/*`
- ✅ 使用 `--prefer-binary` 避免从源码编译

### 3. 加速构建

- ✅ 使用清华镜像加速 pip 下载
- ✅ 合理安排 Dockerfile 层级，利用缓存
- ✅ 使用 BuildKit：`DOCKER_BUILDKIT=1 docker build ...`

---

## 🔍 调试技巧

### 1. 进入容器调试

```bash
# 启动容器
docker run --rm -it tradingagents-backend:latest bash

# 或进入运行中的容器
docker exec -it <container_id> bash
```

### 2. 查看日志

```bash
# 查看容器日志
docker logs <container_id>

# 实时查看日志
docker logs -f <container_id>

# 使用 docker-compose
docker-compose logs -f backend
```

### 3. 测试 PDF 生成

在容器内运行：

```python
from app.utils.report_exporter import ReportExporter

exporter = ReportExporter()
print(f"WeasyPrint: {exporter.weasyprint_available}")
print(f"pdfkit: {exporter.pdfkit_available}")
print(f"Pandoc: {exporter.pandoc_available}")
```

---

## 📚 相关文档

- [PDF 导出功能使用指南](../guides/pdf_export_guide.md)
- [PDF 工具安装指南](../guides/installation/pdf_tools.md)
- [Windows Cairo 库修复指南](../troubleshooting/windows_cairo_fix.md)
- [Docker 快速开始](../../DOCKER_QUICKSTART.md)

---

## 🆘 获取帮助

如果遇到问题：

1. 查看容器日志
2. 运行测试脚本验证 PDF 工具
3. 查看相关文档
4. 在 GitHub 提交 Issue

---

## ✅ 总结

Docker 环境的 PDF 导出功能已经完全配置好了：

- ✅ **WeasyPrint** - 最推荐，中文支持最好
- ✅ **pdfkit + wkhtmltopdf** - 备选方案，效果也很好
- ✅ **Pandoc** - 回退方案
- ✅ **中文字体** - 完整支持

只需要构建镜像并启动服务，就可以直接使用 PDF 导出功能了！🎉

