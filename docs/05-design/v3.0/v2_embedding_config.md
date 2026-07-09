# v2.0 Embedding 配置获取指南

## 概述

v2.0 系统支持从数据库配置中获取 Embedding 模型和参数。系统会优先使用系统配置的默认 Embedding 模型，如果没有配置则使用厂家配置的模型。

## 配置优先级

1. **系统配置** (`system_settings.default_embedding_model`)
   - 格式：`厂商名:模型名`（如：`dashscope:text-embedding-v3`）
   - 优先级最高，会覆盖厂家配置

2. **厂家配置** (`llm_providers.embedding_model`)
   - 如果厂家配置了 `embedding_model`，使用配置的模型

3. **默认模型**
   - 如果以上都没有配置，使用系统默认模型列表

## 获取配置的方式

### 方式1：通过 WorkflowBuilder

```python
from core.workflow.builder import WorkflowBuilder

# 创建 WorkflowBuilder（会自动初始化 EmbeddingManager）
builder = WorkflowBuilder()

# 获取 Embedding 配置信息
if builder.embedding_manager:
    config = builder.embedding_manager.get_config()
    
    # config 包含以下信息：
    # {
    #     "primary_provider": {
    #         "name": "dashscope",
    #         "display_name": "阿里云百炼",
    #         "model": "text-embedding-v3",
    #         "base_url": "https://dashscope.aliyuncs.com/api/v1"
    #     },
    #     "fallback_providers": [...],
    #     "total_providers": 2,
    #     "has_provider": True
    # }
    
    primary = config['primary_provider']
    print(f"主提供商: {primary['display_name']}")
    print(f"模型: {primary['model']}")
```

### 方式2：直接创建 EmbeddingManager

```python
from core.llm import EmbeddingManager
from app.core.database import get_mongo_db_sync

# 获取数据库连接
db = get_mongo_db_sync()

# 创建 EmbeddingManager
embedding_mgr = EmbeddingManager(db=db)

# 获取配置信息
config = embedding_mgr.get_config()
```

## 使用 Embedding

### 获取文本的 Embedding 向量

```python
# 通过 WorkflowBuilder
builder = WorkflowBuilder()
if builder.embedding_manager:
    embedding, provider_name = builder.embedding_manager.get_embedding("要向量化的文本")
    if embedding:
        print(f"Embedding 维度: {len(embedding)}")
        print(f"使用的提供商: {provider_name}")
```

### 在 Agent 中使用

```python
class MyAgent(BaseAgent):
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 从 state 中获取 embedding_manager（如果已设置）
        embedding_manager = state.get('embedding_manager')
        
        if embedding_manager:
            # 获取文本的 embedding
            text = "要向量化的文本"
            embedding, provider = embedding_manager.get_embedding(text)
            
            if embedding:
                # 使用 embedding 进行后续处理
                # ...
                pass
```

## 配置信息结构

`get_config()` 方法返回的配置信息结构：

```python
{
    "primary_provider": {
        "name": str,              # 提供商名称（如：dashscope）
        "display_name": str,       # 显示名称（如：阿里云百炼）
        "model": str,              # 模型名称（如：text-embedding-v3）
        "base_url": str           # API 地址
    },
    "fallback_providers": [       # 备用提供商列表
        {
            "name": str,
            "display_name": str,
            "model": str,
            "base_url": str
        },
        ...
    ],
    "total_providers": int,        # 提供商总数
    "has_provider": bool          # 是否有可用的提供商
}
```

**注意**：出于安全考虑，配置信息中**不包含 API Key**。

## 系统配置示例

### 在系统设置中配置默认 Embedding 模型

1. 进入"设置" → "配置管理" → "系统设置"
2. 找到"默认 Embedding 模型"配置项
3. 选择厂商和模型（格式：`厂商:模型名`）
4. 保存设置

例如：
- `dashscope:text-embedding-v3`
- `openai:text-embedding-3-small`

### 在厂家管理中配置 Embedding 模型

1. 进入"设置" → "配置管理" → "厂家管理"
2. 编辑支持 embedding 的厂家
3. 勾选"向量化"功能
4. 在"Embedding 模型"字段中输入模型名称
5. 保存设置

## 日志和调试

EmbeddingManager 会输出详细的日志信息：

```
📋 从系统配置读取默认 Embedding 模型: dashscope:text-embedding-v3
🎯 优先使用系统配置的 Embedding 模型: dashscope:text-embedding-v3
✅ 使用系统配置的 Embedding 模型: dashscope:text-embedding-v3
📋 加载 Embedding 提供商: 阿里云百炼 (模型: text-embedding-v3)
🎯 主 Embedding 提供商: 阿里云百炼 (模型: text-embedding-v3)
```

## 错误处理

如果配置获取失败，系统会：

1. 尝试从环境变量初始化
2. 如果环境变量也没有配置，会记录警告日志
3. `get_config()` 会返回 `has_provider: False`

```python
config = embedding_mgr.get_config()
if not config['has_provider']:
    logger.warning("没有可用的 Embedding 提供商，记忆功能将被禁用")
```

## 完整示例

参考 `docs/examples/v2_embedding_config_example.py` 查看完整的使用示例。
