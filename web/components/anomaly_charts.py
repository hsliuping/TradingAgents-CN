#!/usr/bin/env python3
"""
异动曲线图表组件
在投资建议旁边显示股票异动数据的可视化图表
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('anomaly_charts')

# 导入异动相关模块
try:
    from tradingagents.dataflows.realtime_monitor import AnomalyEvent, get_global_monitor
    from tradingagents.agents.analysts.anomaly_analyst import AnomalyAnalysisResult, get_global_anomaly_analyst
    ANOMALY_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ 异动模块未完全加载: {e}")
    ANOMALY_MODULES_AVAILABLE = False


def render_anomaly_curve_tab(symbol: str):
    """
    渲染异动曲线Tab页
    
    Args:
        symbol: 股票代码
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.error("🚫 异动图表模块未就绪")
        return
    
    st.markdown("### 📊 异动曲线分析")
    
    # 获取异动数据
    anomalies = get_stock_anomaly_history(symbol)
    
    if not anomalies:
        st.info(f"暂无 {symbol} 的异动数据")
        return
    
    # 创建图表选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📈 异动时间线", "📊 异动分布", "🎯 异动热力图", "📉 异动统计"])
    
    with tab1:
        render_anomaly_timeline_chart(symbol, anomalies)
    
    with tab2:
        render_anomaly_distribution_chart(symbol, anomalies)
    
    with tab3:
        render_anomaly_heatmap_chart(symbol, anomalies)
    
    with tab4:
        render_anomaly_statistics_chart(symbol, anomalies)


