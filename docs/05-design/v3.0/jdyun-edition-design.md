# 京东云合作版定制设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 JD Cloud Edition |
| 分支 | `release/jdyun-v3.0` |
| 基础分支 | `pro/main` (3e210606d) |
| 日期 | 2026-07-17 |
| 状态 | ✅ 已实施（Phase 1-6 完成，Phase 7 品牌定制暂缓） |
| 实施完成日期 | 2026-07-18 |

---

## 1. 定制目标

将 TradingAgents-CN Pro v3.0 改造为京东云合作版，核心原则：

- **极简配置**：用户无需在界面上配置大模型和数据源
- **环境变量驱动**：所有配置通过京东云平台注入的环境变量读取
- **单一模型源**：只有京东云平台一个 LLM Provider
- **单一数据源**：只有 Tushare 一个数据源
- **模型可选**：用户可从 4 个预置模型中选择

---

## 2. 京东云环境变量

京东云平台会注入以下环境变量：

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `OPENAI_API_BASE` | 京东云模型服务地址 | `https://modelservice.jdcloud.com/v1` |
| `OPENAI_API_KEY` | 京东云 API Key | `<由京东云提供>` |
| `OPENAI_MODEL` | 默认对话模型（4选1） | `GLM-5` / `GLM-5.1` / `GLM-5.2` / `DeepSeek-V4-Flash` |
| `EMBEDDING_MODEL` | Embedding 模型 | `Qwen3-Embedding-8B` |
| `TUSHARE_TOKEN` | Tushare 数据源 Token | `<由用户提供>` |

> **说明**: 对话模型和 Embedding 模型共用同一个 `OPENAI_API_BASE` 和 `OPENAI_API_KEY`，京东云模型服务同时支持 `/v1/chat/completions` 和 `/v1/embeddings` 端点。

---

## 3. 需要修改的模块

### 3.1 后端修改

#### 3.1.1 新增京东云模式检测

**文件**: `app/core/config.py`

**修改内容**: Settings 类新增字段

```python
# 京东云合作版配置
JDYUN_MODE: bool = Field(default=False, description="京东云合作版模式开关")
OPENAI_API_BASE: str = Field(default="", description="OpenAI兼容API地址（京东云模型服务）")
OPENAI_API_KEY: str = Field(default="", description="OpenAI兼容API Key")
OPENAI_MODEL: str = Field(default="", description="默认对话模型名称")
EMBEDDING_MODEL: str = Field(default="", description="Embedding模型名称")
```

**影响范围**: 仅新增字段，不影响现有逻辑

---

#### 3.1.2 LLM 配置查询链路

**文件**: `app/services/simple_analysis_service.py`

**修改函数**: `get_provider_and_url_by_model_sync()`

**修改内容**: 在函数开头添加京东云模式短路逻辑

```python
def get_provider_and_url_by_model_sync(model_name, ...):
    # 🔧 京东云模式：直接使用环境变量配置，跳过数据库查询
    if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
        jdyun_api_base = os.getenv("OPENAI_API_BASE", "")
        jdyun_api_key = os.getenv("OPENAI_API_KEY", "")
        jdyun_model = os.getenv("OPENAI_MODEL", "") or model_name
        
        if jdyun_api_base and jdyun_api_key:
            # 如果传入的 model_name 是 jdyun 预置模型之一，使用它
            # 否则使用 OPENAI_MODEL 环境变量中的模型
            jdyun_models = ["GLM-5", "GLM-5.1", "GLM-5.2", "DeepSeek-V4-Flash"]
            effective_model = model_name if model_name in jdyun_models else jdyun_model
            
            return {
                "provider": "jdyun",
                "backend_url": jdyun_api_base,
                "api_key": jdyun_api_key,
                "model": effective_model,
            }
    
    # ... 原有数据库查询逻辑保持不变
```

**影响范围**: 京东云模式开启时短路返回，不影响原有逻辑

