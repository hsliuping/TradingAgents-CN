# 行业/板块分析师 & 大盘/指数分析师 实现计划

## 📋 实现状态

| 组件 | 状态 | 说明 |
|------|------|------|
| Agent 插件架构 | ✅ 已完成 | AnalystRegistry + ReportAggregator |
| SectorAnalyst | ✅ 已完成 | 板块分析师，无工具调用模式 |
| IndexAnalyst | ✅ 已完成 | 大盘分析师，无工具调用模式 |
| 工作流集成 | ✅ 已完成 | setup.py 动态加载扩展分析师 |
| 下游 Agent 集成 | ✅ 已完成 | 研究员/经理使用 ReportAggregator |
| 单元测试 | ✅ 已完成 | 22 个测试用例全部通过 |
| 数据工具函数 | 🔄 进行中 | sector_tools.py / index_tools.py |

## 概述

本文档规划两个新 Agent 的实现：
1. **行业/板块分析师 (SectorAnalyst)** - 分析行业趋势、板块轮动、同业对比
2. **大盘/指数分析师 (IndexAnalyst)** - 分析大盘走势、市场环境、系统性风险

**设计原则**：
- 新 Agent 实现在 `core/` 目录中，为后续迁移其它 agent 做准备
- 数据源优先级：**Tushare（主）> AKShare（备用）**
- 复用现有 `core/agents/base.py` 基类
- **🆕 使用插件架构**：通过 AnalystRegistry 注册，无需修改引擎源码

## 一、数据源分析

### 1.1 Tushare 可用 API（主数据源）

#### 指数数据 API
```python
import tushare as ts
pro = ts.pro_api()

# 指数基本信息
pro.index_basic(market='SSE')          # 指数基本信息（SSE上交所/SZSE深交所）

# 指数日线行情
pro.index_daily(ts_code='000001.SH')   # 指数日线数据
pro.index_dailybasic(ts_code='000001.SH', trade_date='20241201')  # 大盘指数每日指标

# 指数成分和权重
pro.index_weight(index_code='000300.SH')  # 沪深300成分股权重

# 沪深市场每日交易统计
pro.daily_info(trade_date='20241201')  # 涨跌家数、成交量等
```

#### 行业/板块数据 API
```python
# 同花顺概念板块（需6000积分）
pro.ths_index(type='N')                 # 概念指数列表（N-概念/I-行业/R-地域）
pro.ths_daily(ts_code='885800.TI')      # 板块指数行情
pro.ths_member(ts_code='885800.TI')     # 板块成分股

# 申万行业分类
pro.index_classify(level='L1')          # 申万一级行业
pro.sw_daily(ts_code='801010.SI')       # 申万行业指数行情

# 资金流向
pro.moneyflow(trade_date='20241201')    # 个股资金流向
pro.moneyflow_ths(trade_date='20241201') # 板块资金流向（THS）
```

#### 常用指数代码
| 指数代码 | 名称 |
|---------|------|
| 000001.SH | 上证指数 |
| 399001.SZ | 深证成指 |
| 399006.SZ | 创业板指 |
| 000688.SH | 科创50 |
| 000300.SH | 沪深300 |
| 000016.SH | 上证50 |
| 000905.SH | 中证500 |

### 1.2 AKShare 可用 API（备用数据源）

```python
import akshare as ak

# 板块数据（Tushare 积分不足时的备选）
ak.stock_board_industry_name_em()       # 行业板块名称
ak.stock_board_concept_name_em()        # 概念板块名称

# 指数实时数据
ak.stock_zh_index_spot()                # A股指数实时行情
```

## 二、工具函数设计

工具函数放在 `core/tools/` 目录下，遵循现有工具架构。

### 2.1 行业/板块分析工具

```python
# 文件: core/tools/sector_tools.py

@tool
def get_sector_list(
    sector_type: Annotated[str, "板块类型: industry(行业) 或 concept(概念)"] = "industry"
) -> str:
    """
    获取板块列表
    数据源: Tushare ths_index / sw_industry_classify
    """
    pass

@tool
def get_sector_performance(
    trade_date: Annotated[str, "交易日期 YYYYMMDD"],
    sector_type: Annotated[str, "板块类型"] = "industry",
    top_n: Annotated[int, "返回前N个板块"] = 20
) -> str:
    """
    获取板块涨跌幅排名
    数据源: Tushare ths_daily / sw_daily
    """
    pass

@tool
def get_sector_detail(
    ts_code: Annotated[str, "板块代码（如 885800.TI）"],
    start_date: Annotated[str, "开始日期 YYYYMMDD"],
    end_date: Annotated[str, "结束日期 YYYYMMDD"]
) -> str:
    """
    获取板块详细数据（历史行情、成分股等）
    数据源: Tushare ths_daily + ths_member
    """
    pass

@tool
def get_stock_sector_info(
    ticker: Annotated[str, "股票代码（6位）"]
) -> str:
    """
    获取个股所属行业/概念板块信息
    数据源: Tushare ths_member (反查)
    """
    pass

@tool
def get_sector_fund_flow(
    trade_date: Annotated[str, "交易日期 YYYYMMDD"],
    sector_type: Annotated[str, "板块类型"] = "industry"
) -> str:
    """
    获取板块资金流向
    数据源: Tushare moneyflow_ths
    """
    pass
```

### 2.2 大盘/指数分析工具

```python
# 文件: core/tools/index_tools.py

@tool
def get_index_list() -> str:
    """
    获取主要指数列表
    数据源: Tushare index_basic
    """
    pass

@tool
def get_index_daily(
    ts_code: Annotated[str, "指数代码（如 000001.SH）"] = "000001.SH",
    start_date: Annotated[str, "开始日期 YYYYMMDD"] = None,
    end_date: Annotated[str, "结束日期 YYYYMMDD"] = None
) -> str:
    """
    获取指数日线行情
    数据源: Tushare index_daily
    """
    pass

@tool
def get_index_indicators(
    ts_code: Annotated[str, "指数代码"] = "000001.SH",
    trade_date: Annotated[str, "交易日期 YYYYMMDD"] = None
) -> str:
    """
    获取大盘指数每日指标（PE/PB/成交量等）
    数据源: Tushare index_dailybasic
    """
    pass

@tool
def get_market_overview(
    trade_date: Annotated[str, "交易日期 YYYYMMDD"]
) -> str:
    """
    获取市场整体概览（涨跌家数、成交量、涨停跌停等）
    数据源: Tushare daily_info
    """
    pass

@tool
def get_index_weight(
    index_code: Annotated[str, "指数代码"] = "000300.SH",
    trade_date: Annotated[str, "交易日期 YYYYMMDD"] = None
) -> str:
    """
    获取指数成分股及权重
    数据源: Tushare index_weight
    """
    pass
```

