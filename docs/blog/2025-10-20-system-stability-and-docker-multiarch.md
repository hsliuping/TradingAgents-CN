# TradingAgents-CN 系统稳定性提升与多架构支持（2025-10-20）

今天我们完成了一系列重要的系统稳定性改进和功能增强，主要集中在三个方面：**配置系统完善**、**缓存管理功能实现**、**Docker 多架构支持**。所有更改均已合并至 `v1.0.0-preview` 分支。

## 🎯 核心改进

### 1. 配置系统完善 - 支持动态供应商管理

#### 问题背景
用户在"厂家管理"中添加新的 LLM 供应商后，在"大模型配置"中选择该供应商并提交时，后端返回 422 错误，提示 provider 必须是预定义枚举值之一。这限制了系统的扩展性。

#### 解决方案
- **移除枚举限制**：将 `LLMConfig` 和 `LLMConfigRequest` 模型中的 `provider` 字段从枚举类型改为字符串类型
- **支持动态添加**：用户可以添加任意标识符的新供应商，不再受预定义列表限制
- **向后兼容**：现有的预定义供应商标识符仍然有效

#### 相关修复
- **default_base_url 配置生效**：修复了厂家配置的 `default_base_url` 在分析流程中未生效的问题
  - 在 `tradingagents/graph/trading_graph.py` 的 `create_llm_by_provider()` 和 `TradingAgentsGraph.__init__()` 中添加 `base_url` 参数传递
  - 在 `tradingagents/agents/analysts/fundamentals_analyst.py` 中创建新实例时传递原始 LLM 的 `base_url`
  - 实现配置优先级：模型配置 > 厂家配置 > 硬编码默认值

- **API Key 配置优先级**：修复了 `get_provider_and_url_by_model_sync()` 函数，当数据库中没有模型配置时，优先从厂家配置读取 `default_base_url`

- **供应商启用/禁用功能**：
  - 实现厂家级别的启用/禁用功能，状态同步到后端数据库
  - 禁用供应商后，该供应商的所有模型自动从模型选择列表中隐藏
  - 避免用户选择被禁用供应商的模型导致分析失败

- **模型配置启用/禁用**：在模型列表的操作列添加启用/禁用按钮，状态变更持久化到数据库

- **智能模型加载**：对话框打开时同时刷新供应商列表和模型目录，供应商变更时自动加载可用模型

#### 影响范围
- `app/models/config.py`
- `app/core/unified_config.py`
- `app/services/simple_analysis_service.py`
- `app/services/config_service.py`
- `app/routers/config.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/agents/analysts/fundamentals_analyst.py`
- `tradingagents/llm_adapters/dashscope_openai_adapter.py`
- `frontend/src/views/Settings/components/ProviderDialog.vue`
- `frontend/src/views/Settings/ConfigManagement.vue`

---

### 2. 缓存管理功能 - 从模拟数据到真实 API

#### 问题背景
前端缓存管理页面使用模拟数据，未连接真实后端 API，用户无法通过 Web 界面管理缓存。同时，缓存统计数据格式不一致，导致前端显示 "NaN undefined"。

#### 解决方案

**后端实现**：
- 新增缓存管理路由 `app/routers/cache.py`：
  - `GET /api/cache/stats` - 获取缓存统计
  - `DELETE /api/cache/cleanup?days=7` - 清理过期缓存
  - `DELETE /api/cache/clear` - 清空所有缓存
  - `GET /api/cache/details` - 获取缓存详情列表
  - `GET /api/cache/backend-info` - 获取缓存后端信息

**统一缓存统计格式**：
- 修改所有缓存类的 `get_cache_stats()` 返回标准格式：
  - `total_files`: 总文件数
  - `stock_data_count`: 股票数据数量
  - `news_count`: 新闻数据数量
  - `fundamentals_count`: 基本面数据数量
  - `total_size`: 总大小（字节）
  - `total_size_mb`: 总大小（MB）
  - `skipped_count`: 跳过的缓存数量
  - `backend_info`: 后端详细信息（可选）

