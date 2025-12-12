# 操作复盘功能设计

## 1. 功能概述

操作复盘是专业版独享功能，帮助用户回顾和分析自己的交易操作，通过AI点评找出问题，持续提升交易能力。

### 1.1 核心功能

| 功能 | 说明 |
|------|------|
| **单笔交易复盘** | 分析某次买入/卖出的时机是否合适 |
| **完整交易复盘** | 分析一只股票从买入到卖出的完整操作 |
| **阶段性复盘** | 周/月/季度交易总结与分析 |
| **AI操作点评** | 智能分析操作问题，给出改进建议 |
| **个人案例库** | 将典型操作保存为学习案例 |

### 1.2 复盘维度

- **时机分析**：买入/卖出时机是否合适
- **仓位分析**：仓位控制是否合理
- **止盈止损**：是否严格执行纪律
- **情绪分析**：是否存在追涨杀跌等情绪化操作
- **收益分析**：实际收益 vs 最优收益

---

## 2. 现有代码分析

### 2.1 交易记录结构

**数据来源**: `paper_trades` 集合

```python
{
    "user_id": str,
    "code": str,           # 股票代码
    "market": str,         # CN/HK/US
    "currency": str,       # CNY/HKD/USD
    "side": str,           # buy/sell
    "quantity": int,       # 交易数量
    "price": float,        # 成交价格
    "amount": float,       # 成交金额
    "commission": float,   # 手续费
    "pnl": float,          # 实现盈亏(卖出时)
    "timestamp": str,      # 交易时间
    "analysis_id": str     # 关联的分析ID(可选)
}
```

### 2.2 可复用模块

- **行情数据获取**: `tradingagents/dataflows/` - 获取历史K线
- **LLM调用**: `app/services/simple_analysis_service.py` - 大模型分析
- **报告保存**: `analysis_reports` 集合模式

---

## 3. 技术设计

### 3.1 数据模型

#### 3.1.1 复盘报告集合 `trade_reviews`

```python
{
    "_id": ObjectId,
    "review_id": str,          # 唯一复盘ID
    "user_id": str,
    "review_type": str,        # single_trade / complete_trade / periodic
    
    # 交易信息
    "trade_info": {
        "code": str,
        "name": str,
        "market": str,
        "trades": [             # 关联的交易记录
            {
                "trade_id": str,
                "side": str,
                "quantity": int,
                "price": float,
                "timestamp": str
            }
        ],
        "total_buy_amount": float,
        "total_sell_amount": float,
        "realized_pnl": float,
        "realized_pnl_pct": float,
        "holding_days": int
    },
    
    # 市场数据快照
    "market_snapshot": {
        "buy_date_price": float,   # 买入当日价格区间
        "sell_date_price": float,  # 卖出当日价格区间
        "period_high": float,      # 持仓期间最高价
        "period_low": float,       # 持仓期间最低价
        "optimal_buy_price": float,  # 最优买点
        "optimal_sell_price": float  # 最优卖点
    },
    
    # AI分析结果
    "ai_review": {
        "overall_score": int,      # 总评分 0-100
        "timing_score": int,       # 时机评分
        "position_score": int,     # 仓位评分
        "discipline_score": int,   # 纪律评分
        
        "summary": str,            # 总结
        "strengths": list,         # 做得好的地方
        "weaknesses": list,        # 需要改进的地方
        "suggestions": list,       # 具体建议
        
        "timing_analysis": str,    # 时机分析详情
        "position_analysis": str,  # 仓位分析详情
        "emotion_analysis": str,   # 情绪分析
        
        "missed_profit": float,    # 错失的收益
        "avoided_loss": float      # 避免的亏损
    },
    
    # 元数据
    "is_case_study": bool,         # 是否保存为案例
    "tags": list,                  # 标签
    "created_at": datetime
}
```

#### 3.1.2 阶段性复盘报告 `periodic_reviews`

```python
{
    "_id": ObjectId,
    "review_id": str,
    "user_id": str,
    "period_type": str,        # week / month / quarter / year
    "period_start": datetime,
    "period_end": datetime,
    
    # 交易统计
    "statistics": {
        "total_trades": int,
        "winning_trades": int,
        "losing_trades": int,
        "win_rate": float,
        "total_pnl": float,
        "avg_profit": float,
        "avg_loss": float,
        "profit_loss_ratio": float,  # 盈亏比
        "max_single_profit": float,
        "max_single_loss": float,
        "max_drawdown": float
    },
    
    # 交易明细
    "trades_summary": [...],
    
    # AI分析
    "ai_review": {
        "overall_score": int,
        "summary": str,
        "trading_style": str,      # 交易风格分析
        "common_mistakes": list,   # 常见错误
        "improvement_areas": list, # 改进方向
        "action_plan": list        # 下阶段行动计划
    },
    
    "created_at": datetime
}
```

---

### 3.2 API 设计