**同样需要修改的函数**:
- `_get_env_api_key_for_provider()`: 添加 `"jdyun": "OPENAI_API_KEY"` 映射
- `_get_default_backend_url()`: 添加 `"jdyun"` 的默认 URL（从环境变量读取）
- `_get_default_provider_by_model()`: 添加 4 个京东云模型的 provider 映射

---

#### 3.1.3 工作流引擎 LLM 创建

**文件**: `core/workflow/builder.py`

**修改类**: `LegacyDependencyProvider._create_llm_instances()`

**修改内容**: 京东云模式下，quick_model 和 deep_model 都使用 `OPENAI_MODEL` 环境变量

```python
def _create_llm_instances(self, force_refresh=False):
    # 🔧 京东云模式：使用环境变量配置
    if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
        jdyun_model = os.getenv("OPENAI_MODEL", "GLM-5")
        self._quick_llm = create_llm_by_provider(
            provider="jdyun",
            model=jdyun_model,
            backend_url=os.getenv("OPENAI_API_BASE", ""),
            ...
        )
        self._deep_llm = self._quick_llm  # 京东云版 quick 和 deep 使用同一模型
        return
    # ... 原有逻辑
```

**影响范围**: 京东云模式开启时短路，不影响原有逻辑

---

#### 3.1.4 Tushare Token 配置

**文件**: `app/core/config_bridge.py`

**修改内容**: 京东云模式下，强制使用环境变量中的 TUSHARE_TOKEN，跳过数据库查询

```python
# 京东云模式下，直接使用环境变量
if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
    env_token = os.getenv("TUSHARE_TOKEN", "")
    if env_token:
        logger.info("✓ 京东云模式：使用环境变量中的 TUSHARE_TOKEN")
    else:
        logger.warning("⚠️ 京东云模式：TUSHARE_TOKEN 环境变量未设置")
    return  # 跳过数据库查询
```

**影响范围**: 京东云模式开启时短路

---

#### 3.1.5 Embedding 模型配置

**涉及文件**:
- `core/memory/config.py` — mem0 配置构建
- `core/memory/local_embedder.py` — 本地 Embedding
- `app/services/config_service.py` — Embedding 配置查询

**修改内容**: 京东云模式下，Embedding 使用京东云 Qwen3-Embedding-8B，复用 `OPENAI_API_BASE` 和 `OPENAI_API_KEY`

```python
# core/memory/config.py 中的 build_mem0_config() 函数
if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
    config = {
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-8B"),
                "openai_base_url": os.getenv("OPENAI_API_BASE", ""),
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "embedding_dims": 4096,  # Qwen3-Embedding-8B 输出维度
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "jdyun_memories",
                "embedding_model_dims": 4096,
            },
        },
    }
    return config
```

**注意事项**:
- Qwen3-Embedding-8B 输出维度为 4096，需确保 Qdrant collection 维度匹配
- 向量迁移功能可用于从其他 Embedding 模型迁移到 Qwen3-Embedding-8B
- `app/services/config_service.py` 中的 `get_qdrant_collections()` 和 `migrate_qdrant_collection()` 无需修改，已支持动态维度

**影响范围**: 京东云模式开启时，记忆系统使用京东云 Embedding 服务

---

#### 3.1.6 API 端点保护

**文件**: `app/routers/config.py`

**修改内容**: 京东云模式下，禁用 Provider/数据源/Embedding 的增删改 API

需要保护的端点：
- `POST /api/config/llm/providers` — 新增 Provider
- `PUT /api/config/llm/providers/{id}` — 修改 Provider
- `DELETE /api/config/llm/providers/{id}` — 删除 Provider
- `POST /api/config/llm/providers/{id}/models` — 新增模型
- `PUT /api/config/llm/models/{id}` — 修改模型
- `DELETE /api/config/llm/models/{id}` — 删除模型
- `POST /api/config/datasources` — 新增数据源
- `PUT /api/config/datasources/{id}` — 修改数据源
- `DELETE /api/config/datasources/{id}` — 删除数据源

**保护方式**: 返回 403 Forbidden + 提示信息

```python
# 京东云模式下禁用配置修改
if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
    raise HTTPException(
        status_code=403,
        detail="京东云合作版不支持修改大模型和数据源配置，请通过环境变量配置"
    )
```

