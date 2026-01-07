"""
测试定时分析配置的测试执行端点

测试场景：
1. 测试执行成功
2. 配置不存在
3. 没有启用的时间段
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from datetime import datetime

from app.routers.scheduled_analysis import test_config
from app.core.database import get_mongo_db


@pytest.fixture
def mock_user():
    """模拟用户"""
    return {
        "id": "507f1f77bcf86cd799439011",
        "username": "testuser"
    }


@pytest.fixture
def mock_config():
    """模拟配置"""
    return {
        "_id": ObjectId("507f1f77bcf86cd799439012"),
        "user_id": "507f1f77bcf86cd799439011",
        "name": "测试配置",
        "enabled": True,
        "time_slots": [
            {
                "name": "开盘前",
                "cron_expression": "0 9 * * 1-5",
                "enabled": True,
                "group_ids": ["group1", "group2"]
            },
            {
                "name": "收盘后",
                "cron_expression": "30 15 * * 1-5",
                "enabled": False,
                "group_ids": ["group3"]
            }
        ]
    }


@pytest.mark.asyncio
async def test_test_config_success(mock_user, mock_config):
    """测试成功执行"""
    
    # Mock 数据库
    mock_db = MagicMock()
    mock_db.scheduled_analysis_configs.find_one = AsyncMock(return_value=mock_config)
    
    with patch('app.routers.scheduled_analysis.get_mongo_db', return_value=mock_db):
        with patch('app.routers.scheduled_analysis.asyncio.create_task') as mock_create_task:
            # 调用测试端点
            result = await test_config(
                config_id="507f1f77bcf86cd799439012",
                user=mock_user
            )
            
            # 验证响应
            assert result["success"] is True
            assert "测试任务已启动" in result["data"]["message"]
            assert result["data"]["slot_index"] == 0
            assert result["data"]["slot_name"] == "开盘前"
            
            # 验证异步任务被创建
            mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_test_config_not_found(mock_user):
    """测试配置不存在"""
    
    # Mock 数据库
    mock_db = MagicMock()
    mock_db.scheduled_analysis_configs.find_one = AsyncMock(return_value=None)
    
    with patch('app.routers.scheduled_analysis.get_mongo_db', return_value=mock_db):
        # 调用测试端点
        result = await test_config(
            config_id="507f1f77bcf86cd799439012",
            user=mock_user
        )
        
        # 验证响应
        assert result["success"] is False
        assert "配置不存在" in result["message"]


@pytest.mark.asyncio
async def test_test_config_no_enabled_slots(mock_user):
    """测试没有启用的时间段"""
    
    # Mock 配置（所有时间段都禁用）
    mock_config = {
        "_id": ObjectId("507f1f77bcf86cd799439012"),
        "user_id": "507f1f77bcf86cd799439011",
        "name": "测试配置",
        "enabled": True,
        "time_slots": [
            {
                "name": "开盘前",
                "cron_expression": "0 9 * * 1-5",
                "enabled": False,
                "group_ids": ["group1"]
            }
        ]
    }
    
    # Mock 数据库
    mock_db = MagicMock()
    mock_db.scheduled_analysis_configs.find_one = AsyncMock(return_value=mock_config)
    
    with patch('app.routers.scheduled_analysis.get_mongo_db', return_value=mock_db):
        # 调用测试端点
        result = await test_config(
            config_id="507f1f77bcf86cd799439012",
            user=mock_user
        )
        
        # 验证响应
        assert result["success"] is False
        assert "没有启用的时间段" in result["message"]


@pytest.mark.asyncio
async def test_test_config_invalid_id(mock_user):
    """测试无效的配置ID"""
    
    # 调用测试端点
    result = await test_config(
        config_id="invalid_id",
        user=mock_user
    )
    
    # 验证响应
    assert result["success"] is False
    assert "无效的配置ID" in result["message"]


@pytest.mark.asyncio
async def test_test_config_second_slot_enabled(mock_user):
    """测试第二个时间段启用的情况"""
    
    # Mock 配置（第一个时间段禁用，第二个启用）
    mock_config = {
        "_id": ObjectId("507f1f77bcf86cd799439012"),
        "user_id": "507f1f77bcf86cd799439011",
        "name": "测试配置",
        "enabled": True,
        "time_slots": [
            {
                "name": "开盘前",
                "cron_expression": "0 9 * * 1-5",
                "enabled": False,
                "group_ids": ["group1"]
            },
            {
                "name": "收盘后",
                "cron_expression": "30 15 * * 1-5",
                "enabled": True,
                "group_ids": ["group2"]
            }
        ]
    }
    
    # Mock 数据库
    mock_db = MagicMock()
    mock_db.scheduled_analysis_configs.find_one = AsyncMock(return_value=mock_config)
    
    with patch('app.routers.scheduled_analysis.get_mongo_db', return_value=mock_db):
        with patch('app.routers.scheduled_analysis.asyncio.create_task') as mock_create_task:
            # 调用测试端点
            result = await test_config(
                config_id="507f1f77bcf86cd799439012",
                user=mock_user
            )
            
            # 验证响应
            assert result["success"] is True
            assert result["data"]["slot_index"] == 1  # 第二个时间段
            assert result["data"]["slot_name"] == "收盘后"

