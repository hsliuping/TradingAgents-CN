# Tushare MCP 工具清单参考（来源：zhewenzhang/tushare_MCP）

> **用途**：后续需要新增 Tushare 工具/Skill 时，先查此清单是否有对应接口，有则直接参考其参数和说明去集成。
>
> **来源**：https://github.com/zhewenzhang/tushare_MCP （52 个工具，10 大类）
>
> **最后更新**：2026-02-14

---

## 📊 一、Alpha 策略分析工具（6 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `analyze_sector_alpha_strategy` | 单板块相对强度 Alpha（2日+5日） | sector_code, benchmark_code(000300.SH), end_date | 基础 | ❌ |
| 2 | `rank_sectors_by_alpha` | 申万一级行业 Alpha 排名 TOP N | benchmark_code, end_date, top_n(10) | 基础 | ❌ |
| 3 | `rank_l2_sectors_by_alpha` | 申万二级行业 Alpha 排名 TOP N | benchmark_code, end_date, top_n(20) | 基础 | ❌ |
| 4 | `rank_l1_sectors_alpha_full` | 申万一级行业完整排行（全部31个） | benchmark_code, end_date | 基础 | ❌ |
| 5 | `rank_l1_sectors_alpha_velocity` | 一级行业 Alpha 排名上升速度 | benchmark_code, end_date | 基础 | ❌ |
| 6 | `rank_l2_sectors_alpha_velocity` | 二级行业 Alpha 排名上升速度 | benchmark_code, end_date, top_n(20) | 基础 | ❌ |

---

## 📈 二、股票行情工具（22 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_stock_basic_info` | 股票基本信息（代码/名称/行业/上市日期） | ts_code 或 name | 基础 | ✅ stock_basic |
| 2 | `search_stocks` | 股票模糊搜索 | keyword | 基础 | ✅ |
| 3 | `get_stock_daily` | A股日线行情（未复权） | ts_code, trade_date, start/end_date | 基础 | ✅ daily |
| 4 | `get_stock_weekly` | A股周线行情 | ts_code, trade_date, start/end_date | 基础 | ❌ |
| 5 | `get_stock_min` | A股实时分钟行情（1/5/15/30/60min） | ts_code, freq, date_str | 单独权限 | ❌ |
| 6 | `get_stock_rt_k` | 沪深京实时日线（支持通配符） | ts_code(支持6*.SH等) | 单独权限 | ✅ rt_k |
| 7 | `get_etf_daily` | ETF日线行情 | ts_code, trade_date, start/end_date | 基础 | ❌ |
| 8 | `get_index_daily` | A股指数日线行情 | ts_code, trade_date, start/end_date | 基础 | ✅ index_daily |
| 9 | `get_share_float` | 限售股解禁数据 | ts_code, ann_date, float_date, start/end_date | 2000 | ❌ |
| 10 | `get_stock_repurchase` | 上市公司股票回购 | ann_date, start/end_date | 600 | ❌ |
| 11 | `get_pledge_detail` | 股权质押明细 | ts_code(必填) | 500 | ❌ |
| 12 | `get_block_trade` | 大宗交易数据 | ts_code, trade_date, start/end_date | 基础 | ❌ |
| 13 | `scan_announcement_signals` | 公告信号扫描（利好/利空） | ts_code_list, check_date, start/end_date | 单独权限 | ❌ |
| 14 | `get_stock_holder_trade` | 股东增减持数据 | ts_code, ann_date, trade_type(IN/DE), holder_type | 基础 | ❌ |
| 15 | `get_stock_holder_number` | 股东户数 | ts_code, ann_date, enddate, start/end_date | 基础 | ❌ |
| 16 | `get_stock_survey` | 机构调研记录 | ts_code, trade_date, start/end_date | 5000 | ❌ |
| 17 | `get_cyq_perf` | 筹码分析（平均成本+胜率+集中度） | ts_code(必填), trade_date, start/end_date | 5000 | ❌ |
| 18 | `get_margin` | 融资融券汇总（按交易所） | trade_date, start/end_date, exchange_id | 2000 | ✅ margin |
| 19 | `get_margin_detail` | 融资融券明细（按个股） | ts_code, trade_date, start/end_date | 2000 | ❌ |
| 20 | `get_stock_moneyflow_dc` | 东财个股资金流向（主力/超大/大/中/小单） | ts_code, trade_date, start/end_date | 5000 | ❌ |
| 21 | `get_daily_basic` | 每日指标（PE/PB/PS/换手率/量比/市值） | ts_code, trade_date, start/end_date | 基础 | ✅ daily_basic |
| 22 | `get_top_list` | 龙虎榜每日明细 | trade_date(必填), ts_code | 2000 | ❌ |
|    | `get_top_inst` | 龙虎榜机构成交明细 | trade_date(必填), ts_code | 5000 | ❌ |