**新增端点**: `GET /api/config/jdyun/status` — 返回京东云配置状态

```python
@router.get("/jdyun/status")
async def get_jdyun_status():
    return {
        "jdyun_mode": True,
        "api_base": os.getenv("OPENAI_API_BASE", ""),
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "current_model": os.getenv("OPENAI_MODEL", ""),
        "available_models": ["GLM-5", "GLM-5.1", "GLM-5.2", "DeepSeek-V4-Flash"],
        "embedding_model": os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-8B"),
        "embedding_dims": 4096,
        "tushare_token_configured": bool(os.getenv("TUSHARE_TOKEN")),
    }
```

---

#### 3.1.7 Provider 初始化

**文件**: `app/scripts/init_providers.py`

**修改内容**: 京东云模式下，只初始化一个 "jdyun" Provider 和 4 个模型

```python
if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
    # 只初始化京东云 Provider
    jdyun_provider = {
        "name": "jdyun",
        "display_name": "京东云",
        "default_base_url": os.getenv("OPENAI_API_BASE", ""),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        ...
    }
    # 初始化 4 个模型（均可用作 quick_model 或 deep_model）
    jdyun_models = [
        {"model_name": "GLM-5", "display_name": "GLM-5"},
        {"model_name": "GLM-5.1", "display_name": "GLM-5.1"},
        {"model_name": "GLM-5.2", "display_name": "GLM-5.2"},
        {"model_name": "DeepSeek-V4-Flash", "display_name": "DeepSeek-V4-Flash"},
    ]
    return  # 跳过其他 Provider 初始化
```

---

#### 3.1.8 数据库自动初始化（方案B）

**文件**: `app/main.py`（启动流程）

**修改内容**: 京东云版首次启动时，从环境变量自动写入数据库配置

```python
# app/main.py 启动时
if os.getenv("JDYUN_MODE", "").lower() in ("true", "1", "yes"):
    from app.services.jdyun_init import init_jdyun_config
    await init_jdyun_config()
```

**新建文件**: `app/services/jdyun_init.py`

```python
async def init_jdyun_config():
    """京东云版首次启动时从环境变量初始化数据库配置"""
    # 1. 检查是否已初始化（避免重复）
    if await _is_jdyun_initialized():
        return
    
    # 2. 写入 jdyun Provider
    provider = {
        "name": "jdyun",
        "display_name": "京东云",
        "default_base_url": os.getenv("OPENAI_API_BASE", ""),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }
    
    # 3. 写入 4 个模型配置
    models = [
        {"model_name": "GLM-5", "provider": "jdyun", "category": "chat"},
        {"model_name": "GLM-5.1", "provider": "jdyun", "category": "chat"},
        {"model_name": "GLM-5.2", "provider": "jdyun", "category": "chat"},
        {"model_name": "DeepSeek-V4-Flash", "provider": "jdyun", "category": "chat"},
    ]
    
    # 4. 写入默认 quick/deep 模型配置
    default_model = os.getenv("OPENAI_MODEL", "GLM-5")
    system_config = {
        "quick_think_llm": default_model,
        "deep_think_llm": default_model,
    }
    
    # 5. 写入 Tushare 数据源配置
    tushare_config = {
        "name": "tushare",
        "api_key": os.getenv("TUSHARE_TOKEN", ""),
        "enabled": True,
    }
    
    # 6. 写入 Embedding 配置
    embedding_config = {
        "provider": "openai",
        "model": os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-8B"),
        "api_base": os.getenv("OPENAI_API_BASE", ""),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "embedding_dims": 4096,
    }
    
    # 7. 标记已初始化
    await _mark_jdyun_initialized()
```

**优势**: 系统其他模块无需修改查询逻辑，仍从数据库读取配置；环境变量变化时重启服务即可刷新。

---

### 3.2 前端修改

#### 3.2.1 Settings 页面菜单隐藏

**文件**: `frontend/src/views/Settings/index.vue`

**修改内容**: 京东云模式下隐藏以下菜单项