**前端对接**：
- 新增缓存 API 模块 `frontend/src/api/cache.ts`
- 更新缓存管理页面 `frontend/src/views/Settings/CacheManagement.vue`
  - 移除所有模拟数据
  - 使用真实 API 调用
  - 从 `response.data` 中正确提取数据
  - 添加错误处理和日志

**兼容性改进**：
- 修复自适应缓存系统初始化失败（`cache_dir=None` 处理）
- 修复 MongoDB 缓存统计（添加 'cache' 配置到 `database_manager.get_config()`）
- 支持旧缓存文件的统计（没有元数据文件时直接统计缓存目录）

#### 影响范围
- `app/routers/cache.py` (新增)
- `app/main.py`
- `tradingagents/dataflows/cache/file_cache.py`
- `tradingagents/dataflows/cache/db_cache.py`
- `tradingagents/dataflows/cache/adaptive.py`
- `tradingagents/dataflows/cache/integrated.py`
- `tradingagents/config/database_manager.py`
- `frontend/src/api/cache.ts` (新增)
- `frontend/src/views/Settings/CacheManagement.vue`

---

### 3. SSE 通知系统优化

#### 问题背景
SSE 连接每毫秒发送一次心跳消息，导致数据传输量巨大（5 秒内传输 343 kB）。

#### 根本原因
`pubsub.get_message()` 没有消息时立即返回，导致循环空转，心跳消息每 1ms 发送一次。

#### 解决方案
在没有消息时添加 `await asyncio.sleep(10)`，避免空转，确保心跳间隔为 30 秒。

#### 影响
- 心跳消息现在每 30 秒发送一次
- SSE 连接数据传输量大幅降低
- 不影响实时通知的推送

#### 影响范围
- `app/routers/notifications.py`

---

### 4. Docker 多架构支持 - 解决 ARM 环境运行问题

#### 问题背景
用户反馈 Docker 打包后的镜像不能在 ARM 环境（Apple Silicon、树莓派、AWS Graviton）中运行，出现 "exec format error" 或平台不匹配警告。

#### 解决方案

**修改现有脚本** (`scripts/build-and-publish-linux.sh`)：
- 使用 `docker buildx build` 替代 `docker build`
- 支持 `linux/amd64` 和 `linux/arm64` 架构
- 构建完成后自动推送到 Docker Hub
- **推送完成后自动清理本地镜像和缓存**，释放磁盘空间（5-8GB）

**新增多架构构建脚本**：
- `scripts/build-multiarch.sh` (Linux/macOS)
- `scripts/build-multiarch.ps1` (Windows PowerShell)

**新增详细文档**：
- `docs/deployment/docker/MULTIARCH_BUILD.md` (多架构构建通用指南)
- `docs/deployment/docker/BUILD_MULTIARCH_GUIDE.md` (Ubuntu 服务器专用指南)

#### 使用方法

在 Ubuntu 22.04 服务器上：

```bash
# 基本用法
./scripts/build-and-publish-linux.sh your-dockerhub-username

# 指定版本
./scripts/build-and-publish-linux.sh your-dockerhub-username v1.0.0

# 指定版本和架构
./scripts/build-and-publish-linux.sh your-dockerhub-username v1.0.0 linux/amd64,linux/arm64
```

#### 脚本执行流程

```
步骤1: 检查环境 (Docker, Buildx, Git)
步骤2: 配置 Docker Buildx
步骤3: 登录 Docker Hub
步骤4: 构建并推送后端镜像 (amd64 + arm64)
步骤5: 构建并推送前端镜像 (amd64 + arm64)
步骤6: 验证镜像架构
步骤7: 清理本地镜像和缓存 ⭐ (释放磁盘空间)
```

#### 用户使用

用户在任何平台（x86_64 或 ARM）上都可以直接拉取并运行镜像：

```bash
docker pull your-dockerhub-username/tradingagents-backend:latest
docker pull your-dockerhub-username/tradingagents-frontend:latest
```

