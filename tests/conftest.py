import os
import sys
import pytest
import asyncio

# 将项目根目录加入 sys.path，确保 `import tradingagents` 可用
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """自动清理测试数据"""
    yield
    # 测试后清理
    try:
        from app.services.user_service import user_service
        # 清理所有test开头的用户
        user_service.users_collection.delete_many({
            "username": {"$regex": "^test|^register|^login"}
        })
        # 清理测试邮箱
        user_service.users_collection.delete_many({
            "email": {"$regex": "@example.com$"}
        })
    except:
        pass

