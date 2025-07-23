"""
Stock analysis execution tool
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Import logging module
from tradingagents.utils.logging_manager import get_logger, get_logger_manager
logger = get_logger('web')

# Add project root directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Ensure environment variables are loaded correctly
load_dotenv(project_root / ".env", override=True)

# Import unified logging system
from tradingagents.utils.logging_init import setup_web_logging
logger = setup_web_logging()

# Add configuration manager
try:
    from tradingagents.config.config_manager import token_tracker
    TOKEN_TRACKING_ENABLED = True
    logger.info("✅ Token tracking feature enabled")
except ImportError:
    TOKEN_TRACKING_ENABLED = False
    logger.warning("⚠️ Token tracking feature not enabled")

def translate_analyst_labels(text):
    """Translate analyst English labels to Chinese"""
    if not text:
        return text

    # Analyst label translation map
    translations = {
        'Bull Analyst:': 'Bull Analyst:',
        'Bear Analyst:': 'Bear Analyst:',
        'Risky Analyst:': 'Risky Analyst:',
        'Safe Analyst:': 'Safe Analyst:',
        'Neutral Analyst:': 'Neutral Analyst:',
        'Research Manager:': 'Research Manager:',
        'Portfolio Manager:': 'Portfolio Manager:',
        'Risk Judge:': 'Risk Judge:',
        'Trader:': 'Trader:'
    }

    # Replace all English labels
    for english, chinese in translations.items():
        text = text.replace(english, chinese)

    return text

def extract_risk_assessment(state):
    """Extract risk assessment data from analysis state"""
    try:
        risk_debate_state = state.get('risk_debate_state', {})

        if not risk_debate_state:
            return None

        # Extract opinions from different risk analysts and translate to Chinese
        risky_analysis = translate_analyst_labels(risk_debate_state.get('risky_history', ''))
        safe_analysis = translate_analyst_labels(risk_debate_state.get('safe_history', ''))
        neutral_analysis = translate_analyst_labels(risk_debate_state.get('neutral_history', ''))
        judge_decision = translate_analyst_labels(risk_debate_state.get('judge_decision', ''))

        # Format risk assessment report
        risk_assessment = f"""
## ⚠️ Risk Assessment Report

### 🔴 Risky Analyst Opinions
{risky_analysis if risky_analysis else 'No risky analysis available'}

### 🟢 Neutral Analyst Opinions
{neutral_analysis if neutral_analysis else 'No neutral analysis available'}

### 🟢 Conservative Analyst Opinions
{safe_analysis if safe_analysis else 'No conservative analysis available'}

### 🏛️ Risk Management Committee Final Decision
{judge_decision if judge_decision else 'No risk management decision available'}

