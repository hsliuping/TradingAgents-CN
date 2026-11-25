"""
测试 Agent 插件架构

验证 AnalystRegistry 和 ReportAggregator 的功能
"""

import pytest


class TestAnalystRegistry:
    """测试分析师注册表"""
    
    def test_registry_singleton(self):
        """测试注册表单例模式"""
        from core.agents.analyst_registry import get_analyst_registry
        
        registry1 = get_analyst_registry()
        registry2 = get_analyst_registry()
        
        assert registry1 is registry2
    
    def test_builtin_analysts_loaded(self):
        """测试内置分析师元数据已加载"""
        from core.agents.analyst_registry import get_analyst_registry
        
        registry = get_analyst_registry()
        
        # 检查内置分析师
        assert "market_analyst" in registry.list_all()
        assert "news_analyst" in registry.list_all()
        assert "social_analyst" in registry.list_all()
        assert "fundamentals_analyst" in registry.list_all()
        assert "sector_analyst" in registry.list_all()
        assert "index_analyst" in registry.list_all()
    
    def test_extension_analysts_registered(self):
        """测试扩展分析师已注册"""
        # 触发模块加载（这会自动注册扩展分析师）
        from core.agents.adapters import SectorAnalystAgent, IndexAnalystAgent
        from core.agents.analyst_registry import get_analyst_registry
        
        registry = get_analyst_registry()
        
        # 检查扩展分析师是否已注册实现
        assert registry.is_registered("sector_analyst")
        assert registry.is_registered("index_analyst")
    
    def test_get_analyst_metadata(self):
        """测试获取分析师元数据"""
        from core.agents.analyst_registry import get_analyst_registry
        
        registry = get_analyst_registry()
        
        # 获取板块分析师元数据
        sector_meta = registry.get_analyst_metadata("sector_analyst")
        assert sector_meta is not None
        assert sector_meta.output_field == "sector_report"
        assert sector_meta.requires_tools == False
        
        # 获取大盘分析师元数据
        index_meta = registry.get_analyst_metadata("index_analyst")
        assert index_meta is not None
        assert index_meta.output_field == "index_report"
        assert index_meta.requires_tools == False
    
    def test_get_output_fields(self):
        """测试获取所有输出字段"""
        from core.agents.analyst_registry import get_analyst_registry
        
        registry = get_analyst_registry()
        
        output_fields = registry.get_output_fields()
        
        # 检查输出字段映射
        assert "sector_analyst" in output_fields
        assert output_fields["sector_analyst"] == "sector_report"
        assert "index_analyst" in output_fields
        assert output_fields["index_analyst"] == "index_report"


class TestReportAggregator:
    """测试报告聚合器"""
    
    def test_aggregate_reports(self):
        """测试聚合报告"""
        from core.utils.report_aggregator import get_all_reports
        
        # 模拟 state
        state = {
            "market_report": "市场分析报告内容",
            "sentiment_report": "情绪分析报告内容",
            "news_report": "新闻分析报告内容",
            "fundamentals_report": "基本面分析报告内容",
            "sector_report": "板块分析报告内容",
            "index_report": "大盘分析报告内容",
        }
        
        reports = get_all_reports(state)
        
        # 检查报告数量
        assert len(reports) == 6
        
        # 检查报告内容
        assert reports.get("sector_report") == "板块分析报告内容"
        assert reports.get("index_report") == "大盘分析报告内容"
    
    def test_to_text(self):
        """测试转换为文本"""
        from core.utils.report_aggregator import get_all_reports
        
        state = {
            "index_report": "大盘报告",
            "sector_report": "板块报告",
            "market_report": "市场报告",
        }
        
        reports = get_all_reports(state)
        text = reports.to_text()
        
        # 检查文本包含所有报告
        assert "大盘报告" in text
        assert "板块报告" in text
        assert "市场报告" in text
    
    def test_empty_reports(self):
        """测试空报告处理"""
        from core.utils.report_aggregator import get_all_reports
        
        state = {}
        
        reports = get_all_reports(state)
        
        # 空状态应返回空报告
        assert len(reports) == 0
        assert reports.to_text() == ""


class TestPluginArchitectureIntegration:
    """测试插件架构集成"""
    
    def test_extension_analyst_in_workflow(self):
        """测试扩展分析师可被工作流加载"""
        # 触发模块加载
        from core.agents.adapters import SectorAnalystAgent, IndexAnalystAgent
        from core.agents.analyst_registry import get_analyst_registry
        
        registry = get_analyst_registry()
        
        # 获取板块分析师类
        sector_class = registry.get_analyst_class("sector_analyst")
        assert sector_class is SectorAnalystAgent
        
        # 获取大盘分析师类
        index_class = registry.get_analyst_class("index_analyst")
        assert index_class is IndexAnalystAgent

