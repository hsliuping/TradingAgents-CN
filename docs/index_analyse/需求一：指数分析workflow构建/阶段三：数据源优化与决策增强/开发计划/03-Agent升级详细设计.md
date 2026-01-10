# 03-Agent升级详细设计 (Agent Upgrade)

## 1. 设计目标
通过引入新的 Agent 角色和增强现有 Agent 的 Prompt，使其能够利用“混合数据源”和“实时快照”进行更精准的场景化决策。

## 2. 新增角色：Technical Analyst (技术分析师)

### 2.1 职责定义
专注于量化技术指标的分析，不带任何宏观或新闻偏见，仅基于数字说话。

### 2.2 输入数据
- 指数日线/分钟线数据 (OHLCV)
- 技术指标: MA (5, 20, 60), RSI (6, 12, 24), MACD, KDJ, BOLL

### 2.3 System Prompt 设计
```markdown
你是一个严谨的量化技术分析师。你的任务是根据提供的 K 线数据和技术指标，判断当前的市场趋势和潜在买卖点。

请遵循以下分析框架：
1. **趋势识别**: 使用均线系统判断当前是多头排列、空头排列还是震荡。
2. **动能分析**: 使用 MACD 和成交量判断上涨/下跌的动能是否衰竭。
3. **超买超卖**: 检查 RSI 和 KDJ 是否处于极端区域 (>80 或 <20)。
4. **形态识别**: 识别关键的 K 线形态 (如启明星、吞噬、背离)。

输出格式要求:
- **趋势信号**: BULLISH (看多) / BEARISH (看空) / NEUTRAL (震荡)
- **仓位建议**: 0.0 - 1.0 (仅基于技术面的建议仓位)
- **关键点位**: 支撑位 xxx, 压力位 xxx
- **风险提示**: (如：顶背离风险)
```

## 3. 现有角色升级

### 3.1 Sector Analyst (板块分析师)
**升级点**: 增加对 `MorningSnapshot` 和 `ClosingSnapshot` 的理解能力。

- **早盘 Prompt 注入**:
  > "当前是早盘阶段 (09:45)。请重点分析集合竞价成交额前三的板块，以及开盘 15 分钟内资金净流入最快的板块。忽略昨日的旧新闻，专注于当下的资金攻击方向。"

- **尾盘 Prompt 注入**:
  > "当前是尾盘阶段 (14:45)。请检查是否有板块出现尾盘抢筹现象（最后30分钟量能放大且价格拉升）。这通常预示着明日的主线。"

### 3.2 Strategy Advisor (策略顾问)
**升级点**: 变为 `TimeAwareStrategyAdvisor`，根据时间路由不同的决策逻辑。

#### 决策逻辑表
| 时间段 | 核心权重 | 决策倾向 | 止损策略 |
| :--- | :--- | :--- | :--- |
| **早盘** | 外盘(30%) + 竞价(40%) + 宏观(30%) | 趋势跟随 (追涨杀跌) | 严格 (快进快出) |
| **尾盘** | 全天趋势(50%) + 尾盘异动(30%) + 技术面(20%) | 确认/埋伏 (低吸高抛) | 宽松 (允许隔夜波动) |
| **盘后** | 宏观(40%) + 政策(40%) + 技术面(20%) | 战略配置 (中长线) | N/A |

## 4. 交互流程设计

### 4.1 早盘流程
1. `User` -> `MainAssistant`: 启动 "Morning Session"。
2. `MainAssistant` -> `RealtimeMonitor`: 获取 `MorningSnapshot`。
3. `MainAssistant` -> `TechnicalAnalyst`: 获取隔夜外盘技术面分析。
4. `MainAssistant` -> `SectorAnalyst`: 分析竞价与开盘资金。
5. `MainAssistant` -> `StrategyAdvisor`: 综合上述信息，给出“今日开仓/观望”建议。

### 4.3 盘后/复盘流程 (Post-Market)
1. `User` -> `MainAssistant`: 启动 "Post Session" (默认模式)。
2. `MainAssistant`: **不调用** `RealtimeMonitor`，而是直接调用 `HybridIndexDataProvider.get_index_daily()` 获取清洗后的日线数据。
3. `MainAssistant` -> `TechnicalAnalyst`: 进行日线级别的趋势确认。
4. `MainAssistant` -> `StrategyAdvisor`: 生成 "每日复盘总结" 和 "明日策略展望"。

**兼容性设计**:
- `StrategyAdvisor` 内部维护一个 `SessionContext`。
- 如果 `session == 'post'`: 禁用“追涨杀跌”逻辑，启用“大势研判”逻辑。
- 如果 `session == 'intraday'`: 禁用“长线配置”逻辑，启用“短线博弈”逻辑。
