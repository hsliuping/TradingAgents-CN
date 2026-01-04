import os
import sys
from unittest.mock import MagicMock
from dotenv import load_dotenv

def check_environment():
    """
    Check if the necessary environment variables are set for real environment testing.
    Exits the script gracefully if prerequisites are missing.
    Also mocks database connections to prevent writing to the real database.
    """
    # 0. Disable Database Storage & Cache via Environment Variables
    # We set these BEFORE loading .env or importing modules that use them
    os.environ["USE_MONGODB_STORAGE"] = "false"
    os.environ["MONGODB_ENABLED"] = "false"
    os.environ["REDIS_ENABLED"] = "false"
    
    # Also patch modules to be safe (in case env vars are ignored or overwritten)
    # We need to patch before 'tradingagents' modules are deeply imported
    sys.modules["pymongo"] = MagicMock()
    sys.modules["pymongo.errors"] = MagicMock()
    sys.modules["pymongo.collection"] = MagicMock()
    sys.modules["pymongo.database"] = MagicMock()
    sys.modules["redis"] = MagicMock()
    
    load_dotenv()
    
    # 1. Check LLM API Key (DeepSeek)
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_key or deepseek_key.startswith("your_") or len(deepseek_key) < 20:
        print("\n" + "="*60)
        print("⚠️  SKIPPING TEST: Valid DEEPSEEK_API_KEY not found in .env")
        print("="*60)
        print("Reason: These tests require a real LLM connection to function.")
        print("Current Status: DEEPSEEK_API_KEY appears to be a placeholder or missing.")
        print("\nAction Required:")
        print("1. Open .env file in the project root.")
        print("2. Set a valid DEEPSEEK_API_KEY.")
        print("="*60 + "\n")
        sys.exit(0) 

    # 2. Check Data Source Tokens (Warning only)
    tushare_token = os.getenv("TUSHARE_TOKEN", "")
    if not tushare_token or len(tushare_token) < 20:
        print("\n⚠️  WARNING: TUSHARE_TOKEN missing or invalid.")
        print("   Some data retrieval tools may fail.")