---
*Risk assessment is based on multi-angle analysis, please make investment decisions based on your own risk tolerance*
        """.strip()

        return risk_assessment

    except Exception as e:
        logger.info(f"Error extracting risk assessment data: {e}")
        return None

def run_stock_analysis(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, temperature=0.7, top_p=1.0, max_tokens=1024, frequency_penalty=0.0, presence_penalty=0.0, market_type="US", progress_callback=None):
    """Execute stock analysis

    Args:
        stock_symbol: Stock code
        analysis_date: Analysis date
        analysts: Analyst list
        research_depth: Research depth
        llm_provider: LLM provider (dashscope/deepseek/google)
        llm_model: Large model name
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
        max_tokens: Maximum output tokens
        frequency_penalty: Frequency penalty
        presence_penalty: Presence penalty
        progress_callback: Progress callback function to update UI status
    """

    def update_progress(message, step=None, total_steps=None):
        """Update progress"""
        if progress_callback:
            progress_callback(message, step, total_steps)
        logger.info(f"[Progress] {message}")

    # Market type normalization for compatibility with stock_validator
    market_type_map = {
        "A-Shares": "A-shares",
        "US Stocks": "US stocks",
        "HK Stocks": "Hong Kong stocks",
        "A股": "A-shares",
        "美股": "US stocks",
        "港股": "Hong Kong stocks",
    }
    market_type = market_type_map.get(market_type, market_type)

    # Generate session ID for token tracking and log association
    session_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 1. Data pre-fetch and validation phase
    update_progress("🔍 Validating stock code and pre-fetching data...", 1, 10)

    try:
        from tradingagents.utils.stock_validator import prepare_stock_data

        # Pre-fetch stock data (default 30 days history)
        preparation_result = prepare_stock_data(
            stock_code=stock_symbol,
            market_type=market_type,
            period_days=30,  # Can be adjusted based on research_depth
            analysis_date=analysis_date
        )

        if not preparation_result.is_valid:
            error_msg = f"❌ Stock data validation failed: {preparation_result.error_message}"
            update_progress(error_msg)
            logger.error(f"[{session_id}] {error_msg}")

            return {
                'success': False,
                'error': preparation_result.error_message,
                'suggestion': preparation_result.suggestion,
                'stock_symbol': stock_symbol,
                'analysis_date': analysis_date,
                'session_id': session_id
            }

        # Data pre-fetch successful
        success_msg = f"✅ Data preparation complete: {preparation_result.stock_name} ({preparation_result.market_type})"
        update_progress(success_msg)  # Use smart detection, no longer hardcoded steps
        logger.info(f"[{session_id}] {success_msg}")
        logger.info(f"[{session_id}] Cache status: {preparation_result.cache_status}")

    except Exception as e:
        error_msg = f"❌ Error during data pre-fetching: {str(e)}"
        update_progress(error_msg)
        logger.error(f"[{session_id}] {error_msg}")

        return {
            'success': False,
            'error': error_msg,
            'suggestion': "Please check your network connection or try again later",
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'session_id': session_id
        }

    # Log detailed analysis start
    logger_manager = get_logger_manager()
    import time
    analysis_start_time = time.time()

    logger_manager.log_analysis_start(
        logger, stock_symbol, "comprehensive_analysis", session_id
    )

    logger.info(f"🚀 [Analysis Started] Stock analysis started",
               extra={
                   'stock_symbol': stock_symbol,
                   'analysis_date': analysis_date,
                   'analysts': analysts,
                   'research_depth': research_depth,
                   'llm_provider': llm_provider,
                   'llm_model': llm_model,
                   'market_type': market_type,
                   'session_id': session_id,
                   'event_type': 'web_analysis_start'
               })

    update_progress("🚀 Starting stock analysis...")

    # Estimate token usage (for cost estimation)
    if TOKEN_TRACKING_ENABLED:
        estimated_input = 2000 * len(analysts)  # Estimate 2000 input tokens per analyst
        estimated_output = 1000 * len(analysts)  # Estimate 1000 output tokens per analyst
        estimated_cost = token_tracker.estimate_cost(llm_provider, llm_model, estimated_input, estimated_output)

        update_progress(f"💰 Estimated analysis cost: ¥{estimated_cost:.4f}")

    # Validate environment variables
    update_progress("Checking environment variable configuration...")
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")

    logger.info(f"Environment variable check:")
    logger.info(f"  DASHSCOPE_API_KEY: {'Set' if dashscope_key else 'Not set'}")
    logger.info(f"  FINNHUB_API_KEY: {'Set' if finnhub_key else 'Not set'}")

    if not dashscope_key:
        raise ValueError("DASHSCOPE_API_KEY environment variable not set")
    if not finnhub_key:
        raise ValueError("FINNHUB_API_KEY environment variable not set")

    update_progress("Environment variable validation passed")

    try:
        # Import necessary modules
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        # Create configuration
        update_progress("Configuring analysis parameters...")
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = llm_provider
        config["deep_think_llm"] = llm_model
        config["quick_think_llm"] = llm_model
        config["temperature"] = temperature
        config["top_p"] = top_p
        config["max_tokens"] = max_tokens
        config["frequency_penalty"] = frequency_penalty
        config["presence_penalty"] = presence_penalty
        # Adjust configuration based on research depth
        if research_depth == 1:  # Level 1 - Quick analysis
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            # Keep memory enabled as it has minimal overhead but significantly improves analysis quality
            config["memory_enabled"] = True

            # Use unified tools to avoid various issues with offline tools
            config["online_tools"] = True  # All markets use unified tools
            logger.info(f"🔧 [Quick Analysis] {market_type} uses unified tools to ensure correct data sources and stability")
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-turbo"  # Use fastest model
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"  # DeepSeek has only one model
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 2:  # Level 2 - Basic analysis
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 3:  # Level 3 - Standard analysis (default)
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 4:  # Level 4 - Deep analysis
            config["max_debate_rounds"] = 2
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        else:  # Level 5 - Comprehensive analysis
            config["max_debate_rounds"] = 3
            config["max_risk_discuss_rounds"] = 3
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-max"
                config["deep_think_llm"] = "qwen-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"

        # Set different configurations based on LLM provider
        if llm_provider == "dashscope":
            config["backend_url"] = "https://dashscope.aliyuncs.com/api/v1"
        elif llm_provider == "deepseek":
            config["backend_url"] = "https://api.deepseek.com"
        elif llm_provider == "google":
            # Google AI does not require backend_url, use default OpenAI format
            config["backend_url"] = "https://api.openai.com/v1"

        # Fix path issues
        config["data_dir"] = str(project_root / "data")
        config["results_dir"] = str(project_root / "results")
        config["data_cache_dir"] = str(project_root / "tradingagents" / "dataflows" / "data_cache")

        # Ensure directories exist
        update_progress("📁 Creating necessary directories...")
        os.makedirs(config["data_dir"], exist_ok=True)
        os.makedirs(config["results_dir"], exist_ok=True)
        os.makedirs(config["data_cache_dir"], exist_ok=True)

        logger.info(f"Using configuration: {config}")
        logger.info(f"Analyst list: {analysts}")
        logger.info(f"Stock code: {stock_symbol}")
        logger.info(f"Analysis date: {analysis_date}")

        # Adjust stock code format based on market type
        logger.debug(f"🔍 [RUNNER DEBUG] ===== Stock code formatting =====")
        logger.debug(f"🔍 [RUNNER DEBUG] Original stock code: '{stock_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG] Market type: '{market_type}'")

        if market_type == "A-shares":
            # A-share code does not require special handling, keep as is
            formatted_symbol = stock_symbol
            logger.debug(f"🔍 [RUNNER DEBUG] A-share code remains unchanged: '{formatted_symbol}'")
            update_progress(f"🇨🇳 Preparing A-share analysis: {formatted_symbol}")
        elif market_type == "Hong Kong stocks":
            # HK-share code to uppercase, ensure .HK suffix
            formatted_symbol = stock_symbol.upper()
            if not formatted_symbol.endswith('.HK'):
                # If it's pure digits, add .HK suffix
                if formatted_symbol.isdigit():
                    formatted_symbol = f"{formatted_symbol.zfill(4)}.HK"
            update_progress(f"🇭🇰 Preparing HK-share analysis: {formatted_symbol}")
        else:
            # US-share code to uppercase
            formatted_symbol = stock_symbol.upper()
            logger.debug(f"🔍 [RUNNER DEBUG] US-share code to uppercase: '{stock_symbol}' -> '{formatted_symbol}'")
            update_progress(f"🇺🇸 Preparing US-share analysis: {formatted_symbol}")

        logger.debug(f"🔍 [RUNNER DEBUG] Final stock code passed to analysis engine: '{formatted_symbol}'")

        # Initialize trading graph
        update_progress("🔧 Initializing analysis engine...")
        graph = TradingAgentsGraph(analysts, config=config, debug=False)

        # Execute analysis
        update_progress(f"📊 Starting analysis of {formatted_symbol} stock, this may take a few minutes...")
        logger.debug(f"🔍 [RUNNER DEBUG] ===== Calling graph.propagate =====")
        logger.debug(f"🔍 [RUNNER DEBUG] Parameters passed to graph.propagate:")
        logger.debug(f"🔍 [RUNNER DEBUG]   symbol: '{formatted_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG]   date: '{analysis_date}'")

        state, decision = graph.propagate(formatted_symbol, analysis_date)

        # Debug information
        logger.debug(f"🔍 [DEBUG] Analysis complete, decision type: {type(decision)}")
        logger.debug(f"🔍 [DEBUG] decision content: {decision}")

        # Format results
        update_progress("📋 Analysis complete, organizing results...")

        # Extract risk assessment data
        risk_assessment = extract_risk_assessment(state)

        # Add risk assessment to state
        if risk_assessment:
            state['risk_assessment'] = risk_assessment

        # Log token usage (actual usage, using estimated values here)
        if TOKEN_TRACKING_ENABLED:
            # In a real application, these values should be obtained from LLM responses
            # Here, estimated values based on analyst count and research depth are used
            actual_input_tokens = len(analysts) * (1500 if research_depth == "Quick" else 2500 if research_depth == "Standard" else 4000)
            actual_output_tokens = len(analysts) * (800 if research_depth == "Quick" else 1200 if research_depth == "Standard" else 2000)

            usage_record = token_tracker.track_usage(
                provider=llm_provider,
                model_name=llm_model,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                session_id=session_id,
                analysis_type=f"{market_type}_analysis"
            )

            if usage_record:
                update_progress(f"💰 Recording cost: ¥{usage_record.cost:.4f}")

        results = {
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'analysts': analysts,
            'research_depth': research_depth,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'state': state,
            'decision': decision,
            'success': True,
            'error': None,
            'session_id': session_id if TOKEN_TRACKING_ENABLED else None
        }

        # Log detailed analysis completion
        analysis_duration = time.time() - analysis_start_time

        # Calculate total cost (if token tracking is enabled)
        total_cost = 0.0
        if TOKEN_TRACKING_ENABLED:
            try:
                total_cost = token_tracker.get_session_cost(session_id)
            except:
                pass

        logger_manager.log_analysis_complete(
            logger, stock_symbol, "comprehensive_analysis", session_id,
            analysis_duration, total_cost
        )

        logger.info(f"✅ [Analysis Complete] Stock analysis completed successfully",
                   extra={
                       'stock_symbol': stock_symbol,
                       'session_id': session_id,
                       'duration': analysis_duration,
                       'total_cost': total_cost,
                       'analysts_used': analysts,
                       'success': True,
                       'event_type': 'web_analysis_complete'
                   })

        update_progress("✅ Analysis completed successfully!")
        return results

    except Exception as e:
        # Log detailed analysis failure
        analysis_duration = time.time() - analysis_start_time

        logger_manager.log_module_error(
            logger, "comprehensive_analysis", stock_symbol, session_id,
            analysis_duration, str(e)
        )

        logger.error(f"❌ [Analysis Failed] Stock analysis execution failed",
                    extra={
                        'stock_symbol': stock_symbol,
                        'session_id': session_id,
                        'duration': analysis_duration,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'analysts_used': analysts,
                        'success': False,
                        'event_type': 'web_analysis_error'
                    }, exc_info=True)

        # If real analysis fails, return simulated data for demonstration
        return generate_demo_results(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, str(e), market_type)

def format_analysis_results(results):
    """Format analysis results for display"""
    
    if not results['success']:
        return {
            'error': results['error'],
            'success': False
        }
    
    state = results['state']
    decision = results['decision']

    # Extract key information
    # decision can be a string (e.g., "BUY", "SELL", "HOLD") or a dictionary
    if isinstance(decision, str):
        # Translate English investment suggestions to Chinese
        action_translation = {
            'BUY': 'Buy',
            'SELL': 'Sell',
            'HOLD': 'Hold',
            'buy': 'Buy',
            'sell': 'Sell',
            'hold': 'Hold'
        }
        action = action_translation.get(decision.strip(), decision.strip())

        formatted_decision = {
            'action': action,
            'confidence': 0.7,  # Default confidence
            'risk_score': 0.3,  # Default risk score
            'target_price': None,  # String format does not have target price
            'reasoning': f'Based on AI analysis, the suggestion is to {decision.strip().upper()}'
        }
    elif isinstance(decision, dict):
        # Handle target price - ensure correct extraction of numeric value
        target_price = decision.get('target_price')
        if target_price is not None and target_price != 'N/A':
            try:
                # Try to convert to float
                if isinstance(target_price, str):
                    # Remove currency symbols and spaces
                    clean_price = target_price.replace('$', '').replace('¥', '').replace('￥', '').strip()
                    target_price = float(clean_price) if clean_price and clean_price != 'None' else None
                elif isinstance(target_price, (int, float)):
                    target_price = float(target_price)
                else:
                    target_price = None
            except (ValueError, TypeError):
                target_price = None
        else:
            target_price = None

        # Translate English investment suggestions to Chinese
        action_translation = {
            'BUY': 'Buy',
            'SELL': 'Sell',
            'HOLD': 'Hold',
            'buy': 'Buy',
            'sell': 'Sell',
            'hold': 'Hold'
        }
        action = decision.get('action', 'Hold')
        chinese_action = action_translation.get(action, action)

        formatted_decision = {
            'action': chinese_action,
            'confidence': decision.get('confidence', 0.5),
            'risk_score': decision.get('risk_score', 0.3),
            'target_price': target_price,
            'reasoning': decision.get('reasoning', 'No analysis reasoning available')
        }
    else:
        # Handle other types
        formatted_decision = {
            'action': 'Hold',
            'confidence': 0.5,
            'risk_score': 0.3,
            'target_price': None,
            'reasoning': f'Analysis result: {str(decision)}'
        }
    
    # Format state information
    formatted_state = {}
    
    # Process results of each analysis module
    analysis_keys = [
        'market_report',
        'fundamentals_report', 
        'sentiment_report',
        'news_report',
        'risk_assessment',
        'investment_plan'
    ]
    
    for key in analysis_keys:
        if key in state:
            # Translate text content to Chinese
            content = state[key]
            if isinstance(content, str):
                content = translate_analyst_labels(content)
            formatted_state[key] = content
    
    return {
        'stock_symbol': results['stock_symbol'],
        'decision': formatted_decision,
        'state': formatted_state,
        'success': True,
        # Put configuration at the top for direct access by frontend
        'analysis_date': results['analysis_date'],
        'analysts': results['analysts'],
        'research_depth': results['research_depth'],
        'llm_provider': results.get('llm_provider', 'dashscope'),
        'llm_model': results['llm_model'],
        'metadata': {
            'analysis_date': results['analysis_date'],
            'analysts': results['analysts'],
            'research_depth': results['research_depth'],
            'llm_provider': results.get('llm_provider', 'dashscope'),
            'llm_model': results['llm_model']
        }
    }

def validate_analysis_params(stock_symbol, analysis_date, analysts, research_depth, market_type="US"):
    """Validate analysis parameters"""

    errors = []

    # Validate stock code
    if not stock_symbol or len(stock_symbol.strip()) == 0:
        errors.append("Stock code cannot be empty")
    elif len(stock_symbol.strip()) > 10:
        errors.append("Stock code cannot exceed 10 characters")
    else:
        # Validate code format based on market type
        symbol = stock_symbol.strip()
        if market_type == "A-shares":
            # A-share: 6 digits
            import re
            if not re.match(r'^\d{6}$', symbol):
                errors.append("A-share code format error, should be 6 digits (e.g., 000001)")
        elif market_type == "Hong Kong stocks":
            # HK-share: 4-5 digits.HK or pure 4-5 digits
            import re
            symbol_upper = symbol.upper()
            # Check if it's XXXX.HK or XXXXX.HK format
            hk_format = re.match(r'^\d{4,5}\.HK$', symbol_upper)
            # Check if it's pure 4-5 digit format
            digit_format = re.match(r'^\d{4,5}$', symbol)

            if not (hk_format or digit_format):
                errors.append("HK-share code format error, should be 4 digits.HK (e.g., 0700.HK) or 4 digits (e.g., 0700)")
        elif market_type == "US stocks":
            # US-share: 1-5 letters
            import re
            if not re.match(r'^[A-Z]{1,5}$', symbol.upper()):
                errors.append("US-share code format error, should be 1-5 letters (e.g., AAPL)")
    
    # Validate analyst list
    if not analysts or len(analysts) == 0:
        errors.append("At least one analyst must be selected")
    
    valid_analysts = ['market', 'social', 'news', 'fundamentals']
    invalid_analysts = [a for a in analysts if a not in valid_analysts]
    if invalid_analysts:
        errors.append(f"Invalid analyst type: {', '.join(invalid_analysts)}")
    
    # Validate research depth
    if not isinstance(research_depth, int) or research_depth < 1 or research_depth > 5:
        errors.append("Research depth must be an integer between 1 and 5")
    
    # Validate analysis date
    try:
        from datetime import datetime
        datetime.strptime(analysis_date, '%Y-%m-%d')
    except ValueError:
        errors.append("Analysis date format is invalid, should be YYYY-MM-DD format")
    
    return len(errors) == 0, errors

def get_supported_stocks():
    """Get supported stock list"""
    
    # Common US stock codes
    popular_stocks = [
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
        {'symbol': 'MSFT', 'name': 'Microsoft', 'sector': 'Technology'},
        {'symbol': 'GOOGL', 'name': 'Google', 'sector': 'Technology'},
        {'symbol': 'AMZN', 'name': 'Amazon', 'sector': 'Consumer'},
        {'symbol': 'TSLA', 'name': 'Tesla', 'sector': 'Automotive'},
        {'symbol': 'NVDA', 'name': 'NVIDIA', 'sector': 'Technology'},
        {'symbol': 'META', 'name': 'Meta', 'sector': 'Technology'},
        {'symbol': 'NFLX', 'name': 'Netflix', 'sector': 'Media'},
        {'symbol': 'AMD', 'name': 'AMD', 'sector': 'Technology'},
        {'symbol': 'INTC', 'name': 'Intel', 'sector': 'Technology'},
        {'symbol': 'SPY', 'name': 'S&P 500 ETF', 'sector': 'ETF'},
        {'symbol': 'QQQ', 'name': 'Nasdaq 100 ETF', 'sector': 'ETF'},
    ]
    
    return popular_stocks

def generate_demo_results(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, error_msg, market_type="US"):
    """Generate demo analysis results"""

    import random

    # Set currency symbol and price range based on market type
    if market_type == "Hong Kong stocks":
        currency_symbol = "HK$"
        price_range = (50, 500)  # HK-share price range
        market_name = "HK-share"
    elif market_type == "A-shares":
        currency_symbol = "¥"
        price_range = (5, 100)   # A-share price range
        market_name = "A-share"
    else:  # US-share
        currency_symbol = "$"
        price_range = (50, 300)  # US-share price range
        market_name = "US-share"

    # Generate simulated decision
    actions = ['Buy', 'Hold', 'Sell']
    action = random.choice(actions)

    demo_decision = {
        'action': action,
        'confidence': round(random.uniform(0.6, 0.9), 2),
        'risk_score': round(random.uniform(0.2, 0.7), 2),
        'target_price': round(random.uniform(*price_range), 2),
        'reasoning': f"""
