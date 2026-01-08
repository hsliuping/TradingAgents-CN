# Docker 环境报告导出配置

本文档说明如何在 Docker 环境中配置和使用报告导出功能（PDF、Word、Markdown、JSON）。

## 📦 系统依赖

### Dockerfile.backend 已安装的依赖

```dockerfile
# 报告导出相关依赖
- pandoc          # Markdown 转换引擎（必需）
- wkhtmltopdf     # HTML 转 PDF 引擎（推荐）
- fontconfig      # 字体配置
- fonts-wqy-zenhei      # 文泉驿正黑（中文字体）
- fonts-wqy-microhei    # 文泉驿微米黑（中文字体）
- xfonts-*        # X Window 字体支持
```

### Python 依赖（pyproject.toml）

```toml
"pypandoc>=1.11"   # Pandoc Python 包装器
"markdown>=3.4.0"  # Markdown 解析器
```

## 🚀 构建和部署

### 1. 构建 Docker 镜像

```bash
# 本地构建
docker build -t hsliup/tradingagents-backend:latest -f Dockerfile.backend .

# 推送到 Docker Hub
docker push hsliup/tradingagents-backend:latest
```

### 2. 在服务器上部署

```bash
# 拉取最新镜像
docker-compose -f docker-compose.hub.nginx.yml pull backend

# 重启后端服务
docker-compose -f docker-compose.hub.nginx.yml up -d backend

# 查看启动日志
docker logs -f tradingagents-backend
```

### 3. 验证依赖安装

```bash
# 进入容器
docker exec -it tradingagents-backend bash

# 检查 pandoc 版本
pandoc --version

# 检查 wkhtmltopdf 版本
wkhtmltopdf --version

# 检查中文字体
fc-list :lang=zh

# 退出容器
exit
```

## 📝 支持的导出格式

| 格式 | 文件扩展名 | 依赖 | 说明 |
|------|-----------|------|------|
| **Markdown** | `.md` | 无 | 轻量级，适合查看和编辑 |
| **JSON** | `.json` | 无 | 原始数据，适合程序处理 |
| **Word** | `.docx` | pandoc | 适合进一步编辑和分享 |
| **PDF** | `.pdf` | pandoc + wkhtmltopdf | 适合打印和正式分享 |

## 🔧 API 使用

### 下载报告接口

```http
GET /api/reports/{report_id}/download?format={format}
```

**参数说明：**
- `report_id`: 报告ID（支持多种格式：UUID、analysis_id、stock_symbol）
- `format`: 导出格式（`markdown`、`json`、`docx`、`pdf`）

**示例：**

```bash
# 下载 Markdown 格式
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/reports/abc123/download?format=markdown" \
  -o report.md

# 下载 Word 格式
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/reports/abc123/download?format=docx" \
  -o report.docx

# 下载 PDF 格式
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/reports/abc123/download?format=pdf" \
  -o report.pdf
```

## 🐛 故障排查

### 问题 1：Word/PDF 导出失败，提示 "Pandoc 不可用"

**原因：** Docker 镜像未安装 pandoc

**解决方案：**
```bash
# 重新构建镜像（确保 Dockerfile.backend 包含 pandoc 安装）
docker build -t hsliup/tradingagents-backend:latest -f Dockerfile.backend .

# 验证 pandoc 是否安装
docker exec -it tradingagents-backend pandoc --version
```

### 问题 2：PDF 导出失败，提示 "PDF 引擎不可用"

**原因：** wkhtmltopdf 未安装或不可用

**解决方案：**
```bash
# 验证 wkhtmltopdf 是否安装
docker exec -it tradingagents-backend wkhtmltopdf --version

# 如果未安装，重新构建镜像
docker build -t hsliup/tradingagents-backend:latest -f Dockerfile.backend .
```

### 问题 3：PDF 中文显示为方框或乱码

**原因：** 缺少中文字体

**解决方案：**
```bash
# 检查中文字体是否安装
docker exec -it tradingagents-backend fc-list :lang=zh

# 应该看到类似输出：
# /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc: WenQuanYi Zen Hei:style=Regular
# /usr/share/fonts/truetype/wqy/wqy-microhei.ttc: WenQuanYi Micro Hei:style=Regular

# 如果没有输出，重新构建镜像
docker build -t hsliup/tradingagents-backend:latest -f Dockerfile.backend .
```

### 问题 4：导出速度慢

**原因：** PDF 生成需要渲染，比较耗时

**优化建议：**
- 对于大型报告，建议使用 Word 格式（速度更快）
- 或者先下载 Markdown，再本地转换为 PDF
- 考虑添加后台任务队列处理大型报告导出

## 📊 性能参考

基于测试环境（2核4G内存）的性能数据：

| 格式 | 文件大小 | 生成时间 | 说明 |
|------|---------|---------|------|
| Markdown | ~50KB | <100ms | 最快 |
| JSON | ~100KB | <100ms | 最快 |
| Word | ~200KB | ~2s | 中等 |
| PDF | ~300KB | ~5s | 较慢（需要渲染） |

## 🔐 安全注意事项

1. **文件大小限制：** 建议在 Nginx 配置中限制上传/下载文件大小
2. **并发控制：** PDF 生成消耗资源，建议限制并发数
3. **临时文件清理：** 导出过程会创建临时文件，确保正确清理
4. **权限验证：** 确保用户只能下载自己有权限的报告

## 📚 相关文件

- `Dockerfile.backend` - Docker 镜像配置
- `app/utils/report_exporter.py` - 报告导出工具类
- `app/routers/reports.py` - 报告下载 API
- `frontend/src/views/Reports/index.vue` - 前端报告列表页
- `frontend/src/views/Reports/ReportDetail.vue` - 前端报告详情页

## 🎯 后续优化建议

1. **异步导出：** 对于大型报告，使用后台任务队列（Celery/RQ）
2. **缓存机制：** 缓存已生成的 PDF/Word 文件，避免重复生成
3. **自定义模板：** 支持自定义 Word/PDF 模板样式
4. **批量导出：** 支持批量下载多个报告
5. **邮件发送：** 支持将报告通过邮件发送

## 📞 技术支持

如有问题，请查看：
- 后端日志：`docker logs tradingagents-backend`
- 应用日志：`docker exec tradingagents-backend cat /app/logs/tradingagents.log`
- GitHub Issues: https://github.com/your-repo/issues

