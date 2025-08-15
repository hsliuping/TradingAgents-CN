import streamlit as st
import os
import json
import hashlib
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
from typing import List, Dict, Any

# ======================================================================
# 1. 配置与样式
# ======================================================================
st.set_page_config(page_title="市场动态看板", layout="wide")

def load_css():
    st.markdown("""
    <style>
    /* 新闻内容样式 */
    .news-title {
        font-weight: 700;
        font-size: 16px;
        color: #003366;
        margin-bottom: 0px; /* 减少标题和内容的间距 */
    }
    .news-content {
        font-size: 14px;
        line-height: 1.5;
        white-space: pre-wrap; /* 保持换行 */
        word-break: break-word; /* 防止长链接溢出 */
    }
    /* 时间文本样式 */
    .time-text {
        font-size: 1.2em;
        font-weight: bold;
        color: #555;
    }
    /* 资金流卡片样式 */
    .card {
        border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; 
        border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        max-height: 420px; overflow-y: auto;
    }
    .card h3 {
        margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid #eee;
        padding-bottom: 10px; font-size: 18px;
    }
    .card .fund-flow-item {
        padding: 8px 5px; border-bottom: 1px solid #eee;
        display: flex; justify-content: space-between; align-items: center;
    }
    .card .fund-flow-item:last-child { border-bottom: none; }
    .card .fund-flow-name { font-weight: bold; }
    .card .fund-flow-value { color: #c00; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# ======================================================================
# 2. 数据获取与处理
# ======================================================================

@st.cache_resource
def get_news_fetcher():
    return NewsFetcher()

class NewsFetcher:
    def __init__(self, save_dir="data/news"):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self.news_hashes = self._load_existing_hashes()
    def _load_existing_hashes(self) -> set:
        hashes = set()
        today = datetime.now()
        for i in range(3):
            filename = self._get_news_filename(today - timedelta(days=i))
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        news_data = json.load(f)
                        for item in news_data:
                            h = item.get("hash") or self._calculate_hash(item.get("content", ""))
                            hashes.add(h)
                except (json.JSONDecodeError, IOError):
                    continue
        return hashes
    def _calculate_hash(self, content: str) -> str:
        return hashlib.md5(str(content).encode('utf-8')).hexdigest()
    def _get_news_filename(self, date: datetime = None) -> str:
        dt_str = (date or datetime.now()).strftime('%Y%m%d')
        return os.path.join(self.save_dir, f"news_{dt_str}.json")
    def fetch_and_save(self) -> bool:
        try:
            stock_info_global_cls_df = ak.stock_info_global_cls(symbol="全部")
        except Exception as e:
            st.error(f"获取新闻时出错: {e}")
            return False
        if stock_info_global_cls_df.empty: return True
        news_list = []
        for _, row in stock_info_global_cls_df.iterrows():
            content = str(row.get("内容", ""))
            content_hash = self._calculate_hash(content)
            if content_hash in self.news_hashes: continue
            self.news_hashes.add(content_hash)
            pub_date = str(row.get("发布日期", ""))
            pub_time = str(row.get("发布时间", ""))
            news_item = {
                "title": str(row.get("标题", "")), 
                "content": content, 
                "datetime": f"{pub_date} {pub_time}", 
                "hash": content_hash,
            }
            news_list.append(news_item)
        if not news_list: return True
        filename = self._get_news_filename()
        existing_data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError): pass
        merged_news = sorted(existing_data + news_list, key=lambda x: x.get('datetime', '0'), reverse=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(merged_news, f, ensure_ascii=False, indent=2)
        return True
    def get_latest_news(self, days: int = 1) -> List[Dict[str, Any]]:
        news_data = []
        today = datetime.now()
        for i in range(days):
            filename = self._get_news_filename(today - timedelta(days=i))
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        news_data.extend(json.load(f))
                except (json.JSONDecodeError, IOError): continue
        seen_hashes = set()
        unique_news = []
        for item in sorted(news_data, key=lambda x: x.get('datetime', '0'), reverse=True):
            item_hash = item.get('hash')
            if item_hash not in seen_hashes:
                unique_news.append(item)
                seen_hashes.add(item_hash)
        return unique_news

@st.cache_data(ttl=600)
def get_fund_flow_data(data_type: str) -> pd.DataFrame:
    try:
        if data_type == "industry":
            return ak.stock_fund_flow_industry()
        elif data_type == "concept":
            return ak.stock_fund_flow_concept()
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"获取 {data_type} 资金流数据失败: {e}", icon="🚨")
        return pd.DataFrame()

# ======================================================================
# 3. UI 渲染函数
# ======================================================================

def display_news_timeline(news_list: List[Dict[str, Any]], limit: int):
    st.header("实时新闻")
    if not news_list:
        st.info("暂无新闻数据。请尝试调整侧边栏天数。")
        return

    for news in news_list[:limit]:
        try:
            dt_obj = datetime.strptime(news['datetime'], "%Y-%m-%d %H:%M:%S")
            time_str = dt_obj.strftime("%H:%M")
        except (ValueError, KeyError):
            time_str = "N/A"

        col_time, col_content = st.columns([1, 9])
        with col_time:
            st.markdown(f'<p class="time-text">{time_str}</p>', unsafe_allow_html=True)
        with col_content:
            st.markdown(f"<p class='news-title'>{news.get('title', '无标题')}</p>", unsafe_allow_html=True)
            st.markdown(f"<p class='news-content'>{news.get('content', '无内容')}</p>", unsafe_allow_html=True)
        
        st.divider()

def display_fund_flow_card(title: str, df: pd.DataFrame, name_col: str, value_col: str):
    html_parts = [f'<div class="card"><h3>{title}</h3>']
    if df.empty:
        html_parts.append("<p>暂无数据</p>")
    else:
        if value_col in df.columns:
            df_sorted = df.sort_values(by=value_col, ascending=False).head(15)
        else:
            df_sorted = df.head(15)
            st.warning(f"资金流数据中未找到列 '{value_col}' 用于排序。")
        for _, row in df_sorted.iterrows():
            name = row.get(name_col, '未知')
            value = row.get(value_col, 'N/A')
            value_str = f"{value}亿" if isinstance(value, (int, float)) else "N/A"
            html_parts.append(
                f'<div class="fund-flow-item">'
                f'  <span class="fund-flow-name">{name}</span>'
                f'  <span class="fund-flow-value">{value_str}</span>'
                f'</div>'
            )
    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)

# ======================================================================
# 4. 主应用逻辑
# ======================================================================

def render_news_display():
    load_css()
    st.title("📈 市场动态看板")

    st.sidebar.title("🛠️ 控制面板")
    
    days = st.sidebar.slider("显示最近几天新闻", 1, 7, 3, key="days_slider")
    limit = st.sidebar.slider("最多显示新闻条数", 10, 100, 50, key="limit_slider")

    news_fetcher = get_news_fetcher()

    # 初始化 session_state
    if 'prev_days' not in st.session_state:
        st.session_state.prev_days = None
    if 'prev_limit' not in st.session_state:
        st.session_state.prev_limit = None
    if 'data_refreshed' not in st.session_state:
        st.session_state.data_refreshed = False

    # 滑块变化则刷新数据
    if (days != st.session_state.prev_days) or (limit != st.session_state.prev_limit) or (not st.session_state.data_refreshed):
        with st.spinner("正在刷新新闻数据..."):
            st.cache_data.clear()
            news_fetcher.fetch_and_save()
        st.session_state.prev_days = days
        st.session_state.prev_limit = limit
        st.session_state.data_refreshed = True

    col_left, col_right = st.columns([2, 1])

    with col_left:
        with st.container(height=800, border=False):
            news_list = news_fetcher.get_latest_news(days=days)
            display_news_timeline(news_list, limit)

    with col_right:
        st.header("资金流排行")
        df_industry = get_fund_flow_data("industry")
        display_fund_flow_card("行业资金流", df_industry, name_col="行业", value_col="流入资金")
        df_concept = get_fund_flow_data("concept")
        display_fund_flow_card("概念资金流", df_concept, name_col="行业", value_col="流入资金")

def main():
    render_news_display()

if __name__ == "__main__":
    main()