Based on comprehensive analysis of {market_name}{stock_symbol}, our AI analysis team concluded:

**Investment Suggestion**: {action}
**Target Price**: {currency_symbol}{round(random.uniform(*price_range), 2)}

**Main Analysis Points**:
1. **Technical Analysis**: Current price trend indicates {'up' if action == 'Buy' else 'down' if action == 'Sell' else 'flat'} signal
2. **Fundamental Evaluation**: Company financial health {'good' if action == 'Buy' else 'average' if action == 'Hold' else 'needs attention'}
3. **Market Sentiment**: Investor sentiment {'positive' if action == 'Buy' else 'neutral' if action == 'Hold' else 'cautious'}
4. **Risk Assessment**: Current risk level is {'medium' if action == 'Hold' else 'low' if action == 'Buy' else 'high'}

**Note**: This is demo data, actual analysis requires correct API keys.
        """
    }

    # Generate simulated state data
    demo_state = {}

    if 'market' in analysts:
        current_price = round(random.uniform(*price_range), 2)
        high_price = round(current_price * random.uniform(1.2, 1.8), 2)
        low_price = round(current_price * random.uniform(0.5, 0.8), 2)

        demo_state['market_report'] = f"""
## 📈 {market_name}{stock_symbol} Technical Analysis Report

