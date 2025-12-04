# 股票基础信息同步（后端定时 + 前端状态展示）

本文档介绍如何配置、运行和查看“股票基础信息同步”功能（包含股票代码、名称、行业、市值等）。

## 功能概述
- 使用 Tushare 拉取 A 股基础列表与最新交易日 daily_basic 市值
- 写入 MongoDB 集合 `stock_basic_info`（按 `code` upsert）
- 同步状态记录在 `sync_status`（`job=stock_basics`）
- 后端内置 APScheduler 每日定时执行，可配置时间
- 前端 Streamlit "🔧 系统状态" 页面显示状态并可一键触发

## 前置条件
- 已正确配置 MongoDB，并能被后端连通
- 环境变量设置 TUSHARE_TOKEN（参见 Tushare 官网申请）
- 安装依赖：
  - `pip install -e .`（项目依赖中包含 `APScheduler`、`motor`、`pymongo` 等）

## 配置项
在 `.env` 或系统环境变量中设置（均在 `app/core/config.py` 中定义）：

- `SYNC_STOCK_BASICS_ENABLED`（bool，默认 `true`）
  - 是否启用每日同步任务
- `SYNC_STOCK_BASICS_CRON`（string，默认空）
  - CRON 表达式（例如 `30 6 * * *` 表示每日 06:30）
  - 如设置该项，将优先生效
- `SYNC_STOCK_BASICS_TIME`（string，默认 `06:30`）
  - 当未设置 CRON 时，使用简单时间格式 `HH:MM`（24小时制）
- `TIMEZONE`（string，默认 `Asia/Shanghai`）
  - 调度器时区

示例 `.env`：
```
# 启用每日同步
SYNC_STOCK_BASICS_ENABLED=true
# 每日 07:00 执行（两种配置方式二选一）
# 方式1：CRON
SYNC_STOCK_BASICS_CRON=0 7 * * *
# 方式2：简单时间
SYNC_STOCK_BASICS_TIME=07:00
# 时区
TIMEZONE=Asia/Shanghai
# Tushare token
TUSHARE_TOKEN=你的token
```

## 启动与运行
1. 启动后端 API：
   - `python -m uvicorn app.main:app --reload`
   - 首次启动会异步触发一次全量同步（不阻塞）
2. 打开前端 Streamlit：
   - 运行 `python web/run_web.py` 或直接 `streamlit run web/app.py`
   - 侧边栏选择「🔧 系统状态」查看同步状态
3. 手动触发
   - 前端页面点击「🔄 手动运行全量同步」，或
   - `POST /api/sync/stock_basics/run`
4. 查看状态
   - `GET /api/sync/stock_basics/status`

## MongoDB 集合与索引
- 数据集合：`stock_basic_info`
  - 基础字段：`code`，`name`，`area`，`industry`，`market`，`list_date`，`sse`，`sec`，`source`，`updated_at`
  - 市值字段：`total_mv`（总市值，亿元），`circ_mv`（流通市值，亿元）
  - 财务指标：`pe`（市盈率），`pb`（市净率），`pe_ttm`（滚动市盈率），`pb_mrq`（最新市净率）
  - 交易指标：`turnover_rate`（换手率%），`volume_ratio`（量比）
- 状态集合：`sync_status`（`job=stock_basics`）

初始化索引脚本：
- 路径：`scripts/setup/init_mongodb_indexes.py`
- 作用：
  - `stock_basic_info`
    - 唯一索引：`code`
    - 查询索引：`name`，`industry`，`market`，`sse`，`sec`
    - 排序/筛选：`total_mv`（降序），`circ_mv`（降序），`updated_at`（降序）
    - 财务指标：`pe`，`pb`，`turnover_rate`（降序）
  - `sync_status`
    - 唯一索引：`job`
    - 状态字段索引：`status`
    - 最近完成时间：`finished_at`（降序）

运行脚本：
```
# 使用当前环境变量连接MongoDB
python scripts/setup/init_mongodb_indexes.py

# 或传入连接环境变量（示例）
$env:MONGODB_HOST = "localhost"
$env:MONGODB_PORT = "27017"
$env:MONGODB_DATABASE = "tradingagents"
python scripts/setup/init_mongodb_indexes.py
```

## 常见问题
- Tushare 未配置：状态为 `failed`，message 提示 token 缺失
- 当日无交易：脚本会回退查找最近有数据的交易日
- 初次全量同步数据量较大：请关注日志与 MongoDB 写入速率

## 数据说明
- 市值字段：total_mv、circ_mv 写库时统一为"亿元人民币"（Tushare 的"万元"除以 1e4）
- 财务指标：pe、pb、pe_ttm、pb_mrq 保持 Tushare 原始数值
- 交易指标：turnover_rate（换手率%）、volume_ratio（量比）保持原始数值
- 唯一索引 code：若首次已有重复数据，唯一索引创建会失败；可先去重再建索引
- 调度日志：后端日志会打印定时器启动与任务结果

## 扩展建议
- ✅ 已实现：`circ_mv`、`pe`、`pb`、`turnover_rate` 等指标（来自 daily_basic）
- 增加数据校验与重试策略
- 扩展到 ETF/指数的基础信息同步

