# pyproject.toml 缺失依赖包修复

**日期**: 2025-10-21  
**版本**: v0.1.13-preview (main 分支)  
**类型**: Bug Fix  
**优先级**: High

## 问题描述

### 用户反馈

用户反馈在安装项目时，很多包没有包含在 `pyproject.toml` 文件中，导致安装后运行时出现 `ModuleNotFoundError`。

### 根本原因

`pyproject.toml` 中的 `dependencies` 列表不完整，缺少了以下关键依赖包：

1. **核心框架依赖**
   - `langchain` - LangChain 核心库
   - `langchain-core` - LangChain 核心组件
   - `pydantic` - 数据验证库
   - `typer` - CLI 框架

2. **数据处理依赖**
   - `numpy` - 数值计算库
   - `python-dateutil` - 日期处理库
   - `beautifulsoup4` - HTML 解析库

3. **AI/ML 依赖**
   - `sentence-transformers` - 句子嵌入模型
   - `torch` - PyTorch 深度学习框架
   - `transformers` - Hugging Face Transformers

4. **工具库依赖**
   - `tenacity` - 重试机制库
   - `urllib3` - HTTP 客户端库
   - `toml` - TOML 配置文件解析

5. **Streamlit 扩展**
   - `streamlit-cookies-manager` - Streamlit Cookie 管理

## 解决方案

### 1. 创建依赖检查脚本

创建了 `scripts/check_missing_dependencies.py` 脚本，用于自动扫描代码中使用的第三方包，并与 `pyproject.toml` 中声明的依赖进行对比。

**脚本功能**:
- 扫描 `tradingagents/`, `web/`, `cli/` 目录中的所有 Python 文件
- 提取所有 `import` 和 `from ... import` 语句
- 过滤掉标准库和内部模块
- 与 `pyproject.toml` 中的依赖进行对比
- 输出缺失的依赖列表

### 2. 更新 pyproject.toml

在 `pyproject.toml` 的 `dependencies` 列表中添加了 14 个缺失的依赖包：

```toml
dependencies = [
    # ... 原有依赖 ...
    
    # 🆕 新增依赖
    "beautifulsoup4>=4.12.0",        # HTML 解析
    "langchain>=0.3.0",              # LangChain 核心库
    "langchain-core>=0.3.0",         # LangChain 核心组件
    "numpy>=1.24.0",                 # 数值计算
    "pydantic>=2.0.0",               # 数据验证
    "python-dateutil>=2.8.0",        # 日期处理
    "sentence-transformers>=2.2.0",  # 句子嵌入
    "streamlit-cookies-manager>=0.2.0",  # Streamlit Cookie 管理
    "tenacity>=8.0.0",               # 重试机制
    "toml>=0.10.0",                  # TOML 解析
    "torch>=2.0.0",                  # PyTorch
    "transformers>=4.30.0",          # Hugging Face Transformers
    "typer>=0.9.0",                  # CLI 框架
    "urllib3>=2.0.0",                # HTTP 客户端
]
```

### 3. 依赖包总数

- **更新前**: 38 个依赖包
- **更新后**: 52 个依赖包
- **新增**: 14 个依赖包

## 验证结果

运行依赖检查脚本验证：

```bash
python scripts/check_missing_dependencies.py
```

**输出结果**:
```
✅ 所有第三方包都已在 pyproject.toml 中声明！

📦 所有第三方包导入列表:
  ✅ akshare
  ✅ baostock
  ✅ bs4 (beautifulsoup4)
  ✅ chromadb
  ✅ dashscope
  ✅ dateutil (python-dateutil)
  ✅ langchain
  ✅ langchain_core
  ✅ numpy
  ✅ pydantic
  ✅ sentence_transformers
  ✅ streamlit_cookies_manager
  ✅ tenacity
  ✅ toml
  ✅ torch
  ✅ transformers
  ✅ typer
  ✅ urllib3
  ... (共 41 个第三方包)
```

## 影响范围

### 用户安装体验

**更新前**:
```bash
pip install -e .
# 安装后运行会出现 ModuleNotFoundError
python -m cli.main
# ❌ ModuleNotFoundError: No module named 'typer'
```

**更新后**:
```bash
pip install -e .
# 所有依赖都会自动安装
python -m cli.main
# ✅ 正常运行
```

### 受影响的模块

1. **CLI 模块** (`cli/`)
   - 依赖 `typer` 框架
   - 依赖 `rich` 用于美化输出

2. **Web 模块** (`web/`)
   - 依赖 `streamlit-cookies-manager` 用于 Cookie 管理
   - 依赖 `beautifulsoup4` 用于 HTML 解析

