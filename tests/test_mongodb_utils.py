#!/usr/bin/env python3
"""
测试 MongoDB 工具函数
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.config.mongodb_utils import (
    build_mongodb_connection_string,
    get_mongodb_database_name,
    get_mongodb_config
)


def test_build_connection_string_from_env():
    """测试从环境变量构建连接字符串"""
    print("=" * 70)
    print("测试 1: 从环境变量构建连接字符串")
    print("=" * 70)
    
    # 设置环境变量
    os.environ['MONGODB_HOST'] = 'localhost'
    os.environ['MONGODB_PORT'] = '27017'
    os.environ['MONGODB_USERNAME'] = 'admin'
    os.environ['MONGODB_PASSWORD'] = 'password123'
    os.environ['MONGODB_DATABASE'] = 'testdb'
    os.environ['MONGODB_AUTH_SOURCE'] = 'admin'
    
    # 清除 MONGODB_CONNECTION_STRING（确保使用拼接逻辑）
    if 'MONGODB_CONNECTION_STRING' in os.environ:
        del os.environ['MONGODB_CONNECTION_STRING']
    
    conn_str = build_mongodb_connection_string()
    print(f"连接字符串: {conn_str}")
    
    expected = "mongodb://admin:password123@localhost:27017/testdb?authSource=admin"
    assert conn_str == expected, f"期望: {expected}, 实际: {conn_str}"
    print("✅ 测试通过")
    print()


def test_build_connection_string_from_env_var():
    """测试优先使用 MONGODB_CONNECTION_STRING 环境变量"""
    print("=" * 70)
    print("测试 2: 优先使用 MONGODB_CONNECTION_STRING 环境变量")
    print("=" * 70)
    
    # 设置 MONGODB_CONNECTION_STRING
    custom_conn_str = "mongodb://custom:password@custom-host:12345/customdb?authSource=admin"
    os.environ['MONGODB_CONNECTION_STRING'] = custom_conn_str
    
    conn_str = build_mongodb_connection_string()
    print(f"连接字符串: {conn_str}")
    
    assert conn_str == custom_conn_str, f"期望: {custom_conn_str}, 实际: {conn_str}"
    print("✅ 测试通过")
    print()


def test_get_database_name():
    """测试获取数据库名称"""
    print("=" * 70)
    print("测试 3: 获取数据库名称")
    print("=" * 70)
    
    # 测试 MONGODB_DATABASE_NAME 优先级
    os.environ['MONGODB_DATABASE_NAME'] = 'db_from_name'
    os.environ['MONGODB_DATABASE'] = 'db_from_database'
    
    db_name = get_mongodb_database_name()
    print(f"数据库名称: {db_name}")
    
    assert db_name == 'db_from_name', f"期望: db_from_name, 实际: {db_name}"
    print("✅ 测试通过 (MONGODB_DATABASE_NAME 优先)")
    
    # 测试 MONGODB_DATABASE 作为备选
    del os.environ['MONGODB_DATABASE_NAME']
    db_name = get_mongodb_database_name()
    print(f"数据库名称 (备选): {db_name}")
    
    assert db_name == 'db_from_database', f"期望: db_from_database, 实际: {db_name}"
    print("✅ 测试通过 (MONGODB_DATABASE 作为备选)")
    print()


def test_get_mongodb_config():
    """测试获取完整配置"""
    print("=" * 70)
    print("测试 4: 获取完整 MongoDB 配置")
    print("=" * 70)
    
    config = get_mongodb_config()
    print(f"配置: {config}")
    
    assert 'connection_string' in config
    assert 'database_name' in config
    assert 'auth_source' in config
    print("✅ 测试通过")
    print()


if __name__ == '__main__':
    try:
        test_build_connection_string_from_env()
        test_build_connection_string_from_env_var()
        test_get_database_name()
        test_get_mongodb_config()
        
        print("=" * 70)
        print("🎉 所有测试通过！")
        print("=" * 70)
    except AssertionError as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

