#!/usr/bin/env python3
"""
股票数据本地缓存系统 V3 - 支持增量更新 + 可读文件名
- 自动缓存下载的K线数据
- 支持增量更新（只下载新数据）
- 缓存文件使用股票代码命名，便于识别
"""

import os
import json
import pickle
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# 缓存目录
_STOCK_DIR = Path(__file__).parent
_BASE_DIR = _STOCK_DIR.parent
CACHE_DIR = _BASE_DIR / ".stock_cache"
CACHE_DIR.mkdir(exist_ok=True)

def normalize_symbol(symbol):
    """标准化股票代码格式"""
    # 移除前缀，统一格式
    symbol = str(symbol).strip().lower()
    symbol = re.sub(r'^(sh|sz)', '', symbol)
    return symbol

def get_cache_filename(symbol, adjust):
    """生成可读的缓存文件名"""
    symbol_clean = normalize_symbol(symbol)
    return f"{symbol_clean}_{adjust}"

def get_cache_path(symbol, adjust):
    """获取缓存文件路径"""
    filename = get_cache_filename(symbol, adjust)
    return CACHE_DIR / f"{filename}.pkl"

def get_metadata_path(symbol, adjust):
    """获取元数据文件路径"""
    filename = get_cache_filename(symbol, adjust)
    return CACHE_DIR / f"{filename}_meta.json"

def load_cache_metadata(symbol, adjust):
    """加载缓存元数据"""
    meta_path = get_metadata_path(symbol, adjust)
    
    if not meta_path.exists():
        return None
    
    try:
        with open(meta_path, 'r') as f:
            return json.load(f)
    except:
        return None

def load_cached_data(symbol, adjust):
    """从缓存加载完整数据"""
    cache_path = get_cache_path(symbol, adjust)
    symbol_clean = normalize_symbol(symbol)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'rb') as f:
            df = pickle.load(f)
        
        # 统一列名格式
        column_mapping = {
            '日期': 'date', 'date': 'date',
            '开盘': 'open', 'open': 'open',
            '收盘': 'close', 'close': 'close',
            '最高': 'high', 'high': 'high',
            '最低': 'low', 'low': 'low',
            '换手率': 'turnover', 'turnover': 'turnover',
            '成交量': 'volume', 'volume': 'volume',
            '成交额': 'amount', 'amount': 'amount'
        }
        
        # 重命名列
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df = df.rename(columns={old_col: new_col})
        
        print(f"📂 从缓存加载: {symbol_clean} ({len(df)} 行)")
        return df
    except Exception as e:
        print(f"⚠️ 缓存加载失败: {e}")
        return None

def save_cache(df, symbol, adjust):
    """保存数据到缓存"""
    cache_path = get_cache_path(symbol, adjust)
    meta_path = get_metadata_path(symbol, adjust)
    symbol_clean = normalize_symbol(symbol)
    
    # 保存数据
    with open(cache_path, 'wb') as f:
        pickle.dump(df, f)
    
    # 保存元数据
    latest_date = df['date'].max() if 'date' in df.columns else str(datetime.now().date())
    earliest_date = df['date'].min() if 'date' in df.columns else str(datetime.now().date())
    
    metadata = {
        'symbol': symbol_clean,
        'adjust': adjust,
        'cached_at': datetime.now().isoformat(),
        'latest_date': str(latest_date),
        'earliest_date': str(earliest_date),
        'rows': len(df),
        'cache_file': str(cache_path),
        'version': '3.0'
    }
    
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"💾 已缓存: {cache_path.name} ({len(df)} 行, {earliest_date} ~ {latest_date})")

