"""回测服务配置"""
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:tradingagents123@localhost:27017/tradingagents?authSource=admin")
MONGO_DB = os.getenv("MONGO_DB", "tradingagents")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8900"))
