# QMT 与 TradingAgentsCN 联用使用手册

## 1. 文档说明

- 适用对象：准备将迅投 MiniQMT 作为本项目数据源的用户
- 适用环境：Windows，本地已安装 MiniQMT
- 目标：完成 QMT 配置、联调、同步、分析和常见问题排查

本手册重点说明 QMT 与本项目如何一起使用，不讨论券商交易权限开通流程，也不覆盖 MiniQMT 本体安装教程。

已知示例环境：

- QMT 安装目录：`D:\gjzq\bin.x64`

## 2. QMT 在本项目中的作用

在本项目里，QMT 主要承担两类能力：

1. 数据同步能力
   - 股票基础信息同步
   - 实时行情同步
   - 历史日线同步
   - 财务数据同步
   - ETF 基础信息与 ETF 日线同步

2. 运行时分析能力
   - 作为大盘分析的数据源
   - 作为行业/板块分析的数据源
   - 在 Tushare 不可用，或显式指定 QMT 时，自动走 QMT 分析路径

简单理解就是：

- 如果你想把 QMT 当作“本地行情入口”，它可以负责同步和补数
- 如果你想让系统直接基于 QMT 做分析，它也已经支持大盘和行业两条主链路

## 3. 当前支持范围

当前 QMT 联用能力可以概括为：

- 已支持
  - 股票列表获取
  - ETF 列表获取
  - 实时行情
  - 历史 K 线
  - 财务数据拉取与入库
  - 大盘分析 QMT 模式
  - 行业分析 QMT 模式

- 当前不适合依赖 QMT 直接提供
  - 新闻与公告
  - 北向资金官方统计
  - 两融官方统计
  - 同花顺板块资金流
  - 完整的 Tushare 风格市场统计口径

这意味着：

- QMT 很适合做行情、结构、趋势、活跃度类分析
- 不适合假装替代所有 Tushare 统计类指标

## 4. 使用前准备

开始前请确认以下条件：

1. 操作系统是 Windows
2. 本机已安装并能启动 MiniQMT
3. `xtquant` 已随 MiniQMT 安装完成，Python 环境可访问
4. 本项目后端运行环境正常
5. 如需自动同步，服务端调度器处于运行状态

说明：

- 获取行情数据通常不要求你登录券商交易账户
- 但 MiniQMT 客户端本身必须能正常启动
- 本项目当前使用的是 QMT 的数据能力，不涉及交易下单说明

## 5. 推荐接入方式

建议按下面顺序接入：

1. 先确认 MiniQMT 可以正常启动
2. 在本项目里启用 QMT 基础配置
3. 先做连通性验证
4. 先开“基础信息同步”和“状态检查”
5. 再逐步开启历史、实时、财务同步
6. 最后再把分析数据源切到 QMT 做实际分析

这样做的好处是：

- 更容易定位问题到底出在 MiniQMT、配置，还是项目本身
- 不会一上来就同时打开所有任务导致排障困难

## 6. 核心配置项

QMT 相关核心配置项如下：

```env
QMT_UNIFIED_ENABLED=true

QMT_BASIC_INFO_SYNC_ENABLED=true
QMT_QUOTES_SYNC_ENABLED=false
QMT_HISTORICAL_SYNC_ENABLED=false
QMT_FINANCIAL_SYNC_ENABLED=false
QMT_STATUS_CHECK_ENABLED=true

QMT_TOKEN=
QMT_DATA_DIR=D:\gjzq\bin.x64
QMT_LISTEN_PORT=0
QMT_LISTEN_PORT_RANGE=58620-58650
QMT_INIT_MARKETS=SH,SZ,BJ

QMT_START_LOCAL_SERVICE=false
QMT_KLINE_MIRROR_ENABLED=false
QMT_KLINE_MIRROR_MARKETS=
QMT_ALLOW_OPTIMIZE_ADDRESSES=

QMT_AUTO_DOWNLOAD_HISTORY=true
QMT_AUTO_DOWNLOAD_FINANCIAL=false
QMT_AUTO_DOWNLOAD_SECTOR=true
QMT_HISTORY_START_TIME=

QMT_HISTORICAL_SYNC_DAYS=365
QMT_HISTORICAL_BATCH_SIZE=100
QMT_FINANCIAL_BATCH_SIZE=50
```

