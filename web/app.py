#!/usr/bin/env python3
"""
TradingAgents-CN Streamlit Web Interface
Stock analysis web application based on Streamlit
"""

import streamlit as st
import os
import sys
from pathlib import Path
import datetime
import time
from dotenv import load_dotenv

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env", override=True)

# Import custom components
from components.sidebar import render_sidebar
from components.header import render_header
from components.analysis_form import render_analysis_form
from components.results_display import render_results
from utils.api_checker import check_api_keys
from utils.analysis_runner import run_stock_analysis, validate_analysis_params, format_analysis_results
from utils.progress_tracker import SmartStreamlitProgressDisplay, create_smart_progress_callback
from utils.async_progress_tracker import AsyncProgressTracker
from components.async_progress_display import display_unified_progress
from utils.smart_session_manager import get_persistent_analysis_id, set_persistent_analysis_id

# Set page config
st.set_page_config(
    page_title="TradingAgents-CN Stock Analysis Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# Custom CSS styles
st.markdown("""
<style>
    /* Hide Streamlit top toolbar and Deploy button - multiple selectors for compatibility */
    .stAppToolbar {
        display: none !important;
    }
    
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    .stDeployButton {
        display: none !important;
    }
    
    /* New version Streamlit Deploy button selector */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    
    [data-testid="stDecoration"] {
        display: none !important;
    }
    
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    
    /* Hide the entire top area */
    .stApp > header {
        display: none !important;
    }
    
    .stApp > div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Hide main menu button */
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Hide footer */
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Hide "Made with Streamlit" badge */
    .viewerBadge_container__1QSob {
        display: none !important;
    }
    
    /* Hide all possible toolbar elements */
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Hide all buttons in the top-right corner */
    .stApp > div > div > div > div > section > div {
        padding-top: 0 !important;
    }
    
    /* Apply styles */
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    .analysis-section {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'last_analysis_time' not in st.session_state:
        st.session_state.last_analysis_time = None
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None
    if 'form_config' not in st.session_state:
        st.session_state.form_config = None

    # Try to restore results from the latest completed analysis
    if not st.session_state.analysis_results:
        try:
            from utils.async_progress_tracker import get_latest_analysis_id, get_progress_by_id
            from utils.analysis_runner import format_analysis_results

            latest_id = get_latest_analysis_id()
            if latest_id:
                progress_data = get_progress_by_id(latest_id)
                if (progress_data and
                    progress_data.get('status') == 'completed' and
                    'raw_results' in progress_data):

                    # Restore analysis results
                    raw_results = progress_data['raw_results']
                    formatted_results = format_analysis_results(raw_results)

                    if formatted_results:
                        st.session_state.analysis_results = formatted_results
                        st.session_state.current_analysis_id = latest_id
                        # Check analysis status
                        analysis_status = progress_data.get('status', 'completed')
                        st.session_state.analysis_running = (analysis_status == 'running')
                        # Restore stock info
                        if 'stock_symbol' in raw_results:
                            st.session_state.last_stock_symbol = raw_results.get('stock_symbol', '')
                        if 'market_type' in raw_results:
                            st.session_state.last_market_type = raw_results.get('market_type', '')
                        logger.info(f"📊 [Result restored] Restored results from analysis {latest_id}, status: {analysis_status}")

        except Exception as e:
            logger.warning(f"⚠️ [Result restoration] Restoration failed: {e}")

    # Use cookie manager to restore analysis ID (priority: session state > cookie > Redis/file)
    try:
        persistent_analysis_id = get_persistent_analysis_id()
        if persistent_analysis_id:
            # Use thread detection to check analysis status
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(persistent_analysis_id)

            # Log only when status changes to avoid repetition
            current_session_status = st.session_state.get('last_logged_status')
            if current_session_status != actual_status:
                logger.info(f"📊 [Status check] Actual status of analysis {persistent_analysis_id}: {actual_status}")
                st.session_state.last_logged_status = actual_status

            if actual_status == 'running':
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = persistent_analysis_id
            elif actual_status in ['completed', 'failed']:
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = persistent_analysis_id
            else:  # not_found
                logger.warning(f"📊 [Status check] Analysis {persistent_analysis_id} not found, cleaning up status")
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = None
    except Exception as e:
        # If restoration fails, keep default values
        logger.warning(f"⚠️ [Status restoration] Failed to restore analysis status: {e}")
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None

    # Restore form configuration
    try:
        from utils.smart_session_manager import smart_session_manager
        session_data = smart_session_manager.load_analysis_state()

        if session_data and 'form_config' in session_data:
            st.session_state.form_config = session_data['form_config']
            # Log only when no analysis is running to avoid repetition
            if not st.session_state.get('analysis_running', False):
                logger.info("📊 [Configuration restored] Form configuration restored")
    except Exception as e:
        logger.warning(f"⚠️ [Configuration restoration] Failed to restore form configuration: {e}")

def main():
    """Main application"""

    # Initialize session state
    initialize_session_state()

    # Custom CSS - adjust sidebar width
    st.markdown("""
    <style>
    /* Adjust sidebar width to 260px to avoid title squeeze */
    section[data-testid="stSidebar"] {
        width: 260px !important;
        min-width: 260px !important;
        max-width: 260px !important;
    }

    /* Hide sidebar's hidden button - more comprehensive selectors */
    button[kind="header"],
    button[data-testid="collapsedControl"],
    .css-1d391kg,
    .css-1rs6os,
    .css-17eq0hr,
    .css-1lcbmhc,
    .css-1y4p8pa,
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"],
    [data-testid="collapsedControl"],
    .stSidebar button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Hide specific buttons in the sidebar top area (more precise selectors, avoid affecting form buttons) */
    section[data-testid="stSidebar"] > div:first-child > button[kind="header"],
    section[data-testid="stSidebar"] > div:first-child > div > button[kind="header"],
    section[data-testid="stSidebar"] .css-1lcbmhc > button[kind="header"],
    section[data-testid="stSidebar"] .css-1y4p8pa > button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* Adjust sidebar content padding */
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* Adjust main content area, set 8px margin - use stronger selectors */
    .main .block-container,
    section.main .block-container,
    div.main .block-container,
    .stApp .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
        max-width: none !important;
        width: calc(100% - 16px) !important;
    }

    /* Ensure content is not obscured by scrollbars */
    .stApp > div {
        overflow-x: auto !important;
    }

    /* Adjust right margin for detailed analysis report */
    .element-container {
        margin-right: 8px !important;
    }

    /* Optimize sidebar title and element spacing */
    .sidebar .sidebar-content {
        padding: 0.5rem 0.3rem !important;
    }

    /* Adjust spacing between all elements in the sidebar */
    section[data-testid="stSidebar"] .element-container {
        margin-bottom: 0.5rem !important;
    }

    /* Adjust spacing between sidebar separators */
    section[data-testid="stSidebar"] hr {
        margin: 0.8rem 0 !important;
    }

    /* Ensure sidebar title is not squeezed */
    section[data-testid="stSidebar"] h1 {
        font-size: 1.2rem !important;
        line-height: 1.3 !important;
        margin-bottom: 1rem !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    /* Simplify function selection area style */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }

    /* Adjust width of select boxes and other components */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        min-width: 220px !important;
        width: 100% !important;
    }

    /* Fix right content occlusion */
    .main {
        padding-right: 8px !important;
    }

    /* Ensure page content has enough right margin */
    .stApp {
        margin-right: 0 !important;
        padding-right: 8px !important;
    }

    /* Special handling for expanded analysis report */
    .streamlit-expanderContent {
        padding-right: 8px !important;
        margin-right: 8px !important;
    }

    /* Prevent horizontal scrollbar */
    .main .block-container {
        overflow-x: visible !important;
    }

    /* Force set 8px margin to all possible containers */
    .stApp,
    .stApp > div,
    .stApp > div > div,
    .main,
    .main > div,
    .main > div > div,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewContainer"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* Special handling for column containers */
    div[data-testid="column"],
    .css-1d391kg,
    .css-1r6slb0,
    .css-12oz5g7,
    .css-1lcbmhc {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* Force set container width */
    .main .block-container {
        width: calc(100vw - 276px) !important;
        max-width: calc(100vw - 276px) !important;
    }

    /* Optimize style for usage guide area */
    div[data-testid="column"]:last-child {
        background-color: #f8f9fa !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin-left: 8px !important;
        border: 1px solid #e9ecef !important;
    }

    /* Expander style for usage guide */
    div[data-testid="column"]:last-child .streamlit-expanderHeader {
        background-color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #dee2e6 !important;
        font-weight: 500 !important;
    }

    /* Text style for usage guide */
    div[data-testid="column"]:last-child .stMarkdown {
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }

    /* Usage guide title style */
    div[data-testid="column"]:last-child h1 {
        font-size: 1.3rem !important;
        color: #495057 !important;
        margin-bottom: 1rem !important;
    }
    </style>

    <script>
    // JavaScript to force hide sidebar buttons
    function hideSidebarButtons() {
        // Hide all possible sidebar control buttons
        const selectors = [
            'button[kind="header"]',
            'button[data-testid="collapsedControl"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            '[data-testid="collapsedControl"]',
            '.css-1d391kg',
            '.css-1rs6os',
            '.css-17eq0hr',
            '.css-1lcbmhc button',
            '.css-1y4p8pa button'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
            });
        });
    }

    // Execute after page load
    document.addEventListener('DOMContentLoaded', hideSidebarButtons);

    // Periodically check and hide buttons (to prevent dynamic generation)
    setInterval(hideSidebarButtons, 1000);

    // Force modify page margin to 8px
    function forceOptimalPadding() {
        const selectors = [
            '.main .block-container',
            '.stApp',
            '.stApp > div',
            '.main',
            '.main > div',
            'div[data-testid="stAppViewContainer"]',
            'section[data-testid="stMain"]',
            'div[data-testid="column"]'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.paddingLeft = '8px';
                el.style.paddingRight = '8px';
                el.style.marginLeft = '0px';
                el.style.marginRight = '0px';
            });
        });

        // Special handling for main container width
        const mainContainer = document.querySelector('.main .block-container');
        if (mainContainer) {
            mainContainer.style.width = 'calc(100vw - 276px)';
            mainContainer.style.maxWidth = 'calc(100vw - 276px)';
        }
    }

    // Execute after page load
    document.addEventListener('DOMContentLoaded', forceOptimalPadding);

    // Periodically force apply styles
    setInterval(forceOptimalPadding, 500);
    </script>
    """, unsafe_allow_html=True)

    # Add debug button (only show in debug mode)
    if os.getenv('DEBUG_MODE') == 'true':
        if st.button("🔄 Clear session state"):
            st.session_state.clear()
            st.experimental_rerun()

    # Render page header
    render_header()

    # Page navigation
    st.sidebar.title("TradingAgents-CN")
    st.sidebar.markdown("---")

    # Add function switching title
    st.sidebar.markdown("**🎯 Function Navigation**")

    page = st.sidebar.selectbox(
        "Switch function module",
        ["Stock Analysis", "⚙️ Configuration Management", "💾 Cache Management", "💰 Token Statistics", "📈 History", "🔧 System Status"],
        label_visibility="collapsed"
    )

    # Add separator between function selection and AI model configuration
    st.sidebar.markdown("---")

    # Render different content based on selected page
    if page == "⚙️ Configuration Management":
        try:
            from modules.config_management import render_config_management
            render_config_management()
        except ImportError as e:
            st.error(f"Configuration management module failed to load: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "💾 Cache Management":
        try:
            from modules.cache_management import main as cache_main
            cache_main()
        except ImportError as e:
            st.error(f"Cache management page failed to load: {e}")
        return
    elif page == "💰 Token Statistics":
        try:
            from modules.token_statistics import render_token_statistics
            render_token_statistics()
        except ImportError as e:
            st.error(f"Token statistics page failed to load: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "📈 History":
        st.header("📈 History")
        st.info("History function under development...")
        return
    elif page == "🔧 System Status":
        st.header("🔧 System Status")
        st.info("System status function under development...")
        return

    # Default display stock analysis page
    # Check API keys
    api_status = check_api_keys()
    
    if not api_status['all_configured']:
        st.error("⚠️ API key configuration incomplete, please configure the necessary API keys first")
        
        with st.expander("📋 API Key Configuration Guide", expanded=True):
            st.markdown("""
            ### 🔑 Required API Keys
            
            1. **Aliyun DashScope API Key** (DASHSCOPE_API_KEY)
               - Get address: https://dashscope.aliyun.com/
               - Purpose: AI model inference
            
            2. **Financial Data API Key** (FINNHUB_API_KEY)  
               - Get address: https://finnhub.io/
               - Purpose: Get stock data
            
            ### ⚙️ Configuration Method
            
            1. Copy `.env.example` from the project root directory to `.env`
            2. Edit `.env` file and fill in your actual API keys
            3. Restart the web application
            
            ```bash
            # .env file example
            DASHSCOPE_API_KEY=sk-your-dashscope-key
            FINNHUB_API_KEY=your-finnhub-key
            ```
            """)
        
        # Display current API key status
        st.subheader("🔍 Current API Key Status")
        for key, status in api_status['details'].items():
            if status['configured']:
                st.success(f"✅ {key}: {status['display']}")
            else:
                st.error(f"❌ {key}: Not configured")
        
        return
    
    # Render sidebar
    config = render_sidebar()
    
    # Add usage guide display toggle
    show_guide = st.sidebar.checkbox("📖 Show Usage Guide", value=True, help="Show/hide right usage guide")

    # Add status cleanup button
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Clean up analysis status", help="Clean up zombie analysis status to resolve continuous refresh issues"):
        # Clean up session state
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None
        st.session_state.analysis_results = None

        # Clean up all auto-refresh states
        keys_to_remove = []
        for key in st.session_state.keys():
            if 'auto_refresh' in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state[key]

        # Clean up dead threads
        from utils.thread_tracker import cleanup_dead_analysis_threads
        cleanup_dead_analysis_threads()

        st.sidebar.success("✅ Analysis status cleaned up")
        st.rerun()

    # Main content area - adjust layout based on whether to show guide
    if show_guide:
        col1, col2 = st.columns([2, 1])  # 2:1 ratio, usage guide takes one-third
    else:
        col1 = st.container()
        col2 = None
    
    with col1:
        # 1. Analysis configuration area

        st.header("⚙️ Analysis Configuration")

        # Render analysis form
        try:
            form_data = render_analysis_form()

            # Validate form data format
            if not isinstance(form_data, dict):
                st.error(f"⚠️ Form data format exception: {type(form_data)}")
                form_data = {'submitted': False}

        except Exception as e:
            st.error(f"❌ Form rendering failed: {e}")
            form_data = {'submitted': False}

        # Avoid displaying debug information
        if form_data and form_data != {'submitted': False}:
            # Only display form data in debug mode
            if os.getenv('DEBUG_MODE') == 'true':
                st.write("Debug - Form data:", form_data)

        # Add log receiver
        if form_data.get('submitted', False):
            logger.debug(f"🔍 [APP DEBUG] ===== Main application received form data =====")
            logger.debug(f"🔍 [APP DEBUG] Received form_data: {form_data}")
            logger.debug(f"🔍 [APP DEBUG] Stock code: '{form_data['stock_symbol']}'")
            logger.debug(f"�� [APP DEBUG] Market type: '{form_data['market_type']}'")

        # Check if form is submitted
        if form_data.get('submitted', False) and not st.session_state.get('analysis_running', False):
            # Only process new submissions when no analysis is running
            # Validate analysis parameters
            is_valid, validation_errors = validate_analysis_params(
                stock_symbol=form_data['stock_symbol'],
                analysis_date=form_data['analysis_date'],
                analysts=form_data['analysts'],
                research_depth=form_data['research_depth'],
                market_type=form_data.get('market_type', 'US Stocks')
            )

            if not is_valid:
                # Display validation errors
                for error in validation_errors:
                    st.error(error)
            else:
                # Execute analysis
                st.session_state.analysis_running = True

                # Clear old analysis results
                st.session_state.analysis_results = None
                logger.info("📊 [New analysis] Clearing old analysis results")

                # Generate analysis ID
                import uuid
                analysis_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # Save analysis ID and form configuration to session state and cookie
                form_config = st.session_state.get('form_config', {})
                set_persistent_analysis_id(
                    analysis_id=analysis_id,
                    status="running",
                    stock_symbol=form_data['stock_symbol'],
                    market_type=form_data.get('market_type', 'US Stocks'),
                    form_config=form_config
                )

                # Create asynchronous progress tracker
                async_tracker = AsyncProgressTracker(
                    analysis_id=analysis_id,
                    analysts=form_data['analysts'],
                    research_depth=form_data['research_depth'],
                    llm_provider=config['llm_provider']
                )

                # Create progress callback function
                def progress_callback(message: str, step: int = None, total_steps: int = None):
                    async_tracker.update_progress(message, step)

                # Display successful start message and loading animation
                st.success(f"🚀 Analysis started! Analysis ID: {analysis_id}")

                # Add loading animation
                with st.spinner("🔄 Initializing analysis..."):
                    time.sleep(1.5)  # Allow user to see feedback

                st.info(f"📊 Analyzing: {form_data.get('market_type', 'US Stocks')} {form_data['stock_symbol']}")
                st.info("""
                ⏱️ Page will automatically refresh in 6 seconds...

                📋 **View analysis progress:**
                After refreshing, please scroll down to the "📊 Stock Analysis" section to view real-time progress
                """)

                # Ensure AsyncProgressTracker has saved initial state
                time.sleep(0.1)  # Wait 100 milliseconds to ensure data is written

                # Set analysis status
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = analysis_id
                st.session_state.last_stock_symbol = form_data['stock_symbol']
                st.session_state.last_market_type = form_data.get('market_type', 'US Stocks')

                # Automatically enable auto-refresh option (set all possible keys)
                auto_refresh_keys = [
                    f"auto_refresh_unified_{analysis_id}",
                    f"auto_refresh_unified_default_{analysis_id}",
                    f"auto_refresh_static_{analysis_id}",
                    f"auto_refresh_streamlit_{analysis_id}"
                ]
                for key in auto_refresh_keys:
                    st.session_state[key] = True

                # Run analysis in background thread (start immediately, no countdown)
                import threading

                def run_analysis_in_background():
                    try:
                        # Market type normalization for compatibility
                        market_type_map = {
                            "A-Shares": "A-shares",
                            "US Stocks": "US stocks",
                            "HK Stocks": "Hong Kong stocks",
                            "A股": "A-shares",
                            "美股": "US stocks",
                            "港股": "Hong Kong stocks",
                        }
                        normalized_market_type = market_type_map.get(form_data.get('market_type', 'US Stocks'), form_data.get('market_type', 'US Stocks'))
                        results = run_stock_analysis(
                            stock_symbol=form_data['stock_symbol'],
                            analysis_date=form_data['analysis_date'],
                            analysts=form_data['analysts'],
                            research_depth=form_data['research_depth'],
                            llm_provider=config['llm_provider'],
                            market_type=normalized_market_type,
                            llm_model=config['llm_model'],
                            progress_callback=progress_callback
                        )

                        # Mark analysis as completed and save results (do not access session state)
                        async_tracker.mark_completed("✅ Analysis completed successfully!", results=results)

                        logger.info(f"✅ [Analysis completed] Stock analysis completed successfully: {analysis_id}")

                    except Exception as e:
                        # Mark analysis as failed (do not access session state)
                        async_tracker.mark_failed(str(e))
                        logger.error(f"❌ [Analysis failed] {analysis_id}: {e}")

                    finally:
                        # Unregister thread from tracker
                        from utils.thread_tracker import unregister_analysis_thread
                        unregister_analysis_thread(analysis_id)
                        logger.info(f"🧵 [Thread cleanup] Analysis thread unregistered: {analysis_id}")

                # Start background analysis thread
                analysis_thread = threading.Thread(target=run_analysis_in_background)
                analysis_thread.daemon = True  # Set as daemon thread, so it exits when main program exits
                analysis_thread.start()

                # Register thread to tracker
                from utils.thread_tracker import register_analysis_thread
                register_analysis_thread(analysis_id, analysis_thread)

                logger.info(f"🧵 [Background analysis] Analysis thread started: {analysis_id}")

                # Analysis has started in the background, display start message and refresh page
                st.success("🚀 Analysis started! Running in the background...")

                # Display start message
                st.info("⏱️ Page will automatically refresh to show analysis progress...")

                # Wait 2 seconds for user to see the start message, then refresh page
                time.sleep(2)
                st.rerun()

        # 2. Stock analysis area (only show if analysis ID exists)
        current_analysis_id = st.session_state.get('current_analysis_id')
        if current_analysis_id:
            st.markdown("---")

            st.header("📊 Stock Analysis")

            # Use thread detection to get actual status
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(current_analysis_id)
            is_running = (actual_status == 'running')

            # Synchronize session state status
            if st.session_state.get('analysis_running', False) != is_running:
                st.session_state.analysis_running = is_running
                logger.info(f"🔄 [Status synchronization] Updating analysis status: {is_running} (based on thread detection: {actual_status})")

            # Get progress data for display
            from utils.async_progress_tracker import get_progress_by_id
            progress_data = get_progress_by_id(current_analysis_id)

            # Display analysis info
            if is_running:
                st.info(f"🔄 Analyzing: {current_analysis_id}")
            else:
                if actual_status == 'completed':
                    st.success(f"✅ Analysis completed: {current_analysis_id}")

                elif actual_status == 'failed':
                    st.error(f"❌ Analysis failed: {current_analysis_id}")
                else:
                    st.warning(f"⚠️ Unknown analysis status: {current_analysis_id}")

            # Display progress (only show refresh controls if analysis is running)
            progress_col1, progress_col2 = st.columns([4, 1])
            with progress_col1:
                st.markdown("### 📊 Analysis Progress")

            is_completed = display_unified_progress(current_analysis_id, show_refresh_controls=is_running)

            # If analysis is running, display prompt message (no additional auto-refresh)
            if is_running:
                st.info("⏱️ Analysis is in progress, you can use the auto-refresh feature below to view progress updates...")

            # If analysis is just completed, try to restore results
            if is_completed and not st.session_state.get('analysis_results') and progress_data:
                if 'raw_results' in progress_data:
                    try:
                        from utils.analysis_runner import format_analysis_results
                        raw_results = progress_data['raw_results']
                        formatted_results = format_analysis_results(raw_results)
                        if formatted_results:
                            st.session_state.analysis_results = formatted_results
                            st.session_state.analysis_running = False
                            logger.info(f"📊 [Result synchronization] Restored analysis results: {current_analysis_id}")

                            # Check if already refreshed, avoid duplicate refresh
                            refresh_key = f"results_refreshed_{current_analysis_id}"
                            if not st.session_state.get(refresh_key, False):
                                st.session_state[refresh_key] = True
                                st.success("📊 Analysis results restored, refreshing page...")
                                # Use st.rerun() instead of meta refresh to keep sidebar state
                                time.sleep(1)
                                st.rerun()
                            else:
                                # Already refreshed, no need to refresh
                                st.success("📊 Analysis results restored!")
                    except Exception as e:
                        logger.warning(f"⚠️ [Result synchronization] Restoration failed: {e}")

            if is_completed and st.session_state.get('analysis_running', False):
                # Analysis just completed, update status
                st.session_state.analysis_running = False
                st.success("🎉 Analysis completed! Refreshing page to show report...")

                # Use st.rerun() instead of meta refresh to keep sidebar state
                time.sleep(1)
                st.rerun()



        # 3. Analysis report area (only show if results exist and analysis is completed)

        current_analysis_id = st.session_state.get('current_analysis_id')
        analysis_results = st.session_state.get('analysis_results')
        analysis_running = st.session_state.get('analysis_running', False)

        # Check if analysis report should be displayed
        # 1. Analysis results exist and not running
        # 2. Or user clicked "View Report" button
        show_results_button_clicked = st.session_state.get('show_analysis_results', False)

        should_show_results = (
            (analysis_results and not analysis_running and current_analysis_id) or
            (show_results_button_clicked and analysis_results)
        )

        # Debug logs
        logger.info(f"🔍 [Layout debug] Analysis report check:")
        logger.info(f"  - analysis_results exist: {bool(analysis_results)}")
        logger.info(f"  - analysis_running: {analysis_running}")
        logger.info(f"  - current_analysis_id: {current_analysis_id}")
        logger.info(f"  - show_results_button_clicked: {show_results_button_clicked}")
        logger.info(f"  - should_show_results: {should_show_results}")

        if should_show_results:
            st.markdown("---")
            st.header("📋 Analysis Report")
            render_results(analysis_results)
            logger.info(f"✅ [Layout] Analysis report displayed")

            # Clear "View Report" button state to avoid duplicate triggers
            if show_results_button_clicked:
                st.session_state.show_analysis_results = False
    
    # Only render right content when showing guide
    if show_guide and col2 is not None:
        with col2:
            st.markdown("### ℹ️ Usage Guide")
        
            # Quick start guide
            with st.expander("🎯 Quick Start", expanded=True):
                st.markdown("""
                ### 📋 Operation Steps

                1. **Enter Stock Code**
                   - A-share example: `000001` (Ping An Bank), `600519` (Guizhou Moutai), `000858` (Wuliangye)
                   - US share example: `AAPL` (Apple), `TSLA` (Tesla), `MSFT` (Microsoft)
                   - HK share example: `00700` (Tencent), `09988` (Alibaba)

                ⚠️ **Important Note**: After entering the stock code, please press **Enter** to confirm!

                2. **Select Analysis Date**
                   - Default to today
                   - Can select historical dates for backtesting analysis

                3. **Select Analyst Team**
                   - At least one analyst must be selected
                   - It is recommended to select multiple analysts for a comprehensive analysis

                4. **Set Research Depth**
                   - 1-2 levels: Quick overview
                   - 3 levels: Standard analysis (recommended)
                   - 4-5 levels: Deep research

                5. **Click Start Analysis**
                   - Wait for AI analysis to complete
                   - View detailed analysis report

                ### 💡 Usage Tips

                - **Default A-share**: System defaults to analyzing A-shares, no special settings needed
                - **Code Format**: A-share uses 6-digit code (e.g., `000001`),
                - **Real-time Data**: Get the latest market data and news
                - **Multi-dimensional Analysis**: Combine technical, fundamental, and sentiment analysis
                """)

            # Analysts' explanation
            with st.expander("👥 Analyst Team Explanation"):
                st.markdown("""
                ### 🎯 Professional Analyst Team

                - **📈 Market Analyst**:
                  - Technical indicators analysis (K-line, moving averages, MACD, etc.)
                  - Price trend prediction
                  - Support and resistance analysis

                - **💭 Social Media Analyst**:
                  - Investor sentiment monitoring
                  - Social media heat analysis
                  - Market sentiment indicators

                - **📰 News Analyst**:
                  - Impact of major news events
                  - Policy interpretation analysis
                  - Industry dynamic tracking

                - **💰 Fundamental Analyst**:
                  - Financial statement analysis
                  - Valuation model calculation
                  - Industry comparison analysis
                  - Profitability assessment

                💡 **Suggestion**: Selecting multiple analysts can provide a more comprehensive investment advice
                """)

            # Model selection explanation
            with st.expander("🧠 AI Model Explanation"):
                st.markdown("""
                ### 🤖 Intelligent Model Selection

                - **qwen-turbo**:
                  - Quick response, suitable for quick queries
                  - Lower cost, suitable for frequent use
                  - Response time: 2-5 seconds

                - **qwen-plus**:
                  - Balanced performance, recommended for daily use ⭐
                  - Accuracy and speed balanced
                  - Response time: 5-10 seconds

                - **qwen-max**:
                  - Strongest performance, suitable for deep analysis
                  - Highest accuracy and analysis depth
                  - Response time: 10-20 seconds

                💡 **Recommendation**: Use `qwen-plus` for daily analysis, `qwen-max` for important decisions
                """)

            # Common questions
            with st.expander("❓ Common Questions"):
                st.markdown("""
                ### 🔍 Common Questions and Answers

                **Q: Why does the stock code input not respond?**
                A: Please ensure you press **Enter** after entering the code, this is the default behavior of Streamlit.

                **Q: What is the A-share code format?**
                A: A-share uses 6-digit code, such as `000001`, `600519`, `000858`, etc.

                **Q: How long does an analysis take?**
                A: Depending on research depth and model selection, it usually takes 30 seconds to 2 minutes.

                **Q: Can Hong Kong stocks be analyzed?**
                A: Yes, input 5-digit HK stocks, such as `00700`, `09988`, etc.

                **Q: How far back can historical data be traced?**
                A: Usually, historical data from the past 5 years can be analyzed.
                """)

            # Risk warning
            st.warning("""
            ⚠️ **Investment Risk Warning**

            - The analysis results provided by this system are for reference only and do not constitute investment advice
            - Investing involves risks, please be prudent, and invest rationally
            - Please combine multiple information and professional advice for investment decisions
            - Major investment decisions are recommended to consult professional investment advisors
            - AI analysis has limitations, market changes are difficult to fully predict
            """)
        
        # Display system status
        if st.session_state.last_analysis_time:
            st.info(f"🕒 Last analysis time: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