3. **核心库** (`tradingagents/`)
   - 依赖 `langchain` 和 `langchain-core` 用于 LLM 集成
   - 依赖 `numpy` 用于数值计算
   - 依赖 `pydantic` 用于数据验证
   - 依赖 `sentence-transformers` 和 `torch` 用于嵌入模型
   - 依赖 `tenacity` 用于重试机制
   - 依赖 `toml` 用于配置文件解析

## 安装指南

### 方式 1: 使用 pip（推荐）

```bash
# 开发模式安装（可编辑）
pip install -e .

# 或者从 PyPI 安装（如果已发布）
pip install tradingagents
```

### 方式 2: 使用 uv（更快）

```bash
# 开发模式安装
uv pip install -e .
```

### 方式 3: 安装可选依赖

```bash
# 安装千帆大模型支持
pip install -e ".[qianfan]"
```

## 依赖包说明

### 核心依赖（必需）

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| langchain | >=0.3.0 | LangChain 核心库，用于 LLM 集成 |
| langchain-core | >=0.3.0 | LangChain 核心组件 |
| pydantic | >=2.0.0 | 数据验证和序列化 |
| numpy | >=1.24.0 | 数值计算和数组操作 |
| pandas | >=2.3.0 | 数据处理和分析 |
| typer | >=0.9.0 | CLI 命令行框架 |

### AI/ML 依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| openai | >=1.0.0,<2.0.0 | OpenAI API 客户端 |
| dashscope | >=1.20.0 | 阿里云百炼 API 客户端 |
| langchain-openai | >=0.3.23 | LangChain OpenAI 集成 |
| langchain-anthropic | >=0.3.15 | LangChain Anthropic 集成 |
| sentence-transformers | >=2.2.0 | 句子嵌入模型 |
| torch | >=2.0.0 | PyTorch 深度学习框架 |
| transformers | >=4.30.0 | Hugging Face Transformers |

### 数据源依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| akshare | >=1.16.98 | A股数据源 |
| tushare | >=1.4.21 | Tushare 数据源 |
| yfinance | >=0.2.63 | Yahoo Finance 数据源 |
| baostock | >=0.8.8 | BaoStock 数据源 |
| finnhub-python | >=2.4.23 | Finnhub 数据源 |

### Web 框架依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| streamlit | >=1.28.0 | Web 应用框架 |
| streamlit-cookies-manager | >=0.2.0 | Cookie 管理 |
| chainlit | >=2.5.5 | 对话式 AI 界面 |

### 工具库依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| requests | >=2.32.4 | HTTP 请求 |
| urllib3 | >=2.0.0 | HTTP 客户端 |
| beautifulsoup4 | >=4.12.0 | HTML 解析 |
| python-dateutil | >=2.8.0 | 日期处理 |
| tenacity | >=8.0.0 | 重试机制 |
| toml | >=0.10.0 | TOML 配置解析 |
| rich | >=14.0.0 | 终端美化输出 |

## 后续维护

### 定期检查依赖

建议定期运行依赖检查脚本，确保 `pyproject.toml` 与实际代码保持同步：

```bash
python scripts/check_missing_dependencies.py
```

### 添加新依赖的流程

1. 在代码中使用新的第三方包
2. 运行依赖检查脚本
3. 将缺失的依赖添加到 `pyproject.toml`
4. 更新文档说明新依赖的用途
5. 提交代码并更新版本号

### 版本管理建议

- 使用 `>=` 指定最低版本要求
- 对于关键依赖（如 openai），使用版本范围限制（如 `>=1.0.0,<2.0.0`）
- 定期更新依赖版本，修复安全漏洞

## 相关链接

- **Issue**: 用户反馈依赖包缺失问题
- **Commit**: 待提交
- **检查脚本**: `scripts/check_missing_dependencies.py`
- **配置文件**: `pyproject.toml`

## 注意事项

### torch 和 transformers 依赖

这两个包体积较大（torch 约 2GB），安装时间较长。如果用户不需要使用嵌入模型功能，可以考虑：

1. 将这些依赖移到 `[project.optional-dependencies]` 中
2. 创建一个 `ai` 或 `ml` 可选依赖组

**建议的可选依赖配置**:
```toml
[project.optional-dependencies]
qianfan = ["qianfan>=0.4.20"]
ai = [
    "sentence-transformers>=2.2.0",
    "torch>=2.0.0",
    "transformers>=4.30.0",
]
```

用户可以选择性安装：
```bash
# 不安装 AI 依赖
pip install -e .

# 安装 AI 依赖
pip install -e ".[ai]"
```

### 兼容性说明

- **Python 版本**: 要求 Python >= 3.10
- **操作系统**: 支持 Windows, Linux, macOS
- **架构**: 支持 x86_64 和 ARM64（Apple Silicon）

某些依赖（如 torch）在不同平台上的安装方式可能不同，建议参考官方文档。

