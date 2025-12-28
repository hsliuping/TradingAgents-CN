
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.market_detector import MarketSymbolDetector

def test_detector():
    codes = ["980022", "000001", "399001", "930001", "980022.SZ"]
    for code in codes:
        market, analysis_type = MarketSymbolDetector.detect(code)
        print(f"Code: {code}, Market: {market}, Type: {analysis_type}")

if __name__ == "__main__":
    test_detector()