Docker 会自动检测当前平台架构，拉取对应的镜像版本。

#### 影响范围
- `scripts/build-and-publish-linux.sh` (修改)
- `scripts/build-multiarch.sh` (新增)
- `scripts/build-multiarch.ps1` (新增)
- `docs/deployment/docker/MULTIARCH_BUILD.md` (新增)
- `docs/deployment/docker/BUILD_MULTIARCH_GUIDE.md` (新增)

---

### 5. 其他改进

#### 价格输入优化
- 模型目录管理：将价格输入框从 `el-input` 改为 `el-input-number`，移除 `precision` 属性避免强制补零
- 大模型配置对话框：移除 `precision` 属性，隐藏增减按钮，优化输入体验
- 配置管理列表：修改 `formatPrice` 函数，自动去除尾部多余的零（0.006000 → 0.006）
- 统一价格输入步进值为 0.0001，支持精确的小数输入

#### 配置重载功能修复
- 修复 `configApi` 对象中缺少 `reloadConfig` 方法的问题
- 修复配置桥接中的 `provider.value` 错误（provider 已改为字符串类型）
- "重载配置"按钮现在可以正常工作

#### 数据库导出优化
- 从"配置数据（用于演示系统）"导出选项中移除 `market_quotes` 和 `stock_basic_info`
- 这两个集合数据量大，不适合用于演示系统
- 更新成功提示信息，明确说明不含行情数据

#### 文档更新
- 更新 Tushare 注册链接为官方推荐链接
- 补充积分要求说明（建议 2000 积分以上）
- 说明实时行情需要另外交费

#### 代码清理
- 配置：从 Git 追踪中移除 `frontend/components.d.ts`（自动生成文件）
- 清理：删除临时测试脚本 `test_cache_stats.py` 和 `test_mongodb_cache.py`

---

## 📊 技术细节

### 配置优先级体系

```
API Key 优先级:
模型配置中的 API Key > 厂家配置中的 API Key > 环境变量 > 硬编码默认值

Base URL 优先级:
模型配置中的 base_url > 厂家配置中的 default_base_url > 硬编码默认值
```

### 缓存系统架构

```
IntegratedCacheManager
├── AdaptiveCacheSystem (主缓存)
│   ├── MongoDB (优先)
│   ├── Redis (备选)
│   └── FileCache (降级)
└── LegacyFileCache (兼容旧数据)
```

### Docker 多架构构建原理

```
Docker Buildx + QEMU
├── 在 x86_64 机器上通过 QEMU 模拟 ARM 环境
├── 同时构建 amd64 和 arm64 两个架构的镜像
├── 生成 manifest list 引用多个平台镜像
└── Docker 自动根据运行平台选择对应镜像
```

---

## 🔍 相关提交

### 配置系统
- `ce15d2a` - 修复: 厂家配置的 default_base_url 未生效的问题
- `b522b70` - 修复: 厂家配置的 default_base_url 在分析流程中未生效的问题
- `181b86b` - fix: 支持动态添加新供应商 - 将 provider 字段从枚举改为字符串
- `247a611` - fix: 添加大模型配置时自动加载新供应商的可用模型列表
- `71bdb91` - feat: 添加大模型配置的启用/禁用功能
- `e07ff3b` - fix: 修复厂家启用/禁用功能 - 同步状态到后端
- `ea5aaae` - fix: 修复厂家启用/禁用后前端状态不更新的问题
- `5458926` - feat: 禁用供应商后自动隐藏其所有模型
- `0c9a9b2` - fix: 修复配置重载API调用错误
- `7cd5e5a` - fix: 修复配置桥接中的 provider.value 错误

