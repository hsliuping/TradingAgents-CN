# TradingAgents-CN 后端接口总览与场外基金分析方案

本说明整理项目当前后端接口的功能与入口，并给出场外基金（非交易所公募基金）分析的完整落地方案。接口均基于 FastAPI，统一挂载在 `app/main.py:684-728`。

## 技术栈与架构
- 后端框架：FastAPI（异步）
- 数据库：MongoDB（主存储）、Redis（队列/缓存/消息）
- 鉴权：Bearer Token（数据库用户体系）
- 推送：SSE 与 WebSocket
- 文档：Swagger `/docs` 与 ReDoc `/redoc`（`DEBUG` 模式启用），见 `app/main.py:599-616`

## 路由注册总览
- 路由注册集中在 `app/main.py:684-728`，包含健康检查、认证、分析、筛选、股票数据、同步、系统配置、日志、队列、推送等模块。

## 核心接口一览

### 认证与用户
- `POST /api/auth/login` 登录，`app/routers/auth_db.py:116`
- `POST /api/auth/refresh` 刷新令牌，`app/routers/auth_db.py:219`
- `POST /api/auth/logout` 登出，`app/routers/auth_db.py:267`
- `GET /api/auth/me` 获取当前用户，`app/routers/auth_db.py:303`
- `PUT /api/auth/me` 更新当前用户，`app/routers/auth_db.py:312`
- `POST /api/auth/change-password` 修改密码，`app/routers/auth_db.py:369`
- `POST /api/auth/reset-password` 管理员重置密码，`app/routers/auth_db.py:399`
- `POST /api/auth/create-user` 管理员创建用户，`app/routers/auth_db.py:427`
- `GET /api/auth/users` 管理员用户列表，`app/routers/auth_db.py:478`

### 分析任务与历史
- `POST /api/analysis/single` 提交单股分析，`app/routers/analysis.py:40`
- `POST /api/analysis/batch` 批量分析，`app/routers/analysis.py:771`
- `POST /api/analysis/analyze` 增强分析（兼容通道），`app/routers/analysis.py:875`
- `GET /api/analysis/tasks` 用户任务列表与状态，`app/routers/analysis.py:738`
- `GET /api/analysis/tasks/{task_id}/status` 任务状态，`app/routers/analysis.py:105`
- `GET /api/analysis/tasks/{task_id}/result` 任务结果，`app/routers/analysis.py:221`
- `POST /api/analysis/tasks/{task_id}/cancel` 取消任务，`app/routers/analysis.py:948`
- 历史与僵尸任务清理，`app/routers/analysis.py:969, 984, 1114, 1142, 1169, 1224`

### 股票详情与统一数据
- `GET /api/stocks/{code}/quote` 多市场实时行情（A/H/US），`app/routers/stocks.py:66`
- `GET /api/stocks/{code}/fundamentals` 基础面快照（含实时PE/PB/PS/ROE），`app/routers/stocks.py:215`
- `GET /api/stocks/{code}/kline` K线（含交易时段实时补点），`app/routers/stocks.py:421`
- `GET /api/stocks/{code}/news` 新闻与公告（A/H/US），`app/routers/stocks.py:624`

- 统一股票数据接口（扩展模型）：`app/routers/stock_data.py`
  - `GET /api/stock-data/basic-info/{symbol}` 基础信息，`app/routers/stock_data.py:23`
  - `GET /api/stock-data/quotes/{symbol}` 实时行情，`app/routers/stock_data.py:60`
  - `GET /api/stock-data/list` 列表分页与筛选，`app/routers/stock_data.py:97`
  - `GET /api/stock-data/combined/{symbol}` 基础+行情组合，`app/routers/stock_data.py:145`
  - `GET /api/stock-data/search` 关键字搜索，`app/routers/stock_data.py:203`
  - `GET /api/stock-data/markets` 市场概览，`app/routers/stock_data.py:290`
  - `GET /api/stock-data/sync-status/quotes` 行情同步状态，`app/routers/stock_data.py:343`

- 多市场统一查询：`GET /api/markets/...`，`app/routers/multi_market_stocks.py:26, 78, 135, 198, 259`

### 历史/财务/新闻/社媒/内部消息
- 历史数据：`/api/historical-data/*`，`app/routers/historical_data.py:36, 94, 131, 156, 174`
- 财务数据：`/api/financial-data/*`，`app/routers/financial_data.py:49, 90, 123, 147, 183, 220, 241`
- 新闻数据：`/api/news-data/*` 查询/最新/全文检索/统计/同步，`app/routers/news_data.py:41, 98, 148, 193, 237, 294, 346, 399, 433`
- 社媒数据：`/api/social-media/*` 查询/最新/检索/统计/平台/情绪分析，`app/routers/social_media.py:68, 93, 134, 158, 185, 216, 265, 339`
- 内部消息：`/api/internal-messages/*` 保存/查询/最新/检索/统计/类型/分类/健康，`app/routers/internal_messages.py:77, 101, 143, 169, 243, 274, 313, 347`

