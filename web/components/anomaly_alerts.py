#!/usr/bin/env python3
"""
异动消息提醒组件
在页面右上角显示实时股票异动提醒
"""

import streamlit as st
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('anomaly_alerts')

# 导入异动相关模块
try:
    from tradingagents.dataflows.realtime_monitor import AnomalyEvent, get_global_monitor
    from tradingagents.agents.analysts.anomaly_analyst import AnomalyAnalysisResult, get_global_anomaly_analyst
    ANOMALY_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ 异动模块未完全加载: {e}")
    ANOMALY_MODULES_AVAILABLE = False


def trigger_fake_anomaly():
    """触发假数据异动用于测试"""
    import random
    from datetime import datetime
    
    if not ANOMALY_MODULES_AVAILABLE:
        logger.error("异动模块未就绪，无法触发测试")
        return
    
    try:
        monitor = get_global_monitor()
        
        # 创建假的异动事件
        fake_symbols = ['AAPL', 'GOOGL', 'MSFT', '000001', '600519', '920005']
        fake_names = ['苹果公司', '谷歌', '微软', '平安银行', '贵州茅台', '江龙船艇']
        
        selected_symbol = random.choice(fake_symbols)
        selected_name = random.choice(fake_names)
        
        fake_anomaly = AnomalyEvent(
            symbol=selected_symbol,
            name=selected_name,
            anomaly_type=random.choice(['surge', 'drop']),
            change_percent=round(random.uniform(0.11, 5.0), 2),
            trigger_price=round(random.uniform(10, 500), 2),
            previous_price=round(random.uniform(10, 500), 2),
            detection_time=datetime.now(),
            volume=random.randint(100000, 10000000)
        )
        
        # 计算价格变化
        if fake_anomaly.anomaly_type == 'drop':
            fake_anomaly.change_percent = -fake_anomaly.change_percent
        
        logger.info(f"🧪 触发测试异动: {fake_anomaly.symbol} {fake_anomaly.change_percent:+.2f}%")
        
        # 手动触发异动回调（模拟真实异动检测）
        if hasattr(monitor, 'anomaly_callbacks') and monitor.anomaly_callbacks:
            for callback in monitor.anomaly_callbacks:
                try:
                    callback(fake_anomaly)
                except Exception as e:
                    logger.error(f"❌ 异动回调失败: {e}")
        
        # 将假数据存储到Redis中，以便UI能够显示
        monitor._store_anomaly_event(fake_anomaly)
        
        # 更新会话状态以触发通知
        if 'anomaly_notifications' not in st.session_state:
            st.session_state.anomaly_notifications = []
        
        st.session_state.anomaly_notifications.append({
            'event': fake_anomaly,
            'timestamp': datetime.now(),
            'shown': False
        })
        
        logger.info("✅ 假数据异动触发成功")
        
    except Exception as e:
        logger.error(f"❌ 触发假数据异动失败: {e}")


