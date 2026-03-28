# 社媒分析师现状与数据源融合方案

本文档用于说明当前 `TradingAgents-CN` 仓库中“社媒分析师”的实际实现状态，以及 A 股后续可落地的数据源融合方案。

## 1. 当前实现现状

### 1.1 前端行为

- 分析页前端在 A 股市场下直接禁用了“社媒分析师”选择。
- 关键位置：
  - `frontend/src/views/Analysis/SingleAnalysis.vue`
  - `frontend/src/constants/analysts.ts`

### 1.2 Graph / Toolkit / Backend 实际调用链

- Graph 将 `social` 分析师节点接入到主分析流程：
  - `tradingagents/graph/setup.py`
  - `tradingagents/graph/trading_graph.py`
- `social_media_analyst` 节点实际只绑定了一个工具：
  - `toolkit.get_stock_sentiment_unified`
  - 关键文件：`tradingagents/agents/analysts/social_media_analyst.py`
- `get_stock_sentiment_unified` 当前按市场分流：
  - A 股 / 港股：返回中文市场情绪模板文本
  - 美股：调用 Reddit 情绪接口
  - 关键文件：`tradingagents/agents/utils/agent_utils.py`

### 1.3 当前是否使用 `social_media_messages`

- 仓库里已经有完整的社媒消息存储与查询 API：
  - `app/services/social_media_service.py`
  - `app/routers/social_media.py`
- 但当前主分析链路没有直接读取 `social_media_messages` 集合。
- 也就是说，现有“社媒分析师”并没有消费这套结构化社媒消息库。

结论：

- `social_media_service` 当前更像“预留的数据落库与查询能力”。
- 主分析流程中的社媒分析，现阶段仍是工具层产出，不是数据库驱动。

## 2. 各市场当前实际状态

### 2.1 A 股

- 前端默认禁用“社媒分析师”。
- 后端 `get_stock_sentiment_unified` 虽有 A 股分支，但当前只是模板占位，不是稳定真实数据。
- 中文情绪相关工具入口：
  - `tradingagents/dataflows/news/chinese_finance.py`
- 其中明显的占位 / 模拟实现包括：
  - `_search_finance_news()` 返回示例数据
  - `_get_stock_forum_sentiment()` 直接返回模拟结构

### 2.2 港股

- 前端没有禁用港股“社媒分析师”。
- 但港股并没有单独的真实社媒数据链路。
- 实际上港股和 A 股在 `get_stock_sentiment_unified` 里走的是同一个“中文市场情绪模板”分支。
- 所以当前港股“社媒分析师”本质上也不是“真实社媒抓取”，而是模板占位。

结论：

- 当前仓库并不存在“港股已经有完整社媒实现、A 股没有”的情况。
- 现状更接近：
  - A 股：前端禁用
  - 港股：前端可选，但后端仍是占位实现

### 2.3 美股

- 美股当前的社媒分析实现最接近“真实数据链路”。
- `get_stock_sentiment_unified` 会走 Reddit 情绪相关工具。
- 关键入口：
  - `tradingagents/agents/utils/agent_utils.py`
  - `tradingagents/dataflows/interface.py`
  - `tradingagents/dataflows/news/reddit.py`

## 3. 新闻与社媒相关的现有真实能力

### 3.1 仓库内已接入、且相对真实的中文市场能力

#### A 股 / 港股新闻

- `get_stock_news_unified` 对 A 股 / 港股会优先尝试中文新闻源，再补 Google 新闻。
- 关键文件：
  - `tradingagents/agents/utils/agent_utils.py`
  - `tradingagents/dataflows/news/realtime_news.py`
  - `tradingagents/dataflows/providers/china/akshare.py`
  - `tradingagents/dataflows/providers/china/tushare.py`
- 注意：
  - 当前 `AKShareProvider.get_stock_news_sync()` 会把 `symbol` 统一 `zfill(6)` 后调用 `stock_news_em`。
  - 这更像 A 股 / 东方财富个股新闻接口的适配方式，不能把它视为“港股新闻已经有稳定专用实现”。
  - 另外，`app/routers/stocks.py` 的 `/{code}/news` 接口对港股目前仍是 `TODO` 空返回。

#### A 股新闻同步

- 已有新闻同步链路，可写入数据库：
  - `app/worker/news_data_sync_service.py`
  - `app/routers/news_data.py`

### 3.2 当前真实能力与“社媒分析师”之间的断层