### 缓存管理
- `886d25f` - feat: 实现缓存管理功能的前后端对接
- `40d19e2` - fix: 统一缓存统计数据格式，修复前端显示 NaN 问题
- `ae6e447` - fix: 修复自适应缓存系统初始化和 MongoDB 缓存统计
- `27bbc19` - fix: 修复缓存管理页面从 API 响应中提取数据
- `48224f7` - fix: 修复缓存路由导入错误 - 使用正确的 auth 模块路径
- `413754d` - fix: 移除缓存路由中不存在的 error 导入
- `92dfbcd` - fix: 修复缓存管理API导入路径错误

### SSE 通知
- `97e7af5` - fix: 修复 SSE 心跳消息发送过于频繁的问题

### Docker 多架构
- `b9672d2` - feat: 支持多架构 Docker 镜像构建（amd64 + arm64）

### 其他改进
- `5e17023` - fix: 优化价格输入和显示体验
- `04dffce` - feat: 配置数据导出时排除行情数据集合
- `d4261b8` - docs: 更新 Tushare 注册链接和积分说明
- `a1d0c41` - 配置: 从 Git 追踪中移除 frontend/components.d.ts
- `3d5746c` - fix: 修复 provider 字段从枚举改为字符串后的日志输出
- `612f064` - chore: 清理测试文件
- `22f9e31` - debug: 添加详细日志以调试环境变量 API 密钥读取

---

## ✅ 验证与质量保障

### 配置系统
- ✅ 用户可以添加任意标识符的新供应商
- ✅ 新供应商可以立即用于创建模型配置
- ✅ 厂家的 `default_base_url` 在分析流程中正确生效
- ✅ 禁用供应商后，该供应商的所有模型自动隐藏
- ✅ 配置重载功能正常工作

### 缓存管理
- ✅ 缓存管理页面正确显示统计数据（总文件数、总大小、各类数据数量）
- ✅ 支持 MongoDB、Redis、文件三种缓存后端
- ✅ 清理过期缓存和清空所有缓存功能正常
- ✅ 缓存详情列表正常加载

### SSE 通知
- ✅ 心跳消息每 30 秒发送一次
- ✅ SSE 连接数据传输量大幅降低
- ✅ 实时通知推送不受影响

### Docker 多架构
- ✅ 镜像支持 linux/amd64 和 linux/arm64 架构
- ✅ 用户在 ARM 平台可以正常拉取和运行镜像
- ✅ 构建完成后自动清理本地镜像，释放磁盘空间

---

## 🎁 用户影响与收益

### 配置管理更灵活
- 用户可以自由添加和管理 LLM 供应商，不受预定义列表限制
- 可以在 Web 界面配置厂家的默认 API 地址和 API Key
- 可以快速启用/禁用供应商和模型配置
- 配置优先级清晰，支持多层级覆盖

### 缓存管理更直观
- 用户可以通过 Web 界面查看缓存统计
- 可以清理过期缓存或清空所有缓存
- 支持多种缓存后端，自动降级到可用后端
- 缓存数据格式统一，显示准确

### 系统性能更优
- SSE 连接数据传输量大幅降低，减少网络开销
- 缓存管理功能完善，提升数据访问效率

### 部署更便捷
- 一次构建，支持 x86_64 和 ARM 架构
- 用户在任何平台都可以直接使用 Docker 镜像
- 支持 Apple Silicon、树莓派、AWS Graviton 等 ARM 平台
- 构建服务器自动清理镜像，节省磁盘空间

---

## 📚 相关文档

### 配置系统
- `docs/configuration/API_KEY_PRIORITY.md` - API Key 配置优先级说明
- `docs/configuration/DEFAULT_BASE_URL_USAGE.md` - default_base_url 使用说明

### Docker 多架构
- `docs/deployment/docker/MULTIARCH_BUILD.md` - 多架构构建通用指南
- `docs/deployment/docker/BUILD_MULTIARCH_GUIDE.md` - Ubuntu 服务器专用指南

---

> 本次更新涉及 **30+ 个提交**，修改了 **40+ 个文件**，新增了 **5 个文档**和 **3 个脚本**。所有更改均已通过测试并合并至 `v1.0.0-preview` 分支。感谢所有用户的反馈和支持！🎉

