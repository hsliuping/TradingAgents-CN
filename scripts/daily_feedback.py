#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事后反馈学习器 (离线, 不侵入主链路, 自包含)
================================================
设计原则:
  1. 只读 results/{ticker}/{date}/reports/*.md, 不修改主链路任何代码
  2. 增量更新: 每日只对新报告解析, 累加到 panel_data.csv
  3. 拉取事后股价, 更新 forward_return, 重算因子 IC
  4. 输出反馈报告到 results_analysis/feedback/{YYYY-MM-DD}.md
  5. 自包含: 不依赖 analyze_results.py 等其他脚本
  6. 适合 cron / launchd 每日执行

使用方式:
  # 全量重建 (首次运行或重大变更)
  python3 scripts/daily_feedback.py --rebuild

  # 增量更新 (日常使用)
  python3 scripts/daily_feedback.py

  # 只更新股价, 不重新解析报告
  python3 scripts/daily_feedback.py --price-only

  # 指定回看天数
  python3 scripts/daily_feedback.py --lookback 7

输出:
  results_analysis/panel_data.csv          (累加的因子快照)
  results_analysis/feedback/
    ├─ latest.md                            (最新反馈报告)
    ├─ {YYYY-MM-DD}.md                      (每日归档)
    ├─ factor_ic_trend.csv                  (因子 IC 历史趋势)
    └─ decision_performance_trend.csv        (决策表现趋势)
"""
import argparse
import json
import os
import re
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')

# ============== 路径 ==============
ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / 'results'
OUT_DIR = ROOT / 'results_analysis'
FEEDBACK_DIR = OUT_DIR / 'feedback'
PANEL_CSV = OUT_DIR / 'panel_data.csv'
TODAY = datetime.now().date()

# 多周期 (交易日)
HORIZONS = [1, 3, 5, 10, 15, 20]


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')


# ============== 0. 报告解析器 (自包含, 简化版) ==============
def _search_float(pattern, text, default=np.nan):
    """正则提取浮点数"""
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return float(m.group(1))
    except (ValueError, IndexError):
        return default


def _search_str(pattern, text, default=''):
    m = re.search(pattern, text)
    return m.group(1) if m else default


def _clean_text(text):
    """清理 markdown 报告中的强调符号"""
    return text.replace('**', '').replace('*', '').replace('￥', '¥')


def parse_market_report(path):
    """解析市场分析报告(技术指标为主)"""
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        t = _clean_text(f.read())

    out = {}
    # 当前价格(支持多种格式)
    out['current_price'] = _search_float(r'当前价格[：:\s]*[¥￥\s]*([\d.]+)', t)
    if np.isnan(out['current_price']):
        out['current_price'] = _search_float(r'当前价格\s*\|\s*[¥￥]?\s*([\d.]+)', t)
    if np.isnan(out['current_price']):
        out['current_price'] = _search_float(r'收盘价[报：:\s]*[¥￥\s]*([\d.]+)', t)

    # 涨跌幅
    out['change_pct'] = _search_float(r'涨跌幅[：:\s]*([-\d.]+)\s*%?', t)
    out['change_amt'] = _search_float(r'涨跌额[：:\s]*([-\d.]+)', t)
    out['volume_5d_avg'] = _search_float(r'5\s*日均量[：:\s]*([\d.]+)', t)

    # 均线
    for k in [5, 10, 20, 60]:
        out[f'ma{k}'] = _search_float(rf'MA{k}[：:\s]*([\d.]+)', t)
        out[f'price_vs_ma{k}'] = _search_float(rf'价格/MA{k}[：:\s]*([-\d.]+)', t)
        if np.isnan(out[f'price_vs_ma{k}']):
            out[f'price_vs_ma{k}'] = _search_float(rf'价格相对MA{k}[：:\s]*([-\d.]+)', t)

    # MACD
    out['macd_dif'] = _search_float(r'DIF[：:\s]*([-\d.]+)', t)
    out['macd_dea'] = _search_float(r'DEA[：:\s]*([-\d.]+)', t)
    out['macd_hist'] = _search_float(r'MACD[柱柱线]?[：:\s]*([-\d.]+)', t)

    # RSI
    for k in [6, 12, 24]:
        out[f'rsi{k}'] = _search_float(rf'RSI{k}[：:\s]*([\d.]+)', t)

    # 布林带
    out['boll_upper'] = _search_float(r'布林带上轨[：:\s]*([\d.]+)', t)
    out['boll_lower'] = _search_float(r'布林带下轨[：:\s]*([\d.]+)', t)
    out['boll_middle'] = _search_float(r'布林带中轨[：:\s]*([\d.]+)', t)
    out['boll_pos'] = _search_float(r'布林带位置[：:\s]*([-\d.]+)', t)

    # 衍生标志
    out['macd_golden_cross'] = 1 if '金叉' in t else 0
    out['rsi6_oversold'] = 1 if out.get('rsi6', 100) < 30 else 0
    out['rsi6_overbought'] = 1 if out.get('rsi6', 0) > 70 else 0
    out['ma_bullish_align'] = 1 if (out.get('ma5', 0) > out.get('ma10', 0) > out.get('ma20', 0)) else 0
    out['rsi6_above_50'] = 1 if out.get('rsi6', 0) > 50 else 0

    return out


def parse_fundamentals_report(path):
    """解析基本面报告(估值指标)"""
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        t = _clean_text(f.read())

    out = {}
    out['pe'] = _search_float(r'(?:市盈率|PE)[（(]TTM[)）]?[：:\s]*([\d.]+)', t)
    if np.isnan(out['pe']):
        out['pe'] = _search_float(r'(?:市盈率|PE)[：:\s]*([\d.]+)', t)
    out['pe_ttm'] = _search_float(r'PE\s*\(TTM\)[：:\s]*([\d.]+)', t)
    out['pb'] = _search_float(r'(?:市净率|PB)[：:\s]*([\d.]+)', t)
    out['ps'] = _search_float(r'(?:市销率|PS)[：:\s]*([\d.]+)', t)
    out['market_cap'] = _search_float(r'(?:总市值|市值)[：:\s]*([\d.]+)\s*亿?', t)
    out['circ_market_cap'] = _search_float(r'流通市值[：:\s]*([\d.]+)', t)
    out['dividend_yield'] = _search_float(r'股息率[：:\s]*([\d.]+)\s*%?', t)
    out['industry_pe'] = _search_float(r'行业PE[：:\s]*([\d.]+)', t)
    out['industry_pb'] = _search_float(r'行业PB[：:\s]*([\d.]+)', t)

    # 相对估值
    pe_ind = _search_float(r'PE/行业PE[：:\s]*([\d.]+)', t)
    if np.isnan(pe_ind) and out.get('industry_pe') and out.get('pe'):
        pe_ind = out['pe'] / out['industry_pe']
    out['pe_vs_industry'] = pe_ind
    out['pe_undervalued'] = 1 if (out.get('pe', 999) or 999) < 15 else 0
    out['pb_vs_industry'] = _search_float(r'PB/行业PB[：:\s]*([\d.]+)', t)

    # 最新股价(避免覆盖 market_report 的值, 仅作 fallback)
    fv = _search_float(r'最新股价[^\d]*[¥￥]?\s*([\d.]+)', t)
    if not np.isnan(fv):
        out['_fundamentals_price'] = fv

    return out


def parse_trader_report(path):
    """解析交易员报告(决策)"""
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        t = _clean_text(f.read())

    out = {}
    # 决策
    if re.search(r'最终交易建议[:：\s]*\**\s*买入', t) or '买入' in t[:500]:
        out['action'] = '买入'
    elif re.search(r'最终交易建议[:：\s]*\**\s*卖出', t) or '卖出' in t[:500]:
        out['action'] = '卖出'
    elif '持有' in t[:500]:
        out['action'] = '持有'
    else:
        m = _search_str(r'最终交易建议[:：\s]*\**\s*(\S+)', t)
        out['action'] = m if m else '未知'

    # 目标价 / 止损
    out['target_price'] = _search_float(r'目标价[位格]?[：:\s]*[¥￥]?\s*([\d.]+)', t)
    out['stop_loss'] = _search_float(r'止损[价位]?[：:\s]*[¥￥]?\s*([\d.]+)', t)

    # 预期收益
    out['expected_return'] = _search_float(r'预期(?:涨幅|收益|回报)[：:\s]*([-\d.]+)\s*%?', t)
    out['expected_upside'] = _search_float(r'预期(?:上行|上涨)空间[：:\s]*([-\d.]+)\s*%?', t)

    return out


def parse_single(ticker, date_str, reports_dir):
    """解析一个 (ticker, date) 的所有报告"""
    rec = {'ticker': ticker, 'analysis_date': date_str}
    mr = parse_market_report(os.path.join(reports_dir, 'market_report.md'))
    fr = parse_fundamentals_report(os.path.join(reports_dir, 'fundamentals_report.md'))
    tr = parse_trader_report(os.path.join(reports_dir, 'trader_report.md'))

    rec.update(mr)
    rec.update({k: v for k, v in fr.items() if not k.startswith('_')})
    if 'current_price' not in mr or pd.isna(mr.get('current_price')):
        rec['current_price'] = fr.get('_fundamentals_price', np.nan)
    rec.update(tr)
    return rec


def parse_all_reports(results_dir=RESULTS_DIR):
    """全量解析 results 目录下的所有报告"""
    records = []
    if not os.path.isdir(results_dir):
        return pd.DataFrame()
    for ticker in sorted(os.listdir(results_dir)):
        tp = os.path.join(results_dir, ticker)
        if not os.path.isdir(tp):
            continue
        for date in sorted(os.listdir(tp)):
            dp = os.path.join(tp, date, 'reports')
            if not os.path.isdir(dp):
                continue
            try:
                rec = parse_single(ticker, date, dp)
                if rec.get('action') and rec.get('action') != '未知':
                    records.append(rec)
            except Exception as e:
                log(f'  [警告] {ticker}@{date} 解析失败: {e}')
    df = pd.DataFrame(records)
    if not df.empty:
        df['analysis_date'] = pd.to_datetime(df['analysis_date'])
    return df


# ============== 1. 增量解析 ==============
def rebuild_panel():
    log('全量重建 panel data...')
    df = parse_all_reports()
    if df.empty:
        log('  无可用报告')
        return df
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PANEL_CSV, index=False, encoding='utf-8-sig')
    log(f'  已保存 {len(df)} 条记录 → {PANEL_CSV}')
    return df


def incremental_update_panel():
    """增量更新: 只解析 panel_data.csv 中不存在的 (ticker, date)"""
    if PANEL_CSV.exists():
        existing = pd.read_csv(PANEL_CSV, dtype={'ticker': str})
        existing['analysis_date'] = pd.to_datetime(existing['analysis_date'])
        existing_keys = set(zip(existing['ticker'].astype(str),
                                existing['analysis_date'].dt.strftime('%Y-%m-%d')))
    else:
        existing = pd.DataFrame()
        existing_keys = set()

    new_records = []
    if not RESULTS_DIR.exists():
        log(f'  results 目录不存在: {RESULTS_DIR}')
        return existing

    for ticker in sorted(os.listdir(RESULTS_DIR)):
        tp = RESULTS_DIR / ticker
        if not tp.is_dir():
            continue
        for date in sorted(os.listdir(tp)):
            dp = tp / date / 'reports'
            if not dp.is_dir():
                continue
            if (ticker, date) in existing_keys:
                continue
            log(f'  发现新报告: {ticker} @ {date}')
            try:
                rec = parse_single(ticker, date, str(dp))
                if rec.get('action') and rec.get('action') != '未知':
                    new_records.append(rec)
            except Exception as e:
                log(f'    [警告] 解析失败: {e}')

    if new_records:
        new_df = pd.DataFrame(new_records)
        new_df['analysis_date'] = pd.to_datetime(new_df['analysis_date'])
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['ticker', 'analysis_date']).sort_values(['analysis_date', 'ticker'])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        combined.to_csv(PANEL_CSV, index=False, encoding='utf-8-sig')
        log(f'  新增 {len(new_records)} 条, 总计 {len(combined)} 条')
        return combined
    else:
        log('  无新报告')
        return existing


# ============== 2. 拉取事后股价 ==============
def fetch_price(ticker, start, end, max_retries=3):
    code = str(ticker).zfill(6)
    for i in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period='daily',
                                    start_date=start.replace('-', ''),
                                    end_date=end.replace('-', ''), adjust='qfq')
            if df is None or len(df) == 0:
                return pd.DataFrame()
            df['日期'] = pd.to_datetime(df['日期'])
            return df.sort_values('日期').reset_index(drop=True)[['日期', '收盘', '最高', '最低']]
        except Exception as e:
            wait = (i + 1) * 2
            log(f'  [重试 {i+1}/{max_retries}] {ticker}: {e}, 等 {wait}s')
            time.sleep(wait)
    return pd.DataFrame()


def update_forward_returns(df, lookback_days=30):
    """为最近 lookback_days 内的决策补全 forward_return"""
    cache_file = OUT_DIR / 'factor_validation' / 'post_price_cache.json'
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if cache_file.exists():
        with open(cache_file) as f:
            cache = json.load(f)

    df = df.copy()
    df['analysis_date'] = pd.to_datetime(df['analysis_date'])

    cutoff = pd.Timestamp(TODAY) - timedelta(days=lookback_days + 30)
    mask = (df['analysis_date'] >= cutoff) & (df['action'].isin(['买入', '卖出', '持有']))
    to_update = df[mask]
    log(f'需要更新事后收益的样本: {len(to_update)} 条 (最近 {lookback_days} 天)')

    for h in HORIZONS:
        col = f'fwd_ret_{h}d'
        if col not in df.columns:
            df[col] = np.nan

    updated = 0
    for idx, row in to_update.iterrows():
        ticker = str(row['ticker'])
        eval_date = row['analysis_date']
        eval_price = row.get('current_price')
        if pd.isna(eval_price) or eval_price is None:
            continue
        eval_price = float(eval_price)

        cache_key = f'{ticker}_{eval_date.strftime("%Y-%m-%d")}'
        end_date = (pd.Timestamp(TODAY) + timedelta(days=3)).strftime('%Y-%m-%d')
        start_date = eval_date.strftime('%Y-%m-%d')

        need_fetch = True
        if cache_key in cache:
            cached = cache[cache_key]
            cached_dates = cached.get('dates', [])
            if cached_dates:
                last_cached = pd.to_datetime(cached_dates[-1])
                if (pd.Timestamp(TODAY) - last_cached).days <= 4:
                    need_fetch = False

        if need_fetch:
            pdf = fetch_price(ticker, start_date, end_date)
            if pdf.empty:
                continue
            cache[cache_key] = {
                'dates': pdf['日期'].dt.strftime('%Y-%m-%d').tolist(),
                'close': pdf['收盘'].tolist(),
                'high': pdf['最高'].tolist(),
                'low': pdf['最低'].tolist(),
            }
            with open(cache_file, 'w') as f:
                json.dump(cache, f)
            time.sleep(0.3)
        else:
            cached = cache[cache_key]
            pdf = pd.DataFrame({
                '日期': pd.to_datetime(cached['dates']),
                '收盘': cached['close'],
                '高': cached['high'],
                '低': cached['low'],
            })

        post = pdf[pdf['日期'] >= eval_date].reset_index(drop=True)
        if len(post) == 0:
            continue
        for h in HORIZONS:
            if len(post) > h:
                df.loc[idx, f'fwd_ret_{h}d'] = post.iloc[h]['收盘'] / eval_price - 1
        updated += 1

    log(f'  更新了 {updated} 条样本的事后收益')
    df.to_csv(PANEL_CSV, index=False, encoding='utf-8-sig')
    return df


# ============== 3. 因子 IC 与决策表现 ==============
def compute_factor_ic(df, target='fwd_ret_5d'):
    factor_cols = [
        'pe', 'pb', 'market_cap', 'dividend_yield', 'pe_vs_industry', 'pb_vs_industry',
        'industry_pe', 'industry_pb', 'pe_undervalued',
        'rsi6', 'rsi12', 'rsi24', 'macd_dif', 'macd_dea', 'macd_hist',
        'price_vs_ma5', 'price_vs_ma10', 'price_vs_ma20', 'price_vs_ma60',
        'boll_pos', 'change_pct', 'volume_5d_avg',
        'ma_bullish_align', 'macd_golden_cross', 'rsi6_oversold', 'rsi6_overbought',
        'expected_return', 'expected_upside',
    ]
    factor_cols = [f for f in factor_cols if f in df.columns]
    rows = []
    valid = df.dropna(subset=[target])
    for f in factor_cols:
        s = valid[[f, target]].dropna()
        if len(s) < 5:
            rows.append({'factor': f, 'n': len(s), 'ic': np.nan, 'p_value': np.nan})
            continue
        try:
            r, p = stats.pearsonr(s[f], s[target])
            r, p = float(r), float(p)
        except Exception:
            r, p = np.nan, np.nan
        rows.append({'factor': f, 'n': len(s), 'ic': r, 'p_value': p})
    return pd.DataFrame(rows)


def compute_agent_performance(df):
    buy = df[df['action'] == '买入']
    rows = []
    for h in HORIZONS:
        col = f'fwd_ret_{h}d'
        if col not in buy.columns:
            continue
        s = buy[col].dropna()
        if len(s) == 0:
            continue
        rows.append({
            'horizon': f'{h}d', 'n': len(s),
            'win_rate': (s > 0).mean(), 'avg_return': s.mean(),
            'median_return': s.median(), 'min_return': s.min(),
            'max_return': s.max(), 'std': s.std(),
        })
    return pd.DataFrame(rows)


# ============== 4. 反馈报告 ==============
def generate_feedback_report(df, target='fwd_ret_5d'):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    today_str = TODAY.strftime('%Y-%m-%d')

    ic_df = compute_factor_ic(df, target=target)
    perf_df = compute_agent_performance(df)

    df['analysis_date'] = pd.to_datetime(df['analysis_date'])
    recent_buy = df[(df['action'] == '买入') &
                    (df['analysis_date'] >= pd.Timestamp(TODAY) - timedelta(days=30))]
    recent_buy_ret = recent_buy.dropna(subset=[target])

    lines = []
    lines.append(f'# 事后反馈学习报告 - {today_str}\n')
    lines.append(f'> 自动生成, 不侵入主链路. 源数据: `results/` 下的 markdown 报告\n')
    lines.append(f'> 样本总数: {len(df)}, 其中买入: {len(df[df["action"]=="买入"])}, '
                 f'卖出: {len(df[df["action"]=="卖出"])}, 持有: {len(df[df["action"]=="持有"])}\n')

    lines.append('## 1. 最近 30 天买入决策表现\n')
    if len(recent_buy_ret) > 0:
        s = recent_buy_ret[target]
        lines.append(f'- 样本数: {len(s)}')
        lines.append(f'- 胜率: **{(s > 0).mean():.1%}**')
        lines.append(f'- 平均收益: **{s.mean():+.2%}**')
        lines.append(f'- 中位收益: {s.median():+.2%}')
        lines.append(f'- 区间: [{s.min():+.2%}, {s.max():+.2%}]\n')
    else:
        lines.append('- 暂无足够事后数据\n')

    lines.append('## 2. 多周期持有表现\n')
    if not perf_df.empty:
        lines.append('| 周期 | n | 胜率 | 均值 | 中位 | 最大 | 最小 |')
        lines.append('|:---:|:---:|:---:|:---:|:---:|:---:|:---:|')
        for _, r in perf_df.iterrows():
            lines.append(f'| {r["horizon"]} | {r["n"]} | {r["win_rate"]:.1%} | '
                         f'{r["avg_return"]:+.2%} | {r["median_return"]:+.2%} | '
                         f'{r["max_return"]:+.2%} | {r["min_return"]:+.2%} |')
        lines.append('')
    else:
        lines.append('- 暂无事后收益数据\n')

    lines.append(f'## 3. 因子 IC 排名 (基于 {target})\n')
    ic_valid = ic_df.dropna(subset=['ic']).sort_values('ic', key=lambda s: s.abs(), ascending=False)
    if not ic_valid.empty:
        lines.append('| 排名 | 因子 | n | IC | p 值 | 方向 |')
        lines.append('|:---:|:---|:---:|:---:|:---:|:---:|')
        for i, (_, r) in enumerate(ic_valid.head(15).iterrows(), 1):
            direction = '正向' if r['ic'] > 0 else '负向'
            lines.append(f'| {i} | {r["factor"]} | {r["n"]} | {r["ic"]:+.3f} | {r["p_value"]:.3f} | {direction} |')
        lines.append('')
    else:
        lines.append('- 暂无足够样本计算 IC\n')

    lines.append('## 4. 行动建议\n')
    if not perf_df.empty:
        h5 = perf_df[perf_df['horizon'] == '5d']
        if not h5.empty and len(h5) == 1:
            win_rate = h5.iloc[0]['win_rate']
            avg_ret = h5.iloc[0]['avg_return']
            if win_rate < 0.4 and avg_ret < -0.02:
                lines.append('- ⚠️ **5 日胜率 < 40% 且平均亏损 > 2%, 建议检视 trader 决策逻辑**')
                lines.append('- 考虑启用「市场状态过滤器」: 大盘弱市时禁买')
                lines.append('- 考虑增加止损: 1 日内 -3% 硬止损, 5 日内 -5% 移动止损')
            elif win_rate > 0.6 and avg_ret > 0.02:
                lines.append('- ✅ **5 日胜率 > 60% 且平均盈利 > 2%, 当前策略表现良好**')
            else:
                lines.append('- ➖ 当前策略表现中性, 继续观察')
            lines.append('')

    # 累积 IC 历史
    ic_trend_csv = FEEDBACK_DIR / 'factor_ic_trend.csv'
    ic_trend = pd.read_csv(ic_trend_csv) if ic_trend_csv.exists() else pd.DataFrame()
    if not ic_valid.empty:
        new_record = {'date': today_str}
        for _, r in ic_valid.iterrows():
            new_record[r['factor']] = r['ic']
        ic_trend = pd.concat([ic_trend, pd.DataFrame([new_record])], ignore_index=True)
        ic_trend = ic_trend.drop_duplicates(subset=['date'], keep='last')
        ic_trend.to_csv(ic_trend_csv, index=False, encoding='utf-8-sig')

    # 累积决策表现历史
    perf_trend_csv = FEEDBACK_DIR / 'decision_performance_trend.csv'
    if not perf_df.empty:
        h5 = perf_df[perf_df['horizon'] == '5d']
        if not h5.empty:
            new_record = {
                'date': today_str,
                'sample_5d': h5.iloc[0]['n'],
                'win_rate_5d': h5.iloc[0]['win_rate'],
                'avg_return_5d': h5.iloc[0]['avg_return'],
            }
            perf_trend = pd.read_csv(perf_trend_csv) if perf_trend_csv.exists() else pd.DataFrame()
            perf_trend = pd.concat([perf_trend, pd.DataFrame([new_record])], ignore_index=True)
            perf_trend = perf_trend.drop_duplicates(subset=['date'], keep='last')
            perf_trend.to_csv(perf_trend_csv, index=False, encoding='utf-8-sig')

    content = '\n'.join(lines)
    today_file = FEEDBACK_DIR / f'{today_str}.md'
    with open(today_file, 'w', encoding='utf-8') as f:
        f.write(content)
    latest_file = FEEDBACK_DIR / 'latest.md'
    with open(latest_file, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f'  反馈报告已生成: {today_file}')
    log(f'  最新报告链接: {latest_file}')

    print('\n' + '=' * 60)
    print(content)
    print('=' * 60)


# ============== 主流程 ==============
def main():
    parser = argparse.ArgumentParser(description='事后反馈学习器 (离线, 不侵入主链路)')
    parser.add_argument('--rebuild', action='store_true', help='全量重建 panel_data')
    parser.add_argument('--price-only', action='store_true', help='只更新股价, 不重新解析报告')
    parser.add_argument('--lookback', type=int, default=30, help='回看天数 (默认 30)')
    args = parser.parse_args()

    log('=' * 60)
    log('TradingAgents-CN 事后反馈学习器 (离线)')
    log(f'今日: {TODAY}, 回看: {args.lookback} 天')
    log('=' * 60)

    # Step 1: 解析报告
    if args.rebuild:
        df = rebuild_panel()
    elif args.price_only:
        if not PANEL_CSV.exists():
            log('  panel_data.csv 不存在, 自动全量重建')
            df = rebuild_panel()
        else:
            df = pd.read_csv(PANEL_CSV, dtype={'ticker': str})
            df['analysis_date'] = pd.to_datetime(df['analysis_date'])
    else:
        df = incremental_update_panel()

    if df.empty:
        log('panel_data 为空, 退出')
        return

    # Step 2: 更新事后收益
    df = update_forward_returns(df, lookback_days=args.lookback)

    # Step 3+4: 重算 IC, 生成反馈报告
    generate_feedback_report(df, target='fwd_ret_5d')

    log('\n完成. 所有输出位于: results_analysis/feedback/')


if __name__ == '__main__':
    main()
