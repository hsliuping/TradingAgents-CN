"""
保留同步历史的数据库级探索测试入口。

这类测试需要真实数据库与同步服务，不适合进入默认单元测试套件。
"""

import pytest


pytestmark = pytest.mark.integration


def test_sync_history_db_integration_placeholder() -> None:
    pytest.skip("需要真实 MongoDB 与多源同步服务，默认跳过数据库级集成测试")