### 自选股与标签
- 自选股：`/api/favorites/*` 获取/添加/更新/移除/检查/标签/同步实时，`app/routers/favorites.py:55, 70, 127, 161, 187, 203, 223`
- 标签：`/api/tags/*` 列表/新增/更新/删除，`app/routers/tags.py:36, 45, 60, 79`

### 筛选与行业
- 传统筛选：`POST /api/screening/run`，`app/routers/screening.py:156`
- 增强筛选：`POST /api/screening/enhanced`，`app/routers/screening.py:193`
- 字段配置与校验：`GET /api/screening/fields`（两类），`app/routers/screening.py:47, 234`；`POST /api/screening/validate`，`app/routers/screening.py:262`
- 行业列表：`GET /api/screening/industries`，`app/routers/screening.py:275`

### 队列与实时推送
- 队列统计：`GET /api/queue/stats`，`app/routers/queue.py:7`
- SSE 任务进度：`GET /api/stream/tasks/{task_id}`，`app/routers/sse.py:224`
- SSE 批次进度：`GET /api/stream/batches/{batch_id}`，`app/routers/sse.py:243`
- WebSocket 通知：`/api/ws/*` 统计与推送，`app/routers/websocket_notifications.py:265`（含更多端点）

### 数据同步与初始化
- 单股/批量同步：`/api/stock-sync/*`，`app/routers/stock_sync.py:122, 526`
- 基础数据全量同步：`POST /api/sync/stock_basics/run`，`app/routers/sync.py:16`
- 多源同步与推荐：`/api/multi-source-sync/*`，`app/routers/multi_source_sync.py:40, 88, 137, 154, 277, 349, 402, 448`
- 多周期同步：`/api/multi-period-sync/*`，`app/routers/multi_period_sync.py:36, 72, 103, 134, 165, 202, 247, 265, 313, 364`
- 数据源初始化：`/api/tushare-init/*`，`app/routers/tushare_init.py:55, 111, 136, 160, 193`
- `akshare-init` 与 `baostock-init` 同步初始化，`app/main.py:721-722`

### 系统配置、日志、统计与缓存
- 配置管理：`/api/config/*`（LLM/数据源/数据库/设置/模型目录等），`app/routers/config.py:37, 171, 207, 278, 315, 379, 420, 463, 484, 522, 561, 582, 691, 794, 846, 878, 927, 969, 1020, 1056, 1073, 1283, 1339, 1354, 1392, 1430, 1469, 1484, 1522, 1560, 1599, 1637, 1673, 1688, 1708, 1773, 1804, 1840, 1875, 1913, 1951, 1968, 1983, 2013, 2063, 2096, 2121, 2139, 2166, 2208, 2258`
- 系统配置只读摘要：`GET /api/system/config/summary`，`app/routers/system_config.py:52`
- 使用统计：`/api/usage/*`，`app/routers/usage_statistics.py:19, 56, 81, 100, 119, 138`
- 日志文件：`/api/system/logs/*` 文件/读取/导出/统计/删除，`app/routers/logs.py:66, 88, 124, 172, 199`
- 操作日志：`/api/system/logs/*` 列表/统计/详情/清理/导出，`app/routers/operation_logs.py:25, 73, 99, 133, 168, 206`
- 数据库管理：`/api/system/database/*` 状态/统计/测试/备份/导入导出/清理，`app/routers/database.py:63, 83, 103, 123, 148, 167, 210, 238, 258, 279, 300`
- 缓存管理：`/api/cache/*` 统计/清理/清空/详情/后端信息，`app/routers/cache.py:18, 56, 93, 125, 174`

### 健康检查与调度
- 健康检查：`GET /api/health`，`app/routers/health.py:19`
- 就绪/存活：`GET /api/healthz`、`GET /api/readyz`，`app/routers/health.py:33, 38`
- 调度器：`/api/scheduler/*` 作业/历史/统计/健康/执行管理，`app/routers/scheduler.py:39, 57, 94, 120, 151, 182, 223, 259, 302, 320, 338, 380, 422, 444, 474, 505`

### 模型能力
- 能力默认配置/深度要求/描述/徽章：`/api/model-capabilities/*`，`app/routers/model_capabilities.py:77, 108, 133, 143`
- 模型推荐/校验/批量初始化：`/api/model-capabilities/*`，`app/routers/model_capabilities.py:172, 234, 257, 313`

