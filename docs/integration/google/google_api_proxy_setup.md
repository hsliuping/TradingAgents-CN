# Google API 代理配置指南

## 🔍 问题诊断

您遇到的错误：
```
Connection to generativelanguage.googleapis.com timed out
```

**原因分析**：
- ✅ 浏览器可以访问 Google（因为浏览器使用了代理）
- ❌ Python 程序无法访问 Google API（因为程序没有配置代理）

## 📋 测试结果

运行 `scripts/test_google_api_connection.py` 显示：
```
❌ generativelanguage.googleapis.com: 连接失败 - timed out
❌ www.google.com: 连接失败 - timed out
❌ googleapis.com: 连接失败 - timed out
```

这证实了 **Python 程序需要配置代理才能访问 Google API**。

## ✅ 解决方案

### 方案 1：配置系统代理（推荐）

#### 1.1 找到您的代理端口

常见代理工具的默认端口：
- **Clash**: `http://127.0.0.1:7890`
- **V2Ray**: `http://127.0.0.1:10809`
- **Shadowsocks**: `http://127.0.0.1:1080`
- **Clash Verge**: `http://127.0.0.1:7890`

您可以在代理工具的设置中查看具体端口。

#### 1.2 在 `.env` 文件中添加代理配置

编辑项目根目录的 `.env` 文件，添加：

```bash
# Google API Key
GOOGLE_API_KEY=your-google-api-key

# 代理配置（根据您的代理工具调整端口）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

#### 1.3 重启后端服务

```bash
# 停止当前服务
Ctrl+C

# 重新启动
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 方案 2：使用交互式测试脚本

运行带代理配置的测试脚本：

```bash
.\.venv\Scripts\python scripts/test_google_api_with_proxy.py
```

脚本会提示您输入代理地址，例如：
```
代理地址: http://127.0.0.1:7890
```

### 方案 3：使用国内可访问的模型（最简单）

如果不想配置代理，可以使用国内可直接访问的模型：

#### 阿里百炼（推荐）
```python
quick_model = "qwen-plus"
deep_model = "qwen-max"
```

#### DeepSeek
```python
quick_model = "deepseek-chat"
deep_model = "deepseek-chat"
```

#### 智谱 AI
```python
quick_model = "glm-4"
deep_model = "glm-4"
```

## 🧪 验证代理配置

### 测试 1：基础连接测试

```bash
.\.venv\Scripts\python scripts/test_google_api_connection.py
```

**期望结果**（配置代理后）：
```
✅ generativelanguage.googleapis.com: 连接成功 (0.15秒)
✅ API 调用成功！耗时: 2.73秒
```

### 测试 2：完整分析测试

在前端选择 `gemini-2.5-flash` 模型，发起股票分析。

**期望日志**：
```
✅ [同步查询] 模型 gemini-2.5-flash 使用厂家默认 API: https://generativelanguage.googleapis.com/v1
🔍 [供应商查找] 快速模型 gemini-2.5-flash 对应的供应商: google
✅ Google AI OpenAI 兼容适配器初始化成功
📊 [市场分析师] LLM模型: gemini-2.5-flash
✅ API 调用成功
```

## 🔧 代理配置详解

### Windows PowerShell

临时设置（仅当前会话有效）：
```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
```

### Windows CMD

临时设置：
```cmd
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
```

### 在 Python 代码中设置

如果不想修改 `.env`，可以在代码中设置：

```python
import os
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
```

## ⚠️ 常见问题

### Q1: 设置了代理还是超时？

**检查清单**：
1. ✅ 代理工具是否正在运行？
2. ✅ 代理端口是否正确？
3. ✅ 代理工具是否开启了"系统代理"或"TUN模式"？
4. ✅ 防火墙是否允许 Python 访问网络？

### Q2: 如何确认代理端口？

**Clash 示例**：
1. 打开 Clash 客户端
2. 查看"设置" -> "端口设置"
3. 找到"HTTP 代理端口"（通常是 7890）

**V2Ray 示例**：
1. 打开 V2Ray 客户端
2. 查看"参数设置" -> "本地监听端口"
3. 通常是 10809

### Q3: 代理配置会影响其他 API 吗？

**不会**。代理只影响需要访问国外服务的 API：
- ✅ Google API（需要代理）
- ✅ OpenAI API（需要代理）
- ✅ Anthropic API（需要代理）
- ❌ 阿里百炼（不需要代理）
- ❌ DeepSeek（不需要代理）
- ❌ 智谱 AI（不需要代理）

### Q4: 生产环境如何配置？

**推荐方案**：
1. 使用国内可访问的模型（阿里百炼、DeepSeek）
2. 或者使用聚合 API 服务（如 302.AI、SiliconFlow）
3. 避免在生产环境依赖代理

## 📊 性能对比

| 模型 | 是否需要代理 | 平均响应时间 | 稳定性 |
|------|------------|------------|--------|
| gemini-2.5-flash | ✅ 需要 | 2-3秒 | ⭐⭐⭐ |
| qwen-plus | ❌ 不需要 | 1-2秒 | ⭐⭐⭐⭐⭐ |
| deepseek-chat | ❌ 不需要 | 2-3秒 | ⭐⭐⭐⭐ |
| gpt-4o | ✅ 需要 | 3-5秒 | ⭐⭐⭐ |

## 🎯 推荐配置

### 开发环境
```bash
# .env
GOOGLE_API_KEY=your-key
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 生产环境
```bash
# .env
DASHSCOPE_API_KEY=your-key  # 使用阿里百炼
DEEPSEEK_API_KEY=your-key   # 或 DeepSeek
# 不配置代理
```

## 📞 需要帮助？

如果按照以上步骤仍然无法解决问题，请提供：
1. 您使用的代理工具名称和版本
2. 代理端口号
3. 运行 `test_google_api_with_proxy.py` 的完整输出
4. 后端服务的错误日志

我会帮您进一步诊断！