def fetch_with_retry(symbol_ak, start_date, end_date, adjust="qfq", max_retries=3):
    """
    带重试机制的股票数据获取函数（使用新浪财经接口）
    
    Parameters:
        symbol_ak: akshare格式的股票代码（如sh000001）
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权方式
        max_retries: 最大重试次数
    
    Returns:
        DataFrame with stock data
    """
    import akshare as ak
    
    for attempt in range(max_retries):
        try:
            # 使用新浪财经接口
            # 注意：上证指数（sh000001）的复权数据可能有问题，需要特殊处理
            df = ak.stock_zh_a_daily(symbol=symbol_ak, start_date=start_date, end_date=end_date, adjust=adjust)
            
            return df
        except Exception as e:
            # 如果是上证指数的复权数据问题，尝试获取不复权数据
            if symbol_ak == 'sh000001' and adjust in ['qfq', 'hfq'] and 'Length mismatch' in str(e):
                print(f"⚠️  上证指数复权数据异常，尝试获取不复权数据...")
                try:
                    df = ak.stock_zh_a_daily(symbol=symbol_ak, start_date=start_date, end_date=end_date, adjust='')
                    print(f"✅  成功获取上证指数不复权数据")
                    return df
                except Exception as e2:
                    print(f"❌  获取上证指数不复权数据也失败: {e2}")
                    raise e2
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"⚠️  第{attempt+1}次获取失败: {e}, {wait_time}秒后重试...")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ 所有{max_retries}次尝试均失败: {e}")
                raise e

