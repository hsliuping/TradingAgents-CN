#!/usr/bin/env python3
"""
Cache management page
Users can view, manage, and clear stock data cache
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import UI utility functions
sys.path.append(str(Path(__file__).parent.parent))
from utils.ui_utils import apply_hide_deploy_button_css

try:
    from tradingagents.dataflows.cache_manager import get_cache
    from tradingagents.dataflows.optimized_us_data import get_optimized_us_data_provider
    from tradingagents.dataflows.optimized_china_data import get_optimized_china_data_provider
    CACHE_AVAILABLE = True
    OPTIMIZED_PROVIDERS_AVAILABLE = True
except ImportError as e:
    CACHE_AVAILABLE = False
    OPTIMIZED_PROVIDERS_AVAILABLE = False
    st.error(f"Cache manager is not available: {e}")

def main():
    st.set_page_config(
        page_title="Cache Management - TradingAgents",
        page_icon="💾",
        layout="wide"
    )
    
    # Apply CSS for hiding Deploy button
    apply_hide_deploy_button_css()
    
    st.title("💾 Stock Data Cache Management")
    st.markdown("---")
    
    if not CACHE_AVAILABLE:
        st.error("❌ Cache manager is not available, please check system configuration")
        return
    
    # Get cache instance
    cache = get_cache()
    
    # Sidebar operations
    with st.sidebar:
        st.header("🛠️ Cache Operations")
        
        # Refresh button
        if st.button("🔄 Refresh Statistics", type="primary"):
            st.rerun()
        
        st.markdown("---")
        
        # Clear operations
        st.subheader("🧹 Clear Cache")
        
        max_age_days = st.slider(
            "Clear cache older than how many days",
            min_value=1,
            max_value=30,
            value=7,
            help="Delete cache files older than the specified number of days"
        )
        
        if st.button("🗑️ Clear Expired Cache", type="secondary"):
            with st.spinner("Clearing expired cache..."):
                cache.clear_old_cache(max_age_days)
            st.success(f"✅ Cleared cache older than {max_age_days} days")
            st.rerun()
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📊 Cache Statistics")
        
        # Get cache statistics
        try:
            stats = cache.get_cache_stats()
            
            # Display statistics
            metric_col1, metric_col2 = st.columns(2)
            
            with metric_col1:
                st.metric(
                    label="Total Files",
                    value=stats['total_files'],
                    help="Total number of files in the cache"
                )
                
                st.metric(
                    label="Stock Data",
                    value=f"{stats['stock_data_count']} files",
                    help="Number of stock data files in the cache"
                )
            
            with metric_col2:
                st.metric(
                    label="Total Size",
                    value=f"{stats['total_size_mb']} MB",
                    help="Disk space occupied by cache files"
                )
                
                st.metric(
                    label="News Data",
                    value=f"{stats['news_count']} files",
                    help="Number of news data files in the cache"
                )
            
            # Fundamental data
            st.metric(
                label="Fundamental Data",
                value=f"{stats['fundamentals_count']} files",
                help="Number of fundamental data files in the cache"
            )
            
        except Exception as e:
            st.error(f"Failed to get cache statistics: {e}")

    with col2:
        st.subheader("⚙️ Cache Configuration")

        # Display cache configuration information
        if hasattr(cache, 'cache_config'):
            config_tabs = st.tabs(["US Data Cache", "China Data Cache"])

            with config_tabs[0]:
                st.markdown("**US Data Cache Configuration**")
                us_configs = {k: v for k, v in cache.cache_config.items() if k.startswith('us_')}
                for config_name, config_data in us_configs.items():
                    st.info(f"""
                    **{config_data.get('description', config_name)}**
                    - TTL: {config_data.get('ttl_hours', 'N/A')} hours
                    - Max Files: {config_data.get('max_files', 'N/A')}
                    """)

            with config_tabs[1]:
                st.markdown("**China Data Cache Configuration**")
                china_configs = {k: v for k, v in cache.cache_config.items() if k.startswith('china_')}
                for config_name, config_data in china_configs.items():
                    st.info(f"""
                    **{config_data.get('description', config_name)}**
                    - TTL: {config_data.get('ttl_hours', 'N/A')} hours
                    - Max Files: {config_data.get('max_files', 'N/A')}
                    """)
        else:
            st.warning("Cache configuration information is not available")

    # Cache test functionality
    st.markdown("---")
    st.subheader("🧪 Cache Test")

    if OPTIMIZED_PROVIDERS_AVAILABLE:
        test_col1, test_col2 = st.columns(2)

        with test_col1:
            st.markdown("**Test US Data Cache**")
            us_symbol = st.text_input("US Symbol", value="AAPL", key="us_test")
            if st.button("Test US Cache", key="test_us"):
                if us_symbol:
                    with st.spinner(f"Testing {us_symbol} cache..."):
                        try:
                            from datetime import datetime, timedelta
                            provider = get_optimized_us_data_provider()
                            result = provider.get_stock_data(
                                symbol=us_symbol,
                                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                                end_date=datetime.now().strftime('%Y-%m-%d')
                            )
                            st.success("✅ US cache test successful")
                            with st.expander("View Result"):
                                st.text(result[:500] + "..." if len(result) > 500 else result)
                        except Exception as e:
                            st.error(f"❌ US cache test failed: {e}")

        with test_col2:
            st.markdown("**Test China Data Cache**")
            china_symbol = st.text_input("China Symbol", value="000001", key="china_test")
            if st.button("Test China Cache", key="test_china"):
                if china_symbol:
                    with st.spinner(f"Testing {china_symbol} cache..."):
                        try:
                            from datetime import datetime, timedelta
                            provider = get_optimized_china_data_provider()
                            result = provider.get_stock_data(
                                symbol=china_symbol,
                                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                                end_date=datetime.now().strftime('%Y-%m-%d')
                            )
                            st.success("✅ China cache test successful")
                            with st.expander("View Result"):
                                st.text(result[:500] + "..." if len(result) > 500 else result)
                        except Exception as e:
                            st.error(f"❌ China cache test failed: {e}")
    else:
        st.warning("Optimized data providers are not available, cannot perform cache test")

    # Original cache details section
    with col2:
        st.subheader("⚙️ Cache Configuration")
        
        # Cache settings
        st.info("""
        **Cache Mechanism Explanation:**
        
        🔹 **Stock Data Cache** (6 hours TTL):
        - Reduce API calls
        - Improve data retrieval speed
        - Support offline analysis
        
        🔹 **News Data Cache** (24 hours TTL):
        - Avoid duplicate news fetching
        - Save API quota
        
        🔹 **Fundamental Data Cache** (24 hours TTL):
        - Reduce fundamental analysis API calls
        - Improve analysis response speed
        """)
        
        # Cache directory information
        cache_dir = cache.cache_dir
        st.markdown(f"**Cache Directory:** `{cache_dir}`")
        
        # Subdirectory information
        st.markdown("**Subdirectory Structure:**")
        st.code(f"""