### 6.1 最关键的几个配置

- `QMT_UNIFIED_ENABLED`
  - 总开关
  - 不打开这个，系统会直接认为 QMT 不可用

- `QMT_DATA_DIR`
  - QMT 本地数据目录
  - 你的当前安装目录是 `D:\gjzq\bin.x64`
  - 首次接入可先配置为 `D:\gjzq\bin.x64`
  - 如果后续日志提示数据目录不匹配，再按 MiniQMT 实际数据目录调整

- `QMT_TOKEN`
  - 可选
  - 用于特定行情服务或独立连接场景

- `QMT_LISTEN_PORT` / `QMT_LISTEN_PORT_RANGE`
  - QMT 初始化监听端口
  - 一般保持默认范围即可

- `QMT_INIT_MARKETS`
  - 初始化市场
  - 推荐保留 `SH,SZ,BJ`

### 6.2 同步相关配置

- `QMT_BASIC_INFO_SYNC_ENABLED`
  - 是否启用股票基础信息同步

- `QMT_QUOTES_SYNC_ENABLED`
  - 是否启用实时行情同步

- `QMT_HISTORICAL_SYNC_ENABLED`
  - 是否启用历史数据同步

- `QMT_FINANCIAL_SYNC_ENABLED`
  - 是否启用财务数据同步

- `QMT_STATUS_CHECK_ENABLED`
  - 是否启用 QMT 状态检查

### 6.3 自动补数相关配置

- `QMT_AUTO_DOWNLOAD_HISTORY=true`
  - 在读取历史 K 线前自动补历史数据
  - 推荐开启

- `QMT_AUTO_DOWNLOAD_FINANCIAL=false`
  - 在读取财务数据前自动下载财务数据
  - 初期可先关闭，确认链路稳定后再开

- `QMT_AUTO_DOWNLOAD_SECTOR=true`
  - 读取股票列表前自动下载板块数据
  - 推荐开启

## 7. 一套推荐的初始配置

如果你是第一次接入，推荐先用下面这套：

```env
QMT_UNIFIED_ENABLED=true
QMT_BASIC_INFO_SYNC_ENABLED=true
QMT_QUOTES_SYNC_ENABLED=false
QMT_HISTORICAL_SYNC_ENABLED=false
QMT_FINANCIAL_SYNC_ENABLED=false
QMT_STATUS_CHECK_ENABLED=true

QMT_DATA_DIR=D:\gjzq\bin.x64
QMT_INIT_MARKETS=SH,SZ,BJ
QMT_LISTEN_PORT_RANGE=58620-58650

QMT_AUTO_DOWNLOAD_HISTORY=true
QMT_AUTO_DOWNLOAD_SECTOR=true
QMT_AUTO_DOWNLOAD_FINANCIAL=false

QMT_HISTORICAL_SYNC_DAYS=365
QMT_HISTORICAL_BATCH_SIZE=100
QMT_FINANCIAL_BATCH_SIZE=50
```

推荐原因：

- 先只开最基础的接入链路
- 先验证可用性，不急着跑全量同步
- 先让分析链路能用起来，再慢慢补历史和财务

## 8. 配置方式

本项目支持两种常用配置方式：

### 8.1 通过环境变量配置

适合：

- 本地开发
- 服务器部署
- Docker 外部注入配置

做法：

1. 在 `.env` 或系统环境变量里写入 QMT 配置
2. 对你当前环境，建议先写 `QMT_DATA_DIR=D:\gjzq\bin.x64`
3. 重启服务
4. 观察启动日志或状态检查结果

### 8.2 通过前端设置页配置

适合：

- 已有系统后台界面
- 需要运营或使用人员调整数据源配置

做法：