| 菜单组 | 菜单项 | 处理方式 |
|--------|--------|----------|
| 系统配置 | 配置管理 | **替换**为"京东云配置" |
| 系统配置 | 使用统计 | 保留 |
| 系统配置 | 缓存管理 | 保留 |
| 系统管理 | 数据库管理 | 保留 |
| 系统管理 | 操作日志 | 保留 |
| 系统管理 | 多数据源同步 | **隐藏** |
| 系统管理 | 工具能力索引 | 保留 |

**实现方式**: 通过前端环境变量 `VITE_JDYUN_MODE` 控制

```vue
<!-- 京东云模式下显示 -->
<el-menu-item v-if="isJdyunMode" index="jdyun">
  <el-icon><Cpu /></el-icon>
  <span>京东云配置</span>
</el-menu-item>

<!-- 非京东云模式显示 -->
<el-menu-item v-if="!isJdyunMode" index="config">
  <el-icon><Tools /></el-icon>
  <span>配置管理</span>
</el-menu-item>
```

---

#### 3.2.2 新增京东云配置页面

**文件**: `frontend/src/views/Settings/JdyunConfig.vue`（新建）

**页面内容**:
- 京东云 API 状态显示（已连接/未连接）
- 当前模型显示
- 模型切换（4个模型下拉选择）
- Tushare 数据源状态显示
- 不可修改的配置项（只读展示）

**交互**: 用户可切换模型，切换后调用后端 API 更新 `OPENAI_MODEL` 运行时配置

---

#### 3.2.3 ConfigManagement 页面处理

**文件**: `frontend/src/views/Settings/ConfigManagement.vue`

**修改内容**: 京东云模式下，重定向到 `JdyunConfig.vue`

**实现方式**: 路由守卫或组件内检测

```typescript
// 京东云模式下重定向
if (isJdyunMode()) {
  router.replace('/settings/jdyun')
}
```

---

#### 3.2.4 数据源配置界面隐藏

**涉及组件**:
- `frontend/src/views/Settings/components/DataSourceConfigDialog.vue` — 隐藏入口
- `frontend/src/views/Settings/components/DataSourceGroupingDialog.vue` — 隐藏入口
- `frontend/src/views/Settings/components/SortableDataSourceList.vue` — 隐藏入口

**实现方式**: 京东云模式下不渲染这些组件

---

#### 3.2.5 前端环境变量

**文件**: `frontend/.env.production`（新增）或构建时注入

```bash
# 京东云合作版标志
VITE_JDYUN_MODE=true
```

**文件**: `frontend/src/utils/config.ts`（新增或修改）

```typescript
export const isJdyunMode = (): boolean => {
  return import.meta.env.VITE_JDYUN_MODE === 'true'
}
```

---

#### 3.2.6 路由修改

**文件**: `frontend/src/router/index.ts`

**修改内容**: 京东云模式下添加 `/settings/jdyun` 路由

```typescript
{
  path: 'jdyun',
  name: 'JdyunConfig',
  component: () => import('@/views/Settings/JdyunConfig.vue'),
  meta: { title: '京东云配置' }
}
```

---

#### 3.2.7 模型选择组件

**涉及页面**:
- `frontend/src/views/Analysis/SingleAnalysis.vue` — 单股分析模型选择
- `frontend/src/views/Analysis/BatchAnalysis.vue` — 批量分析模型选择
- `frontend/src/views/Settings/ScheduledAnalysis.vue` — 定时分析模型选择

**修改内容**: 京东云模式下，模型选择下拉框只显示 4 个京东云模型

---

### 3.3 品牌定制（暂缓）

> ⏸️ 等京东云提供品牌素材后再实施。当前阶段保持原有品牌不变。

#### 3.3.1 关于页面（暂缓）

**文件**: `frontend/src/views/About/index.vue`

**修改内容**（等素材后实施）:
- 产品名称添加"京东云合作版"标识
- 赞助商区域替换为京东云
- 技术支持信息替换

---

#### 3.3.2 引导页面（暂缓）