### Price Trend Analysis
- **Current Price**: {currency_symbol}{current_price}
- **Daily Change**: {random.choice(['+', '-'])}{round(random.uniform(0.5, 5), 2)}%
- **52-Week High**: {currency_symbol}{high_price}
- **52-Week Low**: {currency_symbol}{low_price}

### Technical Indicators
- **RSI (14-day)**: {round(random.uniform(30, 70), 1)}
- **MACD**: {'Bullish' if action == 'Buy' else 'Bearish' if action == 'Sell' else 'Neutral'}
- **Moving Averages**: Price {'above' if action == 'Buy' else 'below' if action == 'Sell' else 'near'} 20-day MA

### Support and Resistance Levels
- **Support**: ${round(random.uniform(80, 120), 2)}
- **Resistance**: ${round(random.uniform(250, 350), 2)}

*Note*: This is demo data, actual analysis requires API keys.
        """

    if 'fundamentals' in analysts:
        demo_state['fundamentals_report'] = f"""
## 💰 {stock_symbol} Fundamental Analysis Report

### Financial Metrics
- **Price-to-Earnings (P/E)**: {round(random.uniform(15, 35), 1)}
- **Price-to-Book (P/B)**: {round(random.uniform(1, 5), 1)}
- **Return on Equity (ROE)**: {round(random.uniform(10, 25), 1)}%
- **Gross Profit Margin**: {round(random.uniform(20, 60), 1)}%