1. 打开系统设置
2. 进入数据源配置弹窗
3. 找到 QMT 配置项
4. 保存后做连通性测试

建议：

- 初次接入优先用环境变量
- 稳定后再用前端配置做维护

### 8.3 配置管理界面说明

这些 QMT 参数在当前项目里，原则上是有对应配置管理界面的，但现阶段采用的是：

- 通用数据源配置界面
- QMT 类型选择
- `config_params` 自定义参数录入

也就是说，当前不是把每一个 `QMT_*` 都单独做成一个专属表单项，而是通过“数据源配置弹窗”统一管理。

当前入口是：

- 系统设置
- 数据源配置
- 新增或编辑数据源
- 选择 `QMT / MiniQMT`

在这个界面里：

- 基础字段有独立表单项
  - 数据源类型
  - 显示名称
  - API Key
  - endpoint
  - timeout
  - rate_limit
  - priority
  - enabled

- QMT 专有字段目前主要通过“自定义参数”录入
  - `data_dir`
  - `listen_port`
  - `listen_port_range`
  - `init_markets`
  - `kline_mirror_markets`
  - `allow_optimize_addresses`
  - `history_start_time`
  - `start_local_service`
  - `kline_mirror_enabled`
  - `auto_download_history`
  - `auto_download_financial`
  - `auto_download_sector`

换句话说：

- 配置管理界面是有的
- 只是 QMT 这批参数目前挂在“自定义参数”里，还不是专用 QMT 配置面板

### 8.4 界面字段与环境变量映射

如果你在配置管理界面里编辑 QMT，推荐按下面方式填写：

| 界面位置 | 参数名 | 对应环境变量 | 建议值 |
|------|------|------|------|
| API Key | `api_key` | `QMT_TOKEN` | 留空或按实际填写 |
| 自定义参数 | `data_dir` | `QMT_DATA_DIR` | `D:\gjzq\bin.x64` |
| 自定义参数 | `listen_port` | `QMT_LISTEN_PORT` | `0` |
| 自定义参数 | `listen_port_range` | `QMT_LISTEN_PORT_RANGE` | `58620-58650` |
| 自定义参数 | `init_markets` | `QMT_INIT_MARKETS` | `SH,SZ,BJ` |
| 自定义参数 | `start_local_service` | `QMT_START_LOCAL_SERVICE` | `false` |
| 自定义参数 | `kline_mirror_enabled` | `QMT_KLINE_MIRROR_ENABLED` | `false` |
| 自定义参数 | `kline_mirror_markets` | `QMT_KLINE_MIRROR_MARKETS` | 留空 |
| 自定义参数 | `allow_optimize_addresses` | `QMT_ALLOW_OPTIMIZE_ADDRESSES` | 留空 |
| 自定义参数 | `auto_download_history` | `QMT_AUTO_DOWNLOAD_HISTORY` | `true` |
| 自定义参数 | `auto_download_financial` | `QMT_AUTO_DOWNLOAD_FINANCIAL` | `false` |
| 自定义参数 | `auto_download_sector` | `QMT_AUTO_DOWNLOAD_SECTOR` | `true` |
| 自定义参数 | `history_start_time` | `QMT_HISTORY_START_TIME` | 留空或按需填写 |

补充说明：

- `QMT_BASIC_INFO_SYNC_ENABLED`
- `QMT_QUOTES_SYNC_ENABLED`
- `QMT_HISTORICAL_SYNC_ENABLED`
- `QMT_FINANCIAL_SYNC_ENABLED`
- `QMT_STATUS_CHECK_ENABLED`
- `QMT_HISTORICAL_SYNC_DAYS`
- `QMT_HISTORICAL_BATCH_SIZE`
- `QMT_FINANCIAL_BATCH_SIZE`

这批更偏“系统级调度参数”，当前不在数据源弹窗里单独展开，通常仍建议通过环境变量或系统配置维护。

## 9. 启动顺序建议

推荐按这个顺序启动：

