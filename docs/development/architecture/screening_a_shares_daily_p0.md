# A股日线选股系统（P0）设计方案

版本: v0.1.0
作者: Augment Agent
日期: 2025-08-22

## 1. 目标与范围
- 目标：提供基于 A 股日线数据的最小可用选股系统，支持条件筛选、排序、分页、模板保存、导出。
- 范围：
  - 市场：A 股（主板/科创/创业，按数据源覆盖）
  - 频段：日线（D1）
  - 复权：默认前复权（qfq），支持切换 hfq/none
  - 指标：MA、EMA、MACD、RSI、BOLL、ATR、KDJ（新增）
  - 交互：条件构建器（AND/OR 分组）、预置模板、结果表、导出
  - 性能：分页、统一缓存、增量更新

不在 P0：分钟级、复杂回测、行业中性化、事件/情绪、AI 选股（归入 P1 PoC）。

## 2. 数据与口径
- 数据源：优先 Tushare（已有集成），亦兼容内部缓存/本地镜像。
- 复权口径：
  - 默认 qfq（前复权），原因：保证技术指标与形态连续性，避免除权带来的“断层”误判。
  - API 支持 adj ∈ {"qfq","hfq","none"}，前端可切换；回测与展示需与口径一致。
- 字段（行情与派生）：
  - 基础：ts_code、trade_date、open、high、low、close、pre_close、pct_chg、vol(手)、amount(元)、turnover_rate
  - 指标（固定参数集）：
    - MA: ma5, ma10, ma20, ma60（收盘价）
    - EMA: ema12, ema26（收盘价）
    - MACD: dif(12,26)、dea(9)、macd_hist
    - RSI: rsi14
    - BOLL: boll_mid(20)、boll_upper(20,2)、boll_lower(20,2)
    - ATR: atr14
    - KDJ: kdj_k(9,3,3), kdj_d(9,3,3), kdj_j(9,3,3)

## 3. 指标定义（含 KDJ）
- MA/EMA/MACD/RSI/BOLL/ATR：常规定义，按收盘价计算（ATR 用 TR，n=14）。
- KDJ（n=9, m1=3, m2=3）
  - RSV_t = (C_t - Low_n) / (High_n - Low_n) * 100
  - K_t = 2/3*K_{t-1} + 1/3*RSV_t，初值 50
  - D_t = 2/3*D_{t-1} + 1/3*K_t，初值 50
  - J_t = 3*K_t - 2*D_t
- 交叉判定：
  - cross_up(A,B): A_{t-1} <= B_{t-1} 且 A_t > B_t
  - cross_down(A,B): A_{t-1} >= B_{t-1} 且 A_t < B_t

## 4. 筛选 DSL（P0）
- 结构（递归）：
```json
{
  "logic": "AND|OR",
  "children": [
    { "field": "rsi14", "op": "<", "value": 30 },
    { "op": "group", "logic": "OR", "children": [
      { "field": "kdj_k", "op": "cross_up", "right_field": "kdj_d" },
      { "field": "close", "op": ">", "value": "ma20" }
    ]}
  ]
}
```
- 字段白名单：
  - 原始：close, open, high, low, pct_chg, vol, amount, turnover_rate
  - 指标：ma5, ma10, ma20, ma60, ema12, ema26, dif, dea, macd_hist, rsi14, boll_mid, boll_upper, boll_lower, atr14, kdj_k, kdj_d, kdj_j
- 操作符：>, <, >=, <=, ==, !=, between, cross_up, cross_down
- 排序：[{ field, direction: "asc|desc" }]
- 分页：limit(默认50,≤200)，offset
- 口径：adj: "qfq|hfq|none"，date（可选；为空则取最近交易日）

校验：使用 Pydantic/attrs 对 DSL 进行严格校验，拒绝非白名单字段与操作符。

## 5. API 契约（草案）
### 5.1 运行筛选
- POST /api/screening/run
- Request
```json
{
  "market": "CN",
  "date": "2025-08-21",
  "adj": "qfq",
  "conditions": { "logic": "AND", "children": [ /* DSL */ ] },
  "order_by": [{ "field": "pct_chg", "direction": "desc" }],
  "limit": 50,
  "offset": 0
}
```
- Response
```json
{
  "success": true,
  "data": {
    "total": 1234,
    "items": [
      {
        "ts_code": "600519.SH",
        "name": "贵州茅台",
        "trade_date": "2025-08-21",
        "close": 1788.00,
        "pct_chg": 2.35,
        "amount": 1.23e10,
        "ma20": 1701.2,
        "rsi14": 61.2,
        "kdj_k": 73.4,
        "kdj_d": 65.2,
        "kdj_j": 89.8
      }
    ]
  }
}
```
- 错误：400（DSL校验失败）、422（参数缺失/格式）、500（内部错误）。