def render_anomaly_timeline_chart(symbol: str, anomalies: List[AnomalyEvent]):
    """
    渲染异动时间线图表
    
    Args:
        symbol: 股票代码
        anomalies: 异动事件列表
    """
    st.markdown("#### 📈 异动时间线")
    
    if not anomalies:
        st.warning("暂无异动数据")
        return
    
    # 准备数据
    df_data = []
    for anomaly in anomalies:
        df_data.append({
            'time': anomaly.detection_time,
            'change_percent': anomaly.change_percent,
            'price': anomaly.trigger_price,
            'volume': anomaly.volume,
            'type': anomaly.anomaly_type,
            'type_name': '上涨' if anomaly.anomaly_type == 'surge' else '下跌'
        })
    
    df = pd.DataFrame(df_data)
    df = df.sort_values('time')
    
    # 创建双轴图表
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=('异动幅度变化', '价格变化'),
        vertical_spacing=0.1,
        row_heights=[0.6, 0.4]
    )
    
    # 上涨异动
    surge_data = df[df['type'] == 'surge']
    if not surge_data.empty:
        fig.add_trace(
            go.Scatter(
                x=surge_data['time'],
                y=surge_data['change_percent'],
                mode='markers+lines',
                name='上涨异动',
                marker=dict(
                    color='#ff6b6b',
                    size=10,
                    symbol='triangle-up'
                ),
                line=dict(color='#ff6b6b', width=2),
                hovertemplate='<b>上涨异动</b><br>' +
                             '时间: %{x}<br>' +
                             '涨幅: %{y:.2f}%<br>' +
                             '<extra></extra>'
            ),
            row=1, col=1
        )
    
    # 下跌异动
    drop_data = df[df['type'] == 'drop']
    if not drop_data.empty:
        fig.add_trace(
            go.Scatter(
                x=drop_data['time'],
                y=drop_data['change_percent'].abs(),
                mode='markers+lines',
                name='下跌异动',
                marker=dict(
                    color='#28a745',
                    size=10,
                    symbol='triangle-down'
                ),
                line=dict(color='#28a745', width=2),
                hovertemplate='<b>下跌异动</b><br>' +
                             '时间: %{x}<br>' +
                             '跌幅: %{y:.2f}%<br>' +
                             '<extra></extra>'
            ),
            row=1, col=1
        )
    
    # 价格曲线
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['price'],
            mode='lines+markers',
            name='异动价格',
            marker=dict(color='#007bff', size=6),
            line=dict(color='#007bff', width=2),
            hovertemplate='<b>异动价格</b><br>' +
                         '时间: %{x}<br>' +
                         '价格: %{y:.2f}元<br>' +
                         '<extra></extra>'
        ),
        row=2, col=1
    )
    
    # 更新布局
    fig.update_layout(
        title=f'{symbol} 异动时间线分析',
        height=600,
        showlegend=True,
        hovermode='x unified',
        template='plotly_white'
    )
    
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="异动幅度 (%)", row=1, col=1)
    fig.update_yaxes(title_text="价格 (元)", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 显示异动统计信息
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总异动次数", len(anomalies))
    
    with col2:
        surge_count = len([a for a in anomalies if a.anomaly_type == 'surge'])
        st.metric("上涨异动", surge_count)
    
    with col3:
        drop_count = len([a for a in anomalies if a.anomaly_type == 'drop'])
        st.metric("下跌异动", drop_count)
    
    with col4:
        avg_change = np.mean([abs(a.change_percent) for a in anomalies])
        st.metric("平均异动幅度", f"{avg_change:.2f}%")


def render_anomaly_distribution_chart(symbol: str, anomalies: List[AnomalyEvent]):
    """
    渲染异动分布图表
    
    Args:
        symbol: 股票代码
        anomalies: 异动事件列表
    """
    st.markdown("#### 📊 异动分布分析")
    
    if not anomalies:
        st.warning("暂无异动数据")
        return
    
    # 准备数据
    change_percents = [abs(a.change_percent) for a in anomalies]
    anomaly_types = [a.anomaly_type for a in anomalies]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 异动幅度分布直方图
        fig_hist = go.Figure()
        
        fig_hist.add_trace(
            go.Histogram(
                x=change_percents,
                nbinsx=15,
                name='异动幅度分布',
                marker_color='#17becf',
                opacity=0.7
            )
        )
        
        fig_hist.update_layout(
            title='异动幅度分布',
            xaxis_title='异动幅度 (%)',
            yaxis_title='频次',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig_hist, use_container_width=True)
    
    with col2:
        # 异动类型饼图
        type_counts = pd.Series(anomaly_types).value_counts()
        
        fig_pie = go.Figure()
        
        fig_pie.add_trace(
            go.Pie(
                labels=['上涨异动', '下跌异动'],
                values=[type_counts.get('surge', 0), type_counts.get('drop', 0)],
                hole=0.4,
                marker_colors=['#ff6b6b', '#28a745'],
                textinfo='label+percent+value'
            )
        )
        
        fig_pie.update_layout(
            title='异动类型分布',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # 异动强度分级
    st.markdown("**异动强度分级**")
    
    # 按异动幅度分级
    weak_anomalies = [a for a in anomalies if abs(a.change_percent) < 1.0]
    medium_anomalies = [a for a in anomalies if 1.0 <= abs(a.change_percent) < 3.0]
    strong_anomalies = [a for a in anomalies if abs(a.change_percent) >= 3.0]
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        st.metric(
            "轻度异动 (<1%)",
            len(weak_anomalies),
            delta=f"{len(weak_anomalies)/len(anomalies)*100:.1f}%"
        )
    
    with col4:
        st.metric(
            "中度异动 (1-3%)",
            len(medium_anomalies),
            delta=f"{len(medium_anomalies)/len(anomalies)*100:.1f}%"
        )
    
    with col5:
        st.metric(
            "强度异动 (≥3%)",
            len(strong_anomalies),
            delta=f"{len(strong_anomalies)/len(anomalies)*100:.1f}%"
        )


def render_anomaly_heatmap_chart(symbol: str, anomalies: List[AnomalyEvent]):
    """
    渲染异动热力图
    
    Args:
        symbol: 股票代码
        anomalies: 异动事件列表
    """
    st.markdown("#### 🎯 异动热力图分析")
    
    if not anomalies:
        st.warning("暂无异动数据")
        return
    
    # 准备数据 - 按小时和星期分组
    df_data = []
    for anomaly in anomalies:
        df_data.append({
            'hour': anomaly.detection_time.hour,
            'weekday': anomaly.detection_time.weekday(),
            'weekday_name': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][anomaly.detection_time.weekday()],
            'change_percent': abs(anomaly.change_percent)
        })
    
    df = pd.DataFrame(df_data)
    
    # 创建热力图数据
    heatmap_data = df.groupby(['weekday_name', 'hour'])['change_percent'].agg(['count', 'mean']).reset_index()
    
    # 创建24小时 x 7天的矩阵
    hours = list(range(24))
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    
    # 异动频次热力图
    freq_matrix = np.zeros((7, 24))
    intensity_matrix = np.zeros((7, 24))
    
    for _, row in heatmap_data.iterrows():
        weekday_idx = weekdays.index(row['weekday_name'])
        hour_idx = row['hour']
        freq_matrix[weekday_idx, hour_idx] = row['count']
        intensity_matrix[weekday_idx, hour_idx] = row['mean'] if not np.isnan(row['mean']) else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 异动频次热力图
        fig_freq = go.Figure(data=go.Heatmap(
            z=freq_matrix,
            x=hours,
            y=weekdays,
            colorscale='Reds',
            colorbar=dict(title="异动次数"),
            hoverongaps=False,
            hovertemplate='<b>%{y} %{x}时</b><br>异动次数: %{z}<extra></extra>'
        ))
        
        fig_freq.update_layout(
            title='异动频次热力图',
            xaxis_title='小时',
            yaxis_title='星期',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig_freq, use_container_width=True)
    
    with col2:
        # 异动强度热力图
        fig_intensity = go.Figure(data=go.Heatmap(
            z=intensity_matrix,
            x=hours,
            y=weekdays,
            colorscale='Blues',
            colorbar=dict(title="平均异动幅度(%)"),
            hoverongaps=False,
            hovertemplate='<b>%{y} %{x}时</b><br>平均异动幅度: %{z:.2f}%<extra></extra>'
        ))
        
        fig_intensity.update_layout(
            title='异动强度热力图',
            xaxis_title='小时',
            yaxis_title='星期',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig_intensity, use_container_width=True)
    
    # 异动模式分析
    st.markdown("**异动模式分析**")
    
    # 找出异动高峰时段
    peak_hours = df.groupby('hour').size().nlargest(3)
    peak_weekdays = df.groupby('weekday_name').size().nlargest(3)
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**异动高峰时段**")
        for hour, count in peak_hours.items():
            st.write(f"• {hour}:00-{hour+1}:00 ({count}次)")
    
    with col4:
        st.markdown("**异动高峰日期**")
        for weekday, count in peak_weekdays.items():
            st.write(f"• {weekday} ({count}次)")


def render_anomaly_statistics_chart(symbol: str, anomalies: List[AnomalyEvent]):
    """
    渲染异动统计图表
    
    Args:
        symbol: 股票代码
        anomalies: 异动事件列表
    """
    st.markdown("#### 📉 异动统计分析")
    
    if not anomalies:
        st.warning("暂无异动数据")
        return
    
    # 时间序列分析
    df_data = []
    for anomaly in anomalies:
        df_data.append({
            'date': anomaly.detection_time.date(),
            'time': anomaly.detection_time,
            'change_percent': abs(anomaly.change_percent),
            'type': anomaly.anomaly_type,
            'volume': anomaly.volume,
            'price': anomaly.trigger_price
        })
    
    df = pd.DataFrame(df_data)
    
    # 按日期汇总
    daily_stats = df.groupby('date').agg({
        'change_percent': ['count', 'mean', 'max'],
        'volume': 'sum',
        'price': 'mean'
    }).round(2)
    
    daily_stats.columns = ['异动次数', '平均异动幅度', '最大异动幅度', '总成交量', '平均价格']
    daily_stats = daily_stats.reset_index()
    
    # 异动趋势图
    fig_trend = make_subplots(
        rows=2, cols=2,
        subplot_titles=('每日异动次数', '异动幅度趋势', '成交量趋势', '价格趋势'),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    # 每日异动次数
    fig_trend.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['异动次数'],
            mode='lines+markers',
            name='异动次数',
            line=dict(color='#ff6b6b', width=2),
            marker=dict(size=6)
        ),
        row=1, col=1
    )
    
    # 异动幅度趋势
    fig_trend.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['平均异动幅度'],
            mode='lines+markers',
            name='平均异动幅度',
            line=dict(color='#28a745', width=2),
            marker=dict(size=6)
        ),
        row=1, col=2
    )
    
    # 成交量趋势
    fig_trend.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['总成交量'],
            mode='lines+markers',
            name='总成交量',
            line=dict(color='#007bff', width=2),
            marker=dict(size=6)
        ),
        row=2, col=1
    )
    
    # 价格趋势
    fig_trend.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['平均价格'],
            mode='lines+markers',
            name='平均价格',
            line=dict(color='#ffc107', width=2),
            marker=dict(size=6)
        ),
        row=2, col=2
    )
    
    fig_trend.update_layout(
        title=f'{symbol} 异动统计趋势',
        height=600,
        showlegend=False,
        template='plotly_white'
    )
    
    fig_trend.update_xaxes(title_text="日期")
    fig_trend.update_yaxes(title_text="次数", row=1, col=1)
    fig_trend.update_yaxes(title_text="幅度(%)", row=1, col=2)
    fig_trend.update_yaxes(title_text="成交量", row=2, col=1)
    fig_trend.update_yaxes(title_text="价格(元)", row=2, col=2)
    
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # 异动统计表格
    st.markdown("**每日异动统计**")
    st.dataframe(
        daily_stats.sort_values('date', ascending=False),
        column_config={
            'date': '日期',
            '异动次数': st.column_config.NumberColumn('异动次数', format='%d'),
            '平均异动幅度': st.column_config.NumberColumn('平均异动幅度(%)', format='%.2f'),
            '最大异动幅度': st.column_config.NumberColumn('最大异动幅度(%)', format='%.2f'),
            '总成交量': st.column_config.NumberColumn('总成交量', format='%d'),
            '平均价格': st.column_config.NumberColumn('平均价格(元)', format='%.2f')
        },
        use_container_width=True,
        hide_index=True
    )


