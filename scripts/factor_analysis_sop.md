# 因子分析离线工具 SOP

> 本文档描述如何使用离线工具对 TradingAgents-CN 的因子表现进行事后分析与反馈学习。
>
> **核心原则**: 不侵入主链路。所有分析只读 `results/{ticker}/{date}/reports/*.md`,
> 输出到 `results_analysis/`。主链路代码 (`tradingagents/`) 完全不需要修改。

---

## 1. 工具一览

| 文件 | 用途 | 是否纳入 git |
|---|---|---|
| `scripts/daily_feedback.py` | 每日事后反馈学习器 (自包含) | ✅ 是 |
| `scripts/factor_analysis_sop.md` | 本 SOP 文档 | ✅ 是 |
| `scripts/analyze_results.py` | 全量报告解析器 (探索用) | ❌ 否 (gitignore) |
| `scripts/factor_analysis.py` | 因子 IC 分析 (探索用) | ❌ 否 |
| `scripts/validate_factors.py` | 因子有效性检验 (探索用) | ❌ 否 |
| `scripts/debug_parse.py` | 报告解析调试 (探索用) | ❌ 否 |
| `scripts/show_recent_buys.py` | 查看最近买入 (探索用) | ❌ 否 |
| `scripts/show_results.py` | 结果展示 (探索用) | ❌ 否 |
| `scripts/show_validation.py` | 校验结果展示 (探索用) | ❌ 否 |
| `results_analysis/` | 所有输出 (panel_data、报告、cache) | ❌ 否 |

---

## 2. 因子快照策略 (重要)

**不需要修改 trader_node 主链路代码**。

原因: 主链路的 trader 已经把完整决策报告 (含全部技术指标、估值、目标价、
预期收益等) 写到 `results/{ticker}/{date}/reports/trader_report.md`。
这些 markdown 报告本身就是因子快照, 含:

- 当前价格、涨跌幅、5 日均量
- MA5/10/20/60 及相对位置
- MACD (DIF/DEA/HIST)、RSI6/12/24
- 布林带 (上/中/下轨、位置)
- PE/PB/PS/市值/股息率
- 行业 PE/PB、相对估值
- 决策 (买入/卖出/持有)、目标价、止损、预期收益

`daily_feedback.py` 通过正则解析这些 markdown 报告, 重建结构化因子快照,
完全离线, 不影响主链路。

---

## 3. 使用流程

### 3.1 首次运行 (全量重建)

```bash
cd /Users/lishinho/projects/TradingAgents-CN
python3 scripts/daily_feedback.py --rebuild
```

会扫描 `results/` 下所有 `{ticker}/{date}/reports/*.md`, 解析后保存到:

- `results_analysis/panel_data.csv` (因子快照表, 每行一个 (ticker, date))
- `results_analysis/factor_validation/post_price_cache.json` (股价缓存)
- `results_analysis/feedback/{YYYY-MM-DD}.md` (反馈报告)
- `results_analysis/feedback/latest.md` (最新报告链接)
- `results_analysis/feedback/factor_ic_trend.csv` (因子 IC 历史)
- `results_analysis/feedback/decision_performance_trend.csv` (决策表现历史)

### 3.2 日常增量更新 (推荐 cron)

```bash
python3 scripts/daily_feedback.py
```

只解析 `panel_data.csv` 中不存在的 (ticker, date), 不重新解析已存在的。
然后拉取最近 30+30 天的股价, 更新 `fwd_ret_{1,3,5,10,15,20}d`, 重算 IC,
生成新的反馈报告。

### 3.3 只更新股价 (股价已收盘, 没有新报告)

```bash
python3 scripts/daily_feedback.py --price-only
```

跳过报告解析, 直接读取 panel_data, 拉取最新股价, 更新 forward_return。

### 3.4 自定义回看窗口

```bash
python3 scripts/daily_feedback.py --lookback 7   # 只看最近 7 天
python3 scripts/daily_feedback.py --lookback 90  # 看最近 90 天
```

---

## 4. 定时调度

### macOS (launchd)

创建 `~/Library/LaunchAgents/com.tradingagents.feedback.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tradingagents.feedback</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/lishinho/projects/TradingAgents-CN/.venv/bin/python3</string>
    <string>/Users/lishinho/projects/TradingAgents-CN/scripts/daily_feedback.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/lishinho/projects/TradingAgents-CN</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>17</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/feedback.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/feedback.err</string>
</dict>
</plist>
```