### 5.2 模板管理
- GET /api/screening/templates -> 当前用户模板列表
- POST /api/screening/templates -> 创建/更新模板
- DELETE /api/screening/templates/{id}
- 模板数据结构：{ id, name, description, market:"CN", adj, conditions, order_by, created_at, updated_at }

### 5.3（P1）AI 选股
- POST /api/screening/ai
  - body: { prompt, date?, adj?, topN? }
  - 返回：{ conditions, explain, items }（内部复用 /run）

## 6. 系统设计
### 6.1 后端
- 新增服务 screening_service.py
  - 输入：筛选 DSL、日期、adj、分页、排序
  - 流程：
    1) 解析/校验 DSL -> 生成执行计划（字段集合、交叉检测、窗口需求）
    2) 拉取/读取缓存数据帧（指定日期，按 adj），构造需要的窗口列
    3) 计算指标列（向量化），并缓存（键：CN:{adj}:{date}:ind:v1）
    4) 应用条件过滤（布尔掩码），计算排序与分页
    5) 返回数据与 total
- 指标库
  - 文件：tradingagents/tools/analysis/indicators.py
  - 函数：ma(series, n)、ema(series, n)、macd(close, fast=12, slow=26, signal=9)、rsi(close, n=14)、boll(close, n=20, k=2)、atr(high, low, close, n=14)、kdj(high, low, close, n=9, m1=3, m2=3)
- 缓存
  - Redis/本地：
    - K 线：CN:{adj}:{date}:bars （列裁剪）TTL 24h
    - 指标：CN:{adj}:{date}:ind:v1  TTL 12h（参数固定版本号）
    - 结果：screen:CN:{adj}:{date}:{sha256(dsl+order+page)} TTL 2h
- 依赖与并发
  - 使用 pandas/numpy，尽量批量；指标按列向量化
  - 允许并行计算（多进程/多线程）在 P1 考量

### 6.2 前端（页面：筛选 Screening）
- 区域：
  - 条件构建器：字段下拉（行情/技术），操作符、值输入（数字/字段），分组 AND/OR
  - 预置模板：5 个快捷模板 + 用户模板管理
  - 顶部：市场固定 CN、日期选择（默认最新交易日）、复权切换（qfq/hfq/none）
  - 结果表：关键列、排序、分页、导出、一键加入自选/生成分析任务
- 交互细节：
  - 交叉条件（如 K 上穿 D）用“字段对字段”选择器
  - 值区间（between）支持范围输入
  - 保存模板时校验 DSL 合法性

## 7. 预置策略模板（P0）
1) 趋势突破：close > ma20 AND ma20 > ma60 AND amount > 1.5 * ma20_amount
2) 均线多头：ma5 > ma10 AND ma10 > ma20
3) 放量上攻：pct_chg > 3 AND amount > 1.5x20日均额
4) 超跌反弹：rsi14 < 30 AND close > open
5) KDJ 金叉：kdj_k cross_up kdj_d AND kdj_k < 80

说明：若“20日均额”暂缺，可先用 rolling(amount,20).mean() 内部计算，前端避免暴露。

## 8. 安全与合规
- 字段/操作符白名单；拒绝任意表达式与任意代码。
- 限流：用户/接口级 rate limit（如 30/min），避免批量刷库。
- 日志：记录 DSL hash、用户、响应时间、命中缓存与否。
- 授权：按 Token 绑定用户空间保存模板。

## 9. 错误处理
- 400：DSL 校验失败 -> 返回字段/操作符/类型错误位置信息
- 422：参数缺失或非法 -> 返回缺失字段
- 500：内部错误 -> 请求 ID + 建议重试

## 10. 性能目标
- 指标缓存命中时：单次筛选（Top 50）< 500ms
- 首次无缓存：在 2s 内返回（视数据量与硬件）
- 并发：50 QPS（缓存命中场景）

## 11. 里程碑
- 第 1 周：
  - 指标库实现（含 KDJ）、数据口径对齐、缓存结构落地
  - DSL 校验与执行器、/api/screening/run
- 第 2 周：
  - 前端筛选器与结果页、模板管理 API 与 UI
  - 预置模板、导出、排序分页打磨
- 第 3 周：
  - 压测与优化、文档与示例、验收
- P1（预研并计划落地）：
  - AI 选股：/api/screening/ai（NL→DSL），few-shot 模板
  - 简单回测（TopN/持有期）与策略评分

## 12. 验收标准（P0）
- 能在日线 A 股上运行 5 个预置模板并返回结果
- 支持复权切换（默认 qfq）并稳定输出
- 支持 DSL 条件组合、交叉判定、排序与分页
- 指标与筛选结果可导出；模板可保存/加载
- 具备基本缓存与日志，性能达标

## 13. 变更记录
- 2025-08-22: 初版（加入 KDJ、复权切换、AI 选股 P1 预留）

