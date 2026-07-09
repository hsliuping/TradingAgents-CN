# 配置矩阵（运行时 Settings 与日志/TOML）

本页汇总后端运行时可用的配置项、来源、默认值与注意事项，帮助开发与运维快速查找与核对。

- 唯一读取入口（运行时代码）：`from app.core.config import settings`
- 配置加载顺序（覆盖优先级高→低）：进程环境变量 > .env 文件 > 代码默认值
- 日志配置优先级：`config/logging_docker.toml`（当 LOGGING_PROFILE=docker 或检测到容器）> `config/logging.toml` > 内置默认
- 历史环境变量兼容（已弃用）：`API_HOST`/`API_PORT`/`API_DEBUG` → 映射为 `HOST`/`PORT`/`DEBUG` 并发出 DeprecationWarning

> 敏感项应通过环境变量/密钥服务注入，避免提交到仓库；`.env.example` 仅作示例。

---

## 读取入口与覆盖
- 代码中只允许：`from app.core.config import settings`
- 脚本/测试：优先使用本地 `.venv` 解释器，必要时通过环境变量或临时 `.env` 覆盖
- Pydantic 设置：`Settings.model_config = SettingsConfigDict(env_file=".env", extra="ignore")`

---

## 核心服务
- DEBUG: bool（默认 true）
- HOST: str（默认 "0.0.0.0"）
- PORT: int（默认 8000）
- ALLOWED_ORIGINS: List[str]（默认 ["*"]）
- ALLOWED_HOSTS: List[str]（默认 ["*"]）

备注：历史别名 `API_HOST`/`API_PORT`/`API_DEBUG` 已弃用但仍兼容读取。

---

## MongoDB
- MONGODB_HOST: str（默认 localhost）
- MONGODB_PORT: int（默认 27017）
- MONGODB_USERNAME: str（默认 空）【敏感】
- MONGODB_PASSWORD: str（默认 空）【敏感】
- MONGODB_DATABASE: str（默认 tradingagents）
- MONGODB_AUTH_SOURCE: str（默认 admin）
- MONGO_MAX_CONNECTIONS: int（默认 100）
- MONGO_MIN_CONNECTIONS: int（默认 10）
- 衍生：MONGO_URI（只读属性，基于以上字段拼装）

建议：生产环境使用具名用户+密码，或启用其他认证机制；用户/密码建议从密钥服务注入。

---

## Redis
- REDIS_HOST: str（默认 localhost）
- REDIS_PORT: int（默认 6379）
- REDIS_PASSWORD: str（默认 空）【敏感】
- REDIS_DB: int（默认 0）
- REDIS_MAX_CONNECTIONS: int（默认 20）
- REDIS_RETRY_ON_TIMEOUT: bool（默认 true）
- 衍生：REDIS_URL（只读属性，带密码时形如 `redis://:pwd@host:port/db`）

建议：生产强烈建议设置密码，或在受信网络中以防火墙/ACL 控制访问。

---

## 日志（Settings + TOML）
- LOG_LEVEL: str（默认 INFO）
- LOG_FORMAT: str（默认 "%(asctime)s - %(name)s - %(levelname)s - %(message)s"）
- LOG_FILE: str（默认 logs/tradingagents.log）
- TOML（config/logging.toml 或 config/logging_docker.toml）支持：
  - [logging] level
  - [logging.format] console/file 格式字符串
  - [logging.format] json = true | false（启用控制台 JSON 结构化日志）
  - [logging.handlers.file] directory/level/max_size/backup_count

说明：
- JSON 结构化日志仅影响控制台 handler，文件仍为文本格式（可按需扩展）。
- Python 3.10 使用 tomli 解析；3.11+ 使用 tomllib。

---

## JWT / 安全
- JWT_SECRET: str（默认 change-me-in-production）【敏感】
- JWT_ALGORITHM: str（默认 HS256）
- ACCESS_TOKEN_EXPIRE_MINUTES: int（默认 60）
- REFRESH_TOKEN_EXPIRE_DAYS: int（默认 30）
- BCRYPT_ROUNDS: int（默认 12）
- CSRF_SECRET: str（默认 change-me-csrf-secret）【敏感】

建议：生产强制覆盖 JWT_SECRET/CSRF_SECRET，并妥善存放。

---

## 队列 / 并发 / 速率限制
- QUEUE_MAX_SIZE: int（默认 10000）
- QUEUE_VISIBILITY_TIMEOUT: int 秒（默认 300）
- QUEUE_MAX_RETRIES: int（默认 3）
- WORKER_HEARTBEAT_INTERVAL: int 秒（默认 30）
- DEFAULT_USER_CONCURRENT_LIMIT: int（默认 3）
- GLOBAL_CONCURRENT_LIMIT: int（默认 50）
- DEFAULT_DAILY_QUOTA: int（默认 1000）
- RATE_LIMIT_ENABLED: bool（默认 true）
- DEFAULT_RATE_LIMIT: int（默认 100 每分钟）

---

## 缓存 / 监控
- CACHE_TTL: int 秒（默认 3600）
- SCREENING_CACHE_TTL: int 秒（默认 1800）
- METRICS_ENABLED: bool（默认 true）
- HEALTH_CHECK_INTERVAL: int 秒（默认 60）

---

## 调度 / 时区
- SYNC_STOCK_BASICS_ENABLED: bool（默认 true）
- SYNC_STOCK_BASICS_CRON: str（默认 空，优先生效）
- SYNC_STOCK_BASICS_TIME: str（默认 "06:30"，当未设置 CRON 时生效）
- TIMEZONE: str（默认 Asia/Shanghai）

---

## 路径
- TRADINGAGENTS_DATA_DIR: str（默认 ./data）
- settings.log_dir（只读属性）：由 LOG_FILE 推导目录名

---

## 外部服务（示例）
- STOCK_DATA_API_URL: str（默认 空）
- STOCK_DATA_API_KEY: str（默认 空）【敏感】

---

## 历史别名与弃用策略
- 已弃用但仍兼容读取：
  - API_HOST → HOST
  - API_PORT → PORT
  - API_DEBUG → DEBUG
- 兼容行为：若新键未设置且老键存在，将在进程启动时映射，并发出 DeprecationWarning。
- 文档要求：新增/修改配置必须同步 `.env.example` 与本页矩阵，明确是否敏感、默认值与弃用计划。

---

## 变更流程 Checklist（新增配置项）
- [ ] 在 `app/core/config.py` 的 `Settings` 中添加强类型字段与注释
- [ ] 更新 `.env.example` 示例与说明
- [ ] 仅通过 `settings.X` 读取（禁止在业务代码中 `os.environ`）
- [ ] 若需日志改动，优先通过 TOML，而非硬编码
- [ ] 增加/更新最小单测（默认值、覆盖、边界校验）

---

## 常见问题（FAQ）
- Q: 本地日志为何未使用 TOML？
  - A: Python 3.10 环境需安装 `tomli`；若未安装会回退到内置配置（已处理）。
- Q: Docker 环境如何选择日志配置？
  - A: 设置 `LOGGING_PROFILE=docker`，或存在 `/.dockerenv`/`DOCKER=true|1|yes` 时自动选择 `config/logging_docker.toml`。
- Q: Redis 端口是多少？
  - A: 默认 6379（tests 已覆盖），如本地临时端口不同可在 `.env` 中覆盖。

