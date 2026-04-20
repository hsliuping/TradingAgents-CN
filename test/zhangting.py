import streamlit as st
import pywencai
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak
import plotly.express as px

# 设置全局显示选项
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', 100)

# 自定义CSS样式 - 修改为红涨绿跌
st.markdown("""
<style>
    /* 主标题样式 */
    .title-text {
        color: #2c3e50;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-align: center;
    }

    /* 副标题样式 */
    .subheader-text {
        color: #3498db;
        font-size: 1.5rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.3rem;
    }

    /* 指标卡片样式 */
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        height: 100%;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .metric-title {
        color: #7f8c8d;
        font-size: 1rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        color: #2c3e50;
        font-size: 1.5rem;  /* 减小数字大小 */
        font-weight: bold;
    }

    /* 数据表格样式 */
    .dataframe {
        border-radius: 10px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    .dataframe th {
        background-color: #3498db !important;
        color: white !important;
        font-weight: bold !important;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f8f9fa !important;
    }

    /* 连板卡片样式 - 优化版 */
    .promotion-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #3498db;
        transition: all 0.3s ease;
    }
    .promotion-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .promotion-title {
        color: #2c3e50;
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .promotion-rate {
        color: #3498db;
        font-size: 1rem;
        margin-bottom: 0.8rem;
        display: flex;
        justify-content: space-between;
    }
    .promotion-rate-value {
        font-weight: bold;
        font-size: 1.1rem;
    }
    .stock-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        transition: all 0.2s ease;
    }
    .stock-item:hover {
        background-color: #ecf0f1;
    }
    .stock-name {
        font-weight: 500;
        color: #2c3e50;
    }
    .stock-concept {
        color: #95a5a6;
        font-size: 0.85rem;
        max-width: 150px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* 涨跌停数样式 - 修改为红涨绿跌 */
    .limit-count {
        display: flex;
        justify-content: center;
        gap: 1rem;
    }
    .limit-up {
        color: #e74c3c;  /* 红色表示涨 */
        font-weight: bold;
    }
    .limit-down {
        color: #27ae60;  /* 绿色表示跌 */
        font-weight: bold;
    }
    .limit-separator {
        color: #7f8c8d;
    }

    /* 加载动画 */
    .stSpinner>div {
        border-top-color: #3498db !important;
    }

    /* 空状态提示 */
    .empty-state {
        text-align: center;
        padding: 2rem;
        color: #7f8c8d;
        font-size: 1.1rem;
    }

    /* 涨跌颜色 - 修改为红涨绿跌 */
    .positive-change {
        color: #e74c3c !important;  /* 红色表示涨 */
        font-weight: bold;
    }
    .negative-change {
        color: #27ae60 !important;  /* 绿色表示跌 */
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# 数据获取函数
def get_market_data(date, query_type):
    query_map = {
        'limit_up': f"非ST,{date.strftime('%Y%m%d')}涨停",
        'limit_down': f"非ST,{date.strftime('%Y%m%d')}跌停",
        'poban': f"非ST,{date.strftime('%Y%m%d')}曾涨停"
    }

    try:
        df = pywencai.get(
            query=query_map[query_type],
            sort_key='成交金额',
            sort_order='desc',
            loop=True
        )
        return df if not df.empty else None
    except Exception as e:
        st.error(f"获取{query_type}数据时出错: {str(e)}")
        return None


def get_trade_dates():
    try:
        trade_date_range = ak.tool_trade_date_hist_sina()
        trade_date_range['trade_date'] = pd.to_datetime(trade_date_range['trade_date']).dt.date
        return trade_date_range
    except Exception as e:
        st.error(f"获取交易日数据时出错: {str(e)}")
        return pd.DataFrame()


# 涨停概念统计函数
def get_concept_counts(df, date):
    if df is None or df.empty:
        return pd.DataFrame()

    reason_col = f'涨停原因类别[{date.strftime("%Y%m%d")}]'
    if reason_col not in df.columns:
        return pd.DataFrame()

    try:
        concepts = df[reason_col].astype(str).str.split('+').explode().reset_index(drop=True)
        concept_counts = concepts.value_counts().reset_index()
        concept_counts.columns = ['概念', '出现次数']
        return concept_counts
    except Exception as e:
        st.error(f"统计概念时出错: {str(e)}")
        return pd.DataFrame()


# 分析连续涨停数据
def analyze_continuous_limit_up(df, date):
    if df is None or df.empty:
        return pd.DataFrame()

    date_str = date.strftime("%Y%m%d")
    required_columns = [
        f'连续涨停天数[{date_str}]', '股票代码', '股票简称', '最新价',
        f'涨停原因类别[{date_str}]', f'首次涨停时间[{date_str}]',
        f'最终涨停时间[{date_str}]', f'涨停封单量[{date_str}]',
        f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]'
    ]

    # 只保留存在的列
    available_columns = [col for col in required_columns if col in df.columns]
    if not available_columns:
        return pd.DataFrame()

    # 填充缺失的涨停原因类别
    reason_col = f'涨停原因类别[{date_str}]'
    if reason_col in df.columns:
        df[reason_col] = df[reason_col].fillna('未知')

    # 确保连续涨停天数是数值类型
    days_col = f'连续涨停天数[{date_str}]'
    if days_col in df.columns:
        df[days_col] = pd.to_numeric(df[days_col], errors='coerce').fillna(1)

    # 排序
    sort_cols = []
    if days_col in df.columns:
        sort_cols.append(days_col)
    if reason_col in df.columns:
        sort_cols.append(reason_col)

    df_sorted = df.sort_values(sort_cols, ascending=[False, True]) if sort_cols else df

    # 创建结果DataFrame
    column_mapping = {
        days_col: '连续涨停天数',
        '股票代码': '股票代码',
        '股票简称': '股票简称',
        '最新价': '最新价',
        reason_col: '涨停原因类别',
        f'首次涨停时间[{date_str}]': '首次涨停时间',
        f'最终涨停时间[{date_str}]': '最终涨停时间',
        f'涨停封单量[{date_str}]': '涨停封单量',
        f'涨停封单额[{date_str}]': '涨停封单额',
        f'涨停类型[{date_str}]': '涨停类型'
    }

    final_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
    result = df_sorted[list(final_mapping.keys())].copy()
    result.columns = [final_mapping[col] for col in result.columns]

    return result.reset_index(drop=True)


# 连板晋级率计算函数 - 美观优化版
def calculate_promotion_rates(current_df, previous_df, current_date, previous_date):
    """
    计算连板晋级率

    参数:
        current_df: 当前交易日涨停数据
        previous_df: 前一交易日涨停数据
        current_date: 当前交易日
        previous_date: 前一交易日

    返回:
        包含晋级率分析的DataFrame
    """
    if current_df is None or previous_df is None:
        return pd.DataFrame()

    current_days_col = f'连续涨停天数[{current_date.strftime("%Y%m%d")}]'
    previous_days_col = f'连续涨停天数[{previous_date.strftime("%Y%m%d")}]'

    promotion_data = []

    # 获取最大连板数
    max_days = 0
    if current_days_col in current_df.columns:
        current_df[current_days_col] = pd.to_numeric(current_df[current_days_col], errors='coerce')
        max_days = max(max_days, current_df[current_days_col].max() or 0)

    if previous_days_col in previous_df.columns:
        previous_df[previous_days_col] = pd.to_numeric(previous_df[previous_days_col], errors='coerce')
        max_days = max(max_days, previous_df[previous_days_col].max() or 0)

    for days in range(1, int(max_days) + 1):
        # 前一交易日该连板数的股票数量
        prev_count = 0
        if previous_days_col in previous_df.columns:
            prev_count = len(previous_df[previous_df[previous_days_col] == days])

        # 当前交易日连板数+1的股票数量
        curr_count = 0
        if current_days_col in current_df.columns:
            curr_count = len(current_df[current_df[current_days_col] == days + 1])

        if prev_count > 0:
            rate = round(curr_count / prev_count * 100)
            promotion_rate = {
                'text': f"{curr_count}/{prev_count} = {rate}%",
                'rate': rate,
                'success': curr_count,
                'total': prev_count
            }
        else:
            promotion_rate = {
                'text': "N/A",
                'rate': 0,
                'success': 0,
                'total': 0
            }

        # 获取晋级股票列表
        promoted_stocks = pd.DataFrame()
        if current_days_col in current_df.columns:
            promoted_mask = current_df[current_days_col] == days + 1
            if promoted_mask.any():
                promoted_stocks = current_df.loc[promoted_mask,
                ['股票代码', '股票简称', f'涨停原因类别[{current_date.strftime("%Y%m%d")}]']]

        promotion_data.append({
            '连板数': f"{days} → {days + 1}板",
            '晋级率': promotion_rate,
            '股票列表': promoted_stocks
        })

    return pd.DataFrame(promotion_data)


# 主应用
def app():
    # 主标题
    st.markdown('<p class="title-text">📈 A股涨停概念分析</p>', unsafe_allow_html=True)

    # 获取交易日数据
    with st.spinner("正在加载交易日数据..."):
        trade_date_range = get_trade_dates()
        if trade_date_range.empty:
            st.error("无法获取交易日数据，请检查网络连接或稍后再试。")
            return

    # 日期选择
    today = datetime.now().date()
    if not trade_date_range.empty:
        if today in trade_date_range['trade_date'].values:
            default_date = today
        else:
            default_date = trade_date_range[trade_date_range['trade_date'] <= today]['trade_date'].max()
    else:
        default_date = today

    selected_date = st.date_input(
        "📅 选择分析日期",
        value=default_date,
        min_value=trade_date_range['trade_date'].min() if not trade_date_range.empty else today - timedelta(days=30),
        max_value=trade_date_range['trade_date'].max() if not trade_date_range.empty else today,
        key="date_selector"
    )

    # 检查选择的日期是否是交易日
    if not trade_date_range.empty and selected_date not in trade_date_range['trade_date'].values:
        st.warning("⚠️ 所选日期不是A股交易日，已自动选择最近的交易日")
        selected_date = trade_date_range[trade_date_range['trade_date'] <= selected_date]['trade_date'].max()
        st.info(f"📅 已选择: {selected_date.strftime('%Y-%m-%d')}")

    # 获取前一交易日
    previous_dates = trade_date_range[trade_date_range['trade_date'] < selected_date]
    if previous_dates.empty:
        st.warning("没有找到前一交易日数据")
        return

    previous_date = previous_dates['trade_date'].max()
    st.success(
        f"📊 分析日期: {selected_date.strftime('%Y-%m-%d')} (对比前一交易日: {previous_date.strftime('%Y-%m-%d')})")

    # 获取数据
    with st.spinner("正在获取市场数据..."):
        selected_df = get_market_data(selected_date, 'limit_up')
        previous_df = get_market_data(previous_date, 'limit_up')
        poban_df = get_market_data(selected_date, 'poban')
        yesterday_zt_df = get_market_data(previous_date, 'limit_up')
        selected_limit_down_df = get_market_data(selected_date, 'limit_down')
        previous_limit_down_df = get_market_data(previous_date, 'limit_down')

    # 计算关键指标
    yesterday_zt_stocks = yesterday_zt_df['股票代码'].tolist() if yesterday_zt_df is not None else []
    today_zt_stocks = selected_df['股票代码'].tolist() if selected_df is not None else []
    poban_stocks = poban_df['股票代码'].tolist() if poban_df is not None else []

    # 连板率
    lianban_molecule = len(set(yesterday_zt_stocks) & set(today_zt_stocks))
    lianban_denominator = len(yesterday_zt_stocks) if yesterday_zt_stocks else 1
    lianban_rate = round(lianban_molecule / lianban_denominator * 100, 1)

    # 破板率
    poban_molecule = len(poban_stocks)
    poban_denominator = len(poban_stocks) + len(today_zt_stocks) if today_zt_stocks else 1
    poban_rate = round(poban_molecule / poban_denominator * 100, 1)

    # 昨日涨停今日上涨率
    up_count, total_count, up_rate = 0, 0, 0
    if yesterday_zt_df is not None and '最新涨跌幅' in yesterday_zt_df.columns:
        yesterday_zt_df['最新涨跌幅'] = pd.to_numeric(yesterday_zt_df['最新涨跌幅'], errors='coerce')
        up_count = np.sum(yesterday_zt_df['最新涨跌幅'] > 0)
        total_count = yesterday_zt_df['最新涨跌幅'].count()
        up_rate = round(up_count / total_count * 100, 1) if total_count > 0 else 0

    # 展示关键指标 - 减小数字大小
    st.markdown('<p class="subheader-text">📊 市场情绪指标</p>', unsafe_allow_html=True)

    cols = st.columns(3)
    with cols[0]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">昨日涨停今日上涨率</div>
                <div class="metric-value" style="font-size: 1.2rem;">{up_count}/{total_count}={up_rate}%</div>
                <div style="font-size: 0.8rem; color: #7f8c8d; margin-top: 0.5rem;">昨日涨停股票今日上涨比例</div>
            </div>
        """, unsafe_allow_html=True)

    with cols[1]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">连板晋级率</div>
                <div class="metric-value" style="font-size: 1.2rem;">{lianban_molecule}/{lianban_denominator}={lianban_rate}%</div>
                <div style="font-size: 0.8rem; color: #7f8c8d; margin-top: 0.5rem;">昨日涨停今日继续涨停比例</div>
            </div>
        """, unsafe_allow_html=True)

    with cols[2]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">涨停破板率</div>
                <div class="metric-value" style="font-size: 1.2rem;">{poban_molecule}/{poban_denominator}={poban_rate}%</div>
                <div style="font-size: 0.8rem; color: #7f8c8d; margin-top: 0.5rem;">今日曾触及涨停但未封板比例</div>
            </div>
        """, unsafe_allow_html=True)

    # 涨停和跌停数量变化 - 修改为红涨绿跌
    st.markdown('<p class="subheader-text">📈 涨停和跌停股票数量变化</p>', unsafe_allow_html=True)

    selected_total = len(selected_df) if selected_df is not None else 0
    previous_total = len(previous_df) if previous_df is not None else 0
    change = selected_total - previous_total

    selected_limit_down_total = len(selected_limit_down_df) if selected_limit_down_df is not None else 0
    previous_limit_down_total = len(previous_limit_down_df) if previous_limit_down_df is not None else 0
    limit_down_change = selected_limit_down_total - previous_limit_down_total

    cols = st.columns(3)
    with cols[0]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">上交易日涨跌停数</div>
                <div class="limit-count" style="font-size: 1.3rem;">
                    <span class="limit-up">{previous_total}</span>
                    <span class="limit-separator">/</span>
                    <span class="limit-down">{previous_limit_down_total}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with cols[1]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">选定日期涨跌停数</div>
                <div class="limit-count" style="font-size: 1.3rem;">
                    <span class="limit-up">{selected_total}</span>
                    <span class="limit-separator">/</span>
                    <span class="limit-down">{selected_limit_down_total}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with cols[2]:
        change_color = "#e74c3c" if change >= 0 else "#27ae60"  # 红色表示涨，绿色表示跌
        limit_down_color = "#27ae60" if limit_down_change >= 0 else "#e74c3c"  # 绿色表示跌，红色表示涨
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">涨跌停变化</div>
                <div class="limit-count" style="font-size: 1.3rem;">
                    <span class="limit-up" style="color: {change_color};">{f"+{change}" if change > 0 else change}</span>
                    <span class="limit-separator">/</span>
                    <span class="limit-down" style="color: {limit_down_color};">{f"+{limit_down_change}" if limit_down_change > 0 else limit_down_change}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # 涨停概念分析
    st.markdown('<p class="subheader-text">🧩 涨停概念分析</p>', unsafe_allow_html=True)

    if selected_df is not None and previous_df is not None:
        selected_concepts = get_concept_counts(selected_df, selected_date)
        previous_concepts = get_concept_counts(previous_df, previous_date)

        if not selected_concepts.empty and not previous_concepts.empty:
            # 概念对比图表
            merged = pd.merge(
                selected_concepts,
                previous_concepts,
                on='概念',
                how='outer',
                suffixes=('_今日', '_昨日')
            ).fillna(0)

            merged['变化'] = merged['出现次数_今日'] - merged['出现次数_昨日']
            merged = merged.sort_values('出现次数_今日', ascending=False).head(10)

            fig = px.bar(
                merged,
                x='概念',
                y=['出现次数_昨日', '出现次数_今日'],
                title='热门涨停概念对比',
                labels={'value': '出现次数', 'variable': '日期'},
                barmode='group',
                color_discrete_sequence=['#3498db', '#e74c3c']  # 修改颜色
            )
            fig.update_layout(
                xaxis_title='概念',
                yaxis_title='出现次数',
                legend_title='日期',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#2c3e50')
            )
            st.plotly_chart(fig, use_container_width=True)

            # 概念数据表格
            st.markdown("**概念热度变化**")

            # 修复格式化问题
            def format_change(val):
                if pd.isna(val):
                    return ""
                return f"{int(val):+d}" if not pd.isna(val) else ""

            styled_df = merged.style

            if '出现次数_今日' in merged.columns:
                styled_df = styled_df.background_gradient(
                    cmap='Reds',  # 修改为红色
                    subset=['出现次数_今日']
                ).format({'出现次数_今日': '{:.0f}'})

            if '出现次数_昨日' in merged.columns:
                styled_df = styled_df.format({'出现次数_昨日': '{:.0f}'})

            if '变化' in merged.columns:
                styled_df = styled_df.background_gradient(
                    cmap='Reds',  # 修改为红色
                    subset=['变化']
                ).format({'变化': format_change})

            st.dataframe(styled_df, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">没有可用的概念分析数据</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">缺少涨停数据，无法进行概念分析</div>', unsafe_allow_html=True)

    # 连续涨停天数分析
    st.markdown('<p class="subheader-text">🏆 连续涨停天数分析</p>', unsafe_allow_html=True)

    if selected_df is not None:
        selected_continuous = analyze_continuous_limit_up(selected_df, selected_date)
        if not selected_continuous.empty:
            # 转换数值列
            numeric_cols = ['最新价', '涨停封单量', '涨停封单额']
            for col in numeric_cols:
                if col in selected_continuous.columns:
                    selected_continuous[col] = pd.to_numeric(selected_continuous[col], errors='coerce')

            # 单位转换（新增部分）
            if '涨停封单量' in selected_continuous.columns:
                selected_continuous['涨停封单量(万)'] = round(selected_continuous['涨停封单量'] / 10000,2)
                selected_continuous.drop('涨停封单量', axis=1, inplace=True)  # 删除原列# 转换为万
            if '涨停封单额' in selected_continuous.columns:
                selected_continuous['涨停封单额(亿元)'] = round(selected_continuous['涨停封单额'] / 100000000,2)
                selected_continuous.drop('涨停封单额', axis=1, inplace=True)  # 删除原列# 转换为亿元

            # 应用样式
            styled_df = selected_continuous.style
            if '最新价' in selected_continuous.columns:
                styled_df = styled_df.format({'最新价': '¥{:.2f}'})
            if '涨停封单量（万）' in selected_continuous.columns:
                styled_df = styled_df.format({'涨停封单量（万）': '{:,.2f}'})
            if '涨停封单额（亿元）' in selected_continuous.columns:
                styled_df = styled_df.format({'涨停封单额（亿元）': '¥{:,.2f}'})

            if '连续涨停天数' in selected_continuous.columns:
                styled_df = styled_df.background_gradient(
                    cmap='Reds',  # 修改为红色
                    subset=['连续涨停天数']
                )


            st.dataframe(styled_df, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">没有连续涨停数据</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">缺少涨停数据，无法进行连续涨停分析</div>', unsafe_allow_html=True)

    # 连板晋级率分析 - 美观优化版
    st.markdown('<p class="subheader-text">📶 连板晋级率分析</p>', unsafe_allow_html=True)

    if selected_df is not None and previous_df is not None:
        promotion_rates = calculate_promotion_rates(
            selected_df, previous_df,
            selected_date, previous_date
        )

        if not promotion_rates.empty:
            promotion_list = promotion_rates.to_dict('records')

            for i in range(0, len(promotion_list), 3):
                cols = st.columns(3)
                group = promotion_list[i:i + 3]

                for j in range(len(group)):
                    with cols[j]:
                        item = group[j]
                        # 计算进度条宽度
                        rate_width = min(100, item['晋级率']['rate'])
                        rate_color = "#e74c3c" if item['晋级率']['rate'] >= 50 else "#27ae60"  # 修改颜色

                        st.markdown(f"""
                            <div class="promotion-card">
                                <div class="promotion-title">
                                    <span>{item['连板数']}</span>
                                    <span style="font-size: 0.9rem; color: #7f8c8d;">{item['晋级率']['success']}/{item['晋级率']['total']}</span>
                                </div>
                                <div class="promotion-rate">
                                    <span>晋级率:</span>
                                    <span class="promotion-rate-value" style="color: {rate_color};">{item['晋级率']['text']}</span>
                                </div>
                                <div style="height: 4px; background: #ecf0f1; border-radius: 2px; margin: 0.5rem 0;">
                                    <div style="width: {rate_width}%; height: 100%; background: {rate_color}; border-radius: 2px;"></div>
                                </div>
                        """, unsafe_allow_html=True)

                        if not item['股票列表'].empty:
                            for _, stock in item['股票列表'].iterrows():
                                concept_col = f'涨停原因类别[{selected_date.strftime("%Y%m%d")}]'
                                concept = stock[concept_col] if concept_col in stock else ''
                                st.markdown(f"""
                                    <div class="stock-item">
                                        <span class="stock-name">{stock['股票简称']}</span>
                                        <span class="stock-concept" title="{concept}">{concept}</span>
                                    </div>
                                """, unsafe_allow_html=True)

                        st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">没有可用的晋级率数据</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">缺少必要数据，无法计算晋级率</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    app()