**文件**: `frontend/src/views/Guide/index.vue`

**修改内容**（等素材后实施）:
- 配置指引替换为京东云环境变量配置说明
- 移除多 Provider 配置说明
- 移除多数据源配置说明

---

#### 3.3.3 登录页面（暂缓）

**文件**: `frontend/src/views/Login/index.vue`

**修改内容**（等素材后实施）:
- Logo 替换为京东云合作版
- 产品名称更新

---

### 3.4 配置文件修改

#### 3.4.1 环境变量示例

**文件**: `.env.example`

**修改内容**: 添加京东云环境变量示例

```bash
# ===== 京东云合作版配置 =====
# 京东云模式开关（设置为 true 启用京东云合作版模式）
JDYUN_MODE=false

# 京东云模型服务地址
OPENAI_API_BASE=https://modelservice.jdcloud.com/v1

# 京东云 API Key
OPENAI_API_KEY=

# 默认对话模型（可选：GLM-5 / GLM-5.1 / GLM-5.2 / DeepSeek-V4-Flash）
OPENAI_MODEL=GLM-5

# Embedding 模型（用于记忆系统）
EMBEDDING_MODEL=Qwen3-Embedding-8B

# Tushare 数据源 Token
TUSHARE_TOKEN=
```

---

#### 3.4.2 数据库初始化

**文件**: `install/database_export_config.json`

**修改内容**: 预置京东云 Provider 和 4 个模型配置（仅京东云版使用）

---

#### 3.4.3 前端环境变量

**文件**: `frontend/.env.jdyun`（新建）

```bash
VITE_JDYUN_MODE=true
VITE_APP_TITLE=TradingAgents-CN 京东云版
```

---

### 3.5 部署相关

#### 3.5.1 Docker 配置

**文件**: `docker/docker-compose.compiled.yml`

**修改内容**: 京东云版环境变量注入

```yaml
environment:
  - JDYUN_MODE=true
  - OPENAI_API_BASE=https://modelservice.jdcloud.com/v1
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - OPENAI_MODEL=${OPENAI_MODEL:-GLM-5}
  - TUSHARE_TOKEN=${TUSHARE_TOKEN}
```

---

#### 3.5.2 启动脚本

**文件**: `start_dev.ps1`

**修改内容**: 支持京东云模式启动参数

```powershell
# 京东云模式启动
.\start_dev.ps1 backend 3.0 --jdyun
```

---

#### 3.5.3 打包脚本

**文件**: `scripts/deployment/build_pro_package.ps1`

**修改内容**: 添加京东云版打包选项

```powershell
# 京东云版打包
.\build_pro_package.ps1 -Edition jdyun
```

---

#### 3.5.4 NSIS 安装包

**文件**: `scripts/windows-installer/nsis/installer.nsi`

**修改内容**:
- 安装界面品牌替换
- 安装目录默认值调整
- 环境变量配置引导

---

## 4. 修改清单总览

### 4.1 后端文件（10 个）

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `app/core/config.py` | 修改 | 新增 JDYUN_MODE 等字段 |
| `app/services/simple_analysis_service.py` | 修改 | LLM 查询添加京东云短路逻辑 |
| `core/workflow/builder.py` | 修改 | LLM 创建添加京东云短路逻辑 |
| `app/core/config_bridge.py` | 修改 | Tushare Token 添加京东云短路逻辑 |
| `core/memory/config.py` | 修改 | Embedding 配置添加京东云短路逻辑 |
| `app/routers/config.py` | 修改 | API 保护 + 新增 jdyun/status 端点 |
| `app/scripts/init_providers.py` | 修改 | 京东云 Provider 初始化 |
| `app/services/config_service.py` | 修改 | 京东云模式下的配置查询逻辑 |
| `app/services/jdyun_init.py` | **新建** | 首次启动从环境变量初始化数据库 |
| `.env.example` | 修改 | 添加京东云环境变量示例 |

