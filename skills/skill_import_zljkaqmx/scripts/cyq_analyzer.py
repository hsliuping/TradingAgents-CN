#!/usr/bin/env python3
"""
CYQ筹码分布模型 - 最终版
基于原始算法，保留实用改进

核心算法：
- 当日典型价格 = (Open + High + Low + Close) / 4
- 历史筹码衰减 = (1 - 换手率) 线性衰减
- 分布假设 = 三角分布
- 价格步长 = 0.1 
- 默认天数 = 180

使用方法:
    python3 cyq_final.py 002213
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.font_manager as fm
matplotlib.use('Agg')  # 非交互式后端
import akshare as ak
import os
import pickle
from datetime import datetime

# 设置中文字体（兼容多平台）
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
try:
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP']
    else:
        # Windows / macOS 回退：使用系统已安装的常见中文字体
        plt.rcParams['font.sans-serif'] = [
            'Microsoft YaHei', 'SimHei', 'PingFang SC',
            'Hiragino Sans GB', 'WenQuanYi Micro Hei', 'DejaVu Sans'
        ]
except Exception:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

_STOCK_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.dirname(_STOCK_DIR)
CACHE_DIR = os.path.join(_BASE_DIR, ".stock_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def load_cached_data(stock_code, max_age_days=1):
    """加载缓存数据"""
    cache_path = os.path.join(CACHE_DIR, f"{stock_code}.pkl")
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            cached = pickle.load(f)
        cache_time = cached.get('timestamp')
        if cache_time and (datetime.now() - cache_time).days < max_age_days:
            return cached['data']
    return None


def save_cached_data(stock_code, data):
    """保存数据到缓存"""
    cache_path = os.path.join(CACHE_DIR, f"{stock_code}.pkl")
    with open(cache_path, 'wb') as f:
        pickle.dump({'timestamp': datetime.now(), 'data': data}, f)


def _fetch_raw_data(stock_code, max_days=500):
    """拉取原始数据（尽可能多的天数）"""
    from stock_cache_v3 import get_stock_data as get_stock_data_v3
    
    df = get_stock_data_v3(stock_code, adjust="qfq", force_update=False)
    
    if df is None or len(df) == 0:
        return None
    
    # 确保列名正确
    column_mapping = {
        'date': 'date',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'turnover': 'turnover'
    }
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    # 确保有turnover列
    if 'turnover' not in df.columns:
        df['turnover'] = 0.01
    
    # 确保数据类型正确
    numeric_cols = ['open', 'high', 'low', 'close', 'turnover']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    try:
        df = df.fillna(method='ffill').fillna(method='bfill')
    except:
        df = df.fillna(0)
    
    if 'date' in df.columns:
        df = df.sort_values('date').reset_index(drop=True)
    
    # 只取最近max_days
    if len(df) > max_days:
        df = df.tail(max_days).reset_index(drop=True)
    
    return df


def fetch_stock_data(stock_code, days=180):
    """获取股票数据（兼容旧接口，使用新缓存模型）"""
    try:
        df = _fetch_raw_data(stock_code, max_days=500)
        if df is None:
            return None
        # 返回指定天数的数据
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"⚠️ fetch_stock_data 失败: {e}")
        return None


def parse_turnover(value):
    """解析换手率，自动识别百分比或小数格式"""
    if pd.isna(value):
        return 0.0
    value = float(value)
    return value / 100 if value > 1 else value


def calculate_cyq(df, price_step=0.1, min_price_bins=100):
    """
    计算筹码分布 (CYQ)
    
    参数:
        df: DataFrame with columns ['open', 'high', 'low', 'close', 'turnover']
        price_step: 价格步长（默认0.1）
        min_price_bins: 最小价格区间数
    """
    n_days = len(df)
    if n_days == 0:
        return None
    
    min_price = df['low'].min()
    max_price = df['high'].max()
    price_range = max_price - min_price
    
    n_bins = max(int(price_range / price_step) + 1, min_price_bins)
    price_bins = np.linspace(min_price, max_price, n_bins)
    
    chip_distribution = np.zeros(n_bins - 1)
    
    for i in range(n_days):
        day = df.iloc[i]
        open_p, high, low, close = day['open'], day['high'], day['low'], day['close']
        turnover = parse_turnover(day['turnover'])
        
        # 当日典型价格 (OHLC)/4
        typical_price = (open_p + high + low + close) / 4
        
        # 三角分布
        a, b, c = low, high, typical_price
        
        for j in range(len(price_bins) - 1):
            bin_center = (price_bins[j] + price_bins[j+1]) / 2
            
            if bin_center < a:
                density = 0
            elif bin_center < c:
                density = 2 * (bin_center - a) / ((b - a) * (c - a)) if c != a else 0
            elif bin_center <= b:
                density = 2 * (b - bin_center) / ((b - a) * (b - c)) if b != c else 0
            else:
                density = 0
            
            chip_distribution[j] += density * turnover
        
        # 历史筹码衰减
        if i < n_days - 1:
            chip_distribution *= (1 - turnover)
    
    # 归一化
    total = chip_distribution.sum()
    if total > 0:
        chip_distribution /= total
    
    current_price = df['close'].iloc[-1]
    
    # 获利盘比例（当前价以下筹码）
    profit_ratio = chip_distribution[price_bins[:-1] <= current_price].sum()
    
    # 平均成本
    avg_cost = np.sum(price_bins[:-1] * chip_distribution)
    
    # 筹码峰值
    peak_idx = np.argmax(chip_distribution)
    peak_price = price_bins[peak_idx]
    
    # 筹码集中度 - 标准公式（与通达信、同花顺一致）
    # 90%筹码集中度
    cumsum = np.cumsum(chip_distribution)
    idx_5 = np.searchsorted(cumsum, 0.05)
    idx_95 = np.searchsorted(cumsum, 0.95)
    price_low_90 = price_bins[idx_5]
    price_high_90 = price_bins[idx_95]
    if price_high_90 + price_low_90 > 0:
        concentration = (price_high_90 - price_low_90) / (price_high_90 + price_low_90)
    else:
        concentration = 0.0
    
    # 主力成本区（最密集的20%筹码）
    sorted_idx = np.argsort(chip_distribution)[::-1]
    cumsum_sorted = np.cumsum(chip_distribution[sorted_idx])
    main_indices = sorted_idx[cumsum_sorted <= 0.20]
    if len(main_indices) > 0:
        main_low = price_bins[main_indices.min()]
        main_high = price_bins[min(main_indices.max() + 1, len(price_bins) - 1)]
    else:
        main_low = main_high = peak_price
    
    return {
        'price_bins': price_bins[:-1],
        'chip_distribution': chip_distribution,
        'current_price': current_price,
        'profit_ratio': profit_ratio,
        'avg_cost': avg_cost,
        'peak_price': peak_price,
        'concentration': concentration,
        'main_force_low': main_low,
        'main_force_high': main_high,
        'price_low_90': price_low_90,
        'price_high_90': price_high_90,
        'df': df
    }


def plot_cyq(cyq_result, stock_code):
    """绘制筹码分布图 - 中文标签"""
    if cyq_result is None:
        return None
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor='#0d1117')
    fig.suptitle(f'{stock_code} 筹码分析', fontsize=16, fontweight='bold', color='white')
    
    price_bins = cyq_result['price_bins']
    chip_dist = cyq_result['chip_distribution']
    current_price = cyq_result['current_price']
    avg_cost = cyq_result['avg_cost']
    peak_price = cyq_result['peak_price']
    
    # 1. 筹码分布图
    ax1 = axes[0, 0]
    ax1.set_facecolor('#0d1117')
    ax1.barh(price_bins, chip_dist, height=price_bins[1]-price_bins[0], 
             color='#3b82f6', alpha=0.7, edgecolor='none')
    ax1.axhline(y=current_price, color='#ef4444', linestyle='--', linewidth=2, 
                label=f'现价: {current_price:.2f}')
    ax1.axhline(y=avg_cost, color='#f59e0b', linestyle='--', linewidth=2, 
                label=f'均价: {avg_cost:.2f}')
    ax1.axhline(y=peak_price, color='#10b981', linestyle='--', linewidth=2, 
                label=f'峰值: {peak_price:.2f}')
    ax1.set_xlabel('筹码密度', color='white')
    ax1.set_ylabel('价格', color='white')
    ax1.set_title('筹码分布', color='white')
    ax1.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='white')
    ax1.tick_params(colors='white')
    ax1.grid(True, alpha=0.2, color='#30363d')
    for spine in ax1.spines.values():
        spine.set_color('#30363d')
    
    # 2. K线图
    ax2 = axes[0, 1]
    ax2.set_facecolor('#0d1117')
    df = cyq_result['df']
    x = range(len(df))
    ax2.plot(x, df['close'], color='#3b82f6', linewidth=1.5, label='收盘价')
    ax2.fill_between(x, df['low'], df['high'], alpha=0.3, color='#3b82f6')
    ax2.axhline(y=current_price, color='#ef4444', linestyle='--', alpha=0.7)
    ax2.axhline(y=avg_cost, color='#f59e0b', linestyle='--', alpha=0.7)
    ax2.set_xlabel('交易日', color='white')
    ax2.set_ylabel('价格', color='white')
    ax2.set_title('价格走势', color='white')
    ax2.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='white')
    ax2.tick_params(colors='white')
    ax2.grid(True, alpha=0.2, color='#30363d')
    for spine in ax2.spines.values():
        spine.set_color('#30363d')
    
    # 3. 主力成本区
    ax3 = axes[1, 0]
    ax3.set_facecolor('#0d1117')
    ax3.barh(price_bins, chip_dist, height=price_bins[1]-price_bins[0], 
             color='#3b82f6', alpha=0.5, edgecolor='none')
    main_low = cyq_result['main_force_low']
    main_high = cyq_result['main_force_high']
    mask = (price_bins >= main_low) & (price_bins <= main_high)
    ax3.barh(price_bins[mask], chip_dist[mask], height=price_bins[1]-price_bins[0], 
             color='#fbbf24', alpha=0.9, label=f'主力区: {main_low:.2f}-{main_high:.2f}')
    ax3.axhline(y=current_price, color='#ef4444', linestyle='--', linewidth=2)
    ax3.set_xlabel('筹码密度', color='white')
    ax3.set_ylabel('价格', color='white')
    ax3.set_title('主力成本区', color='white')
    ax3.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='white')
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.2, color='#30363d')
    for spine in ax3.spines.values():
        spine.set_color('#30363d')
    
    # 4. 关键指标
    ax4 = axes[1, 1]
    ax4.set_facecolor('#0d1117')
    ax4.axis('off')
    
    metrics = [
        ('现价', f'{current_price:.2f}', '#ef4444'),
        ('获利比例', f'{cyq_result["profit_ratio"]*100:.2f}%', '#10b981'),
        ('均价', f'{avg_cost:.2f}', '#3b82f6'),
        ('峰值', f'{peak_price:.2f}', '#8b5cf6'),
        ('集中度', f'{cyq_result["concentration"]*100:.2f}%', '#ec4899'),
        ('主力区间', f'{main_low:.2f}-{main_high:.2f}', '#fbbf24'),
    ]
    
    y_pos = 0.9
    for label, value, color in metrics:
        ax4.text(0.1, y_pos, label, fontsize=12, color='#9ca3af', transform=ax4.transAxes)
        ax4.text(0.5, y_pos, value, fontsize=14, fontweight='bold', color=color, transform=ax4.transAxes)
        y_pos -= 0.15
    
    plt.tight_layout()
    
    output_path = os.path.join(_BASE_DIR, f"cyq_{stock_code}.png")
    plt.savefig(output_path, dpi=150, facecolor='#0d1117', edgecolor='none')
    plt.close()
    
    return output_path


def analyze_and_plot(stock_code, days=180):
    """分析并绘制筹码分布（固定天数）"""
    df = fetch_stock_data(stock_code, days)
    if df is None:
        return None, None
    
    cyq = calculate_cyq(df, price_step=0.1)
    if cyq is None:
        return None, None

    # 画图是可选的（仅用于人类查看），失败不影响数据分析结果
    output_path = None
    try:
        output_path = plot_cyq(cyq, stock_code)
    except Exception as e:
        print(f"⚠️ 绘图失败（不影响分析数据）: {e}")

    return cyq, output_path


if __name__ == "__main__":
    import sys
    import json
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "002213"
    cyq, output_path = analyze_and_plot(stock_code)

    if cyq is None:
        print(json.dumps({"success": False, "error": "无法计算筹码分布", "stock_code": stock_code}, ensure_ascii=False))
        sys.exit(1)

    # 输出关键指标为 JSON（numpy 数组太大不输出，只输出标量统计）
    result = {
        "success": True,
        "stock_code": stock_code,
        "current_price": float(cyq.get("current_price", 0)),
        "avg_cost": float(cyq.get("avg_cost", 0)),
        "peak_price": float(cyq.get("peak_price", 0)),
        "chart_path": output_path,
    }
    # 兼容更多键：profit_ratio, concentration_90, main_cost_zone 等
    for key in ("profit_ratio", "concentration_90", "concentration_70",
                "main_cost_low", "main_cost_high", "price_range_low", "price_range_high",
                "total_days", "avg_turnover"):
        if key in cyq:
            v = cyq[key]
            try:
                result[key] = float(v) if hasattr(v, "__float__") else v
            except Exception:
                pass

    print(json.dumps(result, ensure_ascii=False, indent=2))
