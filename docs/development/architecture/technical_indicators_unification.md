# 技术指标库统一方案（全局适用）

版本: v0.1.0
作者: Augment Agent
日期: 2025-08-22

## 1. 背景与目标
目前项目中技术指标散落在多个位置：
- tradingagents/dataflows/tdx_utils.py：内联实现了 MACD、布林带等少量指标（使用 pandas 计算，字段名大小写混杂，如 `Close`）。
- tradingagents/dataflows/stockstats_utils.py：借助第三方 `stockstats` 包通过访问列名形式触发计算（如 `df['macd']`）。
- 其它数据提供器（optimized_*）侧重数据抓取与缓存，未形成统一指标层。

痛点：
- 命名不一致（`MACD`/`MACD_Signal` vs `dif/dea/macd_hist` vs stockstats 命名）。
- 指标分散、重复实现，难以复用和扩展。
- 复权口径与参数未显式纳管，跨场景（选股/分析/回测）难统一。

目标：
- 形成一套“统一指标体系”（Unified Indicator Library，UIL），服务于选股、分析、回测等。
- 统一命名/参数/返回格式；支持批量向量化计算与缓存；可扩展。

## 2. 统一命名与参数规范
- 命名规则：全部小写 snake_case，指标名 + 参数后缀采用固定列名，不在列名里追加参数值。
  - 移动平均：ma5, ma10, ma20, ma60（收盘为基准）
  - EMA：ema12, ema26
  - MACD：dif, dea, macd_hist（= dif - dea）
  - RSI：rsi14
  - BOLL：boll_mid, boll_upper, boll_lower（默认 n=20, k=2）
  - ATR：atr14
  - KDJ：kdj_k, kdj_d, kdj_j（默认 9,3,3）
- 参数暴露：通过函数参数传入（如 rsi(period=14)），但列名固定（例如 period 改动时列名仍为 rsi14? → 约定：P0 使用固定参数集，P1 才支持自定义参数并在列名中追加后缀，如 rsi_21）。
- 复权口径：
  - UIL 不负责复权，统一接收已按 adj 处理后的 OHLCV 数据；调用侧保证口径一致（qfq/hfq/none）。

## 3. 统一指标API设计
核心：既支持“批量计算若干指标并拼列”，也支持“单指标向量化计算”。

### 3.1 函数签名
```python
# tradingagents/tools/analysis/indicators.py
from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd

@dataclass
class IndicatorSpec:
    name: str           # e.g., 'rsi', 'macd', 'ma'
    params: Dict[str, Any] = None  # e.g., {'period': 14}

SUPPORTED = { 'ma', 'ema', 'macd', 'rsi', 'boll', 'atr', 'kdj' }

def compute_indicator(df: pd.DataFrame, spec: IndicatorSpec) -> pd.DataFrame:
    """返回包含所需列的新 DataFrame（在原 df 基础上追加列）。不修改输入副本。"""

def compute_many(df: pd.DataFrame, specs: List[IndicatorSpec]) -> pd.DataFrame:
    """按需计算去重后的指标集合，统一追加列，返回拷贝。"""

def last_values(df: pd.DataFrame, columns: List[str]) -> Dict[str, Any]:
    """从 df 末行提取指定列的数值（便于 API 只返回最新值）。"""
```

### 3.2 输入/输出约定
- 输入 df 至少含：['open','high','low','close','vol','amount']（小写，日线）。
- 输出在原列基础上追加统一命名的指标列。
- 不做 inplace 修改（返回新 df）。