---

## 📊 三、指数行情工具（4 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_global_index` | 国际主要指数行情（道琼斯/标普/纳斯达克等20+） | index_code, trade_date, start/end_date | 基础 | ❌ |
| 2 | `search_global_indexes` | 搜索可用国际指数 | keyword | 基础 | ❌ |
| 3 | `get_sw_industry_daily` | 申万行业指数日线（L1/L2/L3） | ts_code, trade_date, start/end_date, level | 基础 | ❌ |
| 4 | `get_industry_index_codes` | 申万行业分类代码列表 | level(L1/L2/L3), src(SW2021) | 基础 | ❌ |

---

## 💱 四、外汇工具（1 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_fx_daily` | 外汇日线行情（USDCNH/EURUSD等） | ts_code, trade_date, start/end_date | 基础 | ❌ |

---

## 📈 五、期货工具（5 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_fut_basic` | 期货合约基本信息 | exchange(必填), fut_type, fut_code | 基础 | ❌ |
| 2 | `get_nh_index` | 南华期货指数日线 | ts_code, trade_date, start/end_date | 2000 | ❌ |
| 3 | `get_fut_holding` | 期货每日持仓排名 | trade_date, symbol, start/end_date, exchange | 2000 | ❌ |
| 4 | `get_fut_wsr` | 期货仓单日报 | trade_date, symbol, start/end_date, exchange | 2000 | ❌ |
| 5 | `get_fut_min` | 期货实时分钟行情 | ts_code(必填), freq, date_str | 单独权限 | ❌ |

---

## 📋 六、财务报表工具（2 个 MCP + 4 个我们额外覆盖的 Tushare API）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_income_statement` | 利润表（合并/母公司，12种报告类型） | ts_code(必填), start_date, end_date, report_type(1-12) | 基础 | ✅ income → `get_income_analysis` |
| 2 | `get_fina_indicator` | 财务指标（ROE/ROA/毛利率/净利率/资产负债率等） | ts_code, ann_date, start/end_date, period | 基础 | ✅ fina_indicator → 多个工具共用 |

> **我们额外覆盖的 Tushare 财务 API（MCP 未收录）**：

| # | Tushare API | 功能 | 我们的工具 |
|---|-------------|------|-----------|
| 3 | `balancesheet` | 资产负债表 | ✅ `get_balance_sheet_analysis` |
| 4 | `cashflow` | 现金流量表 | ✅ `get_cashflow_analysis` |
| 5 | `dividend` | 分红送股数据（需 2000 积分） | ✅ `get_dividend_data` |
| 6 | `fina_mainbz` | 主营业务构成 | ✅ `get_main_business` |

---