加载:

```bash
launchctl load ~/Library/LaunchAgents/com.tradingagents.feedback.plist
launchctl start com.tradingagents.feedback
```

### Linux (cron)

```bash
# 每天 17:30 运行 (A 股收盘后)
30 17 * * 1-5 cd /path/to/TradingAgents-CN && \
    /path/to/python3 scripts/daily_feedback.py >> /tmp/feedback.log 2>&1
```

---

## 5. 反馈报告解读

每日生成的 `feedback/{YYYY-MM-DD}.md` 包含 4 个部分:

### 5.1 最近 30 天买入决策表现
- 样本数、胜率、平均收益、中位收益、最大/最小收益
- 这是**最直接的策略健康度指标**

### 5.2 多周期持有表现
- 1d / 3d / 5d / 10d / 15d / 20d 各周期的胜率与收益分布
- 用来判断**最优持有周期**

### 5.3 因子 IC 排名
- Pearson 相关系数: 各因子 vs 5 日 forward return
- |IC| > 0.1 视为有效因子, > 0.3 为强因子
- p < 0.05 视为统计显著
- 用于**因子轮动决策**: 哪些因子最近预测力强

### 5.4 行动建议 (自动启发式)
- 5 日胜率 < 40% 且平均亏损 > 2%: ⚠️ 警示, 建议检视 trader
- 5 日胜率 > 60% 且平均盈利 > 2%: ✅ 良好
- 其他: ➖ 中性, 继续观察

---

## 6. 从反馈到主链路优化 (人工闭环)

`daily_feedback.py` 只产出反馈报告, 不自动改主链路。
推荐的人工闭环:

1. **每周回顾**: 打开 `results_analysis/feedback/latest.md`
2. **识别问题因子**: IC 持续低于 0.05 的因子在 prompt 中可能被高估
3. **调整 prompt**: 修改 `tradingagents/agents/trader/trader.py` 的系统提示
   - 强化高 IC 因子的权重
   - 弱化低 IC 因子的影响
4. **加止损规则**: 在 prompt 中增加 "若 RSI6 > 70 且 MACD 死叉, 强制降级为持有"
5. **市场状态过滤**: 在 `tradingagents/graph/trading_graph.py` 增加大盘择时
6. **回归测试**: 用 `daily_feedback.py --rebuild` 重新评估

---

## 7. 故障排查

### 7.1 报告解析为空
检查 `results/` 目录结构和文件名:
```bash
ls results/600519/2026-07-10/reports/
# 应有: market_report.md, fundamentals_report.md, trader_report.md
```

### 7.2 akshare 拉取失败
- 检查网络
- akshare 偶发限流, 重试机制已内置 (3 次)
- 必要时换数据源 (Tushare)

### 7.3 IC 全为 NaN
- 样本数 < 5: 继续累积数据
- `current_price` 缺失: 检查 market_report.md 格式是否变化

### 7.4 增量更新漏报告
- 报告目录命名必须是 `{ticker}/{YYYY-MM-DD}/reports/`
- 用 `--rebuild` 全量重建

---

## 8. 数据流示意

```
主链路 (trader_node)               离线分析 (daily_feedback.py)
─────────────────────             ──────────────────────────
                                  
  trader.py                        parse_market_report()
    │ LLM 生成报告                    │ 正则解析
    v                                v
  results/{ticker}/{date}/         panel_data.csv
    reports/                        (因子快照表)
      ├─ market_report.md            │
      ├─ fundamentals_report.md       │ 增量拉取股价 (akshare)
      └─ trader_report.md            v
                                  
                                   fwd_ret_{1,3,5,10,15,20}d
                                  
                                     │ 计算
                                     v
                                  
                                   feedback/{date}.md
                                   (反馈报告 + 行动建议)
                                  
                                     │ 人工回顾
                                     v
                                  
                                   调整 prompt / 主链路
```

---

## 9. 扩展建议

未来可以基于 panel_data.csv 做更多离线分析:

- **因子衰减分析**: IC 随时间的变化趋势
- **风格归因**: 大盘/小盘、价值/成长的暴露
- **决策路径回溯**: 哪些 agent (market/sentiment/news/fundamentals) 的
  信号对最终决策影响最大
- **多模型对比**: 用同一组股票跑不同 prompt, 对比 forward return

所有这些都可以在不改主链路的前提下, 通过追加分析脚本实现。
