# ChromaDB 替代方案调研

## 🔥 当前问题

**ChromaDB 的 Rust 扩展在多线程环境下不是线程安全的**，会导致 Windows 访问冲突崩溃：

```
Windows fatal exception: access violation
File "chromadb\api\rust.py", line 452 in _add
```

即使使用 Python 线程锁（`threading.Lock()`）也无法完全解决，因为崩溃发生在 Rust 原生代码层面。

---

## 📊 向量数据库对比

### 1. **FAISS** (Facebook AI Similarity Search)

**优势**：
- ✅ **CPU 版本线程安全**（读操作）
- ✅ 性能极高，Facebook 开源
- ✅ 支持多种索引类型（IVF, HNSW, PQ 等）
- ✅ 纯内存操作，速度快
- ✅ LangChain 原生支持

**劣势**：
- ❌ GPU 版本不是线程安全的
- ❌ 写操作需要加锁
- ❌ 需要手动管理持久化

**线程安全性**：
- CPU 索引：读操作线程安全，写操作需要加锁
- GPU 索引：完全不线程安全

**适用场景**：
- ✅ 读多写少的场景
- ✅ 需要极高性能的场景
- ✅ 可以接受手动管理持久化

**安装**：
```bash
pip install faiss-cpu  # CPU 版本
pip install faiss-gpu  # GPU 版本（需要 CUDA）
```

**LangChain 集成**：
```python
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

vectorstore = FAISS.from_documents(documents, OpenAIEmbeddings())
```

---

### 2. **Qdrant**

**优势**：
- ✅ **完全线程安全**（Rust 实现，内置并发控制）
- ✅ 支持本地模式和服务器模式
- ✅ 支持过滤、分页、批量操作
- ✅ 自动持久化
- ✅ LangChain 原生支持

**劣势**：
- ❌ 服务器模式需要额外部署
- ❌ 本地模式性能略低于 FAISS

**线程安全性**：
- ✅ 完全线程安全（Rust 实现）
- ✅ 支持并发读写

**适用场景**：
- ✅ 需要线程安全的场景（**推荐**）
- ✅ 需要持久化的场景
- ✅ 需要过滤和元数据查询

**安装**：
```bash
pip install qdrant-client
```

**LangChain 集成**：
```python
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient

client = QdrantClient(path="./qdrant_data")  # 本地模式
vectorstore = Qdrant(client=client, collection_name="my_collection", embeddings=embeddings)
```

---

### 3. **LanceDB**

**优势**：
- ✅ **线程安全**（Rust 实现）
- ✅ 基于 Apache Arrow，性能高
- ✅ 支持 SQL 查询
- ✅ 自动持久化
- ✅ 轻量级，无需服务器

**劣势**：
- ❌ 相对较新，生态不如 FAISS/Qdrant 成熟
- ❌ LangChain 支持较新

**线程安全性**：
- ✅ 线程安全（Rust 实现）

**适用场景**：
- ✅ 需要 SQL 查询的场景
- ✅ 需要轻量级解决方案

**安装**：
```bash
pip install lancedb
```

---

## 🎯 推荐方案

### **方案 1：切换到 Qdrant（推荐）**

**理由**：
1. ✅ **完全线程安全**，Rust 实现，内置并发控制
2. ✅ 本地模式无需额外部署
3. ✅ LangChain 原生支持，迁移成本低
4. ✅ 自动持久化，无需手动管理

**迁移步骤**：
1. 安装 `qdrant-client`
2. 修改 `core/memory/memory_manager.py`，替换 ChromaDB 为 Qdrant
3. 保持 API 接口不变，只替换底层实现

---

### **方案 2：继续使用 ChromaDB + 完善线程锁**

**理由**：
1. ✅ 无需迁移，保持现有代码
2. ✅ 已添加详细日志，便于调试

**风险**：
- ⚠️ Rust 扩展崩溃可能无法完全避免
- ⚠️ 需要持续监控和调试

---

## 📝 下一步行动

1. **短期**：
   - 使用新增的日志定位崩溃的具体操作
   - 验证线程锁是否生效

2. **中期**：
   - 如果崩溃持续，考虑切换到 Qdrant
   - 准备迁移脚本和测试

3. **长期**：
   - 评估是否需要向量数据库（如果只是简单的记忆功能，可以考虑禁用）

---

**最后更新**: 2026-01-23  
**相关文档**: `docs/deployment/CHROMADB_THREAD_SAFETY.md`

