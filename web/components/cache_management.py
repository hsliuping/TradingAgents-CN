#!/usr/bin/env python3
"""
缓存管理Web组件
提供分析结果缓存的查看、管理功能
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from tradingagents.utils.logging_manager import get_logger
logger = get_logger('cache_management')

try:
    from tradingagents.utils.analysis_cache import get_global_cache, cache_analysis_result, load_cached_analysis, is_analysis_cached
    CACHE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ 缓存模块未加载: {e}")
    CACHE_AVAILABLE = False


def render_cache_management():
    """渲染缓存管理界面"""
    st.markdown("### 📦 分析结果缓存管理")
    
    if not CACHE_AVAILABLE:
        st.error("🚫 缓存系统未就绪")
        st.info("请确保缓存模块正确安装")
        return
    
    cache = get_global_cache()
    
    # 获取缓存统计
    stats = cache.get_cache_stats()
    
    # 显示统计信息
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总缓存数", stats.get('total_files', 0))
    
    with col2:
        st.metric("缓存大小", f"{stats.get('total_size_mb', 0)} MB")
    
    with col3:
        st.metric("股票数量", stats.get('symbol_count', 0))
    
    with col4:
        cache_dir = stats.get('cache_directory', 'unknown')
        st.metric("缓存目录", "已配置" if cache_dir != 'unknown' else "未配置")
    
    st.markdown("---")
    
    # 缓存列表
    st.markdown("#### 📋 缓存列表")
    
    cached_list = cache.list_cached_analyses()
    
    if not cached_list:
        st.info("📭 暂无缓存数据")
        return
    
    # 转换为DataFrame
    df_data = []
    for item in cached_list:
        df_data.append({
            '股票代码': item['symbol'],
            '分析日期': item['date'],
            '文件大小': f"{item['file_size'] / 1024:.1f} KB",
            '修改时间': datetime.fromisoformat(item['modified_time']).strftime('%Y-%m-%d %H:%M'),
            '缓存键': item['cache_key']
        })
    
    df = pd.DataFrame(df_data)
    
    # 筛选选项
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 股票代码筛选
        symbols = ['全部'] + sorted(list(set([item['symbol'] for item in cached_list])))
        selected_symbol = st.selectbox("筛选股票代码", symbols)
    
    with col2:
        # 日期范围筛选
        date_range = st.date_input(
            "筛选日期范围",
            value=(date.today() - timedelta(days=30), date.today()),
            max_value=date.today()
        )
    
    # 应用筛选
    filtered_df = df.copy()
    
    if selected_symbol != '全部':
        filtered_df = filtered_df[filtered_df['股票代码'] == selected_symbol]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['分析日期']) >= pd.Timestamp(start_date)) &
            (pd.to_datetime(filtered_df['分析日期']) <= pd.Timestamp(end_date))
        ]
    
    # 显示筛选后的数据
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )
    
    # 缓存操作
    st.markdown("#### 🔧 缓存操作")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**查看缓存**")
        if st.button("🔍 查看选中缓存"):
            if not filtered_df.empty:
                # 显示第一个缓存的详细信息
                first_item = filtered_df.iloc[0]
                symbol = first_item['股票代码']
                analysis_date = first_item['分析日期']
                
                cached_data = cache.load_analysis(symbol, analysis_date)
                if cached_data:
                    st.json(cached_data)
                else:
                    st.error("无法加载缓存数据")
            else:
                st.warning("没有可查看的缓存")
    
    with col2:
        st.markdown("**手动缓存**")
        manual_symbol = st.text_input("股票代码", placeholder="例如: 920005")
        if st.button("💾 手动创建缓存"):
            if manual_symbol:
                # 创建简单的测试缓存
                test_data = {
                    'type': 'manual_test',
                    'symbol': manual_symbol,
                    'created_time': datetime.now().isoformat(),
                    'note': '手动创建的测试缓存'
                }
                
                success = cache.save_analysis(manual_symbol, test_data)
                if success:
                    st.success(f"✅ 已为 {manual_symbol} 创建测试缓存")
                    st.rerun()
                else:
                    st.error("创建缓存失败")
            else:
                st.warning("请输入股票代码")
    
    with col3:
        st.markdown("**缓存清理**")
        if st.button("🗑️ 清理旧缓存", help="清理30天前的缓存"):
            # 注意：在开发阶段，我们不清理缓存
            st.warning("开发阶段缓存设为永久保存")
            # deleted_count = cache.cleanup_old_cache(30)
            # st.success(f"已清理 {deleted_count} 个旧缓存文件")
    
    # 按股票统计
    st.markdown("#### 📊 按股票统计")
    
    symbol_stats = stats.get('symbol_stats', {})
    if symbol_stats:
        stat_data = []
        for symbol, count in symbol_stats.items():
            stat_data.append({
                '股票代码': symbol,
                '缓存数量': count
            })
        
        stat_df = pd.DataFrame(stat_data)
        stat_df = stat_df.sort_values('缓存数量', ascending=False)
        
        st.dataframe(stat_df, use_container_width=True, hide_index=True)
        
        # 图表显示
        if len(stat_df) > 0:
            st.bar_chart(stat_df.set_index('股票代码')['缓存数量'])


def check_and_suggest_cache(symbol: str, analysis_date: str = None) -> bool:
    """
    检查并建议使用缓存
    
    Args:
        symbol: 股票代码
        analysis_date: 分析日期
        
    Returns:
        bool: 是否存在缓存
    """
    if not CACHE_AVAILABLE:
        return False
    
    if is_analysis_cached(symbol, analysis_date):
        st.info(f"💡 检测到 {symbol} 的缓存数据，可以直接加载以节省时间")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 加载缓存"):
                return True
        with col2:
            if st.button("🔄 重新分析"):
                return False
        
        return True
    
    return False


def auto_cache_analysis_result(symbol: str, analysis_data: Dict[str, Any], analysis_date: str = None) -> bool:
    """
    自动缓存分析结果
    
    Args:
        symbol: 股票代码
        analysis_data: 分析数据
        analysis_date: 分析日期
        
    Returns:
        bool: 是否缓存成功
    """
    if not CACHE_AVAILABLE:
        logger.warning("缓存系统不可用，跳过自动缓存")
        return False
    
    try:
        success = cache_analysis_result(symbol, analysis_data, analysis_date)
        if success:
            logger.info(f"✅ 自动缓存分析结果: {symbol}")
            st.success(f"📦 分析结果已自动缓存: {symbol}")
        else:
            logger.error(f"❌ 自动缓存失败: {symbol}")
            st.warning(f"⚠️ 自动缓存失败: {symbol}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ 自动缓存异常: {symbol} - {e}")
        return False


def load_cached_analysis_if_exists(symbol: str, analysis_date: str = None) -> Dict[str, Any]:
    """
    如果存在缓存则加载
    
    Args:
        symbol: 股票代码
        analysis_date: 分析日期
        
    Returns:
        Dict: 缓存的分析数据，如果不存在则返回None
    """
    if not CACHE_AVAILABLE:
        return None
    
    try:
        cached_data = load_cached_analysis(symbol, analysis_date)
        if cached_data:
            logger.info(f"📦 已加载缓存分析: {symbol}")
            st.info(f"📦 已从缓存加载 {symbol} 的分析结果")
            return cached_data
        
        return None
        
    except Exception as e:
        logger.error(f"❌ 加载缓存失败: {symbol} - {e}")
        return None


def render_cache_info_sidebar():
    """在侧边栏显示缓存信息"""
    if not CACHE_AVAILABLE:
        return
    
    with st.sidebar:
        st.markdown("### 📦 缓存信息")
        
        cache = get_global_cache()
        stats = cache.get_cache_stats()
        
        st.metric("总缓存", stats.get('total_files', 0))
        st.metric("缓存大小", f"{stats.get('total_size_mb', 0):.1f} MB")
        
        # 最近缓存
        recent_cache = cache.list_cached_analyses()[:3]
        if recent_cache:
            st.markdown("**最近缓存**")
            for item in recent_cache:
                st.write(f"📊 {item['symbol']} ({item['date']})")