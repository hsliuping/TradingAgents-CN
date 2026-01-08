#!/usr/bin/env python3
"""
MongoDB 连接字符串工具函数
统一管理 MongoDB 连接字符串的构建逻辑
"""

import os
from typing import Optional


def build_mongodb_connection_string(
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    auth_source: Optional[str] = None
) -> str:
    """
    构建 MongoDB 连接字符串
    
    优先级:
    1. 如果设置了 MONGODB_CONNECTION_STRING 环境变量，直接使用
    2. 如果传入了参数，使用传入的参数
    3. 否则从环境变量读取 MONGODB_HOST, MONGODB_PORT 等
    
    Args:
        host: MongoDB 主机地址
        port: MongoDB 端口
        username: 用户名
        password: 密码
        database: 数据库名称
        auth_source: 认证数据库
    
    Returns:
        str: MongoDB 连接字符串
        
    Examples:
        >>> # 使用环境变量
        >>> conn_str = build_mongodb_connection_string()
        
        >>> # 使用自定义参数
        >>> conn_str = build_mongodb_connection_string(
        ...     host='localhost',
        ...     port=27017,
        ...     username='admin',
        ...     password='password123'
        ... )
    """
    # 优先使用 MONGODB_CONNECTION_STRING 环境变量
    env_conn_str = os.getenv('MONGODB_CONNECTION_STRING')
    if env_conn_str:
        return env_conn_str
    
    # 从参数或环境变量获取配置
    host = host or os.getenv('MONGODB_HOST', 'localhost')
    port = port or int(os.getenv('MONGODB_PORT', '27017'))
    username = username or os.getenv('MONGODB_USERNAME', '')
    password = password or os.getenv('MONGODB_PASSWORD', '')
    database = database or os.getenv('MONGODB_DATABASE', 'tradingagents')
    auth_source = auth_source or os.getenv('MONGODB_AUTH_SOURCE', 'admin')
    
    # 构建连接字符串
    if username and password:
        # 带认证的连接字符串
        connection_string = f"mongodb://{username}:{password}@{host}:{port}/"
        # 添加 authSource 参数
        if database:
            connection_string += f"{database}?authSource={auth_source}"
        else:
            connection_string += f"?authSource={auth_source}"
    else:
        # 不带认证的连接字符串
        connection_string = f"mongodb://{host}:{port}/"
        if database:
            connection_string += database
    
    return connection_string


def get_mongodb_database_name() -> str:
    """
    获取 MongoDB 数据库名称
    
    优先级:
    1. MONGODB_DATABASE_NAME 环境变量
    2. MONGODB_DATABASE 环境变量
    3. 默认值 'tradingagents'
    
    Returns:
        str: 数据库名称
    """
    return os.getenv('MONGODB_DATABASE_NAME') or os.getenv('MONGODB_DATABASE', 'tradingagents')


def get_mongodb_config() -> dict:
    """
    获取完整的 MongoDB 配置

    Returns:
        dict: 包含 connection_string 和 database_name 的字典
    """
    return {
        'connection_string': build_mongodb_connection_string(),
        'database_name': get_mongodb_database_name(),
        'auth_source': os.getenv('MONGODB_AUTH_SOURCE', 'admin')
    }


def build_redis_connection_string(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    db: Optional[int] = None
) -> str:
    """
    构建 Redis 连接字符串

    优先级:
    1. 如果设置了 REDIS_URL 环境变量，直接使用
    2. 如果传入了参数，使用传入的参数
    3. 否则从环境变量读取 REDIS_HOST, REDIS_PORT 等

    Args:
        host: Redis 主机地址
        port: Redis 端口
        password: 密码
        db: 数据库编号

    Returns:
        str: Redis 连接字符串

    Examples:
        >>> # 使用环境变量
        >>> conn_str = build_redis_connection_string()

        >>> # 使用自定义参数
        >>> conn_str = build_redis_connection_string(
        ...     host='localhost',
        ...     port=6379,
        ...     password='password123',
        ...     db=0
        ... )
    """
    # 优先使用 REDIS_URL 环境变量
    env_conn_str = os.getenv('REDIS_URL')
    if env_conn_str:
        return env_conn_str

    # 从参数或环境变量获取配置
    host = host or os.getenv('REDIS_HOST', 'localhost')
    port = port or int(os.getenv('REDIS_PORT', '6379'))
    password = password or os.getenv('REDIS_PASSWORD', '')
    db = db if db is not None else int(os.getenv('REDIS_DB', '0'))

    # 构建连接字符串
    if password:
        # 带密码的连接字符串
        connection_string = f"redis://:{password}@{host}:{port}/{db}"
    else:
        # 不带密码的连接字符串
        connection_string = f"redis://{host}:{port}/{db}"

    return connection_string