📁 {cache_dir.name}/
├── 📁 stock_data/     # Stock data cache
├── 📁 news_data/      # News data cache
├── 📁 fundamentals/   # Fundamental data cache
└── 📁 metadata/       # Metadata files
        """)
    
    st.markdown("---")
    
    # Cache details
    st.subheader("📋 Cache Details")
    
    # Select data type to view
    data_type = st.selectbox(
        "Select Data Type",
        ["stock_data", "news", "fundamentals"],
        format_func=lambda x: {
            "stock_data": "📈 Stock Data",
            "news": "📰 News Data", 
            "fundamentals": "💼 Fundamental Data"
        }[x]
    )
    
    # Display cache file list
    try:
        metadata_files = list(cache.metadata_dir.glob("*_meta.json"))
        
        if metadata_files:
            import json
            from datetime import datetime
            
            cache_items = []
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    if metadata.get('data_type') == data_type:
                        cached_at = datetime.fromisoformat(metadata['cached_at'])
                        cache_items.append({
                            'symbol': metadata.get('symbol', 'N/A'),
                            'data_source': metadata.get('data_source', 'N/A'),
                            'cached_at': cached_at.strftime('%Y-%m-%d %H:%M:%S'),
                            'start_date': metadata.get('start_date', 'N/A'),
                            'end_date': metadata.get('end_date', 'N/A'),
                            'file_path': metadata.get('file_path', 'N/A')
                        })
                except Exception:
                    continue
            
            if cache_items:
                # Sort by cache time
                cache_items.sort(key=lambda x: x['cached_at'], reverse=True)
                
                # Display table
                import pandas as pd
                df = pd.DataFrame(cache_items)
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "symbol": st.column_config.TextColumn("Symbol", width="small"),
                        "data_source": st.column_config.TextColumn("Data Source", width="small"),
                        "cached_at": st.column_config.TextColumn("Cached At", width="medium"),
                        "start_date": st.column_config.TextColumn("Start Date", width="small"),
                        "end_date": st.column_config.TextColumn("End Date", width="small"),
                        "file_path": st.column_config.TextColumn("File Path", width="large")
                    }
                )
                
                st.info(f"📊 Found {len(cache_items)} cache files of type {data_type}")
            else:
                st.info(f"📭 No cache files of type {data_type} found")
        else:
            st.info("📭 No cache files found")
            
    except Exception as e:
        st.error(f"Failed to read cache details: {e}")
    
    # Footer information
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        💾 Cache Management System | TradingAgents v0.1.2 | 
        <a href='https://github.com/your-repo/TradingAgents' target='_blank'>GitHub</a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