## 三、数据获取策略

采用**混合策略**平衡性能和数据新鲜度：

### 3.1 数据分类与缓存策略

| 数据类型 | 更新频率 | 获取策略 | 缓存位置 | 缓存有效期 |
|---------|---------|---------|---------|-----------|
| 板块列表 | 月度 | 定期同步 | SQLite/JSON | 7天 |
| 成分股映射 | 周度 | 定期同步 | SQLite/JSON | 1天 |
| 板块日线行情 | 日度 | 按需获取+缓存 | 内存/文件 | 当日有效 |
| 个股日线行情 | 日度 | 按需获取+缓存 | 内存/文件 | 当日有效 |
| 资金流向 | 日度 | 按需获取+缓存 | 内存/文件 | 当日有效 |
| 实时行情 | 实时 | 直接调用API | 不缓存 | - |

### 3.2 缓存实现

```python
# 文件: core/tools/cache.py

class DataCache:
    """数据缓存管理器"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self.memory_cache = {}  # 内存缓存

    def get(self, key: str, max_age_hours: int = 24) -> Optional[Any]:
        """获取缓存，检查是否过期"""
        # 1. 先查内存缓存
        # 2. 再查文件缓存
        # 3. 检查时间戳是否过期
        pass

    def set(self, key: str, data: Any) -> None:
        """设置缓存"""
        # 1. 写入内存缓存
        # 2. 持久化到文件（JSON/pickle）
        pass

# 使用示例
cache = DataCache()

def get_sector_list_cached():
    key = "sector_list"
    data = cache.get(key, max_age_hours=168)  # 7天
    if data is None:
        data = pro.ths_index(type='I')
        cache.set(key, data)
    return data
```

### 3.3 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent 工具调用                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    缓存层 (DataCache)                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  内存缓存   │ → │  文件缓存   │ → │  数据源API  │     │
│  │ (最快)     │    │ (次快)     │    │ (最慢)     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据源层                                   │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │    Tushare Pro      │    │     AKShare         │        │
│  │    (主数据源)        │    │    (备用数据源)      │        │
│  └─────────────────────┘    └─────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 四、核心功能实现原理

### 4.1 分析目标股票所属行业的整体表现

**原理**: 获取股票所属行业/板块，分析该板块整体的涨跌幅、成交量、换手率等指标。

**数据需求**:
```python
# Tushare API
pro.ths_member(con_code=ticker)        # 反查个股所属板块
pro.ths_daily(ts_code=sector_code)     # 板块日线行情
pro.sw_daily(ts_code=sw_code)          # 申万行业指数行情（更权威）
```

**实现逻辑**:
```python
def analyze_sector_performance(ticker: str, trade_date: str):
    # 1. 查找个股所属板块（缓存1天）
    sectors = get_stock_sectors_cached(ticker)

    # 2. 获取板块近20日行情（缓存当日）
    sector_data = get_sector_daily_cached(sectors[0].ts_code, days=20)

    # 3. 获取同期大盘数据作为基准
    index_data = get_index_daily_cached('000001.SH', days=20)

    # 4. 计算指标
    metrics = {
        '累计涨跌幅': calc_cumulative_return(sector_data),
        '相对强弱': calc_relative_strength(sector_data, index_data),  # 板块涨幅 - 大盘涨幅
        '量比': calc_volume_ratio(sector_data),
        '换手率趋势': calc_turnover_trend(sector_data),
    }

    # 5. 评估板块状态
    if metrics['相对强弱'] > 2:
        status = "强势板块（明显跑赢大盘）"
    elif metrics['相对强弱'] < -2:
        status = "弱势板块（明显跑输大盘）"
    else:
        status = "震荡板块（与大盘同步）"

    return {'metrics': metrics, 'status': status}
```

### 4.2 识别行业/板块轮动趋势

**原理**: 分析多个板块的相对强弱变化，通过动量排名变化识别资金流向。

**数据需求**:
```python
pro.ths_index(type='I')    # 获取所有行业板块列表（缓存7天）
pro.ths_daily()            # 批量获取板块行情（缓存当日）
```

**实现逻辑**:
```python
def identify_sector_rotation(trade_date: str):
    # 1. 获取所有行业板块（缓存）
    sectors = get_sector_list_cached(type='I')

    # 2. 计算每个板块多周期涨幅
    sector_returns = {}
    for sector in sectors:
        data = get_sector_daily_cached(sector.ts_code, days=20)
        sector_returns[sector.name] = {
            '5日涨幅': calc_return(data, 5),
            '10日涨幅': calc_return(data, 10),
            '20日涨幅': calc_return(data, 20),
        }

    # 3. 计算动量得分和排名
    # 动量得分 = 0.5×5日排名 + 0.3×10日排名 + 0.2×20日排名
    for name, returns in sector_returns.items():
        sector_returns[name]['动量得分'] = (
            0.5 * rank(returns['5日涨幅']) +
            0.3 * rank(returns['10日涨幅']) +
            0.2 * rank(returns['20日涨幅'])
        )

    # 4. 对比上周排名，识别轮动方向
    # 排名上升 → 资金流入; 排名下降 → 资金流出

    # 5. 判断市场风格
    top_sectors = get_top_n(sector_returns, '动量得分', 5)
    if is_defensive(top_sectors):  # 消费、医药、公用事业
        style = "防御风格（市场避险）"
    elif is_offensive(top_sectors):  # 科技、券商、有色
        style = "进攻风格（市场做多）"
    elif is_cyclical(top_sectors):  # 煤炭、钢铁、化工
        style = "周期风格（经济复苏预期）"

    return {'rotation': sector_returns, 'style': style}
```

### 4.3 对比同业竞争对手表现

**原理**: 将目标股票与同行业其他股票横向对比，评估其在行业中的相对位置。

**数据需求**:
```python
pro.ths_member(ts_code=sector_code)  # 获取板块成分股（缓存1天）
pro.daily(ts_code, trade_date)        # 个股日线行情
pro.daily_basic(ts_code, trade_date)  # 估值指标（PE、PB、市值）
pro.moneyflow(ts_code, trade_date)    # 个股资金流向
```

