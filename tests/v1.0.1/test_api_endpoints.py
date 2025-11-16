"""
提示词模板系统API端点测试
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    return TestClient(app)


def test_create_template(client):
    """测试创建模板API"""
    payload = {
        "agent_type": "analysts",
        "agent_name": "market_analyst",
        "template_name": "Test Template",
        "preference_type": "neutral",
        "content": {
            "system_prompt": "Test prompt",
            "tool_guidance": "Test tools",
            "analysis_requirements": "Test analysis"
        },
        "status": "draft"
    }
    
    response = client.post("/api/v1/templates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "id" in data["data"]


def test_get_template(client):
    """测试获取模板API"""
    # 先创建一个模板
    payload = {
        "agent_type": "analysts",
        "agent_name": "market_analyst",
        "template_name": "Test Template",
        "preference_type": "neutral",
        "content": {
            "system_prompt": "Test prompt",
            "tool_guidance": "Test tools",
            "analysis_requirements": "Test analysis"
        },
        "status": "draft"
    }
    
    create_response = client.post("/api/v1/templates", json=payload)
    template_id = create_response.json()["data"]["id"]
    
    # 获取模板
    response = client.get(f"/api/v1/templates/{template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["id"] == template_id


def test_create_preference(client):
    """测试创建偏好API"""
    payload = {
        "preference_type": "aggressive",
        "risk_level": 0.8,
        "confidence_threshold": 0.6,
        "position_size_multiplier": 1.5,
        "decision_speed": "fast"
    }
    
    response = client.post(
        "/api/v1/preferences?user_id=test_user",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "id" in data["data"]


def test_get_user_preferences(client):
    """测试获取用户偏好API"""
    # 先创建一个偏好
    payload = {
        "preference_type": "neutral",
        "risk_level": 0.5,
        "confidence_threshold": 0.6,
        "position_size_multiplier": 1.0,
        "decision_speed": "normal"
    }
    
    client.post(
        "/api/v1/preferences?user_id=test_user_list",
        json=payload
    )
    
    # 获取用户偏好列表
    response = client.get("/api/v1/preferences?user_id=test_user_list")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"]["preferences"], list)


def test_get_agent_templates(client):
    """测试获取Agent模板API"""
    response = client.get(
        "/api/v1/templates/agent/analysts/market_analyst"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "templates" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