### Profitability
- **Revenue Growth**: {random.choice(['+', '-'])}{round(random.uniform(5, 20), 1)}%
- **Net Profit Growth**: {random.choice(['+', '-'])}{round(random.uniform(10, 30), 1)}%
- **Earnings Per Share**: ${round(random.uniform(2, 15), 2)}

### Financial Health
- **Debt-to-Equity Ratio**: {round(random.uniform(20, 60), 1)}%
- **Current Ratio**: {round(random.uniform(1, 3), 1)}
- **Cash Flow**: {'Positive' if action != 'Sell' else 'Needs Attention'}

*Note*: This is demo data, actual analysis requires API keys.
        """

    if 'social' in analysts:
        demo_state['sentiment_report'] = f"""
## 💭 {stock_symbol} Market Sentiment Analysis Report

### Social Media Sentiment
- **Overall Sentiment**: {'Positive' if action == 'Buy' else 'Negative' if action == 'Sell' else 'Neutral'}
- **Sentiment Intensity**: {round(random.uniform(0.5, 0.9), 2)}
- **Discussion Heat**: {'High' if random.random() > 0.5 else 'Medium'}

### Investor Sentiment Indicators
- **Fear and Greed Index**: {round(random.uniform(20, 80), 0)}
- **Bullish-Bearish Ratio**: {round(random.uniform(0.8, 1.5), 2)}
- **Put/Call Ratio**: {round(random.uniform(0.5, 1.2), 2)}

