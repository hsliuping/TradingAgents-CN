"""回测服务配置"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 优先加载 backtest-service 目录下的 .env，确保 MongoDB 配置不被项目根 .env 覆盖
load_dotenv(Path(__file__).parent / ".env")
load_dotenv()  # 再加载项目根 .env（若有 backtest 专用变量可覆盖）

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:tradingagents123@localhost:27017/tradingagents?authSource=admin")
MONGO_DB = os.getenv("MONGO_DB", "tradingagents")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8900"))