### 4.2 前端文件（7 个，品牌定制暂缓）

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `frontend/src/views/Settings/index.vue` | 修改 | 隐藏配置管理菜单，添加京东云配置入口 |
| `frontend/src/views/Settings/JdyunConfig.vue` | **新建** | 京东云配置状态页面 |
| `frontend/src/views/Settings/ConfigManagement.vue` | 修改 | 京东云模式下重定向 |
| `frontend/src/router/index.ts` | 修改 | 添加京东云配置路由 |
| `frontend/src/utils/config.ts` | 修改/新建 | 京东云模式检测工具 |
| `frontend/src/views/Analysis/SingleAnalysis.vue` | 修改 | 模型选择限制为4个京东云模型 |
| `frontend/.env.jdyun` | **新建** | 京东云版前端环境变量 |

> ⏸️ 品牌定制相关文件（About、Guide、Login）暂缓，等素材后再改

### 4.3 部署文件（4 个）

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `docker/docker-compose.compiled.yml` | 修改 | 京东云环境变量 |
| `start_dev.ps1` | 修改 | 京东云模式启动参数 |
| `scripts/deployment/build_pro_package.ps1` | 修改 | 京东云版打包选项 |
| `scripts/windows-installer/nsis/installer.nsi` | 修改 | 安装界面品牌 |

### 4.4 数据文件（1 个）

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `install/database_export_config.json` | 修改 | 预置京东云 Provider 和模型 |

---

## 5. 不修改的部分

以下模块**不做修改**，保持原有逻辑：

- ✅ 分析引擎核心（`tradingagents/graph/`）
- ✅ Agent 适配器（`core/agents/adapters/`）
- ✅ 工作流引擎（`core/workflow/`）
- ✅ 工具系统（`core/tools/`）
- ✅ 记忆系统（`core/memory/`）
- ✅ 个人设置（外观、分析偏好、通知等）
- ✅ 分析历史、报告、持仓等功能
- ✅ 数据库管理、操作日志
- ✅ 缓存管理、使用统计

---

## 6. 风险和注意事项

### 6.1 Embedding 模型维度

Qwen3-Embedding-8B 输出维度为 4096，与现有系统可能使用的其他 Embedding 模型（如 1024 维的 text-embedding-v4）不兼容。切换到京东云版时：
- 需要创建新的 Qdrant collection（维度 4096）
- 旧向量数据需要通过向量迁移功能重新编码
- 迁移过程中记忆功能暂时不可用

### 6.2 模型切换

京东云版保持与现有版本一致的模型切换机制：

- **4 个模型均可作为 quick_model 或 deep_model**：GLM-5、GLM-5.1、GLM-5.2、DeepSeek-V4-Flash
- **默认模型设置**：用户可在设置页面设置默认的快速分析模型和深度分析模型
- **分析时切换**：分析页面可选择不同模型进行本次分析
- **模型列表来源**：从数据库 `llm_configs` 集合读取（首次启动时从环境变量初始化）

**前端模型选择组件**：京东云模式下，模型下拉框只显示 4 个京东云模型，不显示其他 Provider 的模型。

### 6.3 数据源单一性

京东云版只有 Tushare 一个数据源，需要：
- 禁用数据源轮换机制
- 禁用 AKShare、BaoStock 等其他数据源
- 确保 Tushare Token 有效性检测

### 6.4 兼容性

所有修改通过 `JDYUN_MODE` 环境变量控制，当 `JDYUN_MODE=false` 或未设置时，系统行为与现有版本完全一致。

---

## 7. 实施顺序建议

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| Phase 1 | 后端京东云模式检测和环境变量读取 | 1 天 |
| Phase 2 | LLM 配置链路改造（含 Embedding） | 1 天 |
| Phase 3 | 数据库自动初始化 + API 端点保护 | 0.5 天 |
| Phase 4 | 前端配置页面替换（隐藏配置管理，新增京东云配置页） | 1 天 |
| Phase 5 | 部署脚本和打包 | 0.5 天 |
| Phase 6 | 测试和验证 | 1 天 |
| Phase 7 | 品牌定制（等素材后实施） | ⏸️ 暂缓 |

**总计**: 约 5 天（品牌定制暂缓）

---

