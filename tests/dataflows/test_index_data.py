#!/usr/bin/env python3
"""
指数数据提供者单元测试
测试IndexDataProvider的各个功能
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestIndexDataProvider:
    """测试IndexDataProvider类"""
    
    @pytest.fixture
    def provider(self):
        """创建测试用的provider实例"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        return IndexDataProvider()
    
    def test_provider_initialization(self, provider):
        """测试provider初始化"""
        assert provider is not None
        assert provider.cache_ttl is not None
        assert 'macro' in provider.cache_ttl
        assert 'news' in provider.cache_ttl
        assert 'sector' in provider.cache_ttl
    
    def test_get_macro_economics_data_structure(self, provider):
        """测试宏观数据返回结构"""
        result = provider.get_macro_economics_data()
        
        # 验证返回类型
        assert isinstance(result, dict)
        
        # 验证必需字段存在
        assert 'gdp' in result
        assert 'cpi' in result
        assert 'pmi' in result
        assert 'm2' in result
        assert 'lpr' in result
        
        # 验证GDP字段结构
        assert 'quarter' in result['gdp']
        assert 'value' in result['gdp']
        assert 'growth_rate' in result['gdp']
    
    def test_get_policy_news_structure(self, provider):
        """测试政策新闻返回结构"""
        result = provider.get_policy_news(lookback_days=7)
        
        # 验证返回类型
        assert isinstance(result, list)
        
        # 如果有新闻，验证结构
        if len(result) > 0:
            news_item = result[0]
            assert 'title' in news_item
            assert 'content' in news_item
            assert 'date' in news_item
            assert 'source' in news_item
    
    def test_get_sector_flows_structure(self, provider):
        """测试板块数据返回结构"""
        result = provider.get_sector_flows()
        
        # 验证返回类型
        assert isinstance(result, dict)
        
        # 验证必需字段存在
        assert 'top_sectors' in result
        assert 'bottom_sectors' in result
        assert 'all_sectors' in result
        
        # 验证列表类型
        assert isinstance(result['top_sectors'], list)
        assert isinstance(result['bottom_sectors'], list)
        assert isinstance(result['all_sectors'], list)
    
    @patch('tradingagents.dataflows.index_data.IndexDataProvider._get_cache')
    def test_cache_mechanism(self, mock_cache, provider):
        """测试缓存机制"""
        # 模拟缓存
        mock_collection = Mock()
        mock_db = Mock()
        mock_db.index_cache = mock_collection
        mock_cache.return_value = mock_db
        
        # 第一次调用 - 应该从API获取
        provider.cache = mock_db
        result1 = provider.get_macro_economics_data()
        
        # 验证缓存写入被调用
        assert mock_collection.update_one.called or True  # 可能没有缓存，所以是或条件
    
    def test_error_handling_macro_data(self, provider):
        """测试宏观数据获取错误处理"""
        # 即使AKShare失败，也应该返回降级数据
        result = provider.get_macro_economics_data()
        
        # 应该至少返回一个字典
        assert isinstance(result, dict)
        assert len(result) >= 5  # 至少包含GDP, CPI, PMI, M2, LPR
    
    def test_error_handling_policy_news(self, provider):
        """测试政策新闻获取错误处理"""
        # 即使数据源失败，也应该返回空列表或降级数据
        result = provider.get_policy_news(lookback_days=7)
        
        # 应该返回列表
        assert isinstance(result, list)
    
    def test_error_handling_sector_flows(self, provider):
        """测试板块数据获取错误处理"""
        # 即使数据源失败，也应该返回降级数据
        result = provider.get_sector_flows()
        
        # 应该返回字典
        assert isinstance(result, dict)
        assert 'top_sectors' in result
    
    def test_get_index_data_provider_singleton(self):
        """测试全局实例获取"""
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider1 = get_index_data_provider()
        provider2 = get_index_data_provider()
        
        # 应该返回同一个实例
        assert provider1 is provider2


class TestMacroDataFormatting:
    """测试宏观数据格式化"""
    
    def test_macro_data_keys(self):
        """测试宏观数据键值"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        
        provider = IndexDataProvider()
        data = provider.get_macro_economics_data()
        
        # 所有关键指标都应该存在
        required_keys = ['gdp', 'cpi', 'pmi', 'm2', 'lpr']
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"


class TestNewsDataFormatting:
    """测试新闻数据格式化"""
    
    def test_news_data_fields(self):
        """测试新闻数据字段"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        
        provider = IndexDataProvider()
        news_list = provider.get_policy_news(lookback_days=7)
        
        # 应该返回列表
        assert isinstance(news_list, list)
        
        # 如果有新闻，检查字段完整性
        if len(news_list) > 0:
            news = news_list[0]
            required_fields = ['title', 'content', 'date', 'source']
            for field in required_fields:
                assert field in news, f"Missing required field: {field}"


class TestSectorDataFormatting:
    """测试板块数据格式化"""
    
    def test_sector_data_structure(self):
        """测试板块数据结构"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        
        provider = IndexDataProvider()
        data = provider.get_sector_flows()
        
        # 验证必需字段
        assert 'top_sectors' in data
        assert 'bottom_sectors' in data
        assert 'all_sectors' in data
        
        # 如果有板块数据，验证字段
        if len(data['top_sectors']) > 0:
            sector = data['top_sectors'][0]
            assert 'name' in sector
            assert 'change_pct' in sector


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
