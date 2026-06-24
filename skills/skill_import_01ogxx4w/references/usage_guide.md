# 估值分析技能使用指南

## 功能概述

本技能提供完整的股票估值分析工具链，支持 A股和港股：

1. **估值快照** - 实时 PE/PB/PS/股息率及历史分位
2. **DCF 计算** - 现金流折现估值模型
3. **同业对比** - 同行业公司估值横向比较
4. **Watchlist 管理** - 目标价监控和预警

## 数据源

- **AKShare** - 免费开源金融数据接口
- 覆盖 A股全市场、港股通标的
- 实时行情、财务数据、历史价格

## 使用场景

### 场景1: 快速估值扫描

```bash
# 查看五粮液当前估值
python scripts/valuation_snapshot.py 000858

# 输出示例:
# PE-TTM: 15.3x (历史23%分位)
# PB: 4.2x
# 股息率: 2.8%
```

### 场景2: DCF 内在价值计算

```bash
python scripts/dcf_calculator.py \
  --fcf 250 \
  --growth "0.12,0.10,0.08,0.06,0.05" \
  --terminal 0.03 \
  --discount 0.09 \
  --net-debt -100 \
  --shares 38.8 \
  --current-price 142
```

参数说明：
- `--fcf`: 当前年度自由现金流（亿元）
- `--growth`: 未来5年增速预测
- `--terminal`: 永续增速（通常3%）
- `--discount`: 折现率/WACC（通常8-10%）
- `--net-debt`: 净负债（负数表示净现金）
- `--shares`: 总股本（亿股）
- `--current-price`: 当前股价（用于计算安全边际）

### 场景3: 同行业对比

```bash
# 对比白酒行业估值
python scripts/industry_compare.py --industry 白酒 --stock 000858

# 或自定义对比标的
python scripts/industry_compare.py --codes "000858,000568,600519" --stock 000858
```

### 场景4: Watchlist 监控

```bash
# 添加股票到监控列表，设定目标估值区间
python scripts/watchlist_manager.py add 000858 \
  --name "五粮液" \
  --pe-low 15 \
  --pe-high 25 \
  --notes "优质白酒龙头"

# 列出所有监控股票
python scripts/watchlist_manager.py list

# 检查预警（可加入 cron 定时执行）
python scripts/watchlist_manager.py check
```

## 价值投资工作流

### 研究新标的

1. **初步筛选**: `valuation_snapshot.py` 快速看估值分位
2. **深度估值**: `dcf_calculator.py` 算内在价值和安全边际
3. **同业验证**: `industry_compare.py` 确认估值相对位置
4. **加入监控**: `watchlist_manager.py add` 设定买入目标价

### 定期复盘

1. **检查预警**: `watchlist_manager.py check` 看是否触发买入/卖出信号
2. **更新模型**: 根据最新财报调整 DCF 假设
3. **记录笔记**: 在投资日志中更新估值逻辑变化

## 局限性与注意事项

1. **数据源限制**: AKShare 免费接口偶尔不稳定，关键决策前建议交叉验证
2. **历史分位**: 个股历史估值数据较难获取，使用价格分位作为近似参考
3. **DCF 敏感性**: 内在价值对折现率和增速假设高度敏感，建议做多情景分析
4. **港股数据**: 港股通标的支持较好，纯港股可能需要额外数据源

## 扩展建议

- 接入理杏仁/乌龟量化等付费数据源获取更完整的历史估值数据
- 增加更多估值方法（EV/EBITDA、股息折现等）
- 集成财报分析，自动提取自由现金流数据
- 与飞书文档联动，自动生成估值报告存档
