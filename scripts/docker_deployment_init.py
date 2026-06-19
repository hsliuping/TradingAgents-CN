#!/usr/bin/env python3
"""
Docker 部署初始化脚本
用于新机器部署后的系统初始化，准备必要的基础数据
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('docker_init')

async def check_docker_services():
    """检查 Docker 服务状态"""
    logger.info("🔍 检查 Docker 服务状态...")
    
    try:
        import subprocess
        
        # 检查 docker-compose 服务状态
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose.hub.yml", "ps"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if result.returncode == 0:
            logger.info("✅ Docker 服务运行正常")
            logger.info(f"服务状态:\n{result.stdout}")
            return True
        else:
            logger.error(f"❌ Docker 服务检查失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 检查 Docker 服务时出错: {e}")
        return False

async def wait_for_services():
    """等待服务启动完成"""
    logger.info("⏳ 等待服务启动完成...")
    
    max_retries = 30
    retry_interval = 10
    
    for i in range(max_retries):
        try:
            # 检查 MongoDB
            from pymongo import MongoClient
            mongo_client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
            mongo_client.server_info()
            logger.info("✅ MongoDB 连接成功")
            
            # 检查 Redis
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
            redis_client.ping()
            logger.info("✅ Redis 连接成功")
            
            # 检查后端 API
            import requests
            response = requests.get("http://localhost:8100/api/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ 后端 API 连接成功")
                return True
            
        except Exception as e:
            logger.warning(f"⏳ 等待服务启动... ({i+1}/{max_retries}): {e}")
            await asyncio.sleep(retry_interval)
    
    logger.error("❌ 服务启动超时")
    return False

async def init_mongodb():
    """初始化 MongoDB 数据库"""
    logger.info("🗄️ 初始化 MongoDB 数据库...")
    
    try:
        from pymongo import MongoClient
        
        # 连接数据库
        client = MongoClient("mongodb://localhost:27017/")
        db = client["tradingagents"]
        
        # 创建集合和索引
        collections_to_create = [
            "users", "user_sessions", "user_activities",
            "stock_basic_info", "stock_financial_data", "market_quotes", "stock_news",
            "analysis_tasks", "analysis_reports", "analysis_progress",
            "screening_results", "favorites", "tags",
            "system_config", "model_config", "sync_status", "operation_logs"
        ]
        
        for collection_name in collections_to_create:
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
                logger.info(f"✅ 创建集合: {collection_name}")
        
        # 创建索引
        await create_database_indexes(db)
        
        # 插入基础数据
        await insert_basic_data(db)
        
        logger.info("✅ MongoDB 初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ MongoDB 初始化失败: {e}")
        return False

async def create_database_indexes(db):
    """创建数据库索引"""
    logger.info("📊 创建数据库索引...")
    
    try:
        # 用户相关索引
        db.users.create_index([("username", 1)], unique=True)
        db.users.create_index([("email", 1)], unique=True)
        db.user_sessions.create_index([("user_id", 1)])
        db.user_activities.create_index([("user_id", 1), ("created_at", -1)])
        
        # 股票数据索引
        # 🔥 多数据源支持：使用 (code, source) 联合唯一索引
        db.stock_basic_info.create_index([("code", 1), ("source", 1)], unique=True)
        db.stock_basic_info.create_index([("code", 1)])  # 非唯一索引，用于查询所有数据源
        db.stock_basic_info.create_index([("source", 1)])  # 数据源索引
        db.stock_basic_info.create_index([("market", 1)])
        db.market_quotes.create_index([("code", 1)], unique=True)
        db.stock_news.create_index([("code", 1), ("published_at", -1)])
        
        # 分析相关索引
        db.analysis_tasks.create_index([("user_id", 1), ("created_at", -1)])
        db.analysis_reports.create_index([("task_id", 1)])
        
        # 系统配置索引
        db.system_config.create_index([("key", 1)], unique=True)
        db.operation_logs.create_index([("created_at", -1)])
        
        logger.info("✅ 数据库索引创建完成")
        
    except Exception as e:
        logger.error(f"❌ 创建数据库索引失败: {e}")

async def insert_basic_data(db):
    """插入基础数据"""
    logger.info("📝 插入基础数据...")
    
    try:
        # 创建默认管理员用户
        await create_default_admin_user(db)
        
        # 创建系统配置
        await create_system_config(db)
        
        # 创建模型配置
        await create_model_config(db)
        
        logger.info("✅ 基础数据插入完成")
        
    except Exception as e:
        logger.error(f"❌ 插入基础数据失败: {e}")

async def create_default_admin_user(db):
    """创建默认管理员用户"""
    logger.info("👤 创建默认管理员用户...")

    try:
        # 使用新的用户服务创建管理员
        from app.services.user_service import user_service

        # 读取当前管理员密码配置
        admin_password = "admin123"  # 默认密码
        config_file = project_root / "config" / "admin_password.json"

        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    admin_password = config.get("password", "admin123")
                logger.info(f"✓ 从配置文件读取管理员密码")
            except Exception as e:
                logger.warning(f"⚠️ 读取密码配置失败，使用默认密码: {e}")

        # 使用用户服务创建管理员用户
        admin_user = await user_service.create_admin_user(
            username="admin",
            password=admin_password,
            email="admin@tradingagents.cn"
        )

        if admin_user:
            logger.info("✅ 创建管理员用户成功")
            logger.info(f"   用户名: admin")
            logger.info(f"   密码: {admin_password}")
            logger.info("   ⚠️  请在首次登录后立即修改密码！")
        else:
            logger.info("✓ 管理员用户已存在")

    except Exception as e:
        logger.error(f"❌ 创建管理员用户失败: {e}")

async def create_system_config(db):
    """创建系统配置"""
    logger.info("⚙️ 创建系统配置...")
    
    try:
        system_configs = [
            {
                "key": "system_version",
                "value": "v1.0.0-preview",
                "description": "系统版本号",
                "updated_at": datetime.utcnow()
            },
            {
                "key": "max_concurrent_tasks",
                "value": 3,
                "description": "最大并发分析任务数",
                "updated_at": datetime.utcnow()
            },
            {
                "key": "default_research_depth",
                "value": 2,
                "description": "默认分析深度",
                "updated_at": datetime.utcnow()
            },
            {
                "key": "enable_realtime_pe_pb",
                "value": True,
                "description": "启用实时PE/PB计算",
                "updated_at": datetime.utcnow()
            }
        ]
        
        for config in system_configs:
            db.system_config.replace_one(
                {"key": config["key"]},
                config,
                upsert=True
            )
        
        logger.info("✅ 系统配置创建完成")
        
    except Exception as e:
        logger.error(f"❌ 创建系统配置失败: {e}")

async def create_model_config(db):
    """创建模型配置"""
    logger.info("🤖 创建模型配置...")
    
    try:
        model_configs = [
            {
                "provider": "dashscope",
                "model_name": "qwen-plus-latest",
                "display_name": "通义千问 Plus",
                "enabled": True,
                "is_default": True,
                "config": {
                    "max_tokens": 8000,
                    "temperature": 0.7
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        for config in model_configs:
            db.model_config.replace_one(
                {"provider": config["provider"], "model_name": config["model_name"]},
                config,
                upsert=True
            )
        
        logger.info("✅ 模型配置创建完成")
        
    except Exception as e:
        logger.error(f"❌ 创建模型配置失败: {e}")

async def setup_admin_password():
    """设置管理员密码配置"""
    logger.info("🔐 设置管理员密码配置...")
    
    try:
        config_file = project_root / "config" / "admin_password.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果配置文件不存在，创建默认配置
        if not config_file.exists():
            default_config = {"password": "admin123"}
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            logger.info("✅ 创建默认管理员密码配置: admin123")
        else:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                current_password = config.get("password", "admin123")
            logger.info(f"✅ 当前管理员密码: {current_password}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 设置管理员密码配置失败: {e}")
        return False

async def create_env_file():
    """创建 .env 文件（如果不存在）"""
    logger.info("📄 检查 .env 文件...")
    
    try:
        env_file = project_root / ".env"
        env_example = project_root / ".env.example"
        
        if not env_file.exists() and env_example.exists():
            # 复制示例文件
            import shutil
            shutil.copy2(env_example, env_file)
            logger.info("✅ 从 .env.example 创建 .env 文件")
            logger.info("⚠️  请根据实际情况修改 .env 文件中的配置")
        elif env_file.exists():
            logger.info("✅ .env 文件已存在")
        else:
            logger.warning("⚠️ .env.example 文件不存在，无法创建 .env 文件")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建 .env 文件失败: {e}")
        return False

async def main():
    """主函数"""
    logger.info("🚀 开始 Docker 部署初始化...")
    logger.info("=" * 60)
    
    try:
        # 1. 检查 Docker 服务
        if not await check_docker_services():
            logger.error("❌ Docker 服务检查失败，请确保服务正常运行")
            return False
        
        # 2. 等待服务启动
        if not await wait_for_services():
            logger.error("❌ 服务启动失败")
            return False
        
        # 3. 创建 .env 文件
        await create_env_file()
        
        # 4. 设置管理员密码
        await setup_admin_password()
        
        # 5. 初始化数据库
        if not await init_mongodb():
            logger.error("❌ 数据库初始化失败")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Docker 部署初始化完成！")
        logger.info("=" * 60)
        logger.info("\n📋 系统信息:")
        logger.info("- 前端地址: http://localhost:80")
        logger.info("- 后端 API: http://localhost:8100")
        logger.info("- API 文档: http://localhost:8100/docs")
        
        # 读取当前管理员密码
        config_file = project_root / "config" / "admin_password.json"
        admin_password = "admin123"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    admin_password = config.get("password", "admin123")
            except:
                pass
        
        logger.info(f"\n🔐 登录信息:")
        logger.info(f"- 用户名: admin")
        logger.info(f"- 密码: {admin_password}")
        logger.info("\n⚠️  重要提醒:")
        logger.info("1. 请立即登录系统并修改管理员密码")
        logger.info("2. 配置必要的 API 密钥（如 DASHSCOPE_API_KEY）")
        logger.info("3. 根据需要配置数据源（如 TUSHARE_TOKEN）")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