1. 从 `D:\gjzq\bin.x64` 启动 MiniQMT
   - 如果 MiniQMT 可执行文件就在该目录下，可直接从这里启动
2. 确认 MiniQMT 本身正常
3. 启动本项目后端
4. 观察 QMT 状态检查日志
5. 通过配置页或测试接口验证 QMT 连通性
6. 再开启同步任务或开始分析

不要反过来：

- 不建议先启动项目，再去碰 MiniQMT
- 不建议 MiniQMT 没启动就直接跑 QMT 分析

## 10. 如何判断 QMT 是否接通

可以从 4 个层面判断：

### 10.1 看基础开关

确认：

- `QMT_UNIFIED_ENABLED=true`

### 10.2 看客户端状态

确认：

- MiniQMT 已启动
- 启动目录与当前安装目录 `D:\gjzq\bin.x64` 一致
- 本机没有异常弹窗
- 端口未被占用到无法监听

### 10.3 看项目日志

典型正常信号包括：

- QMT 初始化成功
- QMT 状态检查正常
- QMT 同步服务初始化完成

典型异常信号包括：

- `xtquant` 未安装
- `QMT 不可用，请确保 MiniQMT 客户端已启动`
- 主动初始化连接失败

### 10.4 看功能结果

实际验证最直接：

- 能拉到股票列表
- 能拉到 ETF 列表
- 大盘分析能走 QMT 结果
- 行业分析能走 QMT 结果

## 11. QMT 的两种典型用法

### 11.1 用法一：把 QMT 当作同步数据源

适用场景：

- 你希望把 QMT 行情同步到本地数据库
- 后续再由系统统一查询本地数据

建议流程：

1. 开启 `QMT_UNIFIED_ENABLED`
2. 开启 `QMT_BASIC_INFO_SYNC_ENABLED`
3. 验证基础信息同步正常
4. 再按需开启历史、实时、财务同步
5. 让定时任务持续补数

这种方式的特点：

- 更适合长期运行
- 数据可以沉淀到库里
- 对分析速度和稳定性更友好

### 11.2 用法二：把 QMT 当作运行时分析数据源

适用场景：

- 你希望分析时直接走 QMT
- 特别适合大盘和行业结构分析

当前已接入 QMT 模式的主要分析师：

- 大盘分析师
- 行业/板块分析师

特点：

- 系统会根据当前分析上下文判断是否走 QMT
- 工具层会自动路由到 QMT 版本实现
- LLM 不需要知道当前用的是哪一个数据源

## 12. 如何让分析走 QMT

系统当前会优先从以下字段判断期望数据源：

- `analysis_data_source`
- `preferred_data_source`
- `market_data_source`
- `data_source`

如果这些字段里显式指定了 `qmt`，并且 QMT 可用，则分析会进入 QMT 模式。

简单理解：

- 你不需要让 LLM 知道“现在在用 QMT”
- 只要运行态把当前分析数据源设成 `qmt`
- 工具层就会自动改走 QMT 接口

## 13. QMT 模式下的大盘分析

QMT 模式下，大盘分析重点看的是：

- 指数趋势
- 市场扩散
- 成交活跃度
- 风格切换
- 盘面结构

这类分析很适合 QMT，因为 QMT 本身擅长行情和结构数据。

但要注意：

- 不要期待它返回完整的北向资金官方统计
- 不要期待它返回两融官方统计
- 不要期待它补齐所有 Tushare 风格指标

正确理解应该是：

- QMT 大盘分析适合做“盘面结构判断”
- 不适合硬做“官方统计型归因”

## 14. QMT 模式下的行业分析

QMT 模式下，行业分析重点看的是：

- 行业内强弱
- 龙头带动
- 扩散度
- 活跃度
- 行业映射

其中要特别注意：

- 行业映射可能来自本地 `stock_basic_info`
- 行情来自 QMT

所以行业分析结果里会同时存在两类来源：

- 本地行业分类
- QMT 行情数据

这不是问题，是当前设计的一部分。

## 15. ETF 使用方式