### Institutional Investor Trends
- **Institutional Position Changes**: {random.choice(['Increased', 'Decreased', 'Maintained'])}
- **Analyst Ratings**: {'Buy' if action == 'Buy' else 'Sell' if action == 'Sell' else 'Hold'}

*Note*: This is demo data, actual analysis requires API keys.
        """

    if 'news' in analysts:
        demo_state['news_report'] = f"""
## 📰 {stock_symbol} News Event Analysis Report

### Recent Important News
1. **Earnings Release**: Company released {'surprisingly good' if action == 'Buy' else 'worse than expected' if action == 'Sell' else 'as expected'} quarterly earnings
2. **Industry Dynamics**: Industry facing {'favorable' if action == 'Buy' else 'challenging' if action == 'Sell' else 'stable'} policy environment
3. **Company Announcements**: Management {'optimistic' if action == 'Buy' else 'cautious' if action == 'Sell' else 'prudent'} outlook for the future

### News Sentiment Analysis
- **Positive News Proportion**: {round(random.uniform(40, 80), 0)}%
- **Negative News Proportion**: {round(random.uniform(10, 40), 0)}%
- **Neutral News Proportion**: {round(random.uniform(20, 50), 0)}%

### Market Impact Assessment
- **Short-term Impact**: {'Positive' if action == 'Buy' else 'Negative' if action == 'Sell' else 'Neutral'}
- **Long-term Impact**: {'Positive' if action != 'Sell' else 'Needs Observation'}