**实现逻辑**:
```python
def compare_with_peers(ticker: str, trade_date: str):
    # 1. 获取同板块股票（缓存）
    sector = get_stock_main_sector(ticker)
    peers = get_sector_members_cached(sector.ts_code)

    # 2. 批量获取对比数据（缓存当日）
    comparison = []
    for peer in peers[:50]:  # 限制数量，避免API超限
        data = {
            'code': peer.code,
            'name': peer.name,
            # 行情
            'pct_change': get_daily_return(peer, trade_date),
            'volume_ratio': get_volume_ratio(peer, trade_date),
            # 估值
            'pe': get_pe(peer, trade_date),
            'pb': get_pb(peer, trade_date),
            'market_cap': get_market_cap(peer, trade_date),
            # 资金
            'net_inflow': get_net_inflow(peer, trade_date),
        }
        comparison.append(data)

    # 3. 计算目标股票的排名和分位
    target = next(c for c in comparison if c['code'] == ticker)
    rankings = {
        '涨跌幅排名': f"{rank_of(target, 'pct_change')}/{len(comparison)}",
        'PE分位': f"{percentile_of(target, 'pe'):.0%}",
        '资金流入排名': f"{rank_of(target, 'net_inflow')}/{len(comparison)}",
    }

    # 4. 生成结论
    conclusions = []
    if rank_of(target, 'pct_change') <= len(comparison) * 0.2:
        conclusions.append("今日表现跑赢行业80%个股")
    if percentile_of(target, 'pe') < 0.3:
        conclusions.append("估值处于行业较低水平")
    if rank_of(target, 'net_inflow') <= 5:
        conclusions.append("资金关注度高，为板块热门股")

    return {'rankings': rankings, 'conclusions': conclusions, 'peers': comparison[:10]}
```

**对比维度表**:
| 维度 | 指标 | 数据来源 | 说明 |
|------|------|----------|------|
| 股价表现 | 日/周/月涨跌幅 | daily | 相对强弱 |
| 成交活跃 | 换手率、量比 | daily | 市场关注度 |
| 估值水平 | PE、PB、PS | daily_basic | 相对贵贱 |
| 资金关注 | 主力净流入 | moneyflow | 主力态度 |
| 市值规模 | 总市值、流通市值 | daily_basic | 股票体量 |

### 4.4 分析资金流向和市场热点

**原理**: 通过分析主力资金（大单）的流入流出，判断板块热度和持续性。

**数据需求**:
```python
pro.moneyflow_ths(trade_date)     # 板块资金流向（缓存当日）
pro.moneyflow(trade_date)         # 个股资金流向（缓存当日）
```

**资金分类**:
```
主力资金 = 特大单（>100万）+ 大单（20-100万）
散户资金 = 中单（4-20万）+ 小单（<4万）
净流入 = 主动买入金额 - 主动卖出金额
资金强度 = 净流入 / 成交额
```

**实现逻辑**:
```python
def analyze_fund_flow(trade_date: str, sector_code: str = None):
    # 1. 获取板块资金流向排名（缓存当日）
    sector_flow = get_sector_moneyflow_cached(trade_date)

    # 2. 计算净流入和排名
    for sector in sector_flow:
        sector['净流入'] = sector.buy_lg_amount - sector.sell_lg_amount
        sector['资金强度'] = sector['净流入'] / sector.total_amount

    # 3. 识别热点
    hot_sectors = [s for s in sector_flow if s['净流入'] > 0][:10]
    cold_sectors = [s for s in sector_flow if s['净流入'] < 0][-10:]

    # 4. 如果指定板块，分析板块内龙头
    if sector_code:
        members = get_sector_members_cached(sector_code)
        stock_flow = get_stock_moneyflow_cached(trade_date)

        # 筛选板块内个股
        sector_stocks = [s for s in stock_flow if s.ts_code in members]
        leaders = sorted(sector_stocks, key=lambda x: x.net_mf_amount, reverse=True)[:5]

    # 5. 判断热点持续性
    # 获取近5日数据，判断是短线炒作还是持续流入
    recent_flow = get_sector_flow_history(sector_code, days=5)
    consecutive_inflow = sum(1 for d in recent_flow if d['净流入'] > 0)

    if consecutive_inflow >= 3:
        heat_type = "持续热点（主力建仓）"
    elif consecutive_inflow == 1 and recent_flow[0]['净流入'] > threshold:
        heat_type = "短线炒作（谨慎追高）"
    else:
        heat_type = "普通板块"

    return {
        'hot_sectors': hot_sectors,
        'cold_sectors': cold_sectors,
        'leaders': leaders if sector_code else None,
        'heat_type': heat_type
    }
```

## 五、Agent 实现设计

Agent 实现在 `core/agents/adapters/` 目录下，继承 `core/agents/base.py` 基类。

### 5.1 行业/板块分析师 (SectorAnalystAgent)

**文件**: `core/agents/adapters/sector_analyst.py`

```python
from ..base import BaseAgent
from ..config import BUILTIN_AGENTS
from ..registry import register_agent

@register_agent
class SectorAnalystAgent(BaseAgent):
    """行业/板块分析师"""

    metadata = BUILTIN_AGENTS["sector_analyst"]

    def _setup_tools(self) -> None:
        """注册板块分析工具"""
        from core.tools.sector_tools import (
            get_sector_list,
            get_sector_performance,
            get_sector_detail,
            get_stock_sector_info,
            get_sector_fund_flow,
        )
        # 注册工具...

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行板块分析"""
        # 1. 获取个股所属板块
        # 2. 分析板块表现（调用 analyze_sector_performance）
        # 3. 识别轮动趋势（调用 identify_sector_rotation）
        # 4. 对比同业（调用 compare_with_peers）
        # 5. 分析资金流向（调用 analyze_fund_flow）
        # 6. 返回综合分析报告
        pass
```

**职责**:
- 分析目标股票所属行业的整体表现
- 识别行业/板块轮动趋势
- 对比同业竞争对手表现
- 分析资金流向和市场热点

**输入/输出**:
- 输入: `{ ticker, trade_date, messages }`
- 输出: `{ sector_report, messages }`

### 5.2 大盘/指数分析师 (IndexAnalystAgent)

**文件**: `core/agents/adapters/index_analyst.py`

