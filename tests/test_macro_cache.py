import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import asyncio
from tradingagents.tools.index_tools import fetch_macro_data

class TestMacroCache(unittest.IsolatedAsyncioTestCase):
    
    @patch('tradingagents.config.database_manager.get_database_manager')
    @patch('tradingagents.tools.index_tools.get_index_data_provider')
    async def test_cache_miss_and_write(self, mock_get_provider, mock_get_db_manager):
        """测试缓存未命中，执行获取并写入"""
        # Setup DB Mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.find_one.return_value = None  # Cache miss
        
        mock_manager = MagicMock()
        mock_manager.get_mongodb_db.return_value = mock_db
        mock_get_db_manager.return_value = mock_manager
        
        # Setup Provider Mock
        mock_provider = MagicMock()
        mock_data = {"gdp": {"value": 100}}
        # Async mock for get_macro_data
        future = asyncio.Future()
        future.set_result(mock_data)
        mock_provider.get_macro_data.return_value = future
        mock_get_provider.return_value = mock_provider
        
        # Execute
        result = await fetch_macro_data.ainvoke({}) # Tool invoke
        
        # Verify
        # 1. Check DB query
        mock_collection.find_one.assert_called_once()
        # 2. Check Provider call
        mock_provider.get_macro_data.assert_called_once()
        # 3. Check DB write
        mock_collection.replace_one.assert_called_once()
        self.assertIn("宏观经济指标数据", result)

    @patch('tradingagents.config.database_manager.get_database_manager')
    @patch('tradingagents.tools.index_tools.get_index_data_provider')
    async def test_cache_hit(self, mock_get_provider, mock_get_db_manager):
        """测试缓存命中"""
        # Setup DB Mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        
        # Cache hit with valid timestamp
        cached_report = "Mock Cached Report"
        mock_collection.find_one.return_value = {
            "report": cached_report,
            "timestamp": datetime.now()
        }
        
        mock_manager = MagicMock()
        mock_manager.get_mongodb_db.return_value = mock_db
        mock_get_db_manager.return_value = mock_manager
        
        # Execute
        result = await fetch_macro_data.ainvoke({})
        
        # Verify
        # 1. Check DB query
        mock_collection.find_one.assert_called_once()
        # 2. Provider should NOT be called
        mock_get_provider.assert_not_called()
        # 3. Result should be from cache
        self.assertEqual(result, cached_report)

    @patch('tradingagents.config.database_manager.get_database_manager')
    @patch('tradingagents.tools.index_tools.get_index_data_provider')
    async def test_cache_expired(self, mock_get_provider, mock_get_db_manager):
        """测试缓存过期"""
        # Setup DB Mock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        
        # Cache expired (8 days ago)
        mock_collection.find_one.return_value = {
            "report": "Old Report",
            "timestamp": datetime.now() - timedelta(days=8)
        }
        
        mock_manager = MagicMock()
        mock_manager.get_mongodb_db.return_value = mock_db
        mock_get_db_manager.return_value = mock_manager
        
        # Setup Provider Mock
        mock_provider = MagicMock()
        mock_data = {"gdp": {"value": 200}}
        future = asyncio.Future()
        future.set_result(mock_data)
        mock_provider.get_macro_data.return_value = future
        mock_get_provider.return_value = mock_provider
        
        # Execute
        result = await fetch_macro_data.ainvoke({})
        
        # Verify
        # 1. Check DB query
        mock_collection.find_one.assert_called_once()
        # 2. Provider SHOULD be called
        mock_provider.get_macro_data.assert_called_once()
        # 3. DB write should happen (update)
        mock_collection.replace_one.assert_called_once()

    @patch('tradingagents.config.database_manager.get_database_manager')
    @patch('tradingagents.tools.index_tools.get_index_data_provider')
    async def test_db_failure_fallback(self, mock_get_provider, mock_get_db_manager):
        """测试数据库故障降级"""
        # Setup DB Mock to raise exception
        mock_manager = MagicMock()
        mock_manager.get_mongodb_db.side_effect = Exception("DB Connection Failed")
        mock_get_db_manager.return_value = mock_manager
        
        # Setup Provider Mock
        mock_provider = MagicMock()
        mock_data = {"gdp": {"value": 300}}
        future = asyncio.Future()
        future.set_result(mock_data)
        mock_provider.get_macro_data.return_value = future
        mock_get_provider.return_value = mock_provider
        
        # Execute
        result = await fetch_macro_data.ainvoke({})
        
        # Verify
        # 1. Provider SHOULD be called despite DB error
        mock_provider.get_macro_data.assert_called_once()
        self.assertIn("宏观经济指标数据", result)

if __name__ == '__main__':
    unittest.main()