- 已有新闻抓取与新闻入库。
- 已有社媒消息库模型与 API。
- 但缺少“把 A 股可用的新闻 / 问答 / 热度 / 讨论代理信号统一归一化成情绪分析输入”的中间层。

## 4. 数据源对照

### 4.1 Tushare

官方文档可见：

- 大模型语料专题数据下包含：
  - 新闻快讯（短讯）
  - 新闻通讯（长篇）
  - 新闻联播文字稿
  - 上证 e 互动问答
  - 深证易互动问答
- 参考：
  - `https://tushare.pro/document/2`
  - `https://tushare.pro/document/2?doc_id=143`
  - `https://tushare.pro/document/2?doc_id=154`
  - `https://tushare.pro/document/2?doc_id=366`
  - `https://tushare.pro/document/2?doc_id=367`

适合度判断：

- 最适合做 A 股“社媒分析师”的正式主源。
- 原因：
  - 有官方问答语料能力，能替代部分社媒情绪输入。
  - 有较完整的新闻 / 文本 / 公告 / 问答体系。
  - A 股适配度最高。

风险与成本：

- 部分接口可能需要积分或单独权限。
- 当前仓库已有相关错误处理，说明实际接入时要考虑权限不足路径。

### 4.2 AKShare

官方文档 / 教程里可见：

- 个股新闻：
  - `stock_news_em`
- 雪球热度榜：
  - `stock_hot_follow_xq`
  - `stock_hot_tweet_xq`
  - `stock_hot_deal_xq`
- 百度股市通投票 / 热搜：
  - `stock_zh_vote_baidu`
  - `stock_hot_search_baidu`
- 参考：
  - `https://akshare.akfamily.xyz/tutorial.html`

适合度判断：

- 适合做 A 股社媒分析的补充源 / 代理热度源。
- 价值在于：
  - 可以提供讨论热度、关注热度、投票倾向、热搜等“准社媒信号”。
  - 与 A 股用户实际讨论场景较接近。

风险与成本：

- 更偏网页抓取封装，稳定性受上游页面和反爬影响更大。
- 适合 fallback，不适合作为唯一正式主源。

### 4.3 FuShare

- 项目定位更偏中国商品期货基本面数据。
- 参考：
  - `https://github.com/LowinLi/fushare`

适合度判断：

- 不适合接到当前 A 股社媒分析链路。
- 不建议纳入此方案。

### 4.4 三者对照表

| 数据源 | 可用性 | 稳定性 | 成本 | A股适配度 | 是否需要积分/Key | 适合接入当前链路的角色 |
| --- | --- | --- | --- | --- | --- | --- |
| Tushare | 高 | 高 | 中 | 最高 | 多数能力需要 Token，部分高价值接口可能需要积分 | A 股正式文本主源、问答主源 |
| AKShare | 高 | 中 | 低 | 高 | 通常不需要单独积分，但依赖上游网页接口 | 新闻补充源、热度/投票/热搜代理源 |
| FuShare | 低 | 中 | 低 | 低 | 依项目而定 | 不建议接入当前股票社媒分析链路 |

结论：

- 如果目标是“尽快让 A 股社媒分析师真正可用”，最合适的组合不是三选一，而是：
  - `Tushare = 正式文本/问答主源`
  - `AKShare = 热度/讨论代理补充源`
  - `FuShare = 排除`

## 5. 港股与其他市场当前实现状态

### 5.1 港股新闻分析师当前如何实现

当前港股并不是“单独的社媒分析链路”，而是：

- 新闻分析师走 `get_stock_news_unified`
- 其中港股原生新闻当前通过：
  - `ForeignStockService.get_hk_news()`
  - 再由其按优先级尝试：
    - `_get_hk_news_from_akshare`
    - `_get_hk_news_from_finnhub`
- 同时并列调用新的 Google RSS 新闻抓取
- 最终在 `get_stock_news_unified` 内做：
  - 多关键词查询
  - 相关性打分
  - 去重
  - 排序
  - 双空明确报错

这说明：

- 港股当前真正能跑通的是“新闻/舆情近似链路”
- 还不是严格意义上的“真实社交媒体原文抓取”

### 5.2 港股社媒分析师当前状态

- 前端没有像 A 股那样直接禁用港股“社媒分析师”
- 但后端 `get_stock_sentiment_unified` 对港股仍是模板型占位输出
- 所以当前港股“社媒分析师”可选，不等于“真实社媒数据已经接通”