```python
from ..base import BaseAgent
from ..config import BUILTIN_AGENTS
from ..registry import register_agent

@register_agent
class IndexAnalystAgent(BaseAgent):
    """大盘/指数分析师"""

    metadata = BUILTIN_AGENTS["index_analyst"]

    def _setup_tools(self) -> None:
        """注册指数分析工具"""
        from core.tools.index_tools import (
            get_index_list,
            get_index_daily,
            get_index_indicators,
            get_market_overview,
            get_index_weight,
        )
        # 注册工具...

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行大盘分析"""
        # 1. 获取主要指数数据（调用 analyze_index_trend）
        # 2. 分析市场宽度（调用 analyze_market_breadth）
        # 3. 评估市场环境（调用 assess_market_environment）
        # 4. 识别市场周期（调用 identify_market_cycle）
        # 5. 返回综合分析报告
        pass
```

**职责**:
- 分析大盘整体走势和市场环境
- 评估系统性风险水平
- 分析市场宽度和资金面
- 识别市场周期阶段

**输入/输出**:
- 输入: `{ ticker, trade_date, messages }`
- 输出: `{ index_report, messages }`

## 六、IndexAnalyst 核心功能实现原理

### 6.1 分析主要指数走势

**原理**: 分析上证指数、深证成指、创业板指等主要指数的技术形态和趋势。

**数据需求**:
```python
pro.index_daily(ts_code)           # 指数日线行情（缓存当日）
pro.index_dailybasic(ts_code)      # 指数估值指标（缓存当日）
```

**实现逻辑**:
```python
def analyze_index_trend(trade_date: str):
    # 主要指数列表
    indices = ['000001.SH', '399001.SZ', '399006.SZ', '000300.SH', '000905.SH']

    results = {}
    for index_code in indices:
        # 获取近60日数据（缓存当日）
        data = get_index_daily_cached(index_code, days=60)

        # 计算技术指标
        metrics = {
            '当日涨跌幅': data.iloc[-1].pct_chg,
            '5日涨跌幅': calc_return(data, 5),
            '20日涨跌幅': calc_return(data, 20),
            'MA5': data['close'].rolling(5).mean().iloc[-1],
            'MA20': data['close'].rolling(20).mean().iloc[-1],
            'MA60': data['close'].rolling(60).mean().iloc[-1],
            '成交量变化': data.iloc[-1].vol / data['vol'].rolling(20).mean().iloc[-1],
        }

        # 判断趋势
        close = data.iloc[-1].close
        if close > metrics['MA20'] > metrics['MA60']:
            trend = "上涨趋势"
        elif close < metrics['MA20'] < metrics['MA60']:
            trend = "下跌趋势"
        else:
            trend = "震荡整理"

        results[index_code] = {'metrics': metrics, 'trend': trend}

    return results
```

### 6.2 分析市场宽度

**原理**: 通过涨跌家数、涨停跌停数量等指标，判断行情是否具有广泛性。

**数据需求**:
```python
pro.daily_info(trade_date)    # 市场每日统计（缓存当日）
# 返回: 涨跌家数、涨停跌停数、成交额等
```

**实现逻辑**:
```python
def analyze_market_breadth(trade_date: str):
    # 获取市场统计数据
    daily_info = get_daily_info_cached(trade_date)

    # 计算宽度指标
    metrics = {
        '上涨家数': daily_info.up_count,
        '下跌家数': daily_info.down_count,
        '涨跌比': daily_info.up_count / max(daily_info.down_count, 1),
        '涨停家数': daily_info.limit_up_count,
        '跌停家数': daily_info.limit_down_count,
        '成交额(亿)': daily_info.amount / 100000000,
    }

    # 判断市场宽度
    ratio = metrics['涨跌比']
    if ratio > 2:
        breadth = "普涨格局（做多情绪高涨）"
    elif ratio > 1:
        breadth = "多头占优（温和上涨）"
    elif ratio > 0.5:
        breadth = "空头占优（温和下跌）"
    else:
        breadth = "普跌格局（恐慌情绪蔓延）"

    # 成交额判断
    avg_amount = get_recent_avg_amount(20)  # 近20日平均成交额
    if metrics['成交额(亿)'] > avg_amount * 1.3:
        volume_status = "放量（资金活跃）"
    elif metrics['成交额(亿)'] < avg_amount * 0.7:
        volume_status = "缩量（观望情绪）"
    else:
        volume_status = "量能正常"

    return {'metrics': metrics, 'breadth': breadth, 'volume': volume_status}
```

### 6.3 评估市场环境

**原理**: 综合指数估值、成交量、波动率等因素，评估当前市场的风险水平。

**数据需求**:
```python
pro.index_dailybasic(ts_code)    # 指数每日指标（PE、PB、换手率等）
```

**实现逻辑**:
```python
def assess_market_environment(trade_date: str):
    # 获取上证指数估值数据
    valuation = get_index_valuation_cached('000001.SH', trade_date)

    # 获取历史估值分位（需要历史数据）
    hist_pe = get_index_pe_history('000001.SH', years=5)
    current_pe = valuation.pe
    pe_percentile = percentile_rank(current_pe, hist_pe)

    # 风险评估
    risk_factors = []

    # 估值风险
    if pe_percentile > 80:
        risk_factors.append("估值偏高（PE处于历史80%分位以上）")
    elif pe_percentile < 20:
        risk_factors.append("估值偏低（PE处于历史20%分位以下）")

    # 成交量风险
    volume_ratio = get_volume_ratio()
    if volume_ratio > 2:
        risk_factors.append("成交异常放大（可能见顶）")
    elif volume_ratio < 0.5:
        risk_factors.append("成交极度萎缩（流动性风险）")

    # 综合评估
    if len(risk_factors) >= 2:
        risk_level = "高风险"
    elif len(risk_factors) == 1:
        risk_level = "中等风险"
    else:
        risk_level = "低风险"

    return {
        'pe': current_pe,
        'pe_percentile': pe_percentile,
        'risk_level': risk_level,
        'risk_factors': risk_factors
    }
```

### 6.4 识别市场周期阶段

**原理**: 根据技术指标和市场特征，判断当前处于牛市、熊市还是震荡市。