## 8. 待确认事项

1. ~~**Embedding 模型**: 京东云是否提供 Embedding 接口？~~ ✅ 已确认：使用 Qwen3-Embedding-8B
2. ~~**模型切换**: 用户是否需要运行时切换模型？~~ ✅ 已确认：与现有版本一致，用户可设置默认模型，分析时可选择不同模型
3. ~~**品牌资料**: 京东云合作版的产品名称、Logo、配色方案？~~ ⏸️ 暂缓，等素材
4. ~~**Tushare Token**: 是京东云统一提供，还是用户自行注册？~~ ✅ 已确认：由京东云统一提供
5. ~~**数据库初始化**: 京东云版是否需要预置数据库配置？~~ ✅ 已确认：采用方案B，首次启动从环境变量自动初始化
6. ~~**快速分析 vs 深度分析**: 京东云版是否区分 quick_model 和 deep_model？~~ ✅ 已确认：保持双模型机制，4个模型都可选为 quick 或 deep

---

## 9. 实施进度

> 更新日期: 2026-07-18

### Phase 1: 后端京东云模式检测和环境变量读取 ✅ 已完成

- ✅ `app/core/jdyun.py` 新建：京东云配置核心模块（is_jdyun_mode、get_jdyun_status 等）
- ✅ `app/core/config.py` 修改：Settings 类新增 JDYUN_MODE / OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_MODEL / EMBEDDING_MODEL 字段
- ✅ `.env.example` 修改：添加京东云环境变量示例

### Phase 2: LLM 配置链路改造（含 Embedding） ✅ 已完成

- ✅ `app/services/simple_analysis_service.py` 修改：get_provider_and_url_by_model_sync() 添加京东云短路逻辑
- ✅ `tradingagents/graph/trading_graph.py` 修改：支持 jdyun provider
- ✅ `core/workflow/builder.py` 修改：LLM 实例创建添加京东云逻辑
- ✅ `app/core/config_bridge.py` 修改：Tushare Token 桥接添加京东云短路逻辑
- ✅ `core/memory/config.py` 修改：mem0 记忆系统 Embedding 配置添加京东云短路逻辑

### Phase 3: 数据库自动初始化 + API 端点保护 ✅ 已完成

- ✅ `app/services/jdyun_init.py` 新建：首次启动从环境变量初始化数据库 Provider/Model/数据源
- ✅ `app/main.py` 修改：启动流程中调用 init_jdyun_config()
- ✅ `app/routers/config.py` 修改：京东云模式下禁用 Provider/数据源/模型增删改 API（返回 403），新增 `/api/config/jdyun/status` 状态查询端点

### Phase 4: 前端配置页面替换 ✅ 已完成

- ✅ `frontend/src/utils/config.ts` 新建：isJdyunMode() / JDYUN_CHAT_MODELS / getAvailableModels()
- ✅ `frontend/.env.jdyun` 新建：VITE_JDYUN_MODE=true
- ✅ `frontend/src/views/Settings/JdyunConfig.vue` 新建：京东云配置状态页（只读展示）
- ✅ `frontend/src/api/config.ts` 修改：添加 getJdyunStatus() API 方法
- ✅ `frontend/src/router/index.ts` 修改：添加 jdyun-config 路由
- ✅ `frontend/src/components/Layout/SidebarMenu.vue` 修改：京东云模式下替换"配置管理"为"系统配置"
- ✅ `frontend/src/views/Settings/index.vue` 修改：京东云模式下隐藏配置管理菜单和卡片，显示系统配置入口
- ✅ `frontend/src/views/Settings/ConfigManagement.vue` 修改：京东云模式下自动重定向到 jdyun-config
- ✅ `frontend/src/views/Analysis/SingleAnalysis.vue` 修改：京东云模式下限制模型选择为4个预置模型
- ✅ `frontend/src/views/Analysis/BatchAnalysis.vue` 修改：同上
- ✅ `frontend/src/views/Analysis/GeneralAnalysis.vue` 修改：同上

### Phase 5: 部署脚本和打包 ✅ 已完成