QMT 已经接入 ETF 链路，当前可支持：

- ETF 列表获取
- ETF 基础信息同步
- ETF 日线同步

适合场景：

- 做 ETF 数据补充
- 做 ETF 基础研究准备

当前边界：

- ETF 数据链路已经有了
- ETF 分析主流程成熟度仍弱于普通股票主流程

因此建议：

- 把 QMT ETF 更多用于“数据同步和补数”
- ETF 深度分析先作为增强功能使用，不要当成唯一主链路

## 16. 推荐的实际使用方案

如果你同时有 QMT 和 Tushare，推荐这样分工：

- QMT
  - 实时行情
  - 历史 K 线
  - ETF 数据
  - 大盘结构分析
  - 行业结构分析

- Tushare
  - 北向资金
  - 两融
  - 更完整的市场统计
  - 更完整的板块统计口径

这套分工最稳，因为它符合两类数据源的天然优势。

## 17. 常见问题

### 17.1 明明开了 QMT，系统还是说不可用

优先检查：

1. `QMT_UNIFIED_ENABLED` 是否为 `true`
2. MiniQMT 是否真的启动
3. 当前启动实例是否来自 `D:\gjzq\bin.x64`
4. Python 环境是否能访问 `xtquant`
5. 监听端口范围是否被占用
6. 是否重启过项目服务

### 17.2 QMT 可用，但拿不到股票列表

优先检查：

1. `QMT_AUTO_DOWNLOAD_SECTOR` 是否开启
2. MiniQMT 本地板块数据是否可读
3. 当前 QMT 本地环境是否完整

### 17.3 QMT 可以连，但历史数据不全

优先检查：

1. `QMT_AUTO_DOWNLOAD_HISTORY=true`
2. `QMT_HISTORY_START_TIME` 是否需要设置更早日期
3. `QMT_HISTORICAL_SYNC_DAYS` 是否太小

### 17.4 为什么 QMT 分析里没有北向资金或两融

这是正常的。

原因不是系统坏了，而是：

- QMT 分析模式本来就不伪造 Tushare 风格统计
- 拿不到的数据就不硬补

正确做法：

- 盘面结构分析用 QMT
- 官方统计分析用 Tushare

### 17.5 行业分析里为什么会提到本地行业映射

这是当前设计特性。

原因是：

- 行业分类不一定来自 QMT 原生分类
- 可能来自本地 `stock_basic_info`
- 但行情走势来自 QMT

所以系统会保留这个说明，避免把两个来源混成一种口径。

## 18. 排障清单

遇到问题时，按这个顺序排：

1. 看 MiniQMT 是否启动
2. 看 `QMT_UNIFIED_ENABLED` 是否打开
3. 看 `xtquant` 是否可导入
4. 看日志里是否有 QMT 初始化报错
5. 看状态检查是否通过
6. 先测试股票列表，再测历史数据，再测分析
7. 不要一上来同时开全部同步任务

## 19. 最佳实践

- 初次接入时，先只开启基础信息同步和状态检查
- 历史同步建议在非交易时段跑
- 实时行情同步要结合机器性能和网络情况评估
- 财务同步建议单独安排在低峰时段
- QMT 更适合做行情和结构分析，不要强行替代统计型数据源
- 如果同时有 Tushare，优先采用“QMT + Tushare”混合方案

## 20. 推荐结论

如果你问“QMT 和本项目到底该怎么一起用”，最推荐的答案是：

1. 用 QMT 做行情和数据补充
2. 用 QMT 做大盘和行业结构分析
3. 用 Tushare 补官方统计指标
4. 在工具层自动判断当前数据源，不让 LLM 理解底层差异

这样最稳定，也最符合当前项目实现。

## 21. 相关文档

- `docs/design/v3.0/qmt-support.md`
- `docs/design/v3.0/implementation-status-report.md`
- `app/services/data_sources/qmt_adapter.py`
- `app/worker/qmt_sync_service.py`
- `app/worker/etf_sync_service.py`