**实现逻辑**:
```python
def identify_market_cycle(trade_date: str):
    # 获取上证指数数据
    data = get_index_daily_cached('000001.SH', days=250)  # 一年

    # 计算周期指标
    current = data.iloc[-1].close
    ma60 = data['close'].rolling(60).mean().iloc[-1]
    ma250 = data['close'].rolling(250).mean().iloc[-1]

    # 计算从高点/低点的回撤/反弹
    high_250 = data['high'].max()
    low_250 = data['low'].min()
    drawdown = (high_250 - current) / high_250
    rebound = (current - low_250) / low_250

    # 判断周期
    if current > ma60 > ma250 and drawdown < 0.1:
        cycle = "牛市（上涨趋势明确）"
        strategy = "持股为主，逢低加仓"
    elif current < ma60 < ma250 and rebound < 0.1:
        cycle = "熊市（下跌趋势明确）"
        strategy = "空仓观望，等待企稳"
    else:
        cycle = "震荡市（方向不明）"
        strategy = "高抛低吸，控制仓位"

    return {
        'cycle': cycle,
        'strategy': strategy,
        'drawdown': f"{drawdown:.1%}",
        'rebound': f"{rebound:.1%}"
    }

## 七、实现步骤

### 阶段 0: 插件架构实现 ✅ 已完成

**目标**：建立可扩展的 Agent 插件架构，新增 Agent 无需修改引擎源码。

**已完成的工作**：

1. **创建 AnalystRegistry** `core/agents/analyst_registry.py` ✅
   - 分析师专用注册表
   - 支持 agent_class 和 factory 两种注册方式
   - 提供 `get_analysts_ordered()` 按执行顺序获取分析师
   - 提供 `get_output_fields()` 获取所有输出字段映射

2. **创建 ReportAggregator** `core/utils/report_aggregator.py` ✅
   - 动态从 state 获取所有 `*_report` 字段
   - 支持按执行顺序排列
   - 提供 `to_text()` 和 `to_dict()` 转换方法

3. **扩展 AgentMetadata** `core/agents/config.py` ✅
   - 新增 `requires_tools` 字段（是否需要工具调用）
   - 新增 `output_field` 字段（输出状态字段名）
   - 新增 `report_label` 字段（报告标签）
   - 新增 `node_name` 字段（工作流节点名称）
   - 新增 `execution_order` 字段（执行顺序）

4. **修改 setup.py 动态加载** `tradingagents/graph/setup.py` ✅
   - 新增 `_get_extension_registry()` 方法
   - 新增 `_load_extension_analysts()` 方法
   - 自动处理 `requires_tools=False` 的分析师

5. **修改下游 Agent 使用 ReportAggregator** ✅
   - `tradingagents/agents/researchers/bull_researcher.py`
   - `tradingagents/agents/researchers/bear_researcher.py`
   - `tradingagents/agents/managers/research_manager.py`

6. **编写插件架构测试** `tests/unit/agents/test_plugin_architecture.py` ✅
   - 9 个测试用例全部通过

### 阶段 1: Tushare 数据层扩展 (预计 1 天) 🔄 进行中

扩展现有 Tushare 适配器，添加板块和指数相关方法。

**文件**: `tradingagents/dataflows/providers/china/tushare.py`

```python
# 新增方法
async def get_index_daily(self, ts_code: str, start_date: str = None, end_date: str = None):
    """获取指数日线"""
    pass

async def get_index_dailybasic(self, ts_code: str, trade_date: str = None):
    """获取指数每日指标"""
    pass

async def get_ths_index(self, type: str = 'N'):
    """获取同花顺板块列表"""
    pass

async def get_ths_daily(self, ts_code: str, trade_date: str = None):
    """获取板块行情"""
    pass

async def get_daily_info(self, trade_date: str):
    """获取市场每日统计"""
    pass
```

### 阶段 2: 工具函数实现 (预计 1-2 天) 🔄 进行中

1. **创建板块数据工具** `core/tools/sector_tools.py`
   - [ ] get_sector_list - 板块列表
   - [ ] get_sector_performance - 板块排名
   - [ ] get_sector_detail - 板块详情
   - [ ] get_stock_sector_info - 个股所属板块
   - [ ] get_sector_fund_flow - 资金流向

2. **创建指数数据工具** `core/tools/index_tools.py`
   - [ ] get_index_list - 指数列表
   - [ ] get_index_daily - 指数日线
   - [ ] get_index_indicators - 指数指标
   - [ ] get_market_overview - 市场概览
   - [ ] get_index_weight - 指数权重

### 阶段 3: Agent 实现 ✅ 已完成

1. **创建行业分析师** `core/agents/adapters/sector_analyst.py` ✅
   - [x] 继承 BaseAgent
   - [x] 定义系统提示词
   - [x] 实现 execute() 方法（无工具调用模式）
   - [x] 注册到 AnalystRegistry

2. **创建指数分析师** `core/agents/adapters/index_analyst.py` ✅
   - [x] 继承 BaseAgent
   - [x] 定义系统提示词
   - [x] 实现 execute() 方法（无工具调用模式）
   - [x] 注册到 AnalystRegistry

### 阶段 4: 集成和测试 ✅ 已完成

1. **更新配置** ✅
   - [x] `core/agents/config.py` 中 BUILTIN_AGENTS 已包含两个 Agent
   - [x] AgentMetadata 扩展工作流字段

2. **工作流集成** ✅
   - [x] `tradingagents/graph/setup.py` 动态加载扩展分析师
   - [x] 自动处理无工具调用的分析师

3. **编写测试** ✅
   - [x] `tests/unit/agents/test_sector_analyst.py` - 6 个测试通过
   - [x] `tests/unit/agents/test_index_analyst.py` - 7 个测试通过
   - [x] `tests/unit/agents/test_plugin_architecture.py` - 9 个测试通过

## 八、系统提示词设计

### 8.1 行业/板块分析师提示词

```
你是一位专业的行业分析师，专门分析股票所属行业和板块的情况。

你的分析职责包括:
1. 识别目标股票所属的行业和概念板块
2. 分析该行业近期整体表现（涨跌幅、成交量、换手率）
3. 对比同行业其他公司的表现
4. 分析行业资金流向和市场热度
5. 评估行业周期位置和未来趋势

分析时请注意:
- 行业龙头的表现往往预示行业趋势
- 板块轮动规律对投资决策有重要参考价值
- 资金流向反映市场对行业的偏好
- 概念炒作需要辨别真伪

请使用提供的工具获取数据，生成全面的行业分析报告。
```

### 8.2 大盘/指数分析师提示词

```
你是一位专业的大盘分析师，专门分析市场整体环境和系统性风险。

你的分析职责包括:
1. 分析主要指数（上证、深证、创业板等）的走势
2. 评估市场宽度（涨跌比例、涨停跌停家数等）
3. 分析成交量和资金面状况
4. 评估市场情绪和风险偏好
5. 判断市场周期阶段（牛市、熊市、震荡市）

