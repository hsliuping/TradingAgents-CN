# 便携版二进制包修复总结

## 📋 问题描述

便携版 Python 环境中，某些包的二进制扩展模块（`.pyd`, `.so` 文件）缺失，导致导入失败。

### 根本原因

1. **嵌入式 Python 没有编译工具链**
   - 无法从源码编译 C/Rust/Cython 扩展
   - 必须使用预编译的二进制包（wheel）

2. **pip 安装时可能尝试源码构建**
   - 某些包在安装时会尝试从源码编译
   - 编译失败后，包虽然安装了，但二进制扩展缺失

3. **依赖传递问题**
   - 某些包依赖其他包的二进制扩展
   - 如果依赖包的二进制扩展缺失，会导致连锁失败

---

## 🔧 解决方案

### 方案 1：扩展 `fix_binary_packages.ps1` 脚本

**位置**: `scripts/deployment/fix_binary_packages.ps1`

**功能**: 自动重新安装所有二进制包，确保使用预编译版本

**修复的包**:
1. **核心依赖**:
   - `pydantic`, `pydantic-core` (Rust 编译)
   - `grpcio` (Cython 编译)
   - `cryptography==41.0.7` (Rust 编译，锁定版本避免 PyO3 兼容性问题)

2. **LangChain 集成**:
   - `langchain-openai`
   - `langchain-google-genai`
   - `langchain-anthropic`

3. **LLM SDK**:
   - `anthropic`

4. **数据源**:
   - `akshare`
   - `tushare`
   - `baostock`

5. **PDF 工具**:
   - `weasyprint`

6. **二进制依赖**（关键！）:
   - `jiter` (Rust, 用于 anthropic/openai)
   - `tiktoken` (Rust, 用于 langchain_openai)
   - `uuid-utils` (Rust, 用于 langchain_core)
   - `zstandard` (C, 用于 langchain_core)
   - `orjson` (Rust, 用于 langsmith)
   - `xxhash` (C, 用于 langgraph)
   - `ormsgpack` (C, 用于 langgraph)
   - `numpy` (C/Fortran)
   - `pandas` (C/Cython)
   - `curl-cffi<0.14,>=0.7` (C, 用于 akshare/yfinance)
   - `lxml` (C, libxml2/libxslt)
   - `Pillow` (C, 图像处理)
   - `frozenlist`, `multidict`, `yarl`, `propcache` (C, 用于 aiohttp)

**使用方法**:
```powershell
.\scripts\deployment\fix_binary_packages.ps1 -PortableDir "C:\path\to\portable"
```

---

### 方案 2：修改 `verify_portable_dependencies.ps1` 的 `-Fix` 参数

**位置**: `scripts/deployment/verify_portable_dependencies.ps1`

**改进**: 在使用 `-Fix` 参数时，强制添加 `--only-binary :all:` 参数

**修改内容**:
```powershell
# 从 requirements.txt 安装时
$installArgs = @("-r", $requirementsFile, "--only-binary", ":all:", "--no-warn-script-location", "--upgrade") + $mirror.Args

# 单个包安装时
$installArgs = @($pkg.Pip, "--only-binary", ":all:", "--no-warn-script-location") + $mirror.Args
```

**使用方法**:
```powershell
.\scripts\deployment\verify_portable_dependencies.ps1 -PortableDir "C:\path\to\portable" -Fix
```

---

## 📊 修复效果

### 修复前
- ✅ 通过: 11 个
- ❌ 失败: 9 个

### 修复后
- ✅ 通过: **20 个**
- ❌ 失败: **0 个**

### 详细对比

| 包名 | 修复前 | 修复后 | 关键依赖 |
|------|--------|--------|----------|
| pydantic | ✅ | ✅ | pydantic_core |
| pydantic_core | ❌ | ✅ | - |
| grpcio | ❌ | ✅ | cygrpc |
| google.generativeai | ❌ | ✅ | grpcio |
| anthropic | ❌ | ✅ | jiter |
| langchain_openai | ❌ | ✅ | tiktoken, uuid-utils, zstandard |
| langchain_google_genai | ❌ | ✅ | uuid-utils, zstandard |
| langchain_anthropic | ❌ | ✅ | uuid-utils, zstandard |
| akshare | ❌ | ✅ | curl-cffi, numpy, pandas, lxml |
| tushare | ❌ | ✅ | lxml |
| baostock | ❌ | ✅ | - |
| weasyprint | ❌ | ✅ | Pillow |

---

## 🎯 关键发现

### 1. 二进制依赖链

许多包的导入失败不是因为包本身，而是因为它们依赖的底层二进制包缺失：

```
anthropic → jiter (Rust 编译)
langchain_openai → tiktoken (Rust) + uuid-utils (Rust) + zstandard (C)
akshare → curl-cffi (C) + numpy (C) + pandas (Cython) + lxml (C)
weasyprint → Pillow (C)
```

### 2. `--only-binary :all:` 的重要性

这个参数强制 pip 只安装预编译的二进制包（wheel），避免尝试从源码编译。

### 3. 版本锁定

某些包需要锁定版本以避免兼容性问题：
- `cryptography==41.0.7` (避免 46.x 的 PyO3 兼容性问题)
- `curl-cffi<0.14,>=0.7` (yfinance 要求)

---

## 📝 建议

### 1. 在打包流程中集成修复脚本

在 `build_portable_package.ps1` 中，安装依赖后自动运行修复脚本：

```powershell
# 安装依赖
& $pythonExe -m pip install -r requirements.txt --only-binary :all: ...

# 修复二进制包
.\scripts\deployment\fix_binary_packages.ps1 -PortableDir $portableDir
```

### 2. 定期更新二进制依赖列表

随着项目依赖的增加，可能会有新的二进制包需要修复。建议：
- 定期运行 `verify_portable_dependencies.ps1`
- 发现新的导入错误时，分析依赖链
- 更新 `fix_binary_packages.ps1` 中的 `$binaryDeps` 列表

### 3. 文档化二进制依赖

在 `requirements.txt` 或单独的文档中，标注哪些包需要二进制扩展。

---

**最后更新**: 2026-01-20  
**相关脚本**:
- `scripts/deployment/fix_binary_packages.ps1`
- `scripts/deployment/verify_portable_dependencies.ps1`