def get_stock_anomaly_history(symbol: str, days: int = 30) -> List[AnomalyEvent]:
    """
    获取指定股票的异动历史
    
    Args:
        symbol: 股票代码
        days: 查询天数
        
    Returns:
        List[AnomalyEvent]: 异动事件列表
    """
    if not ANOMALY_MODULES_AVAILABLE:
        return []
    
    try:
        monitor = get_global_monitor()
        
        # 获取异动历史
        anomalies = monitor.get_anomaly_history(symbol, limit=100)
        
        # 过滤指定天数内的异动
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_anomalies = [
            anomaly for anomaly in anomalies 
            if anomaly.detection_time >= cutoff_date
        ]
        
        return filtered_anomalies
        
    except Exception as e:
        logger.error(f"❌ 获取 {symbol} 异动历史失败: {e}")
        return []


def render_anomaly_comparison_chart(symbols: List[str]):
    """
    渲染多股票异动对比图表
    
    Args:
        symbols: 股票代码列表
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.error("🚫 异动图表模块未就绪")
        return
    
    st.markdown("#### 📊 多股票异动对比")
    
    if not symbols:
        st.warning("请选择要对比的股票")
        return
    
    # 获取各股票的异动数据
    all_data = {}
    for symbol in symbols:
        anomalies = get_stock_anomaly_history(symbol, days=7)  # 最近7天
        if anomalies:
            all_data[symbol] = anomalies
    
    if not all_data:
        st.info("选择的股票暂无异动数据")
        return
    
    # 创建对比图表
    fig = go.Figure()
    
    colors = ['#ff6b6b', '#28a745', '#007bff', '#ffc107', '#6f42c1']
    
    for i, (symbol, anomalies) in enumerate(all_data.items()):
        times = [a.detection_time for a in anomalies]
        changes = [abs(a.change_percent) for a in anomalies]
        
        fig.add_trace(
            go.Scatter(
                x=times,
                y=changes,
                mode='markers+lines',
                name=symbol,
                marker=dict(
                    color=colors[i % len(colors)],
                    size=8
                ),
                line=dict(
                    color=colors[i % len(colors)],
                    width=2
                ),
                hovertemplate=f'<b>{symbol}</b><br>' +
                             '时间: %{x}<br>' +
                             '异动幅度: %{y:.2f}%<br>' +
                             '<extra></extra>'
            )
        )
    
    fig.update_layout(
        title='多股票异动对比 (近7天)',
        xaxis_title='时间',
        yaxis_title='异动幅度 (%)',
        template='plotly_white',
        height=500,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 对比统计
    comparison_stats = []
    for symbol, anomalies in all_data.items():
        avg_change = np.mean([abs(a.change_percent) for a in anomalies])
        max_change = max([abs(a.change_percent) for a in anomalies])
        comparison_stats.append({
            '股票代码': symbol,
            '异动次数': len(anomalies),
            '平均异动幅度(%)': round(avg_change, 2),
            '最大异动幅度(%)': round(max_change, 2)
        })
    
    st.markdown("**对比统计**")
    st.dataframe(pd.DataFrame(comparison_stats), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    # 测试组件
    st.set_page_config(page_title="异动图表测试", layout="wide")
    
    st.title("📊 异动图表组件测试")
    
    # 测试单股票异动曲线
    test_symbol = st.text_input("输入股票代码", value="000001")
    
    if test_symbol:
        render_anomaly_curve_tab(test_symbol)
    
    st.markdown("---")
    
    # 测试多股票对比
    test_symbols = st.multiselect("选择对比股票", ["000001", "000002", "600036", "600519"])
    
    if test_symbols:
        render_anomaly_comparison_chart(test_symbols) 