分析时请注意:
- 大盘走势对个股有系统性影响
- 成交量是判断趋势的重要依据
- 市场宽度反映行情的健康程度
- 极端情绪往往是反转信号

请使用提供的工具获取数据，生成全面的大盘分析报告。
```

## 九、工具元数据配置

已在 `core/agents/config.py` 中定义:
- sector_analyst (行业/板块分析师)
- index_analyst (大盘/指数分析师)

已在 `core/tools/config.py` 中定义:
- get_sector_performance
- get_industry_comparison
- get_index_data
- get_market_overview

## 十、依赖和风险

### 依赖项
- Tushare Pro >= 1.4.0（**主数据源**，需 6000+ 积分获取板块数据）
- AKShare >= 1.10.0（备用数据源）

### Tushare 积分要求
| API | 所需积分 |
|-----|---------|
| index_daily | 基础 |
| index_dailybasic | 2000 |
| ths_index | 6000 |
| ths_daily | 6000 |
| ths_member | 6000 |
| moneyflow_ths | 2000 |
| daily_info | 2000 |

### 风险点
1. Tushare 积分限制（板块数据需 6000 积分）
2. 数据延迟（非实时）
3. 板块分类标准差异（申万/同花顺/东财）

### 缓解措施
- 实现 Tushare -> AKShare 多数据源降级机制
- 添加请求频率控制和缓存
- 默认使用申万行业分类（更权威）

## 十一、目录结构

```
core/
├── agents/
│   ├── adapters/
│   │   ├── sector_analyst.py    # 新增：行业/板块分析师
│   │   ├── index_analyst.py     # 新增：大盘/指数分析师
│   │   └── ...
│   ├── base.py
│   ├── config.py                # 已有 sector_analyst, index_analyst 定义
│   └── registry.py
├── tools/
│   ├── sector_tools.py          # 新增：板块工具
│   ├── index_tools.py           # 新增：指数工具
│   ├── cache.py                 # 新增：数据缓存管理器
│   └── config.py                # 已有工具元数据
└── ...

tradingagents/
├── dataflows/
│   └── providers/
│       └── china/
│           └── tushare.py       # 扩展：添加板块/指数 API
└── ...

data/
├── cache/
│   ├── sector_list.json         # 板块列表缓存
│   ├── sector_members/          # 板块成分股缓存
│   ├── index_daily/             # 指数日线缓存
│   └── market_stats/            # 市场统计缓存
└── ...
```

## 十二、基本面分析师职责边界与数据扩展

### 12.1 基本面分析 vs 板块分析的职责划分

两个分析师需要明确职责边界，避免重复分析：

| 分析师 | 核心问题 | 关注维度 | 分析目标 |
|--------|---------|----------|---------|
| **FundamentalsAnalyst** | 公司**值不值**得投资？ | 公司质地 | 个股估值、财务健康 |
| **SectorAnalyst** | 板块**热不热**？ | 板块动量 | 资金流向、轮动趋势 |

### 12.2 基本面分析师职责（扩展后）

```
FundamentalsAnalyst（基本面分析师）- 聚焦"公司质地"
├── 1️⃣ 公司财务分析（现有功能）
│   ├── 盈利能力（ROE、毛利率、净利率）
│   ├── 成长性（营收增速、利润增速）
│   ├── 财务健康（资产负债率、现金流）
│   └── 分红能力（股息率、分红记录）
│
├── 2️⃣ 估值分析（现有功能 + 行业对比）
│   ├── 绝对估值（PE、PB、PS、PEG）
│   ├── 🆕 行业PE/PB分位数（判断贵不贵）
│   └── 🆕 历史估值分位数（当前在历史中的位置）
│
└── 3️⃣ 🆕 简单同业对比（新增功能）
    ├── 获取目标股票所属行业
    ├── 获取同行业TOP10股票财务指标
    ├── 关键指标同业排名（ROE、增速、估值）
    └── 生成同业对比分析报告
```

### 12.3 板块分析师职责

```
SectorAnalyst（板块分析师）- 聚焦"板块动量"
├── 1️⃣ 板块整体表现
│   ├── 板块涨跌幅排名
│   ├── 板块成交量变化
│   └── 板块换手率
│
├── 2️⃣ 板块轮动趋势
│   ├── 资金流入/流出方向
│   ├── 近期热点板块识别
│   └── 轮动周期判断
│
└── 3️⃣ 板块内部结构
    ├── 龙头股识别
    ├── 板块分化程度
    └── 目标股在板块中的位置（涨幅排名）
```

### 12.4 基本面分析师数据扩展需求

#### 12.4.1 新增 Tushare API 需求

| API 名称 | 用途 | 返回字段 | 积分要求 |
|----------|------|---------|---------|
| `stock_basic` | 获取个股所属行业 | `industry` | 免费 |
| `daily_basic` | 行业内股票估值数据 | `pe`, `pb`, `ps`, `total_mv` | 120 |
| `fina_indicator` | 行业内股票财务指标 | `roe`, `roa`, `grossprofit_margin` | 120 |

#### 12.4.2 新增工具函数设计

**文件**: `core/tools/fundamentals_tools.py`

```python
@tool(
    name="get_industry_peers_fundamentals",
    description="获取同行业公司的关键财务指标，用于同业对比分析"
)
def get_industry_peers_fundamentals(
    ticker: str,
    trade_date: str,
    top_n: int = 10
) -> str:
    """
    获取同行业公司的财务指标对比数据

    Args:
        ticker: 目标股票代码
        trade_date: 交易日期
        top_n: 返回同业公司数量（按市值排序）

    Returns:
        同业对比报告（包含PE/PB/ROE排名）
    """
    # 实现步骤：
    # 1. 获取目标股票所属行业
    # 2. 获取该行业所有股票列表
    # 3. 按市值排序取TOP N
    # 4. 批量获取财务指标
    # 5. 计算目标股票在行业中的排名
    # 6. 生成对比报告