## 📊 七、概念板块工具（8 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_eastmoney_concept_board` | 东财概念板块行情（涨跌幅/领涨股/市值/换手率） | ts_code, name, trade_date, start/end_date | 6000 | ❌ |
| 2 | `get_eastmoney_concept_member` | 东财板块每日成分数据 | ts_code, con_code, trade_date | 6000 | ❌ |
| 3 | `get_eastmoney_concept_daily` | 东财概念/行业/地域板块行情 | ts_code, trade_date, start/end_date, idx_type | 6000 | ❌ |
| 4 | `analyze_concept_alpha_strategy` | 单个东财概念板块 Alpha 分析 | concept_code(必填), benchmark_code, end_date | 6000 | ❌ |
| 5 | `rank_concepts_by_alpha` | 概念板块 Alpha 排名（热门板块筛选） | benchmark_code, end_date, top_n(20), hot_limit(80) | 6000 | ❌ |
| 6 | `rank_concepts_alpha_velocity` | 概念板块 Alpha 排名上升速度 | benchmark_code, end_date | 6000 | ❌ |
| 7 | `get_concept_moneyflow_dc` | 东财板块资金流向（概念/行业/地域） | ts_code, trade_date, start/end_date, content_type | 5000 | ❌ |
| 8 | `scan_concepts_volume_anomaly` | 概念板块成交量异动扫描 | end_date, vol_ratio_threshold, price_change_5d_min/max, hot_limit | 6000 | ❌ |

> **注**：概念板块工具使用**东方财富**（DC）数据源，与我们现有的**同花顺**（THS）板块体系代码不同，混用需注意。

---

## 📊 八、成交量异动分析工具（1 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `scan_l2_volume_anomaly` | 申万二级行业成交量异动（量价背离信号） | end_date, vol_ma_short(3), vol_ma_long(10), vol_ratio_threshold(1.5), price_change_5d_threshold(0.03) | 基础 | ❌ |

---

## 🗄️ 九、缓存管理工具（1 个）

| # | 工具名 | 功能 | 关键参数 | 权限 | 我们已有？ |
|---|--------|------|----------|------|-----------|
| 1 | `get_cache_stats` | 缓存统计（数量/访问次数） | 无 | - | ❌（我们用 MongoDB 缓存） |

---

## 📊 十、README 末尾提及的额外工具（3 个，未计入 52 个）

| # | 工具名 | 功能 | 说明 |
|---|--------|------|------|
| 1 | `analyze_sector_health` | 板块健康度分析（线性回归趋势斜率 + A/B/C 评级） | 结合成交量连贯性和内生广度 |
| 2 | `get_index_rt_k` | 指数实时日线快照（基准用） | 基于 rt_k API |
| 3 | `scan_realtime_strong_sectors` | 实时强度扫描（全市场行情 + 与昨日同刻成交量对比） | 自动抓取通配符行情 |

---

## 📝 权限速查

| 权限等级 | 涉及工具 |
|----------|---------|
| **基础权限** | 大部分股票行情、指数行情、Alpha策略、外汇、财务报表 |
| **500 积分** | `get_pledge_detail`（股权质押） |
| **600 积分** | `get_stock_repurchase`（股票回购） |
| **2000 积分** | `get_margin`, `get_margin_detail`, `get_top_list`, `get_share_float`, `get_nh_index`, `get_fut_holding`, `get_fut_wsr` |
| **5000 积分** | `get_stock_survey`, `get_cyq_perf`, `get_stock_moneyflow_dc`, `get_concept_moneyflow_dc`, `get_top_inst` |
| **6000 积分** | 东财概念板块系列（`get_eastmoney_concept_*`） |
| **单独权限** | `get_stock_min`, `get_stock_rt_k`, `get_fut_min`, `scan_announcement_signals` |

---

## 📊 汇总统计

| 分类 | 工具数(MCP) | 我们已覆盖 | 备注 |
|------|------------|-----------|------|
| Alpha 策略分析 | 6 | 0 | |
| 股票行情 | 22 | ~7 | |
| 指数行情 | 4 | 0 | |
| 外汇 | 1 | 0 | |
| 期货 | 5 | 0 | |
| 财务报表 | 2 | 2 + 4 额外 | MCP 的 2 个全覆盖，另外我们额外覆盖了 balancesheet/cashflow/dividend/fina_mainbz |
| 概念板块 | 8 | 0 | 我们使用同花顺(THS)板块体系 |
| 成交量异动 | 1 | 0 | |
| 缓存管理 | 1 | 0 | 我们用 MongoDB 缓存 |
| **合计** | **52** | **~9 + 4 额外** | |
