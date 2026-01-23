# Qdrant 向量数据库迁移总结

## 📋 概述

为了解决 ChromaDB Rust 扩展在多线程环境下的崩溃问题，我们实现了双向量数据库后端支持，默认使用 Qdrant。

---

## 🔥 问题背景

### ChromaDB 线程安全问题

**症状**：
- 系统在分析进度 45% 时崩溃
- Windows 弹窗提示 "python程序异常"
- 崩溃位置：`chromadb\api\rust.py`, line 452 in `_add`

**根本原因**：
- ChromaDB 的 Rust 扩展不是线程安全的
- 在多线程环境下会发生访问冲突（access violation）
- Python 线程锁无法完全防止 Rust 层面的崩溃

---

## ✅ 解决方案

### 实现双向量数据库后端

支持两种向量数据库：
1. **Qdrant**（推荐，默认）- 完全线程安全
2. **ChromaDB**（保留）- 有线程安全问题

### 架构设计

```
VectorStoreInterface (抽象接口)
    ├── QdrantAdapter (Qdrant 适配器)
    │   └── QdrantCollection
    └── ChromaDBAdapter (ChromaDB 适配器)
        └── ChromaDBCollection

VectorStoreManager (单例管理器)
    └── 根据环境变量选择适配器

AgentMemory
    └── 使用 VectorStoreManager
```

---

## 📦 新增文件

### 1. `core/memory/vector_store_interface.py`
**用途**: 统一向量数据库接口

**方法**：
- `add()` - 添加文档
- `query()` - 查询相似文档
- `count()` - 获取文档数量
- `delete_collection()` - 删除集合
- `get_backend_name()` - 获取后端名称

### 2. `core/memory/qdrant_adapter.py`
**用途**: Qdrant 向量数据库适配器

**特性**：
- ✅ 完全线程安全（Rust 实现，内置并发控制）
- ✅ 本地模式（无需服务器）
- ✅ 自动持久化
- ✅ 支持元数据过滤

**配置**：
- 数据目录：`QDRANT_DATA_DIR=./data/qdrant`
- 向量距离：COSINE
- 自动创建集合

### 3. `core/memory/chromadb_adapter.py`
**用途**: ChromaDB 向量数据库适配器

**特性**：
- ⚠️ 保留线程锁保护（但仍有 Rust 崩溃风险）
- ⚠️ 不推荐在生产环境使用
- ✅ 向后兼容

### 4. `scripts/check_vector_store_backend.py`
**用途**: 检查当前使用的向量数据库后端

**功能**：
- 检查环境变量配置
- 检查依赖包是否安装
- 尝试初始化并显示实际使用的后端
- 给出配置建议

---

## 🔧 修改文件

### 1. `core/memory/memory_manager.py`
**主要变更**：
- `ChromaDBManager` → `VectorStoreManager`
- 支持多后端选择
- 移除显式线程锁（由适配器内部处理）

### 2. `core/memory/__init__.py`
**主要变更**：
- 导出 `VectorStoreManager`
- 添加向后兼容别名：`ChromaDBManager = VectorStoreManager`

### 3. `requirements.txt`
**新增依赖**：
```
qdrant-client>=1.7.0
```

### 4. `.env` / `.env.example`
**新增环境变量**：
```bash
# 向量数据库后端配置
VECTOR_STORE_BACKEND=qdrant  # 默认，推荐

# Qdrant 数据目录
QDRANT_DATA_DIR=./data/qdrant
```

### 5. 便携版文件
- `release/TradingAgentsCN-portable/requirements.txt` - 添加 qdrant-client
- `release/TradingAgentsCN-portable/.env.example` - 添加环境变量配置

---

## 🚀 使用方法

### 1. 安装依赖

```bash
pip install qdrant-client>=1.7.0
```

### 2. 配置环境变量

在 `.env` 文件中设置：

```bash
# 使用 Qdrant（推荐）
VECTOR_STORE_BACKEND=qdrant
QDRANT_DATA_DIR=./data/qdrant

# 或使用 ChromaDB（不推荐）
# VECTOR_STORE_BACKEND=chromadb
```

### 3. 检查配置

```bash
python scripts/check_vector_store_backend.py
```

### 4. 查看日志

启动系统后，查找以下日志：

```
✅ 向量数据库后端: Qdrant (线程安全)
✅ Qdrant 客户端初始化成功 (本地模式: ./data/qdrant)
🧠 初始化 Agent 记忆: {agent_id} (后端: qdrant)
```

---

## 📊 对比

| 特性 | Qdrant | ChromaDB |
|------|--------|----------|
| **线程安全** | ✅ 完全安全 | ❌ 不安全 |
| **崩溃风险** | ✅ 无 | ❌ 高 |
| **性能** | ✅ 高 | ✅ 高 |
| **持久化** | ✅ 自动 | ✅ 自动 |
| **本地模式** | ✅ 支持 | ✅ 支持 |
| **元数据过滤** | ✅ 支持 | ✅ 支持 |
| **推荐度** | ✅ 推荐 | ❌ 不推荐 |

