# TradingAgents-CN Pro 开发规则

## 完整流程文档

详见 [docs/03-development/workflow/development-workflow.md](docs/03-development/workflow/development-workflow.md)

## 文档管理规范

### 文档目录体系

所有文档存放在 `docs/` 下，按编号分层管理：

| 目录 | 用途 | 版本管理方式 |
|------|------|-------------|
| `01-product/` | 产品定位、发布说明、版本对比 | 按版本号命名文件 |
| `02-user-guide/` | 用户指南（安装/配置/功能/进阶） | 跟随当前版本 |
| `03-development/` | 开发文档（架构/API/指南/流程） | 跟随当前版本 |
| `04-operations/` | 运维文档（部署/数据库/监控/排障） | 跟随当前版本 |
| `05-design/` | 设计文档 | **按版本号目录** |
| `06-knowledge/` | 知识沉淀（经验教训/Bug编年史） | 跨版本积累 |
| `07-courses/` | 高级交易课程 | 独立维护 |
| `08-blog/` | 技术博客 | 独立维护 |
| `99-archive/` | 归档区（老版本/废弃功能/历史修复） | **按版本号目录** |

### 版本号管理规则（强制）

**`05-design/` 和 `99-archive/` 必须使用明确版本号目录**，禁止使用 `current`、`latest`、`new`、`next`、`future` 等相对概念命名。

```
05-design/
├── v3.0/     # 当前发布版本的设计文档
├── v4.0/     # 下一版本规划
├── v5.0/     # 远期愿景
└── research/ # 前沿探索（不绑定版本）

99-archive/
├── v0.1.x/   # 老版本归档
├── v1.0.x/
├── v2.0/
├── v2.1/
├── deprecated-features/  # 已废弃功能（跨版本）
└── historical-fixes/     # 历史修复记录（跨版本）
```

**版本号命名规则**：
- 主版本号目录：`v3.0`、`v4.0`、`v5.0`（对应 major.minor 中的 major）
- 同一主版本号下的小版本迭代不新建目录，直接在原目录内更新文件
- 例如 v3.0.1、v3.0.2、v3.1.0 的设计文档都放在 `v3.0/` 目录下

### 版本迭代流程

当发布新主版本（如 v3.0 → v4.0）时：

1. `05-design/v3.0/` → `99-archive/v3.0/`（当前版本归档）
2. `05-design/v4.0/` 保持不变（成为新的当前版本）
3. 新建 `05-design/v5.0/`（开始下一版本规划）
4. 在 `01-product/release-notes/` 新建版本发布说明
5. 将本版本周期内的重大 Bug 整理到 `06-knowledge/bug-chronicle/`

**禁止的操作**：
- ❌ 禁止在 `05-design/` 下使用 `current/`、`next/`、`future/` 等相对命名
- ❌ 禁止把旧版本文档留在当前版本目录中不归档
- ❌ 禁止跨版本修改已归档的文档（如需修改，复制到当前版本目录）

### 文档命名规范

- 统一使用小写 kebab-case（如 `quick-start.md`）
- 版本相关文件加版本后缀（如 `docker-deployment-v1.md`）
- 临时文件加日期前缀（如 `2025-10-26-bugfix.md`）
- 中文文件名允许，但建议优先使用英文命名

### 文档创建原则

创建新文档时必须：
1. 放到正确的层级目录（参考文档目录体系表）
2. 如果是设计文档，放到对应版本号目录下
3. 如果是临时文档（如 git 提交计划），放到 `data/temp/` 而非 `docs/`
4. 更新 `docs/README.md` 的导航索引（如果是重要文档）

### ADR（架构决策记录）

重要架构决策记录在 `docs/03-development/decisions/`，每个 ADR 包含：
- 背景：面临什么问题
- 决策：选择了什么方案
- 原因：为什么选这个方案
- 后果：带来了什么影响

## 分支模型