def render_anomaly_alerts_sidebar():
    """在侧边栏渲染异动提醒面板"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🚨 异动监控")
        
        if not ANOMALY_MODULES_AVAILABLE:
            st.error("异动监控模块未就绪")
            return
        
        # 监控状态显示
        monitor = get_global_monitor()
        status = monitor.get_monitoring_status()
        
        # 监控状态指示器
        if status["is_monitoring"]:
            st.success("🟢 监控中")
        else:
            st.error("🔴 已停止")
        
        # 监控配置信息
        with st.expander("监控配置", expanded=False):
            st.write(f"异动阈值: {status['anomaly_threshold']}%")
            st.write(f"监控间隔: {status['monitor_interval']}秒")
            st.write(f"监控股票: {len(status['monitored_stocks'])}只")
            
            if status['monitored_stocks']:
                st.write("监控列表:")
                for stock in status['monitored_stocks']:
                    st.write(f"• {stock}")
        
        # 最新异动提醒
        render_latest_anomalies()


def render_anomaly_alerts_header():
    """在页面顶部渲染异动提醒横幅"""
    if not ANOMALY_MODULES_AVAILABLE:
        return
    
    # 获取最新异动
    latest_anomalies = get_recent_anomalies(limit=3)
    
    if not latest_anomalies:
        return
    
    # 创建提醒容器
    alert_container = st.container()
    
    with alert_container:
        # 自定义CSS样式
        st.markdown("""
        <style>
        .anomaly-alert {
            background: linear-gradient(90deg, #ff6b6b, #ffa500);
            padding: 10px 15px;
            border-radius: 8px;
            margin: 5px 0;
            color: white;
            font-weight: bold;
            border-left: 4px solid #ff4444;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            animation: pulse 2s infinite;
        }
        
        .anomaly-alert-success {
            background: linear-gradient(90deg, #28a745, #20c997);
            border-left: 4px solid #1e7e34;
        }
        
        .anomaly-alert-warning {
            background: linear-gradient(90deg, #ffc107, #fd7e14);
            border-left: 4px solid #e0a800;
        }
        
        .anomaly-alert-danger {
            background: linear-gradient(90deg, #dc3545, #fd7e14);
            border-left: 4px solid #bd2130;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.8; }
            100% { opacity: 1; }
        }
        
        .alert-time {
            font-size: 0.8em;
            opacity: 0.9;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 显示异动提醒
        for anomaly in latest_anomalies:
            time_diff = datetime.now() - anomaly.detection_time
            
            # 根据异动类型选择样式
            if anomaly.anomaly_type == "surge":
                alert_class = "anomaly-alert anomaly-alert-success"
                icon = "🔺"
            else:
                alert_class = "anomaly-alert anomaly-alert-danger"
                icon = "🔻"
            
            # 根据时间选择紧急程度
            if time_diff.total_seconds() < 300:  # 5分钟内
                alert_class += " anomaly-alert-danger"
            elif time_diff.total_seconds() < 900:  # 15分钟内
                alert_class += " anomaly-alert-warning"
            
            # 格式化时间
            if time_diff.total_seconds() < 60:
                time_str = "刚刚"
            elif time_diff.total_seconds() < 3600:
                time_str = f"{int(time_diff.total_seconds() // 60)}分钟前"
            else:
                time_str = f"{int(time_diff.total_seconds() // 3600)}小时前"
            
            # 显示异动提醒
            st.markdown(f"""
            <div class="{alert_class}">
                {icon} <strong>{anomaly.symbol} {anomaly.name}</strong> 
                {"上涨" if anomaly.anomaly_type == "surge" else "下跌"} 
                <strong>{abs(anomaly.change_percent):.2f}%</strong>
                <br>
                <span class="alert-time">💰 {anomaly.trigger_price:.2f}元 • ⏰ {time_str}</span>
            </div>
            """, unsafe_allow_html=True)


def render_latest_anomalies():
    """渲染最新异动列表"""
    st.markdown("**最新异动**")
    
    # 获取最新异动
    recent_anomalies = get_recent_anomalies(limit=5)
    
    if not recent_anomalies:
        st.info("暂无异动")
        return
    
    # 显示异动列表
    for i, anomaly in enumerate(recent_anomalies):
        time_diff = datetime.now() - anomaly.detection_time
        
        # 格式化时间
        if time_diff.total_seconds() < 60:
            time_str = "刚刚"
        elif time_diff.total_seconds() < 3600:
            time_str = f"{int(time_diff.total_seconds() // 60)}分钟前"
        else:
            time_str = f"{int(time_diff.total_seconds() // 3600)}小时前"
        
        # 选择图标和颜色
        if anomaly.anomaly_type == "surge":
            icon = "🔺"
            color = "🟢"
        else:
            icon = "🔻"
            color = "🔴"
        
        # 显示异动信息
        with st.expander(f"{icon} {anomaly.symbol} {abs(anomaly.change_percent):.2f}%", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**{anomaly.name}**")
                st.write(f"价格: {anomaly.previous_price:.2f} → {anomaly.trigger_price:.2f}")
                st.write(f"成交量: {anomaly.volume:,}")
            
            with col2:
                st.write(f"{color} {time_str}")
                if st.button("分析", key=f"analyze_{anomaly.symbol}_{i}"):
                    st.session_state[f'trigger_analysis_{anomaly.symbol}'] = True
                    st.rerun()


def render_anomaly_notification_popup():
    """渲染异动通知弹窗"""
    # 检查是否有新的异动需要弹窗显示
    if 'show_anomaly_popup' in st.session_state and st.session_state.show_anomaly_popup:
        anomaly = st.session_state.get('popup_anomaly')
        if anomaly:
            render_anomaly_popup(anomaly)
            # 清除弹窗状态
            st.session_state.show_anomaly_popup = False


def render_anomaly_popup(anomaly: AnomalyEvent):
    """渲染单个异动弹窗"""
    # 使用modal对话框样式
    st.markdown("""
    <style>
    .anomaly-popup {
        position: fixed;
        top: 20px;
        right: 20px;
        width: 350px;
        background: white;
        border: 2px solid #ff6b6b;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .popup-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        font-weight: bold;
        color: #ff6b6b;
    }
    
    .popup-close {
        cursor: pointer;
        font-size: 18px;
        color: #999;
    }
    
    .popup-close:hover {
        color: #ff6b6b;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 异动类型图标
    icon = "🔺" if anomaly.anomaly_type == "surge" else "🔻"
    action = "上涨" if anomaly.anomaly_type == "surge" else "下跌"
    
    # 弹窗内容
    popup_html = f"""
    <div class="anomaly-popup">
        <div class="popup-header">
            <span>{icon} 股票异动提醒</span>
            <span class="popup-close" onclick="this.parentElement.parentElement.style.display='none'">×</span>
        </div>
        <div>
            <strong>{anomaly.symbol} {anomaly.name}</strong><br>
            {action} <strong style="color: {'#28a745' if anomaly.anomaly_type == 'surge' else '#dc3545'}">
            {abs(anomaly.change_percent):.2f}%</strong><br>
            <small>价格: {anomaly.previous_price:.2f} → {anomaly.trigger_price:.2f}</small><br>
            <small>时间: {anomaly.detection_time.strftime('%H:%M:%S')}</small>
        </div>
    </div>
    """
    
    st.markdown(popup_html, unsafe_allow_html=True)


def get_recent_anomalies(limit: int = 10) -> List[AnomalyEvent]:
    """
    获取最近的异动事件
    
    Args:
        limit: 返回数量限制
        
    Returns:
        List[AnomalyEvent]: 异动事件列表
    """
    if not ANOMALY_MODULES_AVAILABLE:
        return []
    
    try:
        monitor = get_global_monitor()
        
        # 获取所有监控股票的异动历史
        all_anomalies = []
        for symbol in monitor.monitored_stocks:
            anomalies = monitor.get_anomaly_history(symbol, limit=limit)
            all_anomalies.extend(anomalies)
        
        # 按时间倒序排序
        all_anomalies.sort(key=lambda x: x.detection_time, reverse=True)
        
        return all_anomalies[:limit]
        
    except Exception as e:
        logger.error(f"❌ 获取异动历史失败: {e}")
        return []


def check_new_anomalies():
    """检查是否有新的异动，用于触发通知"""
    if not ANOMALY_MODULES_AVAILABLE:
        return False
    
    try:
        # 获取最新异动
        latest_anomalies = get_recent_anomalies(limit=1)
        
        if not latest_anomalies:
            return False
        
        latest_anomaly = latest_anomalies[0]
        
        # 检查是否是新异动（5分钟内）
        time_diff = datetime.now() - latest_anomaly.detection_time
        if time_diff.total_seconds() < 300:
            # 检查是否已经通知过
            last_notified = st.session_state.get('last_anomaly_notification')
            if not last_notified or latest_anomaly.detection_time > last_notified:
                # 设置弹窗状态
                st.session_state.show_anomaly_popup = True
                st.session_state.popup_anomaly = latest_anomaly
                st.session_state.last_anomaly_notification = latest_anomaly.detection_time
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ 检查新异动失败: {e}")
        return False


def render_anomaly_monitoring_control():
    """渲染异动监控控制面板"""
    if not ANOMALY_MODULES_AVAILABLE:
        st.error("🚫 异动监控模块未就绪")
        return
    
    # 使用tabs来组织不同功能
    tab1, tab2, tab3 = st.tabs(["🎛️ 监控控制", "📋 股票列表管理", "📊 快速概览"])
    
    monitor = get_global_monitor()
    status = monitor.get_monitoring_status()
    
    with tab1:
        st.markdown("### 🔧 异动监控控制")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**监控状态**")
            if status["is_monitoring"]:
                st.success("🟢 正在监控")
                if st.button("⏹️ 停止监控"):
                    monitor.stop_monitoring()
                    st.rerun()
            else:
                st.error("🔴 监控已停止")
                if st.button("▶️ 开始监控"):
                    if status["monitored_stocks"]:
                        monitor.start_monitoring()
                        st.rerun()
                    else:
                        st.warning("请先添加要监控的股票")
        
        with col2:
            st.markdown("**监控配置**")
            st.write(f"异动阈值: {status['anomaly_threshold']}%")
            st.write(f"监控间隔: {status['monitor_interval']}秒")
            st.write(f"监控股票: {len(status['monitored_stocks'])}只")
            
            # 添加测试按钮
            st.markdown("**测试功能**")
            if st.button("🧪 触发假数据异动"):
                trigger_fake_anomaly()
                st.success("已触发测试异动！")
                st.rerun()
    
    with tab2:
        render_enhanced_stock_list_management()
    
    with tab3:
        render_monitoring_overview()


def render_enhanced_stock_list_management():
    """渲染增强版股票列表管理功能"""
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.markdown("### 📋 监控股票列表管理")
        
        # 自动加载已保存的股票配置
        monitor.load_all_configs()
        stock_configs = monitor.get_all_stock_configs()
        
        # 添加股票区域
        st.markdown("#### ➕ 添加新股票")
        
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            new_stock = st.text_input(
                "股票代码", 
                placeholder="例如: 000001, AAPL, 0700.HK", 
                key="enhanced_new_stock_input",
                help="输入股票代码，支持A股(6位数字)、美股(字母)、港股(数字.HK)"
            )
        
        with col2:
            anomaly_threshold = st.number_input(
                "异动阈值(%)",
                min_value=0.01,
                max_value=50.0,
                value=0.1,
                step=0.01,
                key="new_anomaly_threshold"
            )
        
        with col3:
            monitor_interval = st.number_input(
                "监控间隔(秒)",
                min_value=10,
                max_value=3600,
                value=300,
                step=10,
                key="new_monitor_interval"
            )
        
        with col4:
            enable_push = st.checkbox(
                "实时推送",
                value=True,
                key="new_enable_push"
            )
        
        # 添加按钮
        if st.button("➕ 添加股票", type="primary"):
            if new_stock and new_stock.strip():
                cleaned_stock = new_stock.strip().upper()
                from tradingagents.dataflows.realtime_monitor import StockMonitorConfig
                config = StockMonitorConfig(
                    symbol=cleaned_stock,
                    anomaly_threshold=anomaly_threshold,
                    monitor_interval=monitor_interval,
                    enable_realtime_push=enable_push
                )
                if monitor.add_stock_with_config(cleaned_stock, config):
                    st.success(f"✅ 已添加 {cleaned_stock}")
                    st.rerun()
                else:
                    st.error(f"❌ 添加 {cleaned_stock} 失败")
            else:
                st.error("请输入有效的股票代码")
        
        # 显示当前监控列表
        if stock_configs:
            st.markdown("#### 📊 当前监控列表")
            
            # 创建表格数据
            table_data = []
            for symbol, config in stock_configs.items():
                # 获取异动统计
                anomaly_count = 0
                try:
                    anomalies = monitor.get_anomaly_history(symbol, limit=1000)
                    anomaly_count = len(anomalies)
                except:
                    pass
                
                table_data.append({
                    "股票代码": symbol,
                    "股票名称": config.name or "未知",
                    "异动阈值(%)": f"{config.anomaly_threshold:.2f}",
                    "监控间隔(秒)": config.monitor_interval,
                    "实时推送": "✅" if config.enable_realtime_push else "❌",
                    "异动次数": anomaly_count,
                    "创建时间": config.created_time.strftime("%m-%d %H:%M") if config.created_time else "",
                    "最后更新": config.last_updated.strftime("%m-%d %H:%M") if config.last_updated else ""
                })
            
            # 显示表格
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无监控股票，请添加股票开始监控")
        
    except Exception as e:
        logger.error(f"❌ 渲染增强股票列表管理失败: {e}")
        st.error(f"股票列表管理错误: {e}")


def render_monitoring_overview():
    """渲染监控概览"""
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.markdown("### 📊 监控概览")
        
        # 获取监控状态和股票配置
        status = monitor.get_monitoring_status()
        stock_configs = monitor.get_all_stock_configs()
        
        # 监控状态概览
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="监控状态",
                value="运行中" if status["is_monitoring"] else "已停止",
                delta="正常" if status["is_monitoring"] else "待启动"
            )
        
        with col2:
            st.metric(
                label="监控股票数",
                value=len(stock_configs),
                delta=f"活跃: {len(status['monitored_stocks'])}"
            )
        
        with col3:
            # 计算总异动数
            total_anomalies = 0
            for symbol in stock_configs.keys():
                try:
                    anomalies = monitor.get_anomaly_history(symbol, limit=1000)
                    total_anomalies += len(anomalies)
                except:
                    pass
            
            st.metric(
                label="总异动次数",
                value=total_anomalies,
                delta="累计记录"
            )
        
        with col4:
            # 计算平均阈值
            if stock_configs:
                avg_threshold = sum(config.anomaly_threshold for config in stock_configs.values()) / len(stock_configs)
                st.metric(
                    label="平均阈值",
                    value=f"{avg_threshold:.2f}%",
                    delta="全局设置"
                )
            else:
                st.metric("平均阈值", "0.00%", "无数据")
        
        # 最近异动概览
        if stock_configs:
            st.markdown("#### 🚨 最近异动")
            
            recent_anomalies = []
            for symbol in stock_configs.keys():
                try:
                    anomalies = monitor.get_anomaly_history(symbol, limit=5)
                    for anomaly in anomalies:
                        recent_anomalies.append({
                            "时间": anomaly.detection_time.strftime("%m-%d %H:%M:%S"),
                            "股票": f"{anomaly.symbol} ({anomaly.name})",
                            "类型": "📈 上涨" if anomaly.anomaly_type == "surge" else "📉 下跌",
                            "幅度": f"{anomaly.change_percent:.2f}%",
                            "触发价": f"{anomaly.trigger_price:.2f}"
                        })
                except:
                    pass
            
            if recent_anomalies:
                # 按时间排序，显示最新的10条
                recent_anomalies.sort(key=lambda x: x["时间"], reverse=True)
                df_recent = pd.DataFrame(recent_anomalies[:10])
                st.dataframe(df_recent, use_container_width=True, hide_index=True)
            else:
                st.info("暂无最近异动记录")
        else:
            st.info("请先添加监控股票")
        
        # Redis连接状态
        st.markdown("#### 🔗 系统状态")
        col5, col6 = st.columns(2)
        
        with col5:
            if monitor.redis_client:
                try:
                    monitor.redis_client.ping()
                    st.success("✅ Redis连接正常")
                except:
                    st.error("❌ Redis连接异常")
            else:
                st.warning("⚠️ Redis未配置")
        
        with col6:
            # 显示数据源状态
            data_sources = []
            if monitor.tushare_adapter:
                data_sources.append("Tushare")
            if monitor.akshare_provider:
                data_sources.append("AKShare")
            if monitor.db_cache_manager:
                data_sources.append("Database")
            
            if data_sources:
                st.success(f"✅ 数据源: {', '.join(data_sources)}")
            else:
                st.error("❌ 无可用数据源")
        
    except Exception as e:
        logger.error(f"❌ 渲染监控概览失败: {e}")
        st.error(f"监控概览错误: {e}")


def render_anomaly_analytics_dashboard():
    """渲染异动分析仪表板"""
    if not ANOMALY_MODULES_AVAILABLE:
        st.error("🚫 异动分析模块未就绪")
        return
    
    st.markdown("### 📊 异动分析仪表板")
    
    # 获取异动数据
    anomalies = get_recent_anomalies(limit=50)
    
    if not anomalies:
        st.info("暂无异动数据")
        return
    
    # 转换为DataFrame用于分析
    anomaly_data = []
    for anomaly in anomalies:
        anomaly_data.append({
            'symbol': anomaly.symbol,
            'name': anomaly.name,
            'type': anomaly.anomaly_type,
            'change_percent': anomaly.change_percent,
            'detection_time': anomaly.detection_time,
            'volume': anomaly.volume
        })
    
    df = pd.DataFrame(anomaly_data)
    
    # 统计指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总异动次数", len(df))
    
    with col2:
        surge_count = len(df[df['type'] == 'surge'])
        st.metric("上涨异动", surge_count)
    
    with col3:
        drop_count = len(df[df['type'] == 'drop'])
        st.metric("下跌异动", drop_count)
    
    with col4:
        avg_change = df['change_percent'].abs().mean()
        st.metric("平均异动幅度", f"{avg_change:.2f}%")
    
    # 异动分布图表
    st.markdown("**异动类型分布**")
    type_counts = df['type'].value_counts()
    st.bar_chart(type_counts)
    
    # 最活跃股票
    st.markdown("**最活跃股票**")
    stock_counts = df['symbol'].value_counts().head(10)
    st.bar_chart(stock_counts)
    
    # 详细异动列表
    st.markdown("**详细异动记录**")
    display_df = df.copy()
    display_df['detection_time'] = display_df['detection_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df['type'] = display_df['type'].map({'surge': '🔺 上涨', 'drop': '🔻 下跌'})
    
    st.dataframe(
        display_df[['detection_time', 'symbol', 'name', 'type', 'change_percent', 'volume']],
        column_config={
            'detection_time': '检测时间',
            'symbol': '代码',
            'name': '名称',
            'type': '类型',
            'change_percent': '涨跌幅(%)',
            'volume': '成交量'
        },
        use_container_width=True
    )


def init_anomaly_alerts():
    """初始化异动提醒功能"""
    # 初始化会话状态
    if 'last_anomaly_notification' not in st.session_state:
        st.session_state.last_anomaly_notification = None
    
    if 'show_anomaly_popup' not in st.session_state:
        st.session_state.show_anomaly_popup = False
    
    # 检查新异动
    check_new_anomalies()


# 自动刷新脚本
def get_auto_refresh_script(interval_seconds: int = 30):
    """获取自动刷新JavaScript脚本"""
    return f"""
    <script>
        // 自动刷新页面以获取最新异动
        setTimeout(function() {{
            window.location.reload();
        }}, {interval_seconds * 1000});
        
        // 检查新异动的函数
        function checkNewAnomalies() {{
            // 这里可以通过Ajax调用后端API检查新异动
            // 暂时使用页面刷新的方式
        }}
        
        // 每10秒检查一次新异动
        setInterval(checkNewAnomalies, 10000);
    </script>
    """


if __name__ == "__main__":
    # 测试组件
    st.set_page_config(page_title="异动提醒测试", layout="wide")
    
    st.title("🚨 异动提醒组件测试")
    
    # 初始化
    init_anomaly_alerts()
    
    # 渲染头部异动提醒
    render_anomaly_alerts_header()
    
    # 渲染控制面板
    render_anomaly_monitoring_control()
    
    # 渲染分析仪表板
    render_anomaly_analytics_dashboard()
    
    # 渲染弹窗
    render_anomaly_notification_popup()
    
    # 添加自动刷新
    st.markdown(get_auto_refresh_script(30), unsafe_allow_html=True)


def render_historical_stocks():
    """
    渲染历史监控股票列表
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.subheader("📋 历史监控股票")
        
        # 获取历史股票数据
        historical_stocks = monitor.get_historical_stocks()
        
        if not historical_stocks:
            st.info("暂无历史监控股票")
            return
        
        # 创建数据表格
        df_data = []
        for stock in historical_stocks:
            df_data.append({
                "股票代码": stock.get("symbol", ""),
                "添加时间": stock.get("added_time", "").split('T')[0] if stock.get("added_time") else "",
                "异动次数": stock.get("total_anomalies", 0),
                "最后监控": stock.get("last_monitored", "").split('T')[0] if stock.get("last_monitored") else ""
            })
        
        df = pd.DataFrame(df_data)
        
        # 显示表格
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )
        
        # 统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总股票数", len(historical_stocks))
        with col2:
            total_anomalies = sum(stock.get("total_anomalies", 0) for stock in historical_stocks)
            st.metric("总异动次数", total_anomalies)
        with col3:
            current_monitoring = len(monitor.monitored_stocks)
            st.metric("当前监控", current_monitoring)
            
    except Exception as e:
        logger.error(f"❌ 渲染历史股票失败: {e}")
        st.error(f"获取历史股票数据失败: {e}")


def render_stock_monitoring_list():
    """
    渲染监控股票列表页面 - 包含配置管理
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.subheader("📋 监控股票列表")
        
        # 获取所有股票配置
        stock_configs = monitor.get_all_stock_configs()
        
        if not stock_configs:
            st.info("暂无监控股票，请先添加股票")
            return
        
        # 创建表格数据
        table_data = []
        for symbol, config in stock_configs.items():
            # 获取异动统计
            anomaly_count = 0
            try:
                anomalies = monitor.get_anomaly_history(symbol, limit=1000)
                anomaly_count = len(anomalies)
            except:
                pass
            
            table_data.append({
                "股票代码": symbol,
                "股票名称": config.name or "未知",
                "异动阈值(%)": f"{config.anomaly_threshold:.2f}",
                "监控间隔(秒)": config.monitor_interval,
                "实时推送": "✅" if config.enable_realtime_push else "❌",
                "异动次数": anomaly_count,
                "创建时间": config.created_time.strftime("%Y-%m-%d %H:%M") if config.created_time else "",
                "最后更新": config.last_updated.strftime("%Y-%m-%d %H:%M") if config.last_updated else ""
            })
        
        # 显示表格
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 配置编辑区域
        st.subheader("⚙️ 配置管理")
        
        # 选择要编辑的股票
        selected_symbol = st.selectbox(
            "选择要编辑的股票",
            options=list(stock_configs.keys()),
            help="选择一个股票进行配置编辑"
        )
        
        if selected_symbol:
            current_config = stock_configs[selected_symbol]
            
            # 配置表单
            with st.form(f"config_form_{selected_symbol}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    new_threshold = st.number_input(
                        "异动阈值 (%)",
                        min_value=0.01,
                        max_value=50.0,
                        value=current_config.anomaly_threshold,
                        step=0.01,
                        help="股票涨跌幅超过此阈值时触发异动警报"
                    )
                    
                    new_interval = st.number_input(
                        "监控间隔 (秒)",
                        min_value=10,
                        max_value=3600,
                        value=current_config.monitor_interval,
                        step=10,
                        help="检查股票价格变化的时间间隔"
                    )
                
                with col2:
                    new_push = st.checkbox(
                        "启用实时推送",
                        value=current_config.enable_realtime_push,
                        help="是否在检测到异动时发送实时通知"
                    )
                    
                    new_name = st.text_input(
                        "股票名称",
                        value=current_config.name,
                        help="股票的中文名称（可选）"
                    )
                
                # 提交按钮
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    if st.form_submit_button("💾 保存配置", type="primary"):
                        # 创建新配置
                        from tradingagents.dataflows.realtime_monitor import StockMonitorConfig
                        new_config = StockMonitorConfig(
                            symbol=selected_symbol,
                            anomaly_threshold=new_threshold,
                            monitor_interval=new_interval,
                            enable_realtime_push=new_push,
                            name=new_name,
                            created_time=current_config.created_time
                        )
                        
                        # 更新配置
                        if monitor.update_stock_config(selected_symbol, new_config):
                            st.success(f"✅ 已更新 {selected_symbol} 配置")
                            st.rerun()
                        else:
                            st.error(f"❌ 更新 {selected_symbol} 配置失败")
                
                with col2:
                    if st.form_submit_button("🗑️ 删除股票", type="secondary"):
                        if monitor.remove_stock(selected_symbol):
                            st.success(f"✅ 已删除 {selected_symbol}")
                            st.rerun()
                        else:
                            st.error(f"❌ 删除 {selected_symbol} 失败")
                
                with col3:
                    if st.form_submit_button("🔄 重置配置"):
                        # 重置为默认配置
                        from tradingagents.dataflows.realtime_monitor import StockMonitorConfig
                        default_config = StockMonitorConfig(
                            symbol=selected_symbol,
                            name=current_config.name,
                            created_time=current_config.created_time
                        )
                        
                        if monitor.update_stock_config(selected_symbol, default_config):
                            st.success(f"✅ 已重置 {selected_symbol} 配置")
                            st.rerun()
                        else:
                            st.error(f"❌ 重置 {selected_symbol} 配置失败")
            
    except Exception as e:
        logger.error(f"❌ 渲染监控列表失败: {e}")
        st.error(f"监控列表错误: {e}")


def render_stock_monitoring_control():
    """
    渲染股票监控控制面板 - 增强版
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.subheader("🎛️ 监控控制")
        
        # 添加股票输入区域
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # 支持多股票输入
            stock_input = st.text_input(
                "添加监控股票",
                placeholder="输入股票代码，多个股票用逗号分隔，如: 000001,600519,AAPL",
                help="支持A股代码(如000001)、港股代码(如00700.HK)、美股代码(如AAPL)"
            )
        
        with col2:
            add_clicked = st.button("➕ 添加", type="primary")
        
        # 处理添加股票
        if add_clicked and stock_input:
            symbols = [s.strip() for s in stock_input.split(',') if s.strip()]
            if symbols:
                results = monitor.add_stocks_batch(symbols)
                
                success_symbols = [s for s, result in results.items() if result]
                failed_symbols = [s for s, result in results.items() if not result]
                
                if success_symbols:
                    st.success(f"✅ 成功添加: {', '.join(success_symbols)}")
                if failed_symbols:
                    st.error(f"❌ 添加失败: {', '.join(failed_symbols)}")
        
        # 当前监控状态
        status = monitor.get_monitoring_status()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if status.get("is_monitoring", False):
                st.success("🟢 监控中")
                if st.button("⏹️ 停止监控"):
                    monitor.stop_monitoring()
                    st.rerun()
            else:
                st.info("🔴 未监控")
                if st.button("▶️ 开始监控"):
                    monitor.start_monitoring()
                    st.rerun()
        
        with col2:
            monitored_count = len(monitor.monitored_stocks)
            st.metric("监控股票数", monitored_count)
        
        with col3:
            if monitor.monitored_stocks:
                st.metric("监控间隔", f"{monitor.monitor_interval}秒")
        
        # 显示当前监控的股票
        if monitor.monitored_stocks:
            st.write("**当前监控股票:**")
            stocks_text = ", ".join(monitor.monitored_stocks)
            st.code(stocks_text)
            
    except Exception as e:
        logger.error(f"❌ 渲染监控控制失败: {e}")
        st.error(f"监控控制面板错误: {e}")


def render_anomaly_analysis_dashboard():
    """
    渲染异动分析仪表板
    """
    if not ANOMALY_MODULES_AVAILABLE:
        st.warning("⚠️ 异动监控模块未加载")
        return
    
    try:
        monitor = get_global_monitor()
        if not monitor:
            st.warning("⚠️ 监控器未初始化")
            return
        
        st.subheader("📊 异动分析仪表板")
        
        # 获取所有监控股票
        stock_configs = monitor.get_all_stock_configs()
        if not stock_configs:
            st.info("暂无监控股票，请先添加股票进行监控")
            return
        
        # 股票选择区域
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_stocks = st.multiselect(
                "选择要分析的股票",
                options=list(stock_configs.keys()),
                default=list(stock_configs.keys())[:3] if len(stock_configs) <= 3 else list(stock_configs.keys())[:2],
                help="可以选择多个股票进行对比分析"
            )
        
        with col2:
            # 时间范围选择
            time_range = st.selectbox(
                "分析时间范围",
                options=[
                    ("最近24小时", 1),
                    ("最近3天", 3),
                    ("最近一周", 7),
                    ("最近半月", 15),
                    ("最近一个月", 30)
                ],
                format_func=lambda x: x[0],
                index=2
            )
        
        if not selected_stocks:
            st.warning("请至少选择一个股票进行分析")
            return
        
        # 获取选中股票的异动数据
        time_limit = datetime.now() - timedelta(days=time_range[1])
        all_anomaly_data = []
        
        for symbol in selected_stocks:
            try:
                anomalies = monitor.get_anomaly_history(symbol, limit=1000)
                # 过滤时间范围
                filtered_anomalies = [
                    a for a in anomalies 
                    if a.detection_time >= time_limit
                ]
                
                for anomaly in filtered_anomalies:
                    all_anomaly_data.append({
                        "股票代码": symbol,
                        "股票名称": stock_configs[symbol].name or symbol,
                        "异动类型": "上涨" if anomaly.anomaly_type == "surge" else "下跌",
                        "变化幅度": anomaly.change_percent,
                        "触发价格": anomaly.trigger_price,
                        "前一价格": anomaly.previous_price,
                        "成交量": anomaly.volume,
                        "检测时间": anomaly.detection_time,
                        "日期": anomaly.detection_time.strftime("%Y-%m-%d"),
                        "时间": anomaly.detection_time.strftime("%H:%M:%S")
                    })
            except Exception as e:
                logger.warning(f"获取 {symbol} 异动数据失败: {e}")
        
        if not all_anomaly_data:
            st.info(f"在{time_range[0]}内没有检测到异动数据")
            return
        
        df = pd.DataFrame(all_anomaly_data)
        
        # 统计指标区域
        st.subheader("📈 统计概览")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_anomalies = len(df)
            st.metric("总异动次数", total_anomalies)
        
        with col2:
            surge_count = len(df[df["异动类型"] == "上涨"])
            st.metric("上涨异动", surge_count, delta=f"{surge_count/total_anomalies*100:.1f}%" if total_anomalies > 0 else "0%")
        
        with col3:
            drop_count = len(df[df["异动类型"] == "下跌"])
            st.metric("下跌异动", drop_count, delta=f"{drop_count/total_anomalies*100:.1f}%" if total_anomalies > 0 else "0%")
        
        with col4:
            avg_change = df["变化幅度"].abs().mean() if len(df) > 0 else 0
            st.metric("平均变化幅度", f"{avg_change:.2f}%")
        
        # 图表分析区域
        tab1, tab2, tab3, tab4 = st.tabs(["📈 异动趋势", "📊 股票对比", "🕐 时间分布", "📋 详细数据"])
        
        with tab1:
            st.subheader("异动趋势分析")
            if len(df) > 0:
                # 按日期聚合数据
                daily_stats = df.groupby(['股票代码', '日期']).agg({
                    '变化幅度': ['count', 'mean', 'max', 'min'],
                    '检测时间': 'first'
                }).reset_index()
                daily_stats.columns = ['股票代码', '日期', '异动次数', '平均幅度', '最大幅度', '最小幅度', '首次检测']
                
                # 创建折线图
                fig = go.Figure()
                
                for symbol in selected_stocks:
                    stock_data = daily_stats[daily_stats['股票代码'] == symbol]
                    if len(stock_data) > 0:
                        fig.add_trace(go.Scatter(
                            x=stock_data['日期'],
                            y=stock_data['异动次数'],
                            mode='lines+markers',
                            name=f"{symbol} 异动次数",
                            line=dict(width=2),
                            marker=dict(size=8)
                        ))
                
                fig.update_layout(
                    title="各股票异动次数趋势",
                    xaxis_title="日期",
                    yaxis_title="异动次数",
                    hovermode='x unified',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 平均异动幅度趋势
                fig2 = go.Figure()
                for symbol in selected_stocks:
                    stock_data = daily_stats[daily_stats['股票代码'] == symbol]
                    if len(stock_data) > 0:
                        fig2.add_trace(go.Scatter(
                            x=stock_data['日期'],
                            y=stock_data['平均幅度'].abs(),
                            mode='lines+markers',
                            name=f"{symbol} 平均异动幅度",
                            line=dict(width=2),
                            marker=dict(size=8)
                        ))
                
                fig2.update_layout(
                    title="各股票平均异动幅度趋势",
                    xaxis_title="日期",
                    yaxis_title="平均异动幅度 (%)",
                    hovermode='x unified',
                    height=400
                )
                st.plotly_chart(fig2, use_container_width=True)
        
        with tab2:
            st.subheader("股票异动对比")
            if len(df) > 0:
                # 股票异动统计对比
                stock_summary = df.groupby('股票代码').agg({
                    '变化幅度': ['count', lambda x: (x > 0).sum(), lambda x: (x < 0).sum(), lambda x: x.abs().mean()],
                }).reset_index()
                stock_summary.columns = ['股票代码', '总异动次数', '上涨次数', '下跌次数', '平均异动幅度']
                
                # 异动次数对比柱状图
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x=stock_summary['股票代码'],
                    y=stock_summary['上涨次数'],
                    name='上涨异动',
                    marker_color='green'
                ))
                fig3.add_trace(go.Bar(
                    x=stock_summary['股票代码'],
                    y=stock_summary['下跌次数'],
                    name='下跌异动',
                    marker_color='red'
                ))
                
                fig3.update_layout(
                    title="各股票异动次数对比",
                    xaxis_title="股票代码",
                    yaxis_title="异动次数",
                    barmode='stack',
                    height=400
                )
                st.plotly_chart(fig3, use_container_width=True)
                
                # 平均异动幅度对比
                fig4 = px.bar(
                    stock_summary, 
                    x='股票代码', 
                    y='平均异动幅度',
                    title="各股票平均异动幅度对比",
                    color='平均异动幅度',
                    color_continuous_scale='Viridis'
                )
                fig4.update_layout(height=400)
                st.plotly_chart(fig4, use_container_width=True)
        
        with tab3:
            st.subheader("异动时间分布")
            if len(df) > 0:
                # 按小时统计异动分布
                df['小时'] = pd.to_datetime(df['检测时间']).dt.hour
                hourly_dist = df.groupby('小时').size().reset_index(name='异动次数')
                
                fig5 = px.bar(
                    hourly_dist, 
                    x='小时', 
                    y='异动次数',
                    title="异动时间分布（按小时）",
                    color='异动次数',
                    color_continuous_scale='Blues'
                )
                fig5.update_layout(height=400)
                st.plotly_chart(fig5, use_container_width=True)
                
                # 热力图：股票 x 小时
                if len(selected_stocks) > 1:
                    heatmap_data = df.groupby(['股票代码', '小时']).size().reset_index(name='异动次数')
                    heatmap_pivot = heatmap_data.pivot(index='股票代码', columns='小时', values='异动次数').fillna(0)
                    
                    fig6 = px.imshow(
                        heatmap_pivot,
                        title="股票异动时间热力图",
                        color_continuous_scale='Reds',
                        aspect='auto'
                    )
                    fig6.update_layout(height=400)
                    st.plotly_chart(fig6, use_container_width=True)
        
        with tab4:
            st.subheader("详细异动数据")
            # 数据过滤器
            col1, col2, col3 = st.columns(3)
            
            with col1:
                type_filter = st.selectbox(
                    "异动类型过滤",
                    options=["全部", "上涨", "下跌"],
                    index=0
                )
            
            with col2:
                min_change = st.number_input(
                    "最小变化幅度 (%)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1
                )
            
            with col3:
                sort_by = st.selectbox(
                    "排序方式",
                    options=["检测时间", "变化幅度", "股票代码"],
                    index=0
                )
            
            # 应用过滤器
            filtered_df = df.copy()
            if type_filter != "全部":
                filtered_df = filtered_df[filtered_df["异动类型"] == type_filter]
            
            filtered_df = filtered_df[filtered_df["变化幅度"].abs() >= min_change]
            
            # 排序
            if sort_by == "检测时间":
                filtered_df = filtered_df.sort_values("检测时间", ascending=False)
            elif sort_by == "变化幅度":
                filtered_df = filtered_df.sort_values("变化幅度", key=abs, ascending=False)
            else:
                filtered_df = filtered_df.sort_values("股票代码")
            
            # 显示数据表格
            display_df = filtered_df[["股票代码", "股票名称", "异动类型", "变化幅度", "触发价格", "前一价格", "检测时间"]].copy()
            display_df["变化幅度"] = display_df["变化幅度"].apply(lambda x: f"{x:+.2f}%")
            display_df["触发价格"] = display_df["触发价格"].apply(lambda x: f"{x:.2f}")
            display_df["前一价格"] = display_df["前一价格"].apply(lambda x: f"{x:.2f}")
            display_df["检测时间"] = pd.to_datetime(display_df["检测时间"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 导出功能
            if st.button("📥 导出数据到CSV"):
                csv_data = filtered_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="下载CSV文件",
                    data=csv_data,
                    file_name=f"anomaly_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
    except Exception as e:
        logger.error(f"❌ 渲染异动分析仪表板失败: {e}")
        st.error(f"异动分析仪表板错误: {e}") 