```

#### 12.4.3 数据获取流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     同业对比数据获取流程                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤1: 获取目标股票行业                                                  │
│  API: stock_basic(ts_code=ticker) → industry 字段                        │
│  示例: 000001.SZ → "银行"                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤2: 获取同行业股票列表                                                │
│  API: stock_basic(industry="银行") → 所有银行股列表                       │
│  返回: [601398, 601939, 601288, 600036, 000001, ...]                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤3: 获取估值数据                                                      │
│  API: daily_basic(trade_date=xxx) → 筛选同行业                           │
│  返回: pe, pb, ps, total_mv (市值)                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤4: 获取财务指标                                                      │
│  API: fina_indicator(ts_code=xxx) → 批量获取                             │
│  返回: roe, roa, grossprofit_margin, netprofit_yoy                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤5: 计算排名和分位数                                                  │
│  - PE排名: 目标股在行业中的PE排名 (越低越好)                              │
│  - ROE排名: 目标股在行业中的ROE排名 (越高越好)                            │
│  - 市值排名: 目标股在行业中的市值排名                                     │
│  - 综合评分: 基于多维度的综合排名                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  步骤6: 生成同业对比报告                                                  │
│                                                                          │
│  📊 招商银行(600036) 同业对比分析报告                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  所属行业: 银行（共42家上市公司）                                          │
│                                                                          │
│  📈 估值对比:                                                             │
│  | 指标    | 招商银行 | 行业平均 | 行业中位数 | 排名  |                   │
│  |---------|---------|---------|-----------|-------|                   │
│  | PE(TTM) | 6.5     | 5.2     | 4.8       | 35/42 |                   │
│  | PB      | 0.95    | 0.58    | 0.52      | 40/42 |                   │
│                                                                          │
│  📊 盈利能力对比:                                                          │
│  | 指标     | 招商银行 | 行业平均 | 行业中位数 | 排名  |                  │
│  |----------|---------|---------|-----------|-------|                  │
│  | ROE      | 15.8%   | 10.2%   | 9.5%      | 3/42  |                  │
│  | 净利增速 | 12.5%   | 5.8%    | 4.2%      | 5/42  |                  │
│                                                                          │
│  🏆 综合评价:                                                             │
│  - 估值水平: 偏高（PE、PB均高于行业平均）                                  │
│  - 盈利能力: 优秀（ROE行业第3，增速行业第5）                               │
│  - 结论: 优质银行股，但估值溢价较高                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.5 缓存策略

同业对比数据缓存：

| 数据类型 | 缓存时间 | 说明 |
|---------|---------|------|
| 行业分类映射 | 7天 | 行业归属很少变化 |
| 行业内股票列表 | 1天 | 新股上市可能改变 |
| 估值数据 (PE/PB) | 当日 | 每日变化 |
| 财务指标 (ROE等) | 季度 | 按财报周期更新 |

### 12.6 基本面分析师提示词调整

需要在基本面分析师的提示词中增加同业对比的要求：

```python
# fundamentals_analyst.py 中的提示词扩展

system_prompt = f"""你是一位专业的股票基本面分析师。

任务：分析{company_name}（股票代码：{ticker}）的基本面

🔴 分析要求：

1️⃣ **公司财务分析**
   - 分析盈利能力（ROE、毛利率、净利率）
   - 分析成长性（营收增速、利润增速）
   - 分析财务健康（资产负债率、现金流）

2️⃣ **估值分析**
   - 计算当前PE、PB、PS、PEG
   - 与历史估值对比（是否处于高估/低估区间）
   - 🆕 与行业估值对比（PE/PB行业分位数）

3️⃣ **🆕 同业对比分析**
   - 调用 get_industry_peers_fundamentals 获取同业数据
   - 分析目标股票在行业中的位置
   - 对比关键指标（ROE、增速、估值）与行业龙头的差距

📊 输出格式：
- 公司基本面评级：优秀/良好/一般/较差
- 估值水平：低估/合理/高估
- 行业地位：龙头/第二梯队/普通
- 投资建议：买入/持有/卖出
"""
```

## 十三、与个股分析流程的集成

### 13.1 现有工作流分析

当前个股分析流程：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AgentState (状态管理)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  company_of_interest    # 股票代码                                        │
│  trade_date             # 交易日期                                        │
│                                                                          │
│  # 分析师报告（第一阶段）                                                   │
│  market_report          # 市场分析师报告（技术分析）                        │
│  sentiment_report       # 社交媒体分析师报告                               │
│  news_report            # 新闻分析师报告                                   │
│  fundamentals_report    # 基本面分析师报告                                 │
│                                                                          │
│  # 研究团队（第二阶段）                                                    │
│  investment_debate_state  # 牛熊辩论状态                                  │
│  investment_plan          # 投资计划                                      │
│                                                                          │
│  # 交易员和风险管理（第三阶段）                                             │
│  trader_investment_plan   # 交易员计划                                    │
│  risk_debate_state        # 风险辩论状态                                  │
│  final_trade_decision     # 最终决策                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.2 集成方案：扩展 AgentState

**方案**: 新增 `sector_report` 和 `index_report` 字段，与现有报告并行。

**修改文件**: `tradingagents/agents/utils/agent_states.py`

```python
class AgentState(MessagesState):
    # 基础信息
    company_of_interest: Annotated[str, "目标股票代码"]
    trade_date: Annotated[str, "交易日期"]

    # 🆕 新增：宏观分析报告
    sector_report: Annotated[str, "行业/板块分析报告"]    # 新增
    index_report: Annotated[str, "大盘/指数分析报告"]     # 新增

    # 现有分析师报告
    market_report: Annotated[str, "市场分析报告（技术分析）"]
    sentiment_report: Annotated[str, "社交媒体情绪报告"]
    news_report: Annotated[str, "新闻分析报告"]
    fundamentals_report: Annotated[str, "基本面分析报告"]

    # ... 其他字段不变
```

### 13.3 工作流调整

**新的分析流程**:

```
┌───────────────────────────────────────────────────────────────────────┐
│                         第一阶段：数据采集                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ 🌐 大盘分析 │  │ 🏭 板块分析 │  │ 📈 技术分析 │  │ 📊 基本面   │  │
│  │ IndexAnalyst│  │SectorAnalyst│  │MarketAnalyst│  │FundAnalyst  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │         │
│         ▼                ▼                ▼                ▼         │
│   index_report    sector_report    market_report    fundamentals     │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      第二阶段：研究员辩论                                │
│                                                                        │
│  输入：6份报告合并为 curr_situation                                     │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ curr_situation = index_report + sector_report +                 │  │
│  │                  market_report + sentiment_report +              │  │
│  │                  news_report + fundamentals_report               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  🐂 看涨研究员 ←──辩论──→ 🐻 看跌研究员                                  │
│                    │                                                   │
│                    ▼                                                   │
│              👔 研究经理                                                │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      第三阶段：交易与风控                                │
│                                                                        │
│  💼 交易员 → ⚠️ 风险团队辩论 → 🎯 风险经理 → 最终决策                    │
└───────────────────────────────────────────────────────────────────────┘
```

### 13.4 下游 Agent 提示词调整

需要调整以下 Agent 的提示词，将 `sector_report` 和 `index_report` 纳入分析：

#### 13.4.1 看涨/看跌研究员 (bull_researcher.py / bear_researcher.py)

**当前代码** (第 90 行):
```python
curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
```

**修改为**:
```python
# 获取新增的报告
index_report = state.get("index_report", "")
sector_report = state.get("sector_report", "")