- `main`：v3.0 开发主线，所有新功能只往这里合
- `release/2.0.x`：v2.0.1 维护分支，只接受 Bug 修复
- `release/2.1.x`：v2.1.0 维护分支，只接受 Bug 修复
- `hotfix/<version>/<issue>`：紧急修复，用完即删

## Commit 规范

使用 Conventional Commits 格式：

```
feat: 新功能描述
fix: Bug修复描述
docs: 文档变更
refactor: 重构描述
chore: 构建/工具/依赖变更
perf: 性能优化
test: 测试相关
```

## 版本号规则

- 正式版本：`v2.1.0`（semver）
- 测试构建：`v2.1.0-006`（版本号 + 构建号）
- `VERSION` 文件是版本号唯一来源，所有构建/打包/镜像 tag 从此读取
- 构建号由脚本自动管理，正式发布时归零

## 发布规则

- 每次正式发布必须：打 Tag + 创建/更新 Release 分支
- 测试构建打构建 Tag：`v2.1.0-006`
- Docker 镜像不使用裸 `latest`，用 `2-latest` / `3-latest` 替代
- 精确版本标签不可变，永不覆盖

## Bug 修复流程

1. 先在 `main` 修复
2. Cherry-pick 到需要的 `release/*` 分支
3. 如果只影响某个 release 版本，可直接在该分支修复

## 数据库迁移

- 补丁版本（2.1.0 → 2.1.1）：只做加法，不删除/重命名字段和表
- 小版本（2.1 → 2.2）：允许结构变更，但需提供迁移和回滚脚本
- 补丁版本不包含数据库结构变更，确保可安全回退

## Python 开发环境

**统一使用 `env/` 虚拟环境**，不要创建新的虚拟环境。

| 项目 | 说明 |
|------|------|
| 虚拟环境目录 | `env/`（项目根目录下） |
| Python 解释器 | `env/Scripts/python.exe` |
| Python 版本 | 3.11.9 |
| 激活方式 | IDE 自动激活（`.vscode/settings.json` 已配置） |
| 依赖安装 | `env/Scripts/pip install -e .` 或 `env/Scripts/python -m pip install -e .` |
| 运行命令 | 使用 `env/Scripts/python` 而非系统 `python` |

**禁止操作**：
- ❌ 禁止创建 `.venv/`、`venv/` 等新的虚拟环境
- ❌ 禁止使用系统 Python 直接运行项目
- ❌ 禁止在虚拟环境外安装项目依赖

**AI 助手注意事项**：
- 执行 Python 命令时，使用 `env/Scripts/python.exe` 而非 `python`
- 执行 pip 安装时，使用 `env/Scripts/pip.exe` 或 `env/Scripts/python.exe -m pip`
- 运行测试时，使用 `env/Scripts/python.exe -m pytest`
- 启动后端服务时，使用 `env/Scripts/python.exe -m uvicorn` 或通过 `env/Scripts/python.exe main.py`

## 开发环境隔离

三个版本使用独立目录、独立端口、独立数据卷，互不干扰：

| 版本 | MongoDB | Redis | Backend | 前端 | Docker 项目名 |
|------|---------|-------|---------|------|--------------|
| v3.0 | 27019 | 6381 | 8002 | 8082 | `ta-v3` |
| v2.1.0 | 27018 | 6380 | 8001 | 8081 | `ta-v210` |
| v2.0.1 | 27017 | 6379 | 8000 | 8080 | `ta-v201` |

## 分发渠道

- Windows：百度网盘 + QQ群（主渠道），阿里云 OSS/腾讯云 COS（可选加速），GitHub Releases（归档）
- Linux/Mac：Docker Hub

## 推送规则

- `pro` 远程（`hsliuping/TradingAgents-CN-Pro`）是 Pro 版私有仓库
- 推送时注意分支映射：本地 `pro-main` 对应远程 `main`
- Release 分支和 Tag 都要推送到 `pro` 远程
