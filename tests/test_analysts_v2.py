import unittest
from unittest.mock import MagicMock, ANY
import json
from langchain_core.messages import AIMessage
from tradingagents.agents.analysts.policy_analyst import create_strategic_policy_analyst
from tradingagents.agents.analysts.international_news_analyst import create_index_news_analyst

class TestAnalystsV2(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_toolkit = MagicMock()
        
        # Mock bind_tools to return the LLM itself (or a chain that mimics it)
        self.mock_chain = MagicMock()
        
        # Default behavior
        default_response = AIMessage(content="Default Content")
        self.mock_chain.invoke.return_value = default_response
        self.mock_chain.return_value = default_response
        
        self.mock_llm.bind_tools.return_value = self.mock_chain
        
        # Base state
        self.state = {
            "messages": [],
            "index_info": {"name": "沪深300", "symbol": "000300"},
            "company_of_interest": "000300"
        }

    @classmethod
    def tearDownClass(cls):
        # 尝试关闭 MongoDB 连接以避免 ResourceWarning
        try:
            from tradingagents.config.config_manager import config_manager
            if hasattr(config_manager, 'mongodb_storage') and config_manager.mongodb_storage:
                if hasattr(config_manager.mongodb_storage, 'client') and config_manager.mongodb_storage.client:
                    config_manager.mongodb_storage.client.close()
        except Exception:
            pass

    def test_strategic_policy_analyst_structure(self):
        """验证战略政策分析师的结构和Prompt构建"""
        node_func = create_strategic_policy_analyst(self.mock_llm, self.mock_toolkit)
        
        expected_report = "这是一份关于长期战略政策的深度报告..."
        response = AIMessage(content=expected_report)
        
        # Explicitly set return values
        self.mock_chain.invoke.return_value = response
        self.mock_chain.return_value = response
        
        print(f"\n[Test Policy] Expected: {expected_report}")
        print(f"[Test Policy] Chain Invoke Return: {self.mock_chain.invoke.return_value.content}")
        
        result = node_func(self.state)
        
        print(f"[Test Policy] Actual: {result.get('policy_report')}")
        
        self.mock_llm.bind_tools.assert_called_once()
        tools_arg = self.mock_llm.bind_tools.call_args[0][0]
        tool_names = [t.name for t in tools_arg]
        self.assertIn("fetch_policy_news", tool_names)
        self.assertEqual(len(tool_names), 1)

        self.assertEqual(result["policy_report"], expected_report)

    def test_index_news_analyst_structure(self):
        """验证综合新闻分析师的结构和工具集成"""
        node_func = create_index_news_analyst(self.mock_llm, self.mock_toolkit)
        
        expected_report = "这是一份综合新闻简报..."
        response = AIMessage(content=expected_report)
        
        self.mock_chain.invoke.return_value = response
        self.mock_chain.return_value = response
        
        print(f"\n[Test News] Expected: {expected_report}")
        
        result = node_func(self.state)
        
        print(f"[Test News] Actual: {result.get('international_news_report')}")
        
        self.mock_llm.bind_tools.assert_called_once()
        tools_arg = self.mock_llm.bind_tools.call_args[0][0]
        tool_names = [t.name for t in tools_arg]
        
        expected_tools = [
            "fetch_bloomberg_news",
            "fetch_reuters_news",
            "fetch_google_news",
            "fetch_cn_international_news",
            "fetch_policy_news"
        ]
        
        for tool_name in expected_tools:
            self.assertIn(tool_name, tool_names)
            
        self.assertEqual(result["international_news_report"], expected_report)

    def test_policy_analyst_fallback(self):
        """验证政策分析师的降级逻辑"""
        node_func = create_strategic_policy_analyst(self.mock_llm, self.mock_toolkit)
        state = self.state.copy()
        state["policy_tool_call_count"] = 3
        
        result = node_func(state)
        
        # Should not invoke LLM
        # Note: Depending on implementation, bind_tools might still be called or not.
        # But invoke should NOT be called.
        # Check chain.invoke calls
        self.mock_chain.invoke.assert_not_called()
        
        report = json.loads(result["policy_report"])
        self.assertEqual(report["strategic_direction"], "数据获取受限")

    def test_news_analyst_fallback(self):
        """验证新闻分析师的降级逻辑"""
        node_func = create_index_news_analyst(self.mock_llm, self.mock_toolkit)
        state = self.state.copy()
        state["international_news_tool_call_count"] = 3
        
        result = node_func(state)
        
        self.mock_chain.invoke.assert_not_called()
        
        report = json.loads(result["international_news_report"])
        self.assertIn("数据获取受限", report["overall_impact"])

if __name__ == "__main__":
    unittest.main()