### 5.3 美股当前状态

- 美股社媒分析是当前最接近“真实社媒”的市场
- 主链路仍以 Reddit 情绪接口为主
- 说明当前仓库真正成熟的“社媒分析师”范式，更接近：
  - `文本源 -> 情绪摘要`
  - 而不是“统一结构化社媒消息库驱动”

## 6. 推荐融合方案

### 6.1 总体原则

- 不追求“拿到真正微博 / 雪球全量社媒原文”。
- 目标是先把 A 股“社媒分析师”从不可用变成可稳定输出。
- 因此采用“正式文本源 + 讨论热度代理源 + 可选结构化社媒库”的组合方案。

### 6.2 推荐分层

#### 第一层：正式文本主源

- 主源：Tushare
- 输入内容：
  - 新闻快讯
  - 新闻通讯
  - 上证 e 互动问答
  - 深证易互动问答
  - 必要时补公告 / 研报

作用：

- 提供正式、可持续、A 股适配度高的文本语料。
- 其中 e 互动问答非常适合补足“投资者关注点与公司回应”的情绪上下文。

#### 第二层：讨论热度代理源

- 补充源：AKShare
- 输入内容：
  - 东方财富个股新闻
  - 雪球热度榜 / 讨论榜 / 交易榜
  - 百度股市通投票
  - 百度热搜股

作用：

- 不是替代正式文本，而是补“市场讨论热度”和“偏情绪代理信号”。

#### 第三层：统一归一化层

- 新增一个“中文市场情绪聚合器”，统一产出：
  - `source_type`: `news` / `qa` / `heat` / `vote`
  - `source_name`
  - `publish_time`
  - `title`
  - `content`
  - `symbol`
  - `sentiment`
  - `sentiment_score`
  - `importance`
  - `metadata`

建议：

- 正式文本仍可写入 `stock_news`
- 讨论热度 / 问答 / 投票等可写入 `social_media_messages`，但平台字段不要硬编码成“微博/Reddit”语义
- 可以新增平台枚举，如：
  - `tushare_irm_sh`
  - `tushare_irm_sz`
  - `akshare_xueqiu_heat`
  - `akshare_baidu_vote`
  - `akshare_baidu_hot_search`

### 6.3 分阶段落地

#### 阶段 1

- 保持前端 A 股暂时禁用不变。
- 先把后端“中文市场情绪聚合器”做出来。
- 输出真实的 A 股情绪报告文本，但仍可标注为“新闻 / 问答 / 热度代理情绪”。

#### 阶段 2

- 当 Tushare 问答与新闻链路稳定后，放开 A 股“社媒分析师”。
- UI 文案建议从“社媒分析师”调整为更准确的：
  - `舆情与投资者情绪分析师`

#### 阶段 3

- 如果后续确实需要更纯粹的社交平台原文数据，再考虑单独接微博 / 雪球等更高维护成本的采集链路。

## 7. 当前代码层面的直接结论

1. 当前港股“社媒分析师”不是独立真实实现，而是与 A 股共用中文模板占位逻辑。
2. 当前主分析链路没有使用 `social_media_messages` 数据库。
3. 当前最适合先接入 A 股社媒分析链路的不是 FuShare，而是：
   - 主源：Tushare
   - 补充源：AKShare
4. 如果目标是尽快让 A 股版块可用，最合理的命名和口径不是“纯社媒”，而是：
   - `舆情 / 问答 / 热度 / 新闻代理情绪分析`

## 8. 推荐的实现落点

如果后续正式开做 A 股“社媒分析师”落地，建议直接按下面的顺序改：

1. 新增一个中文市场情绪聚合器，统一拉取：
   - Tushare 新闻
   - Tushare e 互动 / 易互动
   - AKShare 东方财富新闻
   - AKShare 雪球热度 / 百度热搜 / 投票
2. 聚合器输出统一结构，再决定：
   - 正式新闻写入 `stock_news`
   - 问答 / 热度 / 投票 / 代理情绪写入 `social_media_messages`
3. 将 `get_stock_sentiment_unified` 从“模板占位”替换为：
   - `A股/港股统一顶层入口`
   - `A股优先 Tushare + AKShare`
   - `港股优先原生新闻 + Google RSS`
   - `美股维持 Reddit/现有链路`
4. 前端文案从“社媒分析师”调整为更精确的：
   - `舆情与投资者情绪分析师`
