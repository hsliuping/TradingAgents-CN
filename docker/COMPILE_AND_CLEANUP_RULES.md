# Docker 构建时编译和清理规则

## 📋 概述

在 Docker 镜像构建时，我们会编译 Python 代码并清理源码，以保护知识产权和许可证验证逻辑。

**关键原则**：
- ✅ 编译在**目标架构**上进行（AMD64 或 ARM64）
- ✅ 使用 Docker Buildx 自动处理多架构编译
- ✅ 删除源码，只保留必要的 `.py` 文件
- ✅ 保留开源部分（`tradingagents/`）的源码

---

## 🔧 编译策略

### 1. core/licensing/ - Cython 编译（最强保护）

**编译方式**: Cython → `.so` 文件（C 扩展）

**编译文件**:
- `validator.py` → `validator.so`
- `manager.py` → `manager.so`
- `hardware.py` → `hardware.so`
- `crypto_utils.py` → `crypto_utils.so`

**保留文件**:
- ✅ `__init__.py` - 包导入需要
- ✅ `models.py` - 数据模型，被其他模块导入

**删除文件**:
- ❌ `validator.py` - 已编译为 `.so`
- ❌ `manager.py` - 已编译为 `.so`
- ❌ `hardware.py` - 已编译为 `.so`
- ❌ `crypto_utils.py` - 已编译为 `.so`

**原因**: 
- 许可证验证逻辑最关键，必须使用 Cython 编译为二进制
- 防止用户修改验证逻辑或搭建假服务器绕过验证

---

### 2. core/ 其他模块 - 字节码编译

**编译方式**: Python 字节码 → `.pyc` 文件

**编译目录**:
- `core/workflow/`
- `core/agents/`
- `core/llm/`
- `core/config/`
- `core/state/`
- `core/tools/`
- `core/prompts/`
- `core/compat/`

**保留文件**:
- ✅ 所有 `__init__.py` - 包导入需要

**删除文件**:
- ❌ 所有其他 `.py` 文件（已编译为 `.pyc`）

**原因**:
- 保护商业逻辑和知识产权
- 字节码编译足够（不需要 Cython）

---

### 3. app/ - 字节码编译

**编译方式**: Python 字节码 → `.pyc` 文件

**编译目录**:
- `app/routers/`
- `app/services/`
- `app/models/`
- `app/schemas/`
- `app/middleware/`
- `app/core/`

**保留文件**:
- ✅ 所有 `__init__.py` - 包导入需要
- ✅ 所有 `__main__.py` - 入口文件

**删除文件**:
- ❌ 所有其他 `.py` 文件（已编译为 `.pyc`）

**原因**:
- 保护 API 业务逻辑
- 防止用户修改 API 行为

---

### 4. tradingagents/ - 保留源码（开源部分）

**编译方式**: 不编译

**保留文件**:
- ✅ 所有 `.py` 文件

**原因**:
- 这是开源部分（Apache 2.0 许可证）
- 用户可以查看和修改

---

## 📁 编译后的文件结构

```
/app/
├── core/
│   ├── licensing/
│   │   ├── __init__.py          ✅ 保留
│   │   ├── models.py            ✅ 保留（数据模型）
│   │   ├── validator.so         ✅ 编译产物（AMD64 或 ARM64）
│   │   ├── manager.so           ✅ 编译产物
│   │   ├── hardware.so          ✅ 编译产物
│   │   └── crypto_utils.so      ✅ 编译产物
│   ├── workflow/
│   │   ├── __init__.py          ✅ 保留
│   │   ├── engine.pyc           ✅ 编译产物
│   │   └── ...
│   └── ...
├── app/
│   ├── __init__.py              ✅ 保留
│   ├── main.pyc                 ✅ 编译产物
│   ├── routers/
│   │   ├── __init__.py          ✅ 保留
│   │   ├── workflow.pyc         ✅ 编译产物
│   │   └── ...
│   └── ...
└── tradingagents/
    ├── __init__.py              ✅ 源码（开源）
    ├── agents/
    │   ├── __init__.py          ✅ 源码（开源）
    │   ├── base.py              ✅ 源码（开源）
    │   └── ...
    └── ...
```

---

## 🔍 架构依赖性

### .so 文件（Cython 编译产物）

| 架构 | 文件扩展名 | 示例 | 可移植性 |
|------|-----------|------|---------|
| AMD64 (x86_64) | `.so` | `validator.cpython-310-x86_64-linux-gnu.so` | ❌ 只能在 AMD64 上运行 |
| ARM64 (aarch64) | `.so` | `validator.cpython-310-aarch64-linux-gnu.so` | ❌ 只能在 ARM64 上运行 |

### .pyc 文件（字节码）

| 架构 | 文件扩展名 | 可移植性 |
|------|-----------|---------|
| 所有架构 | `.pyc` | ✅ 跨架构通用 |

**关键点**:
- `.so` 文件是**平台相关**的二进制文件
- 必须在**目标架构**上编译
- Docker Buildx 会自动在正确的架构上编译

---

## 🛠️ 编译脚本

### docker/scripts/compile-and-cleanup.sh

**功能**:
1. 编译 `core/licensing/` 为 `.so`（Cython）
2. 编译 `core/` 其他模块为 `.pyc`
3. 编译 `app/` 为 `.pyc`
4. 移动 `.pyc` 文件到正确位置
5. 清理源码文件

**调用位置**: `Dockerfile.backend.compiled.ubuntu`

**执行时机**: Docker 镜像构建时

---

## 🚀 构建流程

### 多架构构建（推荐）

```bash
# 同时构建 AMD64 和 ARM64
./docker/scripts/build-multiarch.sh
```

**流程**:
1. Docker Buildx 创建 AMD64 构建环境
2. 在 AMD64 环境中编译代码（生成 AMD64 的 `.so`）
3. 清理源码
4. 构建 AMD64 镜像
5. Docker Buildx 创建 ARM64 构建环境（使用 QEMU）
6. 在 ARM64 环境中编译代码（生成 ARM64 的 `.so`）
7. 清理源码
8. 构建 ARM64 镜像
9. 推送到 Docker Hub（自动创建 manifest）

---

## ✅ 验证

### 检查编译产物

```bash
# 进入容器
docker run -it --rm hsliup/tradingagents-pro-backend:latest bash

# 检查 .so 文件
ls -la /app/core/licensing/*.so

# 检查 .pyc 文件
find /app/core -name "*.pyc" | head -10
find /app/app -name "*.pyc" | head -10

# 检查源码是否删除
find /app/core -name "*.py" ! -name "__init__.py" ! -name "models.py"
find /app/app -name "*.py" ! -name "__init__.py" ! -name "__main__.py"

# 检查 tradingagents/ 源码保留
ls -la /app/tradingagents/agents/*.py
```

---

**最后更新**: 2026-01-13  
**相关文档**:
- `docker/scripts/compile-and-cleanup.sh`
- `docker/Dockerfile.backend.compiled.ubuntu`
- `docker/scripts/build-multiarch.sh`

