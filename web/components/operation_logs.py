"""
操作日志管理组件
提供用户操作日志的查看和管理功能
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
import os
from pathlib import Path

def get_operation_logs_dir():
    """获取操作日志目录"""
    logs_dir = Path(__file__).parent.parent / "data" / "operation_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

def get_user_activities_dir():
    """获取用户活动日志目录"""
    logs_dir = Path(__file__).parent.parent / "data" / "user_activities"
    return logs_dir

def load_operation_logs(start_date=None, end_date=None, username=None, action_type=None, limit=1000):
    """加载操作日志（包含用户活动日志）"""
    all_logs = []
    
    # 1. 加载新的操作日志（operation_logs目录）
    logs_dir = get_operation_logs_dir()
    for log_file in logs_dir.glob("*.json"):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                if isinstance(logs, list):
                    all_logs.extend(logs)
                elif isinstance(logs, dict):
                    all_logs.append(logs)
        except Exception as e:
            st.error(f"读取日志文件失败: {log_file.name} - {e}")
    
    for log_file in logs_dir.glob("*.jsonl"):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        log_entry = json.loads(line.strip())
                        all_logs.append(log_entry)
        except Exception as e:
            st.error(f"读取JSONL日志文件失败: {log_file.name} - {e}")
    
    # 2. 加载用户活动日志（user_activities目录）
    user_activities_dir = get_user_activities_dir()
    if user_activities_dir.exists():
        for log_file in user_activities_dir.glob("*.jsonl"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            log_entry = json.loads(line.strip())
                            # 转换用户活动日志格式以兼容操作日志格式
                            converted_log = {
                                'timestamp': log_entry.get('timestamp'),
                                'username': log_entry.get('username'),
                                'user_role': log_entry.get('user_role'),
                                'action_type': log_entry.get('action_type'),
                                'action': log_entry.get('action_name'),
                                'details': log_entry.get('details', {}),
                                'success': log_entry.get('success', True),
                                'error_message': log_entry.get('error_message'),
                                'session_id': log_entry.get('session_id'),
                                'ip_address': log_entry.get('ip_address'),
                                'user_agent': log_entry.get('user_agent'),
                                'page_url': log_entry.get('page_url'),
                                'duration_ms': log_entry.get('duration_ms'),
                                'datetime': log_entry.get('datetime')
                            }
                            all_logs.append(converted_log)
            except Exception as e:
                st.error(f"读取用户活动日志文件失败: {log_file.name} - {e}")
    
    # 过滤日志
    filtered_logs = []
    for log in all_logs:
        # 时间过滤
        if start_date or end_date:
            try:
                # 处理时间戳，支持字符串和数字格式
                timestamp = log.get('timestamp', 0)
                if isinstance(timestamp, str):
                    # 如果是字符串，尝试转换为浮点数
                    try:
                        timestamp = float(timestamp)
                    except (ValueError, TypeError):
                        # 如果转换失败，尝试解析ISO格式的日期时间
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            timestamp = dt.timestamp()
                        except:
                            timestamp = 0
                
                log_date = datetime.fromtimestamp(timestamp).date()
                if start_date and log_date < start_date:
                    continue
                if end_date and log_date > end_date:
                    continue
            except Exception as e:
                # 如果时间戳处理失败，跳过时间过滤
                pass
        
        # 用户名过滤
        if username and log.get('username', '').lower() != username.lower():
            continue
        
        # 操作类型过滤
        if action_type and log.get('action_type', '') != action_type:
            continue
        
        filtered_logs.append(log)
    
    # 定义安全的时间戳转换函数
    def safe_timestamp(log_entry):
        """安全地获取时间戳，确保返回数字类型"""
        timestamp = log_entry.get('timestamp', 0)
        if isinstance(timestamp, str):
            try:
                return float(timestamp)
            except (ValueError, TypeError):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.timestamp()
                except:
                    return 0
        return timestamp if isinstance(timestamp, (int, float)) else 0
    
    # 按时间戳排序（最新的在前）
    filtered_logs.sort(key=safe_timestamp, reverse=True)
    
    # 限制数量
    return filtered_logs[:limit]

def render_operation_logs():
    """渲染操作日志管理界面"""
    
    # 检查权限
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from utils.auth_manager import auth_manager
        
        if not auth_manager or not auth_manager.check_permission("admin"):
            st.error("❌ 您没有权限访问操作日志")
            st.info("💡 提示：操作日志功能需要 'admin' 权限")
            return
    except Exception as e:
        st.error(f"❌ 权限检查失败: {e}")
        return
    
    st.title("📋 操作日志管理")
    
    # 侧边栏过滤选项
    with st.sidebar:
        st.header("🔍 过滤选项")
        
        # 日期范围选择
        date_range = st.selectbox(
            "📅 时间范围",
            ["最近1天", "最近3天", "最近7天", "最近30天", "自定义"],
            index=2
        )
        
        if date_range == "自定义":
            start_date = st.date_input("开始日期", datetime.now() - timedelta(days=7))
            end_date = st.date_input("结束日期", datetime.now())
        else:
            days_map = {"最近1天": 1, "最近3天": 3, "最近7天": 7, "最近30天": 30}
            days = days_map[date_range]
            end_date = datetime.now().date()
            start_date = (datetime.now() - timedelta(days=days)).date()
        
        # 用户过滤
        username_filter = st.text_input("👤 用户名过滤", placeholder="留空显示所有用户")
        
        # 操作类型过滤
        action_type_filter = st.selectbox(
            "🔧 操作类型",
            ["全部", "auth", "analysis", "navigation", "config", "data_export", "user_management", "system", "login", "logout", "export", "admin"]
        )
        
        if action_type_filter == "全部":
            action_type_filter = None
    
    # 加载操作日志
    logs = load_operation_logs(
        start_date=start_date,
        end_date=end_date,
        username=username_filter if username_filter else None,
        action_type=action_type_filter,
        limit=1000
    )
    
    if not logs:
        st.warning("📭 未找到符合条件的操作日志")
        return
    
    # 显示统计概览
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 总操作数", len(logs))
    
    with col2:
        unique_users = len(set(log.get('username', 'unknown') for log in logs))
        st.metric("👥 活跃用户", unique_users)
    
    with col3:
        successful_ops = sum(1 for log in logs if log.get('success', True))
        success_rate = (successful_ops / len(logs) * 100) if logs else 0
        st.metric("✅ 成功率", f"{success_rate:.1f}%")
    
    with col4:
        # 安全处理近1小时的日志统计
        recent_logs = []
        for log in logs:
            try:
                timestamp = log.get('timestamp', 0)
                if isinstance(timestamp, str):
                    try:
                        timestamp = float(timestamp)
                    except (ValueError, TypeError):
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            timestamp = dt.timestamp()
                        except:
                            continue
                if datetime.fromtimestamp(timestamp) > datetime.now() - timedelta(hours=1):
                    recent_logs.append(log)
            except:
                continue
        st.metric("🕐 近1小时", len(recent_logs))
    
    # 标签页
    tab1, tab2, tab3 = st.tabs(["📈 统计图表", "📋 日志列表", "📤 导出数据"])
    
    with tab1:
        render_logs_charts(logs)
    
    with tab2:
        render_logs_list(logs)
    
    with tab3:
        render_logs_export(logs)

def render_logs_charts(logs: List[Dict[str, Any]]):
    """渲染日志统计图表"""
    
    # 按操作类型统计
    st.subheader("📊 按操作类型统计")
    action_types = {}
    for log in logs:
        action_type = log.get('action_type', 'unknown')
        action_types[action_type] = action_types.get(action_type, 0) + 1
    
    if action_types:
        fig_pie = px.pie(
            values=list(action_types.values()),
            names=list(action_types.keys()),
            title="操作类型分布"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # 按时间统计
    st.subheader("📅 按时间统计")
    daily_logs = {}
    for log in logs:
        # 安全处理时间戳
        try:
            timestamp = log.get('timestamp', 0)
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp = dt.timestamp()
                    except:
                        timestamp = 0
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        except:
            date_str = 'unknown'
        
        if date_str != 'unknown':
            daily_logs[date_str] = daily_logs.get(date_str, 0) + 1
    
    if daily_logs:
        dates = sorted(daily_logs.keys())
        counts = [daily_logs[date] for date in dates]
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=dates,
            y=counts,
            mode='lines+markers',
            name='每日操作数',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
        ))
        fig_line.update_layout(
            title="每日操作趋势",
            xaxis_title="日期",
            yaxis_title="操作数量"
        )
        st.plotly_chart(fig_line, use_container_width=True)
    
    # 按用户统计
    st.subheader("👥 按用户统计")
    user_logs = {}
    for log in logs:
        username = log.get('username', 'unknown')
        user_logs[username] = user_logs.get(username, 0) + 1
    
    if user_logs:
        # 只显示前10个最活跃的用户
        top_users = sorted(user_logs.items(), key=lambda x: x[1], reverse=True)[:10]
        usernames = [item[0] for item in top_users]
        counts = [item[1] for item in top_users]
        
        fig_bar = px.bar(
            x=counts,
            y=usernames,
            orientation='h',
            title="用户操作排行榜 (前10名)",
            labels={'x': '操作数量', 'y': '用户名'}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

def render_logs_list(logs: List[Dict[str, Any]]):
    """渲染日志列表"""
    
    st.subheader("📋 操作日志列表")
    
    # 分页设置
    page_size = st.selectbox("每页显示", [10, 25, 50, 100], index=1)
    total_pages = (len(logs) + page_size - 1) // page_size
    
    if total_pages > 1:
        page = st.number_input("页码", min_value=1, max_value=total_pages, value=1) - 1
    else:
        page = 0
    
    # 获取当前页数据
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(logs))
    page_logs = logs[start_idx:end_idx]
    
    # 转换为DataFrame显示
    if page_logs:
        df_data = []
        for log in page_logs:
            # 获取操作描述，兼容不同格式
            action_desc = log.get('action') or log.get('action_name', 'unknown')
            
            # 处理时间戳显示
            try:
                timestamp = log.get('timestamp', 0)
                if isinstance(timestamp, str):
                    try:
                        timestamp = float(timestamp)
                    except (ValueError, TypeError):
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            timestamp = dt.timestamp()
                        except:
                            timestamp = 0
                time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = 'unknown'
            
            df_data.append({
                '时间': time_str,
                '用户': log.get('username', 'unknown'),
                '角色': log.get('user_role', 'unknown'),
                '操作类型': log.get('action_type', 'unknown'),
                '操作描述': action_desc,
                '状态': '✅ 成功' if log.get('success', True) else '❌ 失败',
                '详情': str(log.get('details', ''))[:50] + '...' if len(str(log.get('details', ''))) > 50 else str(log.get('details', ''))
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # 显示分页信息
        if total_pages > 1:
            st.info(f"第 {page + 1} 页，共 {total_pages} 页，总计 {len(logs)} 条记录")
    else:
        st.info("当前页没有数据")

def render_logs_export(logs: List[Dict[str, Any]]):
    """渲染日志导出功能"""
    
    st.subheader("📤 导出操作日志")
    
    if not logs:
        st.warning("没有可导出的日志数据")
        return
    
    # 导出格式选择
    export_format = st.selectbox("选择导出格式", ["CSV", "JSON", "Excel"])
    
    if st.button("📥 导出日志"):
        try:
            if export_format == "CSV":
                # 转换为DataFrame
                df_data = []
                for log in logs:
                    # 获取操作描述，兼容不同格式
                    action_desc = log.get('action') or log.get('action_name', 'unknown')
                    
                    # 处理时间戳显示
                    try:
                        timestamp = log.get('timestamp', 0)
                        if isinstance(timestamp, str):
                            try:
                                timestamp = float(timestamp)
                            except (ValueError, TypeError):
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    timestamp = dt.timestamp()
                                except:
                                    timestamp = 0
                        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = 'unknown'
                    
                    df_data.append({
                        '时间': time_str,
                        '用户': log.get('username', 'unknown'),
                        '角色': log.get('user_role', 'unknown'),
                        '操作类型': log.get('action_type', 'unknown'),
                        '操作描述': action_desc,
                        '状态': '成功' if log.get('success', True) else '失败',
                        '详情': str(log.get('details', ''))
                    })
                
                df = pd.DataFrame(df_data)
                csv_data = df.to_csv(index=False, encoding='utf-8-sig')
                
                st.download_button(
                    label="下载 CSV 文件",
                    data=csv_data,
                    file_name=f"operation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            elif export_format == "JSON":
                json_data = json.dumps(logs, ensure_ascii=False, indent=2)
                
                st.download_button(
                    label="下载 JSON 文件",
                    data=json_data,
                    file_name=f"operation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            elif export_format == "Excel":
                # 转换为DataFrame
                df_data = []
                for log in logs:
                    # 获取操作描述，兼容不同格式
                    action_desc = log.get('action') or log.get('action_name', 'unknown')
                    
                    # 处理时间戳显示
                    try:
                        timestamp = log.get('timestamp', 0)
                        if isinstance(timestamp, str):
                            try:
                                timestamp = float(timestamp)
                            except (ValueError, TypeError):
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    timestamp = dt.timestamp()
                                except:
                                    timestamp = 0
                        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = 'unknown'
                    
                    df_data.append({
                        '时间': time_str,
                        '用户': log.get('username', 'unknown'),
                        '角色': log.get('user_role', 'unknown'),
                        '操作类型': log.get('action_type', 'unknown'),
                        '操作描述': action_desc,
                        '状态': '成功' if log.get('success', True) else '失败',
                        '详情': str(log.get('details', ''))
                    })
                
                df = pd.DataFrame(df_data)
                
                # 使用BytesIO创建Excel文件
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='操作日志')
                
                excel_data = output.getvalue()
                
                st.download_button(
                    label="下载 Excel 文件",
                    data=excel_data,
                    file_name=f"operation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            st.success(f"✅ {export_format} 文件准备完成，请点击下载按钮")
            
        except Exception as e:
            st.error(f"❌ 导出失败: {e}")

def log_operation(username: str, action_type: str, action: str, details: Dict = None, success: bool = True):
    """记录操作日志"""
    try:
        logs_dir = get_operation_logs_dir()
        
        # 按日期创建日志文件
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = logs_dir / f"operations_{today}.json"
        
        # 创建日志条目
        log_entry = {
            'timestamp': datetime.now().timestamp(),
            'username': username,
            'action_type': action_type,
            'action': action,
            'details': details or {},
            'success': success,
            'ip_address': None,  # 可以后续添加IP地址记录
            'user_agent': None   # 可以后续添加用户代理记录
        }
        
        # 读取现有日志
        existing_logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)
            except:
                existing_logs = []
        
        # 添加新日志
        existing_logs.append(log_entry)
        
        # 写入文件
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(existing_logs, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"记录操作日志失败: {e}")
        return False