```
/api/review
├── 单笔/完整交易复盘
│   ├── POST /trade                    # 发起交易复盘
│   ├── GET  /trade/history            # 复盘历史列表
│   └── GET  /trade/:review_id         # 复盘详情
│
├── 阶段性复盘
│   ├── POST /periodic                 # 发起阶段性复盘
│   ├── GET  /periodic/history         # 阶段性复盘历史
│   └── GET  /periodic/:review_id      # 复盘详情
│
├── 案例库
│   ├── POST /case                     # 保存为案例
│   ├── GET  /cases                    # 我的案例库
│   └── DELETE /case/:id               # 删除案例
│
└── 统计
    └── GET  /statistics               # 交易统计概览
```

### 3.3 服务层设计

**新增文件**: `app/services/trade_review_service.py`

```python
class TradeReviewService:
    """交易复盘服务"""

    # 交易复盘
    async def create_trade_review(
        self, user_id: str,
        trade_ids: List[str],       # 要复盘的交易ID
        review_type: str = "complete_trade"
    ) -> ReviewTask

    async def get_review_history(
        self, user_id: str,
        page: int, page_size: int
    ) -> List[TradeReview]

    async def get_review_detail(self, review_id: str) -> TradeReview

    # 阶段性复盘
    async def create_periodic_review(
        self, user_id: str,
        period_type: str,           # week/month/quarter
        start_date: datetime,
        end_date: datetime
    ) -> ReviewTask

    # 案例库
    async def save_as_case(self, review_id: str, tags: List[str]) -> bool
    async def get_cases(self, user_id: str) -> List[CaseStudy]
    async def delete_case(self, case_id: str) -> bool

    # 统计
    async def get_trading_statistics(self, user_id: str) -> TradingStats
```

---

## 4. AI分析流程

### 4.1 单笔/完整交易复盘流程

```
用户选择要复盘的交易
       ↓
获取交易记录详情
       ↓
获取交易期间的K线数据
  - 买入前后10个交易日
  - 卖出前后10个交易日
  - 持仓期间完整K线
       ↓
计算关键指标
  - 最优买点/卖点
  - 错失收益/避免亏损
  - 持仓期间波动
       ↓
构建复盘提示词
       ↓
调用大模型分析
       ↓
解析并保存结果
```

### 4.2 阶段性复盘流程

```
用户选择复盘周期
       ↓
获取该周期所有交易记录
       ↓
计算交易统计指标
  - 胜率、盈亏比
  - 平均收益/亏损
  - 最大回撤
       ↓
分析交易模式
  - 交易频率
  - 持仓时间分布
  - 盈亏分布
       ↓
构建复盘提示词
       ↓
调用大模型分析
       ↓
生成阶段性报告
```

---

## 5. 提示词设计

### 5.1 单笔交易复盘提示词

```markdown
# 交易复盘分析任务

## 交易信息
- 股票: {code} {name}
- 买入时间: {buy_time}
- 买入价格: {buy_price} 元
- 买入数量: {buy_quantity} 股
- 卖出时间: {sell_time}
- 卖出价格: {sell_price} 元
- 持仓天数: {holding_days} 天
- 实现盈亏: {realized_pnl} 元 ({realized_pnl_pct}%)

## 交易期间行情数据
{kline_data}

### 关键价格
- 持仓期间最高价: {period_high} 元 (日期: {high_date})
- 持仓期间最低价: {period_low} 元 (日期: {low_date})
- 买入当日: 开盘 {buy_open} / 最高 {buy_high} / 最低 {buy_low}
- 卖出当日: 开盘 {sell_open} / 最高 {sell_high} / 最低 {sell_low}

## 分析要求

请从以下维度分析这笔交易：

1. **时机评估** (0-100分)
   - 买入时机评价
   - 卖出时机评价
   - 最优买点/卖点分析

2. **操作评价**
   - 做对了什么
   - 做错了什么
   - 如果重来应该如何操作

3. **收益分析**
   - 实际收益率 vs 理论最优收益率
   - 错失收益或避免亏损金额

4. **改进建议**
   - 具体可操作的改进建议

请以JSON格式输出。
```

### 5.2 阶段性复盘提示词

```markdown
# 阶段性交易复盘

## 复盘周期
{period_type}: {start_date} 至 {end_date}

## 交易统计
- 总交易次数: {total_trades}
- 盈利次数: {winning_trades} / 亏损次数: {losing_trades}
- 胜率: {win_rate}%
- 总盈亏: {total_pnl} 元
- 盈亏比: {profit_loss_ratio}
- 最大单笔盈利: {max_profit} 元
- 最大单笔亏损: {max_loss} 元

## 交易明细
{trades_detail}

## 分析要求

1. **整体评价** (0-100分)
2. **交易风格分析** - 短线/中长线，频率是否合理
3. **问题诊断** - 常犯错误，亏损共性
4. **成功经验** - 盈利共性，好习惯
5. **改进计划** - 下阶段行动计划

请以JSON格式输出。
```

