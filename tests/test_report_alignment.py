
import os
import shutil
from pathlib import Path
from tradingagents.utils.logging_manager import get_logger
from web.utils.report_exporter import save_modular_reports_to_results_dir, report_exporter

# Setup logging
logger = get_logger("test")

def test_index_report_saving():
    """Test saving index analysis reports"""
    
    # Mock data mimicking an index analysis result
    stock_symbol = "sh000001"
    mock_results = {
        "stock_symbol": stock_symbol,
        "is_demo": False,
        "decision": {
            "action": "BUY",
            "confidence": 0.8,
            "risk_score": 0.3,
            "target_price": "3500",
            "reasoning": "Macro looks good."
        },
        "state": {
            "macro_report": "# Macro Analysis\nGDP is growing.",
            "policy_report": "# Policy Analysis\nInterest rates are low.",
            "sector_report": "# Sector Analysis\nTech is booming.",
            "international_news_report": "# International News\nGlobal markets are stable.",
            "technical_report": "# Technical Analysis\nTrend is up.",
            "strategy_report": "# Strategy Report\nBuy the dip."
        }
    }
    
    # Define results directory for testing
    test_results_dir = Path("test_results")
    os.environ["TRADINGAGENTS_RESULTS_DIR"] = str(test_results_dir)
    
    try:
        # Clean up previous test run
        if test_results_dir.exists():
            shutil.rmtree(test_results_dir)
            
        print("🚀 Testing modular report saving...")
        saved_files = save_modular_reports_to_results_dir(mock_results, stock_symbol)
        
        # Verify files are saved
        expected_keys = [
            "macro_report", "policy_report", "sector_report", 
            "international_news_report", "technical_report", "strategy_report"
        ]
        
        for key in expected_keys:
            if key in saved_files:
                print(f"✅ Saved {key}: {saved_files[key]}")
                assert Path(saved_files[key]).exists()
            else:
                print(f"❌ Failed to save {key}")
                raise AssertionError(f"Missing {key} in saved files")
                
        print("🚀 Testing markdown report generation...")
        md_content = report_exporter.generate_markdown_report(mock_results)
        
        # Verify content inclusion
        expected_sections = [
            "🌏 宏观经济分析", "📜 政策环境分析", "🔄 板块轮动分析", 
            "🌍 国际新闻分析", "📈 技术面分析", "🎯 投资策略报告"
        ]
        
        for section in expected_sections:
            if section in md_content:
                print(f"✅ Found section: {section}")
            else:
                print(f"❌ Missing section: {section}")
                raise AssertionError(f"Missing section {section} in markdown report")
                
        print("✅ All tests passed!")
        
    finally:
        # Cleanup
        if test_results_dir.exists():
            shutil.rmtree(test_results_dir)

if __name__ == "__main__":
    test_index_report_saving()