# 合并所有报告（宏观→微观顺序）
curr_situation = f"""
【宏观环境分析】
{index_report}

【行业/板块分析】
{sector_report}

【个股技术分析】
{market_research_report}

【市场情绪分析】
{sentiment_report}

【相关新闻分析】
{news_report}

【基本面分析】
{fundamentals_report}
"""
```

**修改提示词模板** (第 162-173 行):
```python
prompt = f"""{system_prompt}

可用资源：
【宏观大盘分析】：{index_report}
【行业板块分析】：{sector_report}
【技术市场分析】：{market_research_report}
【社交媒体情绪】：{sentiment_report}
【最新新闻资讯】：{news_report}
【公司基本面】：{fundamentals_report}
辩论对话历史：{history}
最后的对方论点：{current_response}
类似情况的反思：{past_memory_str}

⚠️ 重要：请在分析中考虑宏观环境（大盘走势、市场周期）和行业板块（板块轮动、同业对比）的影响。
"""
```

#### 13.4.2 研究经理 (research_manager.py)

**当前代码** (第 22 行):
```python
curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
```

**修改为**:
```python
index_report = state.get("index_report", "")
sector_report = state.get("sector_report", "")

curr_situation = f"{index_report}\n\n{sector_report}\n\n{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
```

**修改提示词** (第 94-103 行):
```python
prompt = f"""{system_prompt}

过去的反思和经验教训：
{past_memory_str}

综合分析报告：
【大盘/指数分析】：{index_report}
【行业/板块分析】：{sector_report}
【技术市场分析】：{market_research_report}
【情绪分析】：{sentiment_report}
【新闻分析】：{news_report}
【基本面分析】：{fundamentals_report}

辩论历史：
{history}

⚠️ 在做出投资决策时，请综合考虑：
1. 大盘环境是否有利（牛市/熊市/震荡）
2. 所属板块是否处于轮动热点
3. 个股基本面和技术面信号
"""
```

#### 13.4.3 交易员 (trader.py)

**当前代码** (第 40 行):
```python
curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
```

**修改为**:
```python
index_report = state.get("index_report", "")
sector_report = state.get("sector_report", "")

curr_situation = f"{index_report}\n\n{sector_report}\n\n{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
```

### 13.5 提示词模板系统更新

需要更新 MongoDB 中的提示词模板，增加对 `index_report` 和 `sector_report` 的引用：

**模板变量扩展**:
```python
template_variables = {
    # 现有变量
    "ticker": ticker,
    "company_name": company_name,
    "currency": currency,
    "market_type": market_info['market_name'],

    # 🆕 新增变量
    "index_report": index_report,
    "sector_report": sector_report,

    # 现有报告
    "market_report": market_research_report,
    "sentiment_report": sentiment_report,
    "news_report": news_report,
    "fundamentals_report": fundamentals_report,
}
```

### 13.6 集成检查清单

1. **AgentState 扩展**
   - [ ] 新增 `sector_report` 字段
   - [ ] 新增 `index_report` 字段

2. **工作流节点注册**
   - [ ] 在 `graph/setup.py` 中添加 SectorAnalyst 节点
   - [ ] 在 `graph/setup.py` 中添加 IndexAnalyst 节点
   - [ ] 配置节点执行顺序（与现有分析师并行）

3. **下游 Agent 调整**
   - [ ] `bull_researcher.py` - 获取并使用新报告
   - [ ] `bear_researcher.py` - 获取并使用新报告
   - [ ] `research_manager.py` - 汇总所有6份报告
   - [ ] `trader.py` - 考虑宏观环境

4. **模板系统更新**
   - [ ] 更新 `template_variables` 传递新报告
   - [ ] 更新 MongoDB 中的提示词模板

## 十四、完整数据流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        输入: ticker + trade_date                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ 🌐 IndexAnalyst   │    │ 🏭 SectorAnalyst  │    │ 现有4个分析师      │
│ 大盘/指数分析      │    │ 行业/板块分析      │    │ (并行执行)         │
├───────────────────┤    ├───────────────────┤    ├───────────────────┤
│ • 指数走势分析     │    │ • 板块表现分析     │    │ • MarketAnalyst   │
│ • 市场宽度分析     │    │ • 板块轮动识别     │    │ • SentimentAnalyst│
│ • 市场环境评估     │    │ • 同业对比分析     │    │ • NewsAnalyst     │
│ • 市场周期识别     │    │ • 资金流向分析     │    │ • FundAnalyst     │
└─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘
          │                        │                        │
          ▼                        ▼                        ▼
    index_report            sector_report           market_report
                                                    sentiment_report
                                                    news_report
                                                    fundamentals_report
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      curr_situation (6份报告合并)                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 宏观层面：index_report (大盘环境) + sector_report (板块轮动)      │   │
│  │ 微观层面：market + sentiment + news + fundamentals (个股分析)    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      🐂🐻 研究员辩论 + 👔 研究经理                         │
│                                                                          │
│  辩论时需考虑：                                                           │
│  • 大盘处于什么周期？（牛市做多、熊市谨慎、震荡高抛低吸）                    │
│  • 板块是否热点？（热点板块个股更易上涨）                                   │
│  • 个股在板块中的位置？（龙头vs跟风）                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      💼 交易员 + ⚠️ 风险团队                              │
│                                                                          │
│  交易决策时需考虑：                                                       │
│  • 系统性风险（大盘风险）                                                  │
│  • 行业风险（板块回调）                                                    │
│  • 个股风险（基本面+技术面）                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           🎯 最终决策                                     │
│                                                                          │
│  综合评估：大盘环境 + 板块热度 + 个股质地 = 投资建议                        │
└─────────────────────────────────────────────────────────────────────────┘
```