---

## 6. 前端设计

### 6.1 页面结构

```
frontend/src/views/Review/
├── index.vue              # 复盘总览页面
├── TradeReview.vue        # 交易复盘页面
├── PeriodicReview.vue     # 阶段性复盘页面
├── ReviewDetail.vue       # 复盘详情页面
└── CaseLibrary.vue        # 个人案例库
```

### 6.2 复盘入口

**入口1**: 交易历史页面
- 每笔交易后增加"复盘"按钮

**入口2**: 持仓页面
- 已清仓的股票显示"复盘"入口

**入口3**: 侧边栏菜单
- 新增"交易复盘"菜单项

### 6.3 路由配置

```typescript
{
  path: '/review',
  name: 'Review',
  component: () => import('@/views/Review/index.vue'),
  meta: { requiresAuth: true, requiresPro: true }
},
{
  path: '/review/trade/:id',
  name: 'TradeReview',
  component: () => import('@/views/Review/TradeReview.vue'),
  meta: { requiresAuth: true, requiresPro: true }
},
{
  path: '/review/periodic',
  name: 'PeriodicReview',
  component: () => import('@/views/Review/PeriodicReview.vue'),
  meta: { requiresAuth: true, requiresPro: true }
},
{
  path: '/review/cases',
  name: 'CaseLibrary',
  component: () => import('@/views/Review/CaseLibrary.vue'),
  meta: { requiresAuth: true, requiresPro: true }
}
```

---

## 7. 实现计划

### Phase 1: 后端基础 (Week 1)
- [ ] 创建数据模型 `app/models/review.py`
- [ ] 创建服务层 `app/services/trade_review_service.py`
- [ ] 创建API路由 `app/routers/review.py`
- [ ] 数据库索引

### Phase 2: 交易复盘功能 (Week 2)
- [ ] 实现交易数据聚合
- [ ] 实现K线数据获取
- [ ] 实现AI复盘分析
- [ ] 实现复盘报告保存

### Phase 3: 阶段性复盘 (Week 3)
- [ ] 实现交易统计计算
- [ ] 实现阶段性AI分析
- [ ] 实现报告生成

### Phase 4: 前端开发 (Week 4)
- [ ] 复盘总览页面
- [ ] 交易复盘页面
- [ ] 阶段性复盘页面
- [ ] 复盘详情展示

### Phase 5: 案例库与优化 (Week 5)
- [ ] 案例保存功能
- [ ] 案例库页面
- [ ] 与学习中心集成
- [ ] 测试与优化

---

## 8. 与其他功能的集成

### 8.1 与模拟交易集成
- 复用 `paper_trades` 交易记录
- 在交易历史页面增加复盘入口

### 8.2 与学习中心集成
- 个人案例可作为学习素材
- 提供"如何进行有效复盘"课程

### 8.3 与持仓分析集成
- 复盘时可参考当时的持仓分析报告
- 形成"分析→交易→复盘"闭环

---

## 9. 与分析引擎和模板系统集成

> **详细设计请参考**: [持仓分析与复盘分析引擎集成设计](../v2.0/portfolio-trade-review-engine-integration.md)

### 9.1 集成目标

将操作复盘与 v2.0 版本的以下系统集成：

1. **提示词模板系统** - 使用统一的模板管理替代硬编码提示词
2. **统一输出规范** - 与持仓分析保持一致的 JSON 输出格式

### 9.2 关键改造点

| 改造点 | 现状 | 目标 |
|--------|------|------|
| 复盘提示词 | 硬编码在 `_build_trade_review_prompt` | `get_agent_prompt("managers", "trade_reviewer", ...)` |
| 阶段性复盘提示词 | 硬编码 | `get_agent_prompt("managers", "periodic_reviewer", ...)` |
| 风格支持 | 不支持 | neutral/conservative/aggressive 三档 |
| 输出格式 | 自定义 | 统一 JSON 规范 |

### 9.3 新增模板

- `managers/trade_reviewer` - 单笔/完整交易复盘模板
- `managers/periodic_reviewer` - 阶段性复盘模板

### 9.4 模板变量

```python
{
    "trade": {
        "code": str,              # 股票代码
        "name": str,              # 股票名称
        "trades_table": str,      # 交易明细表
        "holding_days": int,      # 持仓天数
        "realized_pnl": float,    # 实现盈亏
        "realized_pnl_pct": float # 实现盈亏%
    },
    "market_snapshot": {
        "period_high": float,     # 期间最高价
        "period_low": float,      # 期间最低价
        "buy_day_ohlc": str,      # 买入当日OHLC
        "sell_day_ohlc": str      # 卖出当日OHLC
    }
}
```

### 9.5 特性开关

```bash
# 环境变量控制
USE_TEMPLATE_PROMPTS=true/false  # 是否使用模板系统
```