## 4. 实现要点（向量化 & 可维护）
- 统一使用 pandas/numpy 实现；不强依赖 stockstats，保留 stockstats 作为可选兼容层（适配器）。
- 严格对齐边界：窗口长度不足的行返回 NaN；交叉判断在调用侧完成（利用上一行/当前行）。
- 计算细节：
  - EMA 使用 ewm(adjust=False)。
  - MACD：dif=ema12-ema26；dea=dif.ewm(span=9).mean()；macd_hist=dif-dea。
  - BOLL：mid=close.rolling(n).mean()；upper=mid+k*std；lower=mid-k*std。
  - ATR：TR=max(high-low, abs(high-prev_close), abs(low-prev_close)) 滚动均值。
  - KDJ：RSV=(close-low_n)/(high_n-low_n)*100；K/D 用 2/3 平滑或 ewm；J=3K-2D。

## 5. 兼容与迁移计划
- 新增模块：`tradingagents/tools/analysis/indicators.py`
- 迁移/封装：
  1) tdx_utils.py 内的指标计算改为调用 UIL，并统一返回字段名；临时保留旧键名到新键名的映射（兼容期警告）。
  2) stockstats_utils.py 提供适配层：当请求的指标属于 SUPPORTED 时，转用 UIL；否则 fallback 到 stockstats（便于快速支持少见指标）。
  3) 其余调用点（分析师/数据提供器）只接受统一小写字段名。
- 弃用策略（deprecation）：
  - 在文档和代码注释中标注旧接口；两个版本后移除旧命名。

## 6. 缓存与性能
- 指标按“日期/市场/复权口径/固定参数版本”缓存：
  - K 线缓存键：`CN:{adj}:{date}:bars`
  - 指标缓存键：`CN:{adj}:{date}:ind:v1`
- compute_many 内部可做“计算去重”：多个 spec 共享中间结果（如 ema12/26 被 MACD 复用）。

## 7. 测试与验证
- 单元测试（tests/unit/tools/analysis/test_indicators.py）：
  - 每个指标的形状、起始 NaN 数量、典型数值校验（对照已知样本）。
  - 交叉判断用示例序列验证。
- 集成测试：
  - screening_service 使用 compute_many 计算并筛选；验证 DSL 条件对结果的影响。

## 8. 对外字段清单（P0 固定参数）
- ma5, ma10, ma20, ma60
- ema12, ema26
- dif, dea, macd_hist
- rsi14
- boll_mid, boll_upper, boll_lower
- atr14
- kdj_k, kdj_d, kdj_j

## 9. 与选股 DSL 的映射
- 字段名称与 DSL 白名单完全一致，避免额外映射层。
- 交叉条件（cross_up/cross_down）在服务层以列向量方式判断最近两日，或者在筛选执行器中完成。

## 10. 后续（P1）
- 自定义参数列名规范：rsi_21、ma_30、boll_20_2 等；提供列名生成器，避免硬编码。
- 指标注册中心：支持插件化注册（名称→函数、默认参数、依赖列）。
- AI 选股：提示词中暴露字段白名单与中文名称映射（如 “均线20日”→`ma20`）。

## 11. 实施计划
1) 创建 `tools/analysis/indicators.py` 并实现 MA/EMA/MACD/RSI/BOLL/ATR/KDJ（P0）。
2) 改造 tdx_utils.py：改为调用 UIL；输出键统一。
3) 改造 stockstats_utils.py：优先 UIL，fallback stockstats；标注弃用提醒。
4) 编写单元测试；在 screening_service 初版中引入 UIL。
5) 文档与示例更新；逐步清理旧命名。

## 12. 附：现存实现片段（供对照）
- tdx_utils.py（MACD/BOLL 片段，大小写与返回键不统一）
```
# ... 摘要
exp1 = df['Close'].ewm(span=12).mean()
exp2 = df['Close'].ewm(span=26).mean()
macd = exp1 - exp2
signal = macd.ewm(span=9).mean()
# 返回: 'MACD', 'MACD_Signal', 'MACD_Histogram'
```
- stockstats_utils.py（通过 stockstats 触发指标计算）
```
df = wrap(data)
indicator = 'macd'
df[indicator]  # 触发计算
matching_rows = df[df['Date'].str.startswith(curr_date)]
```

> 统一后，两个位置都改为调用 UIL，向外暴露统一列名与口径。

