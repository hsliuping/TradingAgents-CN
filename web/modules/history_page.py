#!/usr/bin/env python3
"""
Streamlit history page for browsing past analyses and viewing details.
"""

import streamlit as st
from typing import Optional

from tradingagents.utils.logging_manager import get_logger
from utils.history_manager import list_history, get_history_item
from utils.analysis_runner import format_analysis_results
from components.results_display import render_results

logger = get_logger('history_page')


def render_history_page():
    st.header("📈 历史记录")

    # Filters
    with st.expander("筛选条件", expanded=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            symbol = st.text_input("股票代码 (可选)", value="", placeholder="如 AAPL / 600519 / 00700")
        with col2:
            limit = st.number_input("显示条目数", min_value=10, max_value=500, value=50, step=10)
        with col3:
            refresh = st.button("🔄 刷新")

    if refresh:
        st.rerun()

    symbol_filter = symbol.strip() or None

    entries = list_history(limit=int(limit), symbol=symbol_filter)
    if not entries:
        st.info("暂无历史记录")
        return

    # List view
    st.subheader("最近分析")
    st.caption(f"共 {len(entries)} 条记录")
    for entry in entries:
        with st.container():
            top = st.columns([2, 2, 2, 2, 2, 2])
            with top[0]:
                st.write(f"**{entry.get('stock_symbol','')}**")
                st.caption(entry.get('analysis_id',''))
            with top[1]:
                st.write(f"日期: {entry.get('analysis_date','')}" )
                st.write(f"时间: {entry.get('created_at','')}")
            with top[2]:
                st.write(f"状态: {'✅ 成功' if entry.get('success') else '❌ 失败'}")
            with top[3]:
                action = entry.get('action') or '-'
                st.write(f"建议: {action}")
            with top[4]:
                tp = entry.get('target_price')
                st.write(f"目标价: {tp if tp is not None else '-'}")
            with top[5]:
                if st.button("查看报告", key=f"view_{entry.get('analysis_id')}"):
                    st.session_state['history_view_id'] = entry.get('analysis_id')

    # Detail view
    view_id: Optional[str] = st.session_state.get('history_view_id')
    if not view_id and entries:
        # Auto select newest entry for first load
        st.session_state['history_view_id'] = entries[0].get('analysis_id')
        view_id = st.session_state['history_view_id']
    if view_id:
        st.markdown("---")
        st.subheader("历史分析报告")
        data = get_history_item(view_id)
        if not data:
            st.warning("未找到该历史记录")
            return
        try:
            formatted = format_analysis_results(data)
            if formatted and formatted.get('success', False):
                render_results(formatted)
            else:
                st.error("该记录无效或未成功")
        except Exception as e:
            logger.error(f"Failed to render history item {view_id}: {e}")
            st.error("渲染历史报告失败")