---

## 🔍 验证方法

### 方法 1: 运行检查脚本

```bash
python scripts/check_vector_store_backend.py
```

### 方法 2: 查看日志

启动后端服务，查找日志中的关键信息：

```bash
# 查找向量数据库初始化日志
Get-Content logs/tradingagents.log | Select-String "向量数据库后端"

# 查找 Qdrant 初始化日志
Get-Content logs/tradingagents.log | Select-String "Qdrant"
```

### 方法 3: 检查数据目录

```bash
# Qdrant 数据目录
ls data/qdrant

# ChromaDB 数据目录
ls data/chromadb
```

---

## 📝 提交记录

```
d078e28 feat: Qdrant 集合自动检测向量维度并重建
bd64f1c fix: 修复 ResearcherAgent 访问 AgentConfig 属性的错误
37c19a9 feat: 添加 get_embedding_dimension() 方法，支持不同 Embedding 模型的向量维度
cfe37e5 fix: 修复 ChromaDBManager 导入错误，添加向后兼容
88edfbc feat: 添加向量数据库后端检查脚本
fafe261 feat: 添加 Qdrant 依赖和环境变量配置
2b6a18f feat: 添加 Qdrant 支持，实现双向量数据库后端
c3c5128 docs: 添加 ChromaDB 替代方案调研文档
```

---

## 🐛 已修复的问题

### 问题 1: 向量维度不匹配 ✅ 已修复

**错误信息**:
```
❌ [Qdrant] 添加文档失败: could not broadcast input array from shape (1024,) into shape (1536,)
```

**原因**:
- DashScope text-embedding-v4 模型的向量维度是 **1024**
- Qdrant 集合创建时使用的是默认维度 **1536**（OpenAI embedding 维度）

**解决方案**:
1. ✅ 添加 `EMBEDDING_DIMENSIONS` 映射表（支持多种 Embedding 模型）
2. ✅ 添加 `get_embedding_dimension()` 方法，动态获取向量维度
3. ✅ Qdrant 集合初始化时自动检测维度不匹配并重建
4. ✅ 提供手动清理脚本 `scripts/clean_qdrant_data.ps1`

**相关提交**: `37c19a9`, `d078e28`

---

### 问题 2: AgentConfig 属性访问错误 ✅ 已修复

**错误信息**:
```
'AgentConfig' object has no attribute 'get'
```

**原因**:
- `self.config` 是 `AgentConfig` (Pydantic BaseModel)，不是字典
- 不能使用 `.get()` 方法访问属性

**解决方案**:
- ✅ 使用 `getattr(self.config, 'memory_enabled', True)` 访问属性
- ✅ 兼容 AgentConfig 对象和字典两种情况

**相关提交**: `bd64f1c`

---

### 问题 3: ChromaDBManager 导入错误 ✅ 已修复

**错误信息**:
```
cannot import name 'ChromaDBManager' from 'core.memory.memory_manager'
```

**原因**:
- `ChromaDBManager` 已重命名为 `VectorStoreManager`
- 但 `core/memory/__init__.py` 中还在导出旧名称

**解决方案**:
- ✅ 导入 `VectorStoreManager`
- ✅ 创建向后兼容别名: `ChromaDBManager = VectorStoreManager`

**相关提交**: `cfe37e5`

---

## 🔧 使用说明

### 方法 1: 自动重建（推荐）⭐

**无需手动操作**，系统会自动检测并重建：

1. 重启后端服务
2. 系统自动检测向量维度不匹配
3. 自动删除旧集合并重新创建
4. 查看日志确认：
   ```
   ⚠️ Qdrant 集合 memory_xxx 的向量维度不匹配！现有: 1536, 需要: 1024
   🔄 将删除并重新创建集合...
   🗑️ 已删除旧集合: memory_xxx
   ✅ Qdrant 集合已创建: memory_xxx (向量维度: 1024)
   ```

### 方法 2: 手动清理（测试环境）

如果需要手动清理所有 Qdrant 数据：

```powershell
# 交互式清理（会提示确认）
.\scripts\clean_qdrant_data.ps1

# 强制清理（不提示确认）
.\scripts\clean_qdrant_data.ps1 -Force
```

**注意**: 清理前请先停止后端服务！

---

**最后更新**: 2026-01-23
**相关文档**:
- `docs/CHROMADB_ALTERNATIVES.md` - ChromaDB 替代方案调研
- `scripts/check_vector_store_backend.py` - 向量数据库后端检查脚本
- `scripts/clean_qdrant_data.ps1` - Qdrant 数据清理脚本