- ✅ `docker/docker-compose.jdyun.yml` 新建：京东云版 Docker Compose 配置（4服务：mongodb/redis/backend/frontend/nginx）
- ✅ `docker/Dockerfile.frontend.jdyun` 新建：多阶段构建前端 Dockerfile（容器内构建，自动注入 VITE_JDYUN_MODE=true）
- ✅ `start_dev.ps1` 修改：添加 `[switch]$Jdyun` 参数，backend 子命令注入 JDYUN_MODE=true，frontend 子命令使用 `--mode jdyun` 启动
- ✅ `scripts/deployment/build_pro_package.ps1` 修改：添加 `-Edition jdyun` 参数，前端构建使用 `--mode jdyun`，生成 `.env.jdyun.example` 配置模板
- ⏸️ `scripts/windows-installer/nsis/installer.nsi` 暂缓：等品牌素材后再定制安装界面
- ⏸️ `install/database_export_config.json` 可选：jdyun_init.py 已处理运行时初始化，无需预置

### Phase 6: 测试和验证 ✅ 已完成

- ✅ 后端模块导入验证：app.core.jdyun / app.services.jdyun_init / app.routers.config / app.core.config / app.services.simple_analysis_service / app.core.config_bridge 全部导入成功
- ✅ 京东云模式状态验证：is_jdyun_mode()=True，get_jdyun_status() 返回正确配置信息
- ✅ API 路由验证：`/api/config/jdyun/status` 端点已注册
- ✅ settings.JDYUN_MODE 配置字段验证：正确读取环境变量
- ✅ 前端文件完整性验证：11 个京东云相关前端文件全部存在
- ✅ Docker 配置验证：docker-compose.jdyun.yml 和 Dockerfile.frontend.jdyun 配置完整，依赖文件齐全
- ✅ 脚本语法验证：start_dev.ps1 和 build_pro_package.ps1 语法正确
- ⏸️ 端到端功能测试：待京东云提供实际 API Key 后进行完整流程测试

### Phase 7: 品牌定制 ⏸️ 暂缓

- ⏸️ 等京东云提供品牌素材（产品名称、Logo、配色方案）后实施
- ⏸️ 涉及文件：About.vue / Guide.vue / Login.vue / 安装界面

---

## 10. 部署指南

### 10.1 开发环境启动（京东云模式）

```powershell
# 终端1: 启动 MongoDB + Redis
.\start_dev.ps1 docker 3.0

# 终端2: 以京东云模式启动后端
.\start_dev.ps1 backend 3.0 --jdyun

# 终端3: 以京东云模式启动前端（加载 .env.jdyun）
.\start_dev.ps1 frontend 3.0 --jdyun
```

### 10.2 Docker 部署

```bash
# 1. 复制 .env.jdyun.example 为 .env 并填写京东云凭据
cp .env.jdyun.example .env
# 编辑 .env，填入 OPENAI_API_KEY 和 TUSHARE_TOKEN

# 2. 启动服务
docker-compose -f docker/docker-compose.jdyun.yml up -d

# 3. 访问
# http://your-server:8082
```

### 10.3 打包京东云版便携包

```powershell
# 打包京东云版便携包
.\scripts\deployment\build_pro_package.ps1 -Edition jdyun

# 打包完成后，在 release\TradingAgentsCN-portable 目录下：
# - .env.jdyun.example: 京东云环境变量配置模板
# - .env: 默认配置（需编辑填入实际 API Key）
```

### 10.4 必需的环境变量

| 环境变量 | 必需 | 说明 |
|----------|------|------|
| `JDYUN_MODE` | ✅ | 必须为 `true` |
| `OPENAI_API_BASE` | ✅ | 京东云模型服务地址 |
| `OPENAI_API_KEY` | ✅ | 京东云 API Key |
| `OPENAI_MODEL` | ✅ | 默认对话模型（4选1） |
| `EMBEDDING_MODEL` | ✅ | Embedding 模型（默认 Qwen3-Embedding-8B） |
| `TUSHARE_TOKEN` | ✅ | Tushare 数据源 Token |
