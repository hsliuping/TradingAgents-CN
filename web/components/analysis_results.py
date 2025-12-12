"""
分析结果管理组件
提供股票分析历史结果的查看和管理功能
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
import hashlib
import logging

# MongoDB相关导入
try:
    from web.utils.mongodb_report_manager import MongoDBReportManager
    MONGODB_AVAILABLE = True
    print("✅ MongoDB模块导入成功")
except ImportError as e:
    MONGODB_AVAILABLE = False
    print(f"❌ MongoDB模块导入失败: {e}")

# 设置日志
logger = logging.getLogger(__name__)

def safe_timestamp_to_datetime(timestamp_value):
    """安全地将时间戳转换为datetime对象"""
    if isinstance(timestamp_value, datetime):
        # 如果已经是datetime对象（来自MongoDB）
        return timestamp_value
    elif isinstance(timestamp_value, (int, float)):
        # 如果是时间戳数字（来自文件系统）
        try:
            return datetime.fromtimestamp(timestamp_value)
        except (ValueError, OSError):
            # 时间戳无效，使用当前时间
            return datetime.now()
    else:
        # 其他情况，使用当前时间
        return datetime.now()

def get_analysis_results_dir():
    """获取分析结果目录"""
    results_dir = Path(__file__).parent.parent / "data" / "analysis_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

def get_favorites_file():
    """获取收藏文件路径"""
    return get_analysis_results_dir() / "favorites.json"

def get_tags_file():
    """获取标签文件路径"""
    return get_analysis_results_dir() / "tags.json"

def load_favorites():
    """加载收藏列表"""
    favorites_file = get_favorites_file()
    if favorites_file.exists():
        try:
            with open(favorites_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_favorites(favorites):
    """保存收藏列表"""
    favorites_file = get_favorites_file()
    try:
        with open(favorites_file, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def load_tags():
    """加载标签数据"""
    tags_file = get_tags_file()
    if tags_file.exists():
        try:
            with open(tags_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tags(tags):
    """保存标签数据"""
    tags_file = get_tags_file()
    try:
        with open(tags_file, 'w', encoding='utf-8') as f:
            json.dump(tags, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def add_tag_to_analysis(analysis_id, tag):
    """为分析结果添加标签"""
    tags = load_tags()
    if analysis_id not in tags:
        tags[analysis_id] = []
    if tag not in tags[analysis_id]:
        tags[analysis_id].append(tag)
        save_tags(tags)

def remove_tag_from_analysis(analysis_id, tag):
    """从分析结果移除标签"""
    tags = load_tags()
    if analysis_id in tags and tag in tags[analysis_id]:
        tags[analysis_id].remove(tag)
        if not tags[analysis_id]:  # 如果没有标签了，删除该条目
            del tags[analysis_id]
        save_tags(tags)

def get_analysis_tags(analysis_id):
    """获取分析结果的标签"""
    tags = load_tags()
    return tags.get(analysis_id, [])

def load_analysis_results(start_date=None, end_date=None, stock_symbol=None, analyst_type=None,
                         limit=100, search_text=None, tags_filter=None, favorites_only=False):
    """加载分析结果 - 优先从MongoDB加载"""
    all_results = []
    favorites = load_favorites() if favorites_only else []
    tags_data = load_tags()
    mongodb_loaded = False

    # 优先从MongoDB加载数据
    if MONGODB_AVAILABLE:
        try:
            print("🔍 [数据加载] 从MongoDB加载分析结果")
            mongodb_manager = MongoDBReportManager()
            mongodb_results = mongodb_manager.get_all_reports()
            print(f"🔍 [数据加载] MongoDB返回 {len(mongodb_results)} 个结果")

            for mongo_result in mongodb_results:
                # 转换MongoDB结果格式
                result = {
                    'analysis_id': mongo_result.get('analysis_id', ''),
                    'timestamp': mongo_result.get('timestamp', 0),
                    'stock_symbol': mongo_result.get('stock_symbol', ''),
                    'analysts': mongo_result.get('analysts', []),
                    'research_depth': mongo_result.get('research_depth', 1),
                    'status': mongo_result.get('status', 'completed'),
                    'summary': mongo_result.get('summary', ''),
                    'performance': mongo_result.get('performance', {}),
                    'tags': tags_data.get(mongo_result.get('analysis_id', ''), []),
                    'is_favorite': mongo_result.get('analysis_id', '') in favorites,
                    'reports': mongo_result.get('reports', {}),
                    'source': 'mongodb'  # 标记数据来源
                }
                all_results.append(result)

            mongodb_loaded = True
            print(f"✅ 从MongoDB加载了 {len(mongodb_results)} 个分析结果")

        except Exception as e:
            print(f"❌ MongoDB加载失败: {e}")
            logger.error(f"MongoDB加载失败: {e}")
            mongodb_loaded = False
    else:
        print("⚠️ MongoDB不可用，将使用文件系统数据")

    # 只有在MongoDB加载失败或不可用时才从文件系统加载
    if not mongodb_loaded:
        print("🔄 [备用数据源] 从文件系统加载分析结果")

        # 首先尝试从Web界面的保存位置读取
        web_results_dir = get_analysis_results_dir()
        for result_file in web_results_dir.glob("*.json"):
            if result_file.name in ['favorites.json', 'tags.json']:
                continue

            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)

                    # 添加标签信息
                    result['tags'] = tags_data.get(result.get('analysis_id', ''), [])
                    result['is_favorite'] = result.get('analysis_id', '') in favorites
                    result['source'] = 'file_system'  # 标记数据来源

                    all_results.append(result)
            except Exception as e:
                st.warning(f"读取分析结果文件 {result_file.name} 失败: {e}")

        # 然后从实际的分析结果保存位置读取
        project_results_dir = Path(__file__).parent.parent.parent / "data" / "analysis_results" / "detailed"

        if project_results_dir.exists():
            # 遍历股票代码目录
            for stock_dir in project_results_dir.iterdir():
                if not stock_dir.is_dir():
                    continue

                stock_code = stock_dir.name

                # 遍历日期目录
                for date_dir in stock_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    date_str = date_dir.name
                    reports_dir = date_dir / "reports"

                    if not reports_dir.exists():
                        continue

                    # 读取所有报告文件
                    reports = {}
                    summary_content = ""

                    for report_file in reports_dir.glob("*.md"):
                        try:
                            with open(report_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                report_name = report_file.stem
                                reports[report_name] = content

                                # 如果是最终决策报告，提取摘要
                                if report_name == "final_trade_decision":
                                    # 提取前200个字符作为摘要
                                    summary_content = content[:200].replace('#', '').replace('*', '').strip()
                                    if len(content) > 200:
                                        summary_content += "..."

                        except Exception as e:
                            continue

                    if reports:
                        # 解析日期
                        try:
                            analysis_date = datetime.strptime(date_str, '%Y-%m-%d')
                            timestamp = analysis_date.timestamp()
                        except:
                            timestamp = datetime.now().timestamp()

                        # 创建分析结果条目
                        analysis_id = f"{stock_code}_{date_str}_{int(timestamp)}"

                        # 尝试从元数据文件中读取真实的研究深度和分析师信息
                        research_depth = 1
                        analysts = ['market', 'fundamentals', 'trader']  # 默认值

                        metadata_file = date_dir / "analysis_metadata.json"
                        if metadata_file.exists():
                            try:
                                with open(metadata_file, 'r', encoding='utf-8') as f:
                                    metadata = json.load(f)
                                    research_depth = metadata.get('research_depth', 1)
                                    analysts = metadata.get('analysts', analysts)
                            except Exception as e:
                                # 如果读取元数据失败，使用推断逻辑
                                if len(reports) >= 5:
                                    research_depth = 3
                                elif len(reports) >= 3:
                                    research_depth = 2
                        else:
                            # 如果没有元数据文件，使用推断逻辑
                            if len(reports) >= 5:
                                research_depth = 3
                            elif len(reports) >= 3:
                                research_depth = 2

                        result = {
                            'analysis_id': analysis_id,
                            'timestamp': timestamp,
                            'stock_symbol': stock_code,
                            'analysts': analysts,
                            'research_depth': research_depth,
                            'status': 'completed',
                            'summary': summary_content,
                            'performance': {},
                            'tags': tags_data.get(analysis_id, []),
                            'is_favorite': analysis_id in favorites,
                            'reports': reports,  # 保存所有报告内容
                            'source': 'file_system'  # 标记数据来源
                        }

                        all_results.append(result)

        print(f"🔄 [备用数据源] 从文件系统加载了 {len(all_results)} 个分析结果")
    
    # 过滤结果
    filtered_results = []
    for result in all_results:
        # 收藏过滤
        if favorites_only and not result.get('is_favorite', False):
            continue
            
        # 时间过滤
        if start_date or end_date:
            result_time = safe_timestamp_to_datetime(result.get('timestamp', 0))
            if start_date and result_time.date() < start_date:
                continue
            if end_date and result_time.date() > end_date:
                continue
        
        # 股票代码过滤
        if stock_symbol and stock_symbol.upper() not in result.get('stock_symbol', '').upper():
            continue
        
        # 分析师类型过滤
        if analyst_type and analyst_type not in result.get('analysts', []):
            continue
            
        # 文本搜索过滤
        if search_text:
            search_text = search_text.lower()
            searchable_text = f"{result.get('stock_symbol', '')} {result.get('summary', '')} {' '.join(result.get('analysts', []))}".lower()
            if search_text not in searchable_text:
                continue
                
        # 标签过滤
        if tags_filter:
            result_tags = result.get('tags', [])
            if not any(tag in result_tags for tag in tags_filter):
                continue
        
        filtered_results.append(result)
    
    # 按时间倒序排列 - 使用安全的时间戳转换函数确保类型一致
    filtered_results.sort(key=lambda x: safe_timestamp_to_datetime(x.get('timestamp', 0)), reverse=True)
    
    # 限制数量
    return filtered_results[:limit]

def render_analysis_results():
    """渲染分析结果管理界面"""
    
    # 检查权限
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from utils.auth_manager import auth_manager
        
        if not auth_manager or not auth_manager.check_permission("analysis"):
            st.error("❌ 您没有权限访问分析结果")
            st.info("💡 提示：分析结果功能需要 'analysis' 权限")
            return
    except Exception as e:
        st.error(f"❌ 权限检查失败: {e}")
        return
    
    st.title("📊 分析结果历史记录")
    
    # 侧边栏过滤选项
    with st.sidebar:
        st.header("🔍 搜索与过滤")
        
        # 文本搜索
        search_text = st.text_input("🔍 关键词搜索", placeholder="搜索股票代码、摘要内容...")
        
        # 收藏过滤
        favorites_only = st.checkbox("⭐ 仅显示收藏")
        
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
        
        # 股票代码过滤
        stock_filter = st.text_input("📈 股票代码", placeholder="如: 000001, AAPL")
        
        # 分析师类型过滤
        analyst_filter = st.selectbox(
            "👥 分析师类型",
            ["全部", "market_analyst", "social_media_analyst", "news_analyst", "fundamental_analyst"],
            help="注意：社交媒体分析师仅适用于美股和港股，A股分析中不包含此类型"
        )
        
        if analyst_filter == "全部":
            analyst_filter = None
            
        # 标签过滤
        all_tags = set()
        tags_data = load_tags()
        for tag_list in tags_data.values():
            all_tags.update(tag_list)
        
        if all_tags:
            selected_tags = st.multiselect("🏷️ 标签过滤", sorted(all_tags))
        else:
            selected_tags = []
    
    # 加载分析结果
    results = load_analysis_results(
        start_date=start_date,
        end_date=end_date,
        stock_symbol=stock_filter if stock_filter else None,
        analyst_type=analyst_filter,
        limit=200,
        search_text=search_text if search_text else None,
        tags_filter=selected_tags if selected_tags else None,
        favorites_only=favorites_only
    )
    
    if not results:
        st.warning("📭 未找到符合条件的分析结果")
        return
    
    # 显示统计概览
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 总分析数", len(results))
    
    with col2:
        unique_stocks = len(set(result.get('stock_symbol', 'unknown') for result in results))
        st.metric("📈 分析股票", unique_stocks)
    
    with col3:
        successful_analyses = sum(1 for result in results if result.get('status') == 'completed')
        success_rate = (successful_analyses / len(results) * 100) if results else 0
        st.metric("✅ 成功率", f"{success_rate:.1f}%")
    
    with col4:
        favorites_count = sum(1 for result in results if result.get('is_favorite', False))
        st.metric("⭐ 收藏数", favorites_count)
    
    # 保留需要的功能按钮，移除不需要的功能
    tab1, tab2, tab3 = st.tabs([
        "📋 结果列表", "📈 统计图表", "📊 详细分析"
    ])
    
    with tab1:
        render_results_list(results)
    
    with tab2:
        render_results_charts(results)
    
    with tab3:
        render_detailed_analysis(results)

def render_results_list(results: List[Dict[str, Any]]):
    """渲染分析结果列表"""
    
    st.subheader("📋 分析结果列表")
    
    # 排序选项
    col1, col2 = st.columns([2, 1])
    with col1:
        sort_by = st.selectbox("排序方式", ["时间倒序", "时间正序", "股票代码", "成功率"])
    with col2:
        view_mode = st.selectbox("显示模式", ["卡片视图", "表格视图"])
    
    # 排序结果
    if sort_by == "时间正序":
        results.sort(key=lambda x: safe_timestamp_to_datetime(x.get('timestamp', 0)))
    elif sort_by == "股票代码":
        results.sort(key=lambda x: x.get('stock_symbol', ''))
    elif sort_by == "成功率":
        results.sort(key=lambda x: 1 if x.get('status') == 'completed' else 0, reverse=True)
    
    if view_mode == "表格视图":
        render_results_table(results)
    else:
        render_results_cards(results)

def render_results_table(results: List[Dict[str, Any]]):
    """渲染表格视图"""
    
    # 准备表格数据
    table_data = []
    for result in results:
        table_data.append({
            '时间': safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M'),
            '股票': result.get('stock_symbol', 'unknown'),
            '分析师': ', '.join(result.get('analysts', [])[:2]) + ('...' if len(result.get('analysts', [])) > 2 else ''),
            '状态': '✅' if result.get('status') == 'completed' else '❌',
            '收藏': '⭐' if result.get('is_favorite', False) else '',
            '标签': ', '.join(result.get('tags', [])[:2]) + ('...' if len(result.get('tags', [])) > 2 else ''),
            '摘要': (result.get('summary', '')[:50] + '...') if len(result.get('summary', '')) > 50 else result.get('summary', '')
        })
    
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

def render_results_cards(results: List[Dict[str, Any]]):
    """渲染卡片视图"""
    
    # 分页设置
    page_size = st.selectbox("每页显示", [5, 10, 20, 50], index=1)
    total_pages = (len(results) + page_size - 1) // page_size
    
    if total_pages > 1:
        page = st.number_input("页码", min_value=1, max_value=total_pages, value=1) - 1
    else:
        page = 0
    
    # 获取当前页数据
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(results))
    page_results = results[start_idx:end_idx]
    
    # 显示结果卡片
    for i, result in enumerate(page_results):
        analysis_id = result.get('analysis_id', '')
        
        with st.container():
            # 卡片头部
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.markdown(f"### 📊 {result.get('stock_symbol', 'unknown')}")
                st.caption(f"🕐 {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col2:
                # 收藏按钮
                is_favorite = result.get('is_favorite', False)
                if st.button("⭐" if is_favorite else "☆", key=f"fav_{start_idx + i}"):
                    toggle_favorite(analysis_id)
                    st.rerun()
            
            with col3:
                # 查看详情按钮
                result_id = result.get('_id') or result.get('analysis_id') or f"result_{start_idx + i}"
                current_expanded = st.session_state.get('expanded_result_id') == result_id
                button_text = "🔼 收起" if current_expanded else "👁️ 详情"

                if st.button(button_text, key=f"view_{start_idx + i}"):
                    if current_expanded:
                        # 如果当前已展开，则收起
                        st.session_state['expanded_result_id'] = None
                    else:
                        # 展开当前结果的详情
                        st.session_state['expanded_result_id'] = result_id
                        st.session_state['selected_result_for_detail'] = result
                    st.rerun()
            
            with col4:
                # 状态显示
                status_icon = "✅" if result.get('status') == 'completed' else "❌"
                st.markdown(f"**状态**: {status_icon}")
            
            # 卡片内容
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**分析师**: {', '.join(result.get('analysts', []))}")
                st.write(f"**研究深度**: {result.get('research_depth', 'unknown')}")

                # 显示分析摘要
                if result.get('summary'):
                    summary = result['summary'][:150] + "..." if len(result['summary']) > 150 else result['summary']
                    st.write(f"**摘要**: {summary}")
            
            with col2:
                # 显示标签
                tags = result.get('tags', [])
                if tags:
                    st.write("**标签**:")
                    for tag in tags[:3]:  # 最多显示3个标签
                        st.markdown(f"`{tag}`")
                    if len(tags) > 3:
                        st.caption(f"还有 {len(tags) - 3} 个标签...")

            # 显示折叠详情
            result_id = result.get('_id') or result.get('analysis_id') or f"result_{start_idx + i}"
            if st.session_state.get('expanded_result_id') == result_id:
                show_expanded_detail(result)

            st.divider()
    
    # 显示分页信息
    if total_pages > 1:
        st.info(f"第 {page + 1} 页，共 {total_pages} 页，总计 {len(results)} 条记录")
    
    # 注意：详情现在以折叠方式显示在每个结果下方

# 弹窗功能已移除，详情现在以折叠方式显示

def toggle_favorite(analysis_id):
    """切换收藏状态"""
    favorites = load_favorites()
    if analysis_id in favorites:
        favorites.remove(analysis_id)
    else:
        favorites.append(analysis_id)
    save_favorites(favorites)

def render_results_comparison(results: List[Dict[str, Any]]):
    """渲染结果对比功能"""
    
    st.subheader("🔄 分析结果对比")
    
    if len(results) < 2:
        st.warning("至少需要2个分析结果才能进行对比")
        return
    
    # 选择要对比的结果
    col1, col2 = st.columns(2)
    
    result_options = []
    for i, result in enumerate(results[:20]):  # 限制选项数量
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))
    
    with col1:
        st.write("**选择结果A**")
        selected_a = st.selectbox("结果A", result_options, format_func=lambda x: x[0], key="compare_a")
        result_a = results[selected_a[1]]
    
    with col2:
        st.write("**选择结果B**")
        selected_b = st.selectbox("结果B", result_options, format_func=lambda x: x[0], key="compare_b")
        result_b = results[selected_b[1]]
    
    if selected_a[1] == selected_b[1]:
        st.warning("请选择不同的分析结果进行对比")
        return
    
    # 对比显示
    st.markdown("---")
    
    # 基本信息对比
    st.subheader("📋 基本信息对比")
    
    comparison_data = {
        '项目': ['股票代码', '分析时间', '分析师', '研究深度', '状态'],
        '结果A': [
            result_a.get('stock_symbol', 'unknown'),
            safe_timestamp_to_datetime(result_a.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
            ', '.join(result_a.get('analysts', [])),
            str(result_a.get('research_depth', 'unknown')),
            '完成' if result_a.get('status') == 'completed' else '失败'
        ],
        '结果B': [
            result_b.get('stock_symbol', 'unknown'),
            safe_timestamp_to_datetime(result_b.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
            ', '.join(result_b.get('analysts', [])),
            str(result_b.get('research_depth', 'unknown')),
            '完成' if result_b.get('status') == 'completed' else '失败'
        ]
    }
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True)
    
    # 摘要对比
    if result_a.get('summary') or result_b.get('summary'):
        st.subheader("📝 分析摘要对比")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**结果A摘要**")
            st.text_area("", value=result_a.get('summary', '暂无摘要'), height=200, key="summary_a", disabled=True)
        
        with col2:
            st.write("**结果B摘要**")
            st.text_area("", value=result_b.get('summary', '暂无摘要'), height=200, key="summary_b", disabled=True)
    
    # 性能对比
    perf_a = result_a.get('performance', {})
    perf_b = result_b.get('performance', {})
    
    if perf_a or perf_b:
        st.subheader("⚡ 性能指标对比")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**结果A性能**")
            if perf_a:
                st.json(perf_a)
            else:
                st.info("暂无性能数据")
        
        with col2:
            st.write("**结果B性能**")
            if perf_b:
                st.json(perf_b)
            else:
                st.info("暂无性能数据")

def render_results_charts(results: List[Dict[str, Any]]):
    """渲染分析结果统计图表"""
    
    st.subheader("📈 统计图表")
    
    # 按股票统计
    st.subheader("📊 按股票统计")
    stock_counts = {}
    for result in results:
        stock = result.get('stock_symbol', 'unknown')
        stock_counts[stock] = stock_counts.get(stock, 0) + 1
    
    if stock_counts:
        # 只显示前10个最常分析的股票
        top_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        stocks = [item[0] for item in top_stocks]
        counts = [item[1] for item in top_stocks]
        
        fig_bar = px.bar(
            x=stocks,
            y=counts,
            title="最常分析的股票 (前10名)",
            labels={'x': '股票代码', 'y': '分析次数'},
            color=counts,
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # 按时间统计
    st.subheader("📅 每日分析趋势")
    daily_results = {}
    for result in results:
        date_str = safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%Y-%m-%d')
        daily_results[date_str] = daily_results.get(date_str, 0) + 1
    
    if daily_results:
        dates = sorted(daily_results.keys())
        counts = [daily_results[date] for date in dates]
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=dates,
            y=counts,
            mode='lines+markers',
            name='每日分析数',
            line=dict(color='#2E8B57', width=3),
            marker=dict(size=8, color='#FF6B6B'),
            fill='tonexty'
        ))
        fig_line.update_layout(
            title="每日分析趋势",
            xaxis_title="日期",
            yaxis_title="分析数量",
            hovermode='x unified'
        )
        st.plotly_chart(fig_line, use_container_width=True)
    
    # 按分析师类型统计
    st.subheader("👥 分析师使用分布")
    analyst_counts = {}
    for result in results:
        analysts = result.get('analysts', [])
        for analyst in analysts:
            analyst_counts[analyst] = analyst_counts.get(analyst, 0) + 1
    
    if analyst_counts:
        fig_pie = px.pie(
            values=list(analyst_counts.values()),
            names=list(analyst_counts.keys()),
            title="分析师使用分布",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # 成功率统计
    st.subheader("✅ 分析成功率统计")
    success_data = {'成功': 0, '失败': 0}
    for result in results:
        if result.get('status') == 'completed':
            success_data['成功'] += 1
        else:
            success_data['失败'] += 1
    
    if success_data['成功'] + success_data['失败'] > 0:
        fig_success = px.pie(
            values=list(success_data.values()),
            names=list(success_data.keys()),
            title="分析成功率",
            color_discrete_map={'成功': '#4CAF50', '失败': '#F44336'}
        )
        st.plotly_chart(fig_success, use_container_width=True)
    
    # 标签使用统计
    tags_data = load_tags()
    if tags_data:
        st.subheader("🏷️ 标签使用统计")
        tag_counts = {}
        for tag_list in tags_data.values():
            for tag in tag_list:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        if tag_counts:
            # 只显示前10个最常用的标签
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            tags = [item[0] for item in top_tags]
            counts = [item[1] for item in top_tags]
            
            fig_tags = px.bar(
                x=tags,
                y=counts,
                title="最常用标签 (前10名)",
                labels={'x': '标签', 'y': '使用次数'},
                color=counts,
                color_continuous_scale='plasma'
            )
            fig_tags.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_tags, use_container_width=True)

def render_tags_management(results: List[Dict[str, Any]]):
    """渲染标签管理功能"""
    
    st.subheader("🏷️ 标签管理")
    
    # 获取所有标签
    all_tags = set()
    tags_data = load_tags()
    for tag_list in tags_data.values():
        all_tags.update(tag_list)
    
    # 标签统计
    if all_tags:
        st.write("**现有标签统计**")
        tag_counts = {}
        for tag_list in tags_data.values():
            for tag in tag_list:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # 显示标签云
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 创建标签云可视化
            if tag_counts:
                fig = px.bar(
                    x=list(tag_counts.keys()),
                    y=list(tag_counts.values()),
                    title="标签使用频率",
                    labels={'x': '标签', 'y': '使用次数'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("**标签列表**")
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                st.write(f"• {tag} ({count})")
    
    # 批量标签操作
    st.markdown("---")
    st.write("**批量标签操作**")
    
    # 选择要操作的结果
    if results:
        selected_results = st.multiselect(
            "选择分析结果",
            options=range(len(results)),
            format_func=lambda i: f"{results[i].get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(results[i].get('timestamp', 0)).strftime('%m-%d %H:%M')}",
            max_selections=10
        )
        
        if selected_results:
            col1, col2 = st.columns(2)
            
            with col1:
                # 添加标签
                new_tag = st.text_input("新标签名称", placeholder="输入标签名称")
                if st.button("➕ 添加标签") and new_tag:
                    for idx in selected_results:
                        analysis_id = results[idx].get('analysis_id', '')
                        if analysis_id:
                            add_tag_to_analysis(analysis_id, new_tag)
                    st.success(f"已为 {len(selected_results)} 个结果添加标签: {new_tag}")
                    st.rerun()
            
            with col2:
                # 移除标签
                if all_tags:
                    remove_tag = st.selectbox("选择要移除的标签", sorted(all_tags))
                    if st.button("➖ 移除标签") and remove_tag:
                        for idx in selected_results:
                            analysis_id = results[idx].get('analysis_id', '')
                            if analysis_id:
                                remove_tag_from_analysis(analysis_id, remove_tag)
                        st.success(f"已从 {len(selected_results)} 个结果移除标签: {remove_tag}")
                        st.rerun()

def render_results_export(results: List[Dict[str, Any]]):
    """渲染分析结果导出功能"""
    
    st.subheader("📤 导出分析结果")
    
    if not results:
        st.warning("没有可导出的分析结果")
        return
    
    # 导出选项
    export_type = st.selectbox("选择导出内容", ["摘要信息", "完整数据"])
    export_format = st.selectbox("选择导出格式", ["CSV", "JSON", "Excel"])
    
    if st.button("📥 导出结果"):
        try:
            if export_type == "摘要信息":
                # 导出摘要信息
                summary_data = []
                for result in results:
                    summary_data.append({
                        '分析时间': safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        '股票代码': result.get('stock_symbol', 'unknown'),
                        '分析师': ', '.join(result.get('analysts', [])),
                        '研究深度': result.get('research_depth', 'unknown'),
                        '状态': result.get('status', 'unknown'),
                        '摘要': result.get('summary', '')[:100] + '...' if len(result.get('summary', '')) > 100 else result.get('summary', '')
                    })
                
                if export_format == "CSV":
                    df = pd.DataFrame(summary_data)
                    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
                    
                    st.download_button(
                        label="下载 CSV 文件",
                        data=csv_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                elif export_format == "JSON":
                    json_data = json.dumps(summary_data, ensure_ascii=False, indent=2)
                    
                    st.download_button(
                        label="下载 JSON 文件",
                        data=json_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
                elif export_format == "Excel":
                    df = pd.DataFrame(summary_data)
                    
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='分析摘要')
                    
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="下载 Excel 文件",
                        data=excel_data,
                        file_name=f"analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            else:  # 完整数据
                if export_format == "JSON":
                    json_data = json.dumps(results, ensure_ascii=False, indent=2)
                    
                    st.download_button(
                        label="下载完整数据 JSON 文件",
                        data=json_data,
                        file_name=f"analysis_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                else:
                    st.warning("完整数据只支持 JSON 格式导出")
            
            st.success(f"✅ {export_format} 文件准备完成，请点击下载按钮")
            
        except Exception as e:
            st.error(f"❌ 导出失败: {e}")

def render_results_comparison(results: List[Dict[str, Any]]):
    """渲染分析结果对比"""
    
    st.subheader("🔍 分析结果对比")
    
    if len(results) < 2:
        st.info("至少需要2个分析结果才能进行对比")
        return
    
    # 选择要对比的分析结果
    st.write("**选择要对比的分析结果：**")
    
    col1, col2 = st.columns(2)
    
    # 准备选项
    result_options = []
    for i, result in enumerate(results[:20]):  # 限制前20个
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))
    
    with col1:
        st.write("**分析结果 A**")
        selected_a = st.selectbox(
            "选择第一个分析结果", 
            result_options, 
            format_func=lambda x: x[0],
            key="compare_a"
        )
        result_a = results[selected_a[1]]
    
    with col2:
        st.write("**分析结果 B**")
        selected_b = st.selectbox(
            "选择第二个分析结果", 
            result_options, 
            format_func=lambda x: x[0],
            key="compare_b"
        )
        result_b = results[selected_b[1]]
    
    if selected_a[1] == selected_b[1]:
        st.warning("请选择不同的分析结果进行对比")
        return
    
    # 基本信息对比
    st.subheader("📊 基本信息对比")
    
    comparison_data = {
        "项目": ["股票代码", "分析时间", "分析师数量", "研究深度", "状态", "标签数量"],
        "分析结果 A": [
            result_a.get('stock_symbol', 'unknown'),
            safe_timestamp_to_datetime(result_a.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
            len(result_a.get('analysts', [])),
            result_a.get('research_depth', 'unknown'),
            "✅ 完成" if result_a.get('status') == 'completed' else "❌ 失败",
            len(result_a.get('tags', []))
        ],
        "分析结果 B": [
            result_b.get('stock_symbol', 'unknown'),
            safe_timestamp_to_datetime(result_b.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
            len(result_b.get('analysts', [])),
            result_b.get('research_depth', 'unknown'),
            "✅ 完成" if result_b.get('status') == 'completed' else "❌ 失败",
            len(result_b.get('tags', []))
        ]
    }
    
    import pandas as pd
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True)
    
    # 性能指标对比
    perf_a = result_a.get('performance', {})
    perf_b = result_b.get('performance', {})
    
    if perf_a or perf_b:
        st.subheader("⚡ 性能指标对比")
        
        # 合并所有性能指标键
        all_perf_keys = set(perf_a.keys()) | set(perf_b.keys())
        
        if all_perf_keys:
            perf_comparison = {
                "指标": list(all_perf_keys),
                "分析结果 A": [perf_a.get(key, "N/A") for key in all_perf_keys],
                "分析结果 B": [perf_b.get(key, "N/A") for key in all_perf_keys]
            }
            
            df_perf = pd.DataFrame(perf_comparison)
            st.dataframe(df_perf, use_container_width=True)
    
    # 标签对比
    tags_a = set(result_a.get('tags', []))
    tags_b = set(result_b.get('tags', []))
    
    if tags_a or tags_b:
        st.subheader("🏷️ 标签对比")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**共同标签**")
            common_tags = tags_a & tags_b
            if common_tags:
                for tag in common_tags:
                    st.markdown(f"✅ `{tag}`")
            else:
                st.write("无共同标签")
        
        with col2:
            st.write("**仅在结果A中**")
            only_a = tags_a - tags_b
            if only_a:
                for tag in only_a:
                    st.markdown(f"🔵 `{tag}`")
            else:
                st.write("无独有标签")
        
        with col3:
            st.write("**仅在结果B中**")
            only_b = tags_b - tags_a
            if only_b:
                for tag in only_b:
                    st.markdown(f"🔴 `{tag}`")
            else:
                st.write("无独有标签")
    
    # 摘要对比
    summary_a = result_a.get('summary', '')
    summary_b = result_b.get('summary', '')
    
    if summary_a or summary_b:
        st.subheader("📝 分析摘要对比")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**分析结果 A 摘要**")
            if summary_a:
                st.markdown(summary_a)
            else:
                st.write("无摘要")
        
        with col2:
            st.write("**分析结果 B 摘要**")
            if summary_b:
                st.markdown(summary_b)
            else:
                st.write("无摘要")
    
    # 详细内容对比
    st.subheader("📊 详细内容对比")
    
    # 定义要对比的关键字段
    comparison_fields = [
        ('market_report', '📈 市场技术分析'),
        ('fundamentals_report', '💰 基本面分析'),
        ('sentiment_report', '💭 市场情绪分析'),
        ('news_report', '📰 新闻事件分析'),
        ('risk_assessment', '⚠️ 风险评估'),
        ('investment_plan', '📋 投资建议'),
        ('final_trade_decision', '🎯 最终交易决策')
    ]
    
    # 创建对比标签页
    available_fields = []
    for field_key, field_name in comparison_fields:
        if (field_key in result_a and result_a[field_key]) or (field_key in result_b and result_b[field_key]):
            available_fields.append((field_key, field_name))
    
    if available_fields:
        tabs = st.tabs([field_name for _, field_name in available_fields])
        
        for i, (tab, (field_key, field_name)) in enumerate(zip(tabs, available_fields)):
            with tab:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**分析结果 A**")
                    content_a = result_a.get(field_key, '')
                    if content_a:
                        if isinstance(content_a, str):
                            st.markdown(content_a)
                        else:
                            st.write(content_a)
                    else:
                        st.write("无此项分析")
                
                with col2:
                    st.write("**分析结果 B**")
                    content_b = result_b.get(field_key, '')
                    if content_b:
                        if isinstance(content_b, str):
                            st.markdown(content_b)
                        else:
                            st.write(content_b)
                    else:
                        st.write("无此项分析")

def render_detailed_analysis(results: List[Dict[str, Any]]):
    """渲染详细分析"""
    
    st.subheader("📊 详细分析")
    
    if not results:
        st.info("没有可分析的数据")
        return
    
    # 选择要查看的分析结果
    result_options = []
    for i, result in enumerate(results[:50]):  # 显示前50个
        option = f"{result.get('stock_symbol', 'unknown')} - {safe_timestamp_to_datetime(result.get('timestamp', 0)).strftime('%m-%d %H:%M')}"
        result_options.append((option, i))
    
    if result_options:
        selected_option = st.selectbox(
            "选择分析结果", 
            result_options, 
            format_func=lambda x: x[0]
        )
        selected_result = results[selected_option[1]]
        
        # 显示基本信息
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("股票代码", selected_result.get('stock_symbol', 'unknown'))
            st.metric("分析师数量", len(selected_result.get('analysts', [])))
        
        with col2:
            analysis_time = safe_timestamp_to_datetime(selected_result.get('timestamp', 0))
            st.metric("分析时间", analysis_time.strftime('%m-%d %H:%M'))
            status = "✅ 完成" if selected_result.get('status') == 'completed' else "❌ 失败"
            st.metric("状态", status)
        
        with col3:
            st.metric("研究深度", selected_result.get('research_depth', 'unknown'))
            tags = selected_result.get('tags', [])
            st.metric("标签数量", len(tags))
        
        # 显示标签
        if tags:
            st.write("**标签**:")
            tag_cols = st.columns(min(len(tags), 5))
            for i, tag in enumerate(tags):
                with tag_cols[i % 5]:
                    st.markdown(f"`{tag}`")
        
        # 显示分析摘要
        if selected_result.get('summary'):
            st.subheader("📝 分析摘要")
            st.markdown(selected_result['summary'])
        
        # 显示性能指标
        performance = selected_result.get('performance', {})
        if performance:
            st.subheader("⚡ 性能指标")
            perf_cols = st.columns(len(performance))
            for i, (key, value) in enumerate(performance.items()):
                with perf_cols[i]:
                    st.metric(key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, (int, float)) else str(value))
        
        # 显示完整分析结果
        if st.checkbox("显示完整分析结果"):
            render_detailed_analysis_content(selected_result)

def render_detailed_analysis_content(selected_result):
    """渲染详细分析结果内容"""
    st.subheader("📊 完整分析数据")

    # 检查是否有报告数据（支持文件系统和MongoDB）
    if 'reports' in selected_result and selected_result['reports']:
        # 显示文件系统中的报告
        reports = selected_result['reports']
        
        if not reports:
            st.warning("该分析结果没有可用的报告内容")
            return
        
        # 调试信息：显示所有可用的报告
        print(f"🔍 [弹窗调试] 数据来源: {selected_result.get('source', '未知')}")
        print(f"🔍 [弹窗调试] 可用报告数量: {len(reports)}")
        print(f"🔍 [弹窗调试] 报告类型: {list(reports.keys())}")

        # 创建标签页显示不同的报告
        report_tabs = list(reports.keys())

        # 为报告名称添加中文标题和图标
        report_display_names = {
            'final_trade_decision': '🎯 最终交易决策',
            'fundamentals_report': '💰 基本面分析',
            'technical_report': '📈 技术面分析',
            'market_sentiment_report': '💭 市场情绪分析',
            'risk_assessment_report': '⚠️ 风险评估',
            'price_target_report': '🎯 目标价格分析',
            'summary_report': '📋 分析摘要',
            'news_analysis_report': '📰 新闻分析',
            'social_media_report': '📱 社交媒体分析'
        }
        
        # 创建显示名称列表
        tab_names = []
        for report_key in report_tabs:
            display_name = report_display_names.get(report_key, f"📄 {report_key.replace('_', ' ').title()}")
            tab_names.append(display_name)
            print(f"🔍 [弹窗调试] 添加标签: {display_name}")

        print(f"🔍 [弹窗调试] 总标签数: {len(tab_names)}")
        
        if len(tab_names) == 1:
            # 只有一个报告，直接显示
            st.markdown(f"### {tab_names[0]}")
            st.markdown("---")
            st.markdown(reports[report_tabs[0]])
        else:
            # 多个报告，使用标签页
            tabs = st.tabs(tab_names)
            
            for i, (tab, report_key) in enumerate(zip(tabs, report_tabs)):
                with tab:
                    st.markdown(reports[report_key])
        
        return
    
    # 添加自定义CSS样式美化标签页
    st.markdown("""
    <style>
    /* 标签页容器样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    /* 单个标签页样式 */
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 8px 16px;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e1e5e9;
        color: #495057;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* 标签页悬停效果 */
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e3f2fd;
        border-color: #2196f3;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(33,150,243,0.2);
    }

    /* 选中的标签页样式 */
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-color: #667eea !important;
        box-shadow: 0 4px 12px rgba(102,126,234,0.3) !important;
        transform: translateY(-2px);
    }

    /* 标签页内容区域 */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 20px;
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e1e5e9;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* 标签页文字样式 */
    .stTabs [data-baseweb="tab"] p {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
    }

    /* 选中标签页的文字样式 */
    .stTabs [aria-selected="true"] p {
        color: white !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 定义分析模块
    analysis_modules = [
        {
            'key': 'market_report',
            'title': '📈 市场技术分析',
            'icon': '📈',
            'description': '技术指标、价格趋势、支撑阻力位分析'
        },
        {
            'key': 'fundamentals_report',
            'title': '💰 基本面分析',
            'icon': '💰',
            'description': '财务数据、估值水平、盈利能力分析'
        },
        {
            'key': 'sentiment_report',
            'title': '💭 市场情绪分析',
            'icon': '💭',
            'description': '投资者情绪、社交媒体情绪指标'
        },
        {
            'key': 'news_report',
            'title': '📰 新闻事件分析',
            'icon': '📰',
            'description': '相关新闻事件、市场动态影响分析'
        },
        {
            'key': 'risk_assessment',
            'title': '⚠️ 风险评估',
            'icon': '⚠️',
            'description': '风险因素识别、风险等级评估'
        },
        {
            'key': 'investment_plan',
            'title': '📋 投资建议',
            'icon': '📋',
            'description': '具体投资策略、仓位管理建议'
        },
        {
            'key': 'investment_debate_state',
            'title': '🔬 研究团队决策',
            'icon': '🔬',
            'description': '多头/空头研究员辩论分析，研究经理综合决策'
        },
        {
            'key': 'trader_investment_plan',
            'title': '💼 交易团队计划',
            'icon': '💼',
            'description': '专业交易员制定的具体交易执行计划'
        },
        {
            'key': 'risk_debate_state',
            'title': '⚖️ 风险管理团队',
            'icon': '⚖️',
            'description': '激进/保守/中性分析师风险评估，投资组合经理最终决策'
        },
        {
            'key': 'final_trade_decision',
            'title': '🎯 最终交易决策',
            'icon': '🎯',
            'description': '综合所有团队分析后的最终投资决策'
        }
    ]
    
    # 过滤出有数据的模块
    available_modules = []
    for module in analysis_modules:
        if module['key'] in selected_result and selected_result[module['key']]:
            # 检查字典类型的数据是否有实际内容
            if isinstance(selected_result[module['key']], dict):
                # 对于字典，检查是否有非空的值
                has_content = any(v for v in selected_result[module['key']].values() if v)
                if has_content:
                    available_modules.append(module)
            else:
                # 对于字符串或其他类型，直接添加
                available_modules.append(module)

    if not available_modules:
        # 如果没有预定义模块的数据，显示所有可用的分析数据
        st.info("📊 显示完整分析报告数据")
        
        # 排除一些基础字段，只显示分析相关的数据
        excluded_keys = {'analysis_id', 'timestamp', 'stock_symbol', 'analysts', 
                        'research_depth', 'status', 'summary', 'performance', 
                        'is_favorite', 'tags', 'full_data'}
        
        # 获取所有分析相关的数据
        analysis_data = {}
        for key, value in selected_result.items():
            if key not in excluded_keys and value:
                analysis_data[key] = value
        
        # 如果有full_data字段，优先使用它
        if 'full_data' in selected_result and selected_result['full_data']:
            full_data = selected_result['full_data']
            if isinstance(full_data, dict):
                for key, value in full_data.items():
                    if key not in excluded_keys and value:
                        analysis_data[key] = value
        
        if analysis_data:
            # 创建动态标签页显示所有分析数据
            tab_names = []
            tab_data = []
            
            for key, value in analysis_data.items():
                # 格式化标签页名称
                tab_name = key.replace('_', ' ').title()
                if 'report' in key.lower():
                    tab_name = f"📊 {tab_name}"
                elif 'analysis' in key.lower():
                    tab_name = f"🔍 {tab_name}"
                elif 'decision' in key.lower():
                    tab_name = f"🎯 {tab_name}"
                elif 'plan' in key.lower():
                    tab_name = f"📋 {tab_name}"
                else:
                    tab_name = f"📄 {tab_name}"
                
                tab_names.append(tab_name)
                tab_data.append((key, value))
            
            # 创建标签页
            tabs = st.tabs(tab_names)
            
            for i, (tab, (key, value)) in enumerate(zip(tabs, tab_data)):
                with tab:
                    st.markdown(f"## {tab_names[i]}")
                    st.markdown("---")
                    
                    # 根据数据类型显示内容
                    if isinstance(value, str):
                        # 如果是长文本，使用markdown显示
                        if len(value) > 100:
                            st.markdown(value)
                        else:
                            st.write(value)
                    elif isinstance(value, dict):
                        # 字典类型，递归显示
                        for sub_key, sub_value in value.items():
                            if sub_value:
                                st.subheader(sub_key.replace('_', ' ').title())
                                if isinstance(sub_value, str):
                                    st.markdown(sub_value)
                                else:
                                    st.write(sub_value)
                    elif isinstance(value, list):
                        # 列表类型
                        for idx, item in enumerate(value):
                            st.subheader(f"项目 {idx + 1}")
                            if isinstance(item, str):
                                st.markdown(item)
                            else:
                                st.write(item)
                    else:
                        # 其他类型直接显示
                        st.write(value)
        else:
            # 如果真的没有任何分析数据，显示原始JSON
            st.warning("📊 该分析结果暂无详细报告数据")
            with st.expander("查看原始数据"):
                st.json(selected_result)
        return

    # 只为有数据的模块创建标签页
    tabs = st.tabs([module['title'] for module in available_modules])

    for i, (tab, module) in enumerate(zip(tabs, available_modules)):
        with tab:
            # 在内容区域显示图标和描述
            st.markdown(f"## {module['icon']} {module['title']}")
            st.markdown(f"*{module['description']}*")
            st.markdown("---")

            # 格式化显示内容
            content = selected_result[module['key']]
            if isinstance(content, str):
                st.markdown(content)
            elif isinstance(content, dict):
                # 特殊处理团队决策报告的字典结构
                if module['key'] == 'investment_debate_state':
                    render_investment_debate_content(content)
                elif module['key'] == 'risk_debate_state':
                    render_risk_debate_content(content)
                else:
                    # 普通字典格式化显示
                    for key, value in content.items():
                        if value:  # 只显示非空值
                            st.subheader(key.replace('_', ' ').title())
                            if isinstance(value, str):
                                st.markdown(value)
                            else:
                                st.write(value)
            else:
                st.write(content)

def render_investment_debate_content(content):
    """渲染投资辩论内容"""
    if 'bull_analyst_report' in content and content['bull_analyst_report']:
        st.subheader("🐂 多头分析师观点")
        st.markdown(content['bull_analyst_report'])
    
    if 'bear_analyst_report' in content and content['bear_analyst_report']:
        st.subheader("🐻 空头分析师观点")
        st.markdown(content['bear_analyst_report'])
    
    if 'research_manager_decision' in content and content['research_manager_decision']:
        st.subheader("👨‍💼 研究经理决策")
        st.markdown(content['research_manager_decision'])

def render_risk_debate_content(content):
    """渲染风险辩论内容"""
    if 'aggressive_analyst_report' in content and content['aggressive_analyst_report']:
        st.subheader("🔥 激进分析师观点")
        st.markdown(content['aggressive_analyst_report'])
    
    if 'conservative_analyst_report' in content and content['conservative_analyst_report']:
        st.subheader("🛡️ 保守分析师观点")
        st.markdown(content['conservative_analyst_report'])
    
    if 'neutral_analyst_report' in content and content['neutral_analyst_report']:
        st.subheader("⚖️ 中性分析师观点")
        st.markdown(content['neutral_analyst_report'])
    
    if 'portfolio_manager_decision' in content and content['portfolio_manager_decision']:
        st.subheader("👨‍💼 投资组合经理决策")
        st.markdown(content['portfolio_manager_decision'])

def save_analysis_result(analysis_id: str, stock_symbol: str, analysts: List[str],
                        research_depth: int, result_data: Dict, status: str = "completed"):
    """保存分析结果"""
    try:
        from web.utils.async_progress_tracker import safe_serialize

        # 创建结果条目，使用安全序列化
        result_entry = {
            'analysis_id': analysis_id,
            'timestamp': datetime.now().timestamp(),
            'stock_symbol': stock_symbol,
            'analysts': analysts,
            'research_depth': research_depth,
            'status': status,
            'summary': safe_serialize(result_data.get('summary', '')),
            'performance': safe_serialize(result_data.get('performance', {})),
            'full_data': safe_serialize(result_data)
        }

        # 1. 保存到文件系统（保持兼容性）
        results_dir = get_analysis_results_dir()
        result_file = results_dir / f"analysis_{analysis_id}.json"

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_entry, f, ensure_ascii=False, indent=2)

        # 2. 保存到MongoDB（如果可用）
        if MONGODB_AVAILABLE:
            try:
                print(f"💾 [MongoDB保存] 开始保存分析结果: {analysis_id}")
                mongodb_manager = MongoDBReportManager()

                # 使用标准的save_analysis_report方法，确保数据结构一致
                analysis_results = {
                    'stock_symbol': result_entry.get('stock_symbol', ''),
                    'analysts': result_entry.get('analysts', []),
                    'research_depth': result_entry.get('research_depth', 1),
                    'summary': result_entry.get('summary', ''),
                    'model_info': result_entry.get('model_info', 'Unknown')  # 🔥 添加模型信息字段
                }

                # 尝试从文件系统读取报告内容
                reports = {}
                try:
                    # 构建报告目录路径
                    from pathlib import Path
                    import os

                    # 获取当前日期
                    current_date = datetime.now().strftime('%Y-%m-%d')

                    # 构建报告路径
                    project_root = Path(__file__).parent.parent.parent
                    reports_dir = project_root / "data" / "analysis_results" / stock_symbol / current_date / "reports"

                    # 确保路径在Windows上正确显示（避免双反斜杠）
                    reports_dir_str = os.path.normpath(str(reports_dir))
                    print(f"🔍 [MongoDB保存] 查找报告目录: {reports_dir_str}")

                    if reports_dir.exists():
                        # 读取所有报告文件
                        for report_file in reports_dir.glob("*.md"):
                            try:
                                with open(report_file, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    report_name = report_file.stem
                                    reports[report_name] = content
                                    print(f"✅ [MongoDB保存] 读取报告: {report_name} ({len(content)} 字符)")
                            except Exception as e:
                                print(f"⚠️ [MongoDB保存] 读取报告文件失败 {report_file}: {e}")

                        print(f"📊 [MongoDB保存] 共读取 {len(reports)} 个报告文件")
                    else:
                        print(f"⚠️ [MongoDB保存] 报告目录不存在: {reports_dir_str}")

                except Exception as e:
                    print(f"⚠️ [MongoDB保存] 读取报告文件异常: {e}")
                    reports = {}

                # 使用标准保存方法，确保字段结构一致
                success = mongodb_manager.save_analysis_report(
                    stock_symbol=result_entry.get('stock_symbol', ''),
                    analysis_results=analysis_results,
                    reports=reports
                )

                if success:
                    print(f"✅ [MongoDB保存] 分析结果已保存到MongoDB: {analysis_id} (包含 {len(reports)} 个报告)")
                else:
                    print(f"❌ [MongoDB保存] 保存失败: {analysis_id}")

            except Exception as e:
                print(f"❌ [MongoDB保存] 保存异常: {e}")
                logger.error(f"MongoDB保存异常: {e}")

        return True

    except Exception as e:
        print(f"❌ [保存分析结果] 保存失败: {e}")
        logger.error(f"保存分析结果异常: {e}")
        return False

def show_expanded_detail(result):
    """显示展开的详情内容"""

    # 创建详情容器
    with st.container():
        st.markdown("---")
        st.markdown("### 📊 详细分析报告")

        # 检查是否有报告数据
        if 'reports' not in result or not result['reports']:
            # 如果没有reports字段，检查是否有其他分析数据
            if result.get('summary'):
                st.subheader("📝 分析摘要")
                st.markdown(result['summary'])

            # 检查是否有full_data中的报告
            if 'full_data' in result and result['full_data']:
                full_data = result['full_data']
                if isinstance(full_data, dict):
                    # 显示full_data中的分析内容
                    analysis_fields = [
                        ('market_report', '📈 市场分析'),
                        ('fundamentals_report', '💰 基本面分析'),
                        ('sentiment_report', '💭 情感分析'),
                        ('news_report', '📰 新闻分析'),
                        ('risk_assessment', '⚠️ 风险评估'),
                        ('investment_plan', '📋 投资建议'),
                        ('final_trade_decision', '🎯 最终决策')
                    ]

                    available_reports = []
                    for field_key, field_name in analysis_fields:
                        if field_key in full_data and full_data[field_key]:
                            available_reports.append((field_key, field_name, full_data[field_key]))

                    if available_reports:
                        # 创建标签页显示分析内容
                        tab_names = [name for _, name, _ in available_reports]
                        tabs = st.tabs(tab_names)

                        for i, (tab, (field_key, field_name, content)) in enumerate(zip(tabs, available_reports)):
                            with tab:
                                if isinstance(content, str):
                                    st.markdown(content)
                                elif isinstance(content, dict):
                                    for key, value in content.items():
                                        if value:
                                            st.subheader(key.replace('_', ' ').title())
                                            st.markdown(str(value))
                                else:
                                    st.write(content)
                    else:
                        st.info("暂无详细分析报告")
                else:
                    st.info("暂无详细分析报告")
            else:
                st.info("暂无详细分析报告")
            return

        # 获取报告数据
        reports = result['reports']

        # 为报告名称添加中文标题和图标
        report_display_names = {
            'final_trade_decision': '🎯 最终交易决策',
            'fundamentals_report': '💰 基本面分析',
            'technical_report': '📈 技术面分析',
            'market_sentiment_report': '💭 市场情绪分析',
            'risk_assessment_report': '⚠️ 风险评估',
            'price_target_report': '🎯 目标价格分析',
            'summary_report': '📋 分析摘要',
            'news_analysis_report': '📰 新闻分析',
            'news_report': '📰 新闻分析',
            'market_report': '📈 市场分析',
            'social_media_report': '📱 社交媒体分析',
            'bull_state': '🐂 多头观点',
            'bear_state': '🐻 空头观点',
            'trader_state': '💼 交易员分析',
            'invest_judge_state': '⚖️ 投资判断',
            'research_team_state': '🔬 研究团队观点',
            'risk_debate_state': '⚠️ 风险管理讨论',
            'research_team_decision': '🔬 研究团队决策',
            'risk_management_decision': '🛡️ 风险管理决策',
            'investment_plan': '📋 投资计划',
            'trader_investment_plan': '💼 交易员投资计划',
            'investment_debate_state': '💬 投资讨论状态'
        }

        # 创建标签页显示不同的报告
        report_tabs = list(reports.keys())
        tab_names = []
        for report_key in report_tabs:
            display_name = report_display_names.get(report_key, f"📄 {report_key.replace('_', ' ').title()}")
            tab_names.append(display_name)

        if len(tab_names) == 1:
            # 只有一个报告，直接显示内容（不添加额外标题，避免重复）
            report_content = reports[report_tabs[0]]
            # 如果报告内容已经包含标题，直接显示；否则添加标题
            if not report_content.strip().startswith('#'):
                st.markdown(f"### {tab_names[0]}")
                st.markdown("---")
            st.markdown(report_content)
        else:
            # 多个报告，使用标签页
            tabs = st.tabs(tab_names)

            for i, (tab, report_key) in enumerate(zip(tabs, report_tabs)):
                with tab:
                    st.markdown(reports[report_key])

        st.markdown("---")