def get_stock_data(symbol, adjust="qfq", force_update=False):
    """
    获取股票数据（支持增量更新 + 可读缓存文件名）
    
    Parameters:
        symbol: 股票代码 (如 "603716", "sh603716", "000547")
        adjust: 复权方式 ("qfq" 前复权)
        force_update: 强制更新（忽略缓存）
    
    Returns:
        DataFrame with OHLCV data
    """
    import akshare as ak
    
    symbol_clean = normalize_symbol(symbol)
    
    # 标准化代码格式（用于akshare）
    if symbol_clean.startswith('6'):
        symbol_ak = f"sh{symbol_clean}"
    else:
        symbol_ak = f"sz{symbol_clean}"
    
    # 尝试加载缓存
    cached_df = None
    if not force_update:
        cached_df = load_cached_data(symbol_clean, adjust)
    
    # 如果有缓存，检查是否需要增量更新
    if cached_df is not None and len(cached_df) > 0:
        cached_df['date'] = pd.to_datetime(cached_df['date'])
        latest_cached_date = cached_df['date'].max()
        today = pd.Timestamp.now().normalize()
        
        # 判断是否需要更新
        need_update = False
        if today.weekday() < 5:  # 周一到周五
            if latest_cached_date < today:
                need_update = True
                print(f"📅 缓存最新: {latest_cached_date.date()}, 今天: {today.date()}")
                print(f"🔄 增量更新...")
        
        if not need_update:
            print(f"✅ 缓存已是最新")
            return cached_df
        
        # 增量更新
        try:
            print(f"🌐 下载新数据: {symbol_clean}...")
            # 使用新浪财经接口获取最新数据
            # 获取最近一年的数据以确保覆盖所有新数据
            today = pd.Timestamp.now().normalize()
            one_year_ago = today - pd.Timedelta(days=365)
            
            new_df = ak.stock_zh_a_daily(symbol=symbol_ak, 
                                         start_date=one_year_ago.strftime('%Y%m%d'), 
                                         end_date=today.strftime('%Y%m%d'), 
                                         adjust=adjust)
            new_df['date'] = pd.to_datetime(new_df['date'])
            
            # 筛选出新数据
            new_data = new_df[new_df['date'] > latest_cached_date]
            
            if len(new_data) > 0:
                combined_df = pd.concat([cached_df, new_data], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                combined_df = combined_df.sort_values('date').reset_index(drop=True)
                
                print(f"✅ 更新完成: +{len(new_data)} 条 ({len(cached_df)} → {len(combined_df)})")
                save_cache(combined_df, symbol_clean, adjust)
                return combined_df
            else:
                print(f"✅ 无新数据")
                return cached_df
                
        except Exception as e:
            print(f"⚠️ 更新失败: {e}")
            return cached_df
    
    else:
        # 无缓存，全量下载
        print(f"🌐 下载数据: {symbol_clean}...")
        try:
            # 使用新浪财经接口
            # 获取最近5年的数据
            today = pd.Timestamp.now().normalize()
            five_years_ago = today - pd.Timedelta(days=5*365)
            
            df = ak.stock_zh_a_daily(symbol=symbol_ak, 
                                     start_date=five_years_ago.strftime('%Y%m%d'), 
                                     end_date=today.strftime('%Y%m%d'), 
                                     adjust=adjust)
            df['date'] = pd.to_datetime(df['date'])
            
            if len(df) > 0:
                save_cache(df, symbol_clean, adjust)
                return df
            else:
                return None
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return None

def list_cached_stocks():
    """列出所有已缓存的股票"""
    stocks = []
    for meta_file in CACHE_DIR.glob("*_meta.json"):
        try:
            with open(meta_file, 'r') as f:
                metadata = json.load(f)
            
            if metadata.get('version', '').startswith('3.'):
                stocks.append({
                    'symbol': metadata['symbol'],
                    'adjust': metadata['adjust'],
                    'latest_date': metadata.get('latest_date', 'N/A'),
                    'earliest_date': metadata.get('earliest_date', 'N/A'),
                    'rows': metadata['rows'],
                    'cached_at': metadata['cached_at'][:10]
                })
        except:
            pass
    
    return sorted(stocks, key=lambda x: x['symbol'])

def get_cache_stats():
    """获取缓存统计信息"""
    stocks = list_cached_stocks()
    total_size = 0
    
    for stock in stocks:
        cache_path = get_cache_path(stock['symbol'], stock['adjust'])
        if cache_path.exists():
            total_size += cache_path.stat().st_size
    
    return {
        'total_stocks': len(stocks),
        'total_size_mb': total_size / (1024 * 1024),
        'stocks': stocks
    }

def delete_cache(symbol, adjust="qfq"):
    """删除指定股票的缓存"""
    symbol_clean = normalize_symbol(symbol)
    cache_path = get_cache_path(symbol_clean, adjust)
    meta_path = get_metadata_path(symbol_clean, adjust)
    
    deleted = False
    if cache_path.exists():
        cache_path.unlink()
        deleted = True
    if meta_path.exists():
        meta_path.unlink()
        deleted = True
    
    if deleted:
        print(f"🗑️ 已删除 {symbol_clean} 的缓存")
    else:
        print(f"⚠️ {symbol_clean} 无缓存")

def clear_all_cache():
    """清理所有缓存"""
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(exist_ok=True)
        print("🗑️ 所有缓存已清理")

if __name__ == "__main__":
    print("=" * 70)
    print("股票数据缓存系统 V3 - 可读文件名")
    print("=" * 70)
    
    # 测试不同格式的代码输入
    test_symbols = ["603716", "sh603716", "000547", "sz000547"]
    
    for symbol in test_symbols:
        print(f"\n[测试] 代码: {symbol}")
        print(f"  标准化: {normalize_symbol(symbol)}")
        print(f"  缓存文件名: {get_cache_filename(symbol, 'qfq')}.pkl")
    
    # 显示当前缓存
    print("\n" + "=" * 70)
    print("当前缓存列表")
    print("=" * 70)
    
    stats = get_cache_stats()
    print(f"\n共 {stats['total_stocks']} 只股票, {stats['total_size_mb']:.2f} MB\n")
    
    for stock in stats['stocks']:
        print(f"📁 {stock['symbol']}_{stock['adjust']}.pkl")
        print(f"   数据: {stock['earliest_date']} ~ {stock['latest_date']} ({stock['rows']} 行)")
        print(f"   缓存时间: {stock['cached_at']}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
