# 🔧 导出功能故障排除指南

## 🎯 概述

本文档提供了TradingAgents-CN导出功能常见问题的详细解决方案，包括Word、PDF、Markdown导出的各种故障排除方法。

## 📄 Word导出问题

### 问题1: YAML解析错误

**错误信息**:

```
Pandoc died with exitcode "64" during conversion: 
YAML parse exception at line 1, column 1,
while scanning an alias:
did not find expected alphabetic or numeric character
```

**原因分析**:

- Markdown内容中的表格分隔符 `|------|------| ` 被pandoc误认为YAML文档分隔符
- 特殊字符导致YAML解析冲突

**解决方案**:

```python
# 已在代码中自动修复
extra_args = ['--from=markdown-yaml_metadata_block']  # 禁用YAML解析
```

**验证方法**:

```bash
# 测试Word导出
docker exec TradingAgents-web python test_conversion.py
```

### 问题2: 中文字符显示异常

**错误现象**:

- Word文档中中文显示为方块或乱码
- 特殊符号（¥、%等）显示异常

**解决方案**:

1. **Docker环境**（推荐）:

   ```bash
   # Docker已预配置中文字体，无需额外设置
   docker-compose up -d
   ```
2. **本地环境**:

   ```bash
   # Windows
   # 确保系统已安装中文字体

   # Linux
   sudo apt-get install fonts-noto-cjk

   # macOS
   # 系统自带中文字体支持
   ```

### 问题3: Word文件损坏或无法打开

**错误现象**:

- 生成的.docx文件无法用Word打开
- 文件大小为0或异常小

**诊断步骤**:

```bash
# 1. 检查生成的文件
docker exec TradingAgents-web ls -la /app/test_*.docx

# 2. 验证pandoc安装
docker exec TradingAgents-web pandoc --version

# 3. 测试基础转换
docker exec TradingAgents-web python test_conversion.py
```

**解决方案**:

```bash
# 重新构建Docker镜像
docker-compose down
docker build -t tradingagents-cn:latest . --no-cache
docker-compose up -d
```

## 📊 PDF导出问题

### 问题1: PDF引擎不可用

**错误信息**:

```
PDF生成失败，最后错误: wkhtmltopdf not found
```

**解决方案**:

1. **Docker环境**（推荐）:

   ```bash
   # 检查PDF引擎安装
   docker exec TradingAgents-web wkhtmltopdf --version
   docker exec TradingAgents-web weasyprint --version
   ```
2. **本地环境安装**:

   ```bash
   # Windows
   choco install wkhtmltopdf

   # macOS
   brew install wkhtmltopdf

   # Linux
   sudo apt-get install wkhtmltopdf
   ```

### 问题2: PDF生成超时

**错误现象**:

- PDF生成过程卡住不动
- 长时间无响应

**解决方案**:

```python
# 增加超时设置（已在代码中配置）
max_execution_time = 180  # 3分钟超时
```

**临时解决**:

```bash
# 重启Web服务
docker-compose restart web
```

### 问题3: PDF中文显示问题

**错误现象**:

- PDF中中文字符显示为空白或方块
- 布局错乱

**解决方案**:

```bash
# Docker环境已预配置，如有问题请重新构建
docker build -t tradingagents-cn:latest . --no-cache
```

## 📝 Markdown导出问题

### 问题1: 特殊字符转义

**错误现象**:

- 特殊字符（&、<、>等）显示异常
- 表格格式错乱

**解决方案**:

```python
# 自动字符转义（已实现）
text = text.replace('&', '&')
text = text.replace('<', '<')
text = text.replace('>', '>')
```

### 问题2: 文件编码问题

**错误现象**:

- 下载的Markdown文件乱码
- 中文字符显示异常

**解决方案**:

```python
# 确保UTF-8编码（已配置）
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
```

## 🔧 通用故障排除

### 诊断工具

1. **测试转换功能**:

   ```bash
   # 基础转换测试
   docker exec TradingAgents-web python test_conversion.py

   # 实际数据转换测试
   docker exec TradingAgents-web python test_real_conversion.py

   # 现有报告转换测试
   docker exec TradingAgents-web python test_existing_reports.py
   ```
2. **检查系统状态**:

   ```bash
   # 查看容器状态
   docker-compose ps

   # 查看日志
   docker logs TradingAgents-web --tail 50

   # 检查磁盘空间
   docker exec TradingAgents-web df -h
   ```
3. **验证依赖**:

   ```bash
   # 检查Python包
   docker exec TradingAgents-web pip list | grep -E "(pandoc|docx|pypandoc)"

   # 检查系统工具
   docker exec TradingAgents-web which pandoc
   docker exec TradingAgents-web which wkhtmltopdf
   ```

### 环境重置

如果问题持续存在，可以尝试完全重置环境：

```bash
# 1. 停止所有服务
docker-compose down

# 2. 清理Docker资源
docker system prune -f

# 3. 重新构建镜像
docker build -t tradingagents-cn:latest . --no-cache

# 4. 重新启动服务
docker-compose up -d

# 5. 验证功能
docker exec TradingAgents-web python test_conversion.py
```

### 性能优化

1. **内存不足**:

   ```yaml
   # docker-compose.yml
   services:
     web:
       deploy:
         resources:
           limits:
             memory: 2G  # 增加内存限制
   ```
2. **磁盘空间**:

   ```bash
   # 清理临时文件
   docker exec TradingAgents-web find /tmp -name "*.docx" -delete
   docker exec TradingAgents-web find /tmp -name "*.pdf" -delete
   ```

## 📞 获取帮助

### 日志收集

遇到问题时，请收集以下信息：

1. **错误日志**:

   ```bash
   docker logs TradingAgents-web --tail 100 > error.log
   ```
2. **系统信息**:

   ```bash
   docker exec TradingAgents-web python --version
   docker exec TradingAgents-web pandoc --version
   docker --version
   docker-compose --version
   ```
3. **测试结果**:

   ```bash
   docker exec TradingAgents-web python test_conversion.py > test_result.log 2>&1
   ```

### 常见解决方案总结


| 问题类型     | 快速解决方案   | 详细方案       |
| ------------ | -------------- | -------------- |
| YAML解析错误 | 重启Web服务    | 检查代码修复   |
| PDF引擎缺失  | 使用Docker环境 | 手动安装引擎   |
| 中文显示问题 | 使用Docker环境 | 安装中文字体   |
| 文件损坏     | 重新生成       | 重建Docker镜像 |
| 内存不足     | 重启容器       | 增加内存限制   |
| 网络超时     | 检查网络       | 增加超时设置   |

### 预防措施

1. **定期更新**:

   ```bash
   git pull origin develop
   docker-compose pull
   ```
2. **监控资源**:

   ```bash
   docker stats TradingAgents-web
   ```
3. **备份配置**:

   ```bash
   cp .env .env.backup
   ```

---

*最后更新: 2025-07-13*
*版本: v0.1.7*
