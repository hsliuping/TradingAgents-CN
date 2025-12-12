# 会议纪要：数据一致性、回测与模拟交易架构与合规

日期：2025-10-19  
项目：TradingAgents-CN  
用途：技术回顾与工程/合规指南

## 1. 数据一致性（Point-in-Time, PIT）与时间线
- 统一时间线：以 `UTC` 作为主时间轴，保留 `timezone` 字段；跨市场（CN/HK/US）统一对齐。
- PIT 一致：所有特征（新闻/社媒/财报/估值/风格因子/LLM输出）需带版本冻结（`data_version`/`feature_version`），保证复现实验可重放。
- 公司行为：分红/拆分/配股与停牌，需在撮合与复权策略（前复权/不复权/动态复权）中保持一致。确保撮合价与持仓账务同一口径。
- 交易日历：使用 `exchange_calendars` 或自研日历服务提供交易日与交易时段（竞价/连续竞价/收盘）。
- 回放模式：支持分钟/tick 回放；心跳与断点续跑；精确控制数据可见性与延迟，以避免“看未来”。

## 2. 整体架构与内核选择（混合方案）
- 短期：`vectorbt` 进行向量化因子与参数网格回测（速度快，适合技术/情绪因子）。
- 中期：`Backtrader` 或 `RQAlpha` 承载事件驱动策略、订单撮合、费用/滑点与市场约束（CN/HK/US）。
- 长期：抽象统一 `BacktestService`/`PaperService` 接口，策略与数据面解耦、内核可替换（含 Lean/自研）。

## 3. 引擎对比（简要）
- `vectorbt`：Apache-2.0 + Commons Clause；擅长向量化回测与可视化；事件驱动弱。商业售卖需避开“主要价值来自其功能”。
- `Backtrader`：GPLv3；成熟撮合与订单生命周期；跨品种；A股规则需扩展。
- `RQAlpha`：Apache-2.0（官方强调非商业）；CN 规则支持较好；生态相对封闭。
- `Lean`：Apache-2.0；工业级、可商业分发；栈较复杂（C# + Python）。
- `vn.py`：CTA 强、股票研究相对弱。

## 4. 模拟交易系统升级（Phase 1 优先）
- 组件：`BrokerSim`（撮合/费用/滑点/延迟/部分成交）、`OMS`（订单生命周期）、`Portfolio`（多币种账户/现金/保证金）、`CorporateActions`。
- 订单类型：市价/限价/止损/止盈/冰山/算法（VWAP/TWAP）。
- 滑点模型：固定 bps、点差/盘口、成交量约束、VWAP/TWAP。
- 事件流：SSE/WebSocket 推送 `order/trade/position/pnl/risk`，前端展示实时订单簿/持仓/图表与告警。

## 5. 市场规则（CN/HK/US）
- CN：T+1、涨跌停、停牌、最小交易单位（手数），融资融券与融券成本。
- HK：无涨跌停、集合竞价、手数与最小报价单位。
- US：盘前/盘后、做空成本、PDT 等限制；期权/ETF/ADR 场景。

## 6. 风控与合规
- 事前：账户/风险敞口/限额校验（单票/行业/风格/杠杆）。
- 事中：订单拒绝/缩量/延迟；异常波动与风控触发。
- 事后：归因与风险报告（风格暴露、行业分布、头寸集中度、回撤与波动）。

## 7. 服务与 API（建议）
- Paper/Backtest 服务端点：
  - `POST /paper/session/start`、`POST /paper/order`、`GET /paper/portfolio`、`GET /paper/report`、`GET /paper/stream`
  - `POST /backtest/run`、`GET /backtest/report`、`GET /backtest/stream`
- 数据服务端点：
  - `GET /data/candles`、`GET /data/calendar`、`GET /data/corp_actions`、`GET /data/constraints`、`GET /features/{name}`、`GET /stream/ticks`

## 8. 集成与目录建议（现有项目）
- 后端：`app/routers/paper.py`（已有）、扩展 `sse.py`（已有）与新增 `data.py`；`app/services/paper/` 实现 `BrokerSim/OMS/Portfolio`；`tradingagents/backtest/` 放统一接口与适配器。
- 数据与特征：`dataflows/features/` 与 `dataflows/labels/`；版本冻结与缓存策略。
- 测试：`tests/tradingagents/paper/` 单元与集成测试；回放与再现性用例。
- 前端：订单簿/持仓/交易与绩效面板、风险与告警卡片、会话控制。

## 9. 许可与商业化策略
- Backtrader（GPLv3）：将其封装为独立服务（进程/容器）并通过网络协议调用，可避免闭源主平台被 GPL 传染；若分发服务端二进制/源码，需附 GPLv3 与对应源代码。
- vectorbt（Commons Clause）：不强制开源，但禁止销售“主要价值源自其功能”的产品/服务（含托管/支持若主要价值即其功能）。
- Lean（Apache-2.0）：商业友好，适合“对外收费”的回测/模拟核心服务；主平台以 HTTP/SSE 调用。
- 合规模式：主平台与数据服务仅通过 HTTP/gRPC/SSE 与内核服务通信；保持内核可替换与接口文档化，降低法律与工程风险。

## 10. 分阶段路线（摘要）
- Phase 1（1周）：可用可观测的模拟交易 MVP（BrokerSim/OMS/Portfolio/SSE/基本费用与滑点）。
- Phase 2：市场规则与公司行为完善（CN/HK/US）。
- Phase 3：执行模型与风控（VWAP/TWAP/延迟/部分成交/风险限额与告警）。
- Phase 4：回放与统一服务（BacktestService/PaperService），与缓存的 LLM 特征集成。

## 11. 决议与行动项
- 决议：采用混合方案；先落地 Paper MVP + 数据服务；逐步引入 Backtrader/Lean 作为可替换内核；坚持 PIT 与版本冻结；事件流与报告优先。
- 行动项：
  1) 设计 `data.py` 路由与响应 schema（含 Arrow/Parquet/JSON）；
  2) 定义 SSE 事件模型（order/trade/position/pnl/risk）；
  3) 制定费用/滑点/延迟策略文件与默认配置；
  4) 实现 CN/HK/US 规则模块与公司行为处理；
  5) 输出统一报告模板（绩效/归因/风险）与导出格式；
  6) 形成 Backtrader/Lean 适配器草案与替换指南；
  7) 补充合规 NOTICE 与 LICENSE 标注。

注：本纪要为工程与开源许可实践建议，非法律意见；最终商业模式需结合法务书面意见确认。