*Note*: This is demo data, actual analysis requires API keys.
        """

    # Add risk assessment and investment advice
    demo_state['risk_assessment'] = f"""
## ⚠️ {stock_symbol} Risk Assessment Report

### Main Risk Factors
1. **Market Risk**: {'Low' if action == 'Buy' else 'High' if action == 'Sell' else 'Medium'}
2. **Industry Risk**: {'Controllable' if action != 'Sell' else 'Needs Attention'}
3. **Company-specific Risk**: {'Low' if action == 'Buy' else 'Medium'}

### Risk Level Assessment
- **Overall Risk Level**: {'Low Risk' if action == 'Buy' else 'High Risk' if action == 'Sell' else 'Medium Risk'}
- **Suggested Position**: {random.choice(['Light Position', 'Standard Position', 'Heavy Position']) if action != 'Sell' else 'Suggestion to Reduce Position'}

*Note*: This is demo data, actual analysis requires API keys.
    """

    demo_state['investment_plan'] = f"""
## 📋 {stock_symbol} Investment Advice

### Specific Operation Suggestions
- **Operation Direction**: {action}
- **Suggested Price**: ${round(random.uniform(90, 310), 2)}
- **Stop Loss**: ${round(random.uniform(80, 200), 2)}
- **Target Price**: ${round(random.uniform(150, 400), 2)}

### Investment Strategy
- **Investment Period**: {'Short-term' if research_depth <= 2 else 'Medium-long term'}
- **Position Management**: {'Dollar-cost averaging' if action == 'Buy' else 'Dollar-cost averaging' if action == 'Sell' else 'Maintain current position'}

*Note*: This is demo data, actual analysis requires API keys.
    """

    return {
        'stock_symbol': stock_symbol,
        'analysis_date': analysis_date,
        'analysts': analysts,
        'research_depth': research_depth,
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'state': demo_state,
        'decision': demo_decision,
        'success': True,
        'error': None,
        'is_demo': True,
        'demo_reason': f"API call failed, showing demo data. Error message: {error_msg}"
    }
