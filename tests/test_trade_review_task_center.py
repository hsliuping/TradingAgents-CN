"""
测试交易复盘任务中心集成

测试目标：
1. 验证 UnifiedAnalysisService 的交易复盘方法
2. 验证任务创建和执行流程
3. 验证任务状态更新
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.services.unified_analysis_service import get_unified_analysis_service
from app.models.review import CreateTradeReviewRequest, ReviewType
from app.models.analysis import AnalysisStatus


@pytest.mark.asyncio
async def test_create_trade_review_task():
    """测试创建交易复盘任务"""
    
    # 准备测试数据
    user_id = "test_user_123"
    request = CreateTradeReviewRequest(
        trade_ids=["trade_1", "trade_2"],
        review_type=ReviewType.COMPLETE_TRADE,
        code="688111",
        source="paper",
        use_workflow=True
    )
    
    # 获取服务实例
    service = get_unified_analysis_service()
    
    # Mock 数据库操作
    with patch('app.core.database.get_mongo_db') as mock_db:
        mock_collection = AsyncMock()
        mock_db.return_value.unified_analysis_tasks = mock_collection
        
        # Mock 内存状态管理器
        with patch('app.services.unified_analysis_service.get_memory_state_manager') as mock_memory:
            mock_memory_instance = AsyncMock()
            mock_memory.return_value = mock_memory_instance
            
            # 执行测试
            result = await service.create_trade_review_task(
                user_id=user_id,
                request=request
            )
            
            # 验证结果
            assert "task_id" in result
            assert result["status"] == AnalysisStatus.PENDING.value
            assert "created_at" in result
            assert "message" in result
            
            # 验证数据库调用
            assert mock_collection.insert_one.called
            
            # 验证内存状态管理器调用
            assert mock_memory_instance.create_task.called
            
            print(f"✅ 测试通过：创建交易复盘任务成功")
            print(f"   - task_id: {result['task_id']}")
            print(f"   - status: {result['status']}")


@pytest.mark.asyncio
async def test_execute_trade_review():
    """测试执行交易复盘任务"""
    
    # 准备测试数据
    task_id = "test_task_123"
    user_id = "test_user_123"
    request = CreateTradeReviewRequest(
        trade_ids=["trade_1", "trade_2"],
        review_type=ReviewType.COMPLETE_TRADE,
        code="688111",
        source="paper",
        use_workflow=True
    )
    
    # 获取服务实例
    service = get_unified_analysis_service()
    
    # Mock TradeReviewService
    with patch('app.services.unified_analysis_service.get_trade_review_service') as mock_service:
        # Mock 复盘结果
        mock_report = Mock()
        mock_report.review_id = "review_123"
        mock_report.trade_info = Mock()
        mock_report.trade_info.code = "688111"
        mock_report.trade_info.name = "思瑞浦"
        mock_report.trade_info.model_dump = Mock(return_value={"code": "688111", "name": "思瑞浦"})
        mock_report.ai_review = Mock()
        mock_report.ai_review.model_dump = Mock(return_value={"score": 85})
        mock_report.market_snapshot = None
        mock_report.status = Mock()
        mock_report.status.value = "completed"
        mock_report.execution_time = 45.2
        
        mock_service_instance = AsyncMock()
        mock_service_instance.create_trade_review = AsyncMock(return_value=mock_report)
        mock_service.return_value = mock_service_instance
        
        # Mock 数据库操作
        with patch('app.core.database.get_mongo_db') as mock_db:
            mock_collection = AsyncMock()
            mock_db.return_value.unified_analysis_tasks = mock_collection
            
            # Mock 内存状态管理器
            with patch('app.services.unified_analysis_service.get_memory_state_manager') as mock_memory:
                mock_memory_instance = AsyncMock()
                mock_memory.return_value = mock_memory_instance
                
                # 执行测试
                result = await service.execute_trade_review(
                    task_id=task_id,
                    user_id=user_id,
                    request=request
                )
                
                # 验证结果
                assert result["success"] is True
                assert result["task_id"] == task_id
                assert result["review_id"] == "review_123"
                assert result["code"] == "688111"
                assert result["name"] == "思瑞浦"
                
                # 验证 TradeReviewService 被调用
                assert mock_service_instance.create_trade_review.called
                
                # 验证任务状态更新
                assert mock_collection.update_one.called
                
                print(f"✅ 测试通过：执行交易复盘任务成功")
                print(f"   - task_id: {result['task_id']}")
                print(f"   - review_id: {result['review_id']}")
                print(f"   - code: {result['code']}")


if __name__ == "__main__":
    print("🧪 开始测试交易复盘任务中心集成...")
    asyncio.run(test_create_trade_review_task())
    asyncio.run(test_execute_trade_review())
    print("✅ 所有测试通过！")