## 鉴权与统一响应
- 绝大多数接口需携带 `Authorization: Bearer <token>`，鉴权逻辑见 `app/routers/auth_db.py:69-115`
- 统一响应封装 `ok(...)`，广泛用于返回结构化数据（示例：`app/routers/stocks.py:102, 212`）

## 实时推送
- SSE 用于任务与批次进度，含心跳与超时处理，见 `app/routers/sse.py:18-259`
- WebSocket 通知模块替代 SSE + Redis PubSub，见 `app/main.py:710-712`

## API 文档入口
- 在 `DEBUG=true` 下访问：`/docs` 与 `/redoc`，入口配置见 `app/main.py:599-616`

---

## 场外基金分析方案（OTC 公募/非交易所）

### 目标
- 建立基金数据采集、存储、指标计算与筛选的完整闭环，支持净值、收益、风险、持仓等维度分析。

### 数据源建议
- AkShare（东财/天天基金接口封装）：如 `fund_em_open_fund_info`、`fund_em_nav_history`、`fund_em_portfolio_holdings`
- 补充数据源：东方财富 Web API、JQData（如需）、Wind/同花顺（企业版）

### 数据库设计（MongoDB 集合）
- `fund_basic_info`：基金基础信息（代码、名称、类型、成立日期、费用等）
- `fund_nav_history`：历史净值（`date`, `nav`, `acc_nav`, `dividend`）
- `fund_portfolio`：持仓与行业分布（定期披露）
- `fund_statistics`：滚动收益与风险指标缓存（1M/3M/6M/1Y/3Y/5Y）

### 指标体系
- 收益类：累计收益、年化收益（CAGR）、滚动收益（1Y/3Y/5Y）
- 风险类：波动率、最大回撤、Sharpe、Sortino、回撤恢复时间
- 相对收益：超额收益、跟踪误差、信息比率（相对基准：如沪深300、中证全指、上证50；债券基金可用中债指数）
- 组合结构：前十大持仓占比、行业集中度（HHI）、换手率估计

### API 设计（新增）
- `GET /api/funds/{code}/nav` 历史净值曲线（支持区间/复权）
- `GET /api/funds/{code}/performance` 绩效汇总（CAGR、滚动收益、回撤、Sharpe）
- `GET /api/funds/{code}/risk-metrics` 风险指标（波动、最大回撤、Sortino、信息比）
- `GET /api/funds/{code}/holdings` 最新持仓与行业分布
- `POST /api/funds/screening` 多维筛选（类型、区间收益、回撤、费用、规模、成立年限）
- `GET /api/funds/compare?codes=...` 多基金对比（同类/同基准）

### 服务与同步流程
- 新增服务：`app/services/fund_data_service.py`（封装 AkShare 抓取与标准化）
- 新增路由：`app/routers/funds.py`（模式与股票路由一致，统一响应与鉴权）
- 同步 Worker：`app/worker/fund_nav_sync_service.py`（每日净值更新、定期持仓）
- 调度集成：复用 `scheduler` 路由进行任务管理（参考 `app/routers/scheduler.py`）

### 实现要点
- 复权与分红：净值序列需处理分红再投资与拆分（使用累计净值 `acc_nav` 作为基准）
- 指标计算：统一以交易日频率计算，缺失日期使用前值填充；Sharpe 以无风险利率近似（如一年期国债/货基收益）
- 基准映射：按基金类型自动选择基准指数；混合基金可按持仓结构分解基准权重
- 性能与缓存：常用窗口（1Y/3Y/5Y）计算结果缓存到 `fund_statistics`，周期性刷新

### 前后端集成建议
- 前端新增“基金”模块（列表/详情/对比/筛选），复用 Element Plus 表格与图表
- 与新闻/社媒模块打通，支持基金相关新闻与舆情的联动分析（接口已具备：`news-data` 与 `social-media`）

### 验证与风控
- 与天天基金/东财公开页面进行抽样验证（收益、回撤、持仓）
- 增加数据质量校验：异常跳变检测、缺值比率、对账基准一致性
- 添加免责声明与风控提示（教育研究用途）

---

## 使用与调试提示
- 所有需要鉴权的接口请携带 `Authorization: Bearer <token>`（见 `app/routers/auth_db.py:69-115`）
- 队列与推送用于长任务追踪：`/api/queue/stats`、`/api/stream/tasks/{id}`、`/api/stream/batches/{id}`
- 常见数据入口：历史（`historical-data`）、财务（`financial-data`）、新闻（`news-data`）、社媒（`social-media`）、内部消息（`internal-messages`）