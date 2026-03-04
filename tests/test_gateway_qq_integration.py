"""
Gateway QQ Bot 集成测试

测试场景：
1. op=13 回调地址验证（ed25519 签名）
2. C2C 单聊消息解析 + QQ ACK
3. 群聊 @Bot 消息解析 + QQ ACK
4. /help 命令处理
5. /bind 命令 → 生成绑定码
6. 已绑定用户消息 → 调用助理 → 被动回复
7. 未绑定用户 → 发送引导消息
8. 未知平台 → 400 错误
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch

from core.gateway.adapters.qq import QQAdapter
from core.gateway.models import ChannelType, GatewayMessage, GatewayResponse, MessageType
from core.gateway.router import GatewayRouter


def run(coro):
    """兼容 Python 3.10+ 的 async 运行器"""
    return asyncio.run(coro)


# ------------------------------------------------------------------ #
# 辅助
# ------------------------------------------------------------------ #

TEST_QQ_CONFIG = {
    "app_id": "test_app_id_123",
    "app_secret": "test_client_secret",
    "bot_secret": "test_bot_secret_for_ed25519",
}


def _make_qq_event(event_type: str, data: dict, op: int = 0) -> bytes:
    return json.dumps({"op": op, "t": event_type, "d": data}).encode()


def _make_c2c_body(content: str, user_openid: str = "user_openid_abc", msg_id: str = "msg_001") -> bytes:
    return _make_qq_event("C2C_MESSAGE_CREATE", {
        "id": msg_id,
        "author": {"user_openid": user_openid},
        "content": content,
    })


def _make_group_body(
    content: str, group_openid: str = "group_123", member_openid: str = "member_456", msg_id: str = "msg_002"
) -> bytes:
    return _make_qq_event("GROUP_AT_MESSAGE_CREATE", {
        "id": msg_id,
        "group_openid": group_openid,
        "author": {"member_openid": member_openid},
        "content": content,
    })


HEADERS_OK = {"x-bot-appid": "test_app_id_123"}


# ------------------------------------------------------------------ #
# 测试 QQAdapter 单元
# ------------------------------------------------------------------ #

def test_ed25519_validation():
    """op=13 回调地址验证：应返回 plain_token + hex 签名"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    payload = json.dumps({
        "op": 13,
        "d": {"plain_token": "hello_token", "event_ts": "1700000000"},
    }).encode()

    ok, result = run(
        adapter.verify_request({}, payload)
    )
    assert ok is True
    assert result is not None
    assert result["plain_token"] == "hello_token"
    assert isinstance(result["signature"], str)
    assert len(result["signature"]) == 128  # ed25519 sig = 64 bytes -> 128 hex chars
    print("✅ test_ed25519_validation passed")


def test_verify_normal_event():
    """普通 op=0 事件，通过 x-bot-appid 验证"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    body = _make_c2c_body("hello")
    ok, result = run(
        adapter.verify_request(HEADERS_OK, body)
    )
    assert ok is True
    assert result is None
    print("✅ test_verify_normal_event passed")


def test_verify_bad_appid():
    """x-bot-appid 不匹配 → 验证失败"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    body = _make_c2c_body("hello")
    ok, _ = run(
        adapter.verify_request({"x-bot-appid": "wrong_id"}, body)
    )
    assert ok is False
    print("✅ test_verify_bad_appid passed")


def test_parse_c2c_message():
    """解析 C2C 单聊消息"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    body = _make_c2c_body("分析贵州茅台", user_openid="u_001", msg_id="m_100")
    msg = run(
        adapter.parse_message(HEADERS_OK, body)
    )
    assert msg is not None
    assert msg.channel_type == "qq"
    assert msg.channel_id == "c2c:u_001"
    assert msg.user_identity == "u_001"
    assert msg.content == "分析贵州茅台"
    assert msg.message_type == "text"
    assert msg.metadata["msg_id"] == "m_100"
    assert msg.metadata["scene"] == "c2c"
    print("✅ test_parse_c2c_message passed")


def test_parse_group_message():
    """解析群聊 @Bot 消息"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    body = _make_group_body("/help", group_openid="g_01", member_openid="m_02")
    msg = run(
        adapter.parse_message(HEADERS_OK, body)
    )
    assert msg is not None
    assert msg.channel_id == "group:g_01"
    assert msg.user_identity == "m_02"
    assert msg.content == "/help"
    assert msg.message_type == "command"
    assert msg.metadata["scene"] == "group"
    print("✅ test_parse_group_message passed")


def test_parse_non_dispatch_event():
    """op != 0 的事件（心跳等）应返回 None"""
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    body = json.dumps({"op": 11, "d": {}}).encode()
    msg = run(
        adapter.parse_message(HEADERS_OK, body)
    )
    assert msg is None
    print("✅ test_parse_non_dispatch_event passed")


# ------------------------------------------------------------------ #
# 测试 GatewayRouter + QQAdapter 集成
# ------------------------------------------------------------------ #

def _make_router_with_qq() -> GatewayRouter:
    router = GatewayRouter()
    adapter = QQAdapter(config=TEST_QQ_CONFIG)
    router.register_adapter(adapter)
    return router


def _mock_db():
    """创建 Mock MongoDB"""
    db = MagicMock()
    # user_identity_mappings
    db.__getitem__ = MagicMock(side_effect=lambda k: MagicMock())
    return db


def test_router_unsupported_platform():
    """未注册的平台 → 400"""
    router = _make_router_with_qq()
    resp, code = run(
        router.handle_webhook("feishu", {}, b"{}", None)
    )
    assert code == 400
    assert "Unsupported" in resp.get("error", "")
    print("✅ test_router_unsupported_platform passed")


def test_router_qq_validation_challenge():
    """op=13 验证请求 → 返回 plain_token + signature"""
    router = _make_router_with_qq()
    body = json.dumps({
        "op": 13,
        "d": {"plain_token": "test123", "event_ts": "1700000000"},
    }).encode()

    resp, code = run(
        router.handle_webhook("qq", {}, body, None)
    )
    assert code == 200
    assert resp["plain_token"] == "test123"
    assert "signature" in resp
    print("✅ test_router_qq_validation_challenge passed")


def test_router_qq_ack_for_non_dispatch():
    """op != 0 的事件 → 返回 {op: 12} ACK"""
    router = _make_router_with_qq()
    body = json.dumps({"op": 11, "d": {}}).encode()

    resp, code = run(
        router.handle_webhook("qq", HEADERS_OK, body, None)
    )
    assert code == 200
    assert resp == {"op": 12}
    print("✅ test_router_qq_ack_for_non_dispatch passed")


def test_router_qq_help_command():
    """QQ /help 命令 → send_response + op=12 ACK"""
    router = _make_router_with_qq()
    adapter = router.get_adapter("qq")

    sent_responses = []
    async def mock_send(resp):
        sent_responses.append(resp)
        return True

    adapter.send_response = mock_send

    body = _make_c2c_body("/help")
    resp, code = run(
        router.handle_webhook("qq", HEADERS_OK, body, MagicMock())
    )
    assert code == 200
    assert resp == {"op": 12}
    assert len(sent_responses) == 1
    assert "/bind" in sent_responses[0].content
    assert sent_responses[0].metadata.get("msg_id") == "msg_001"
    print("✅ test_router_qq_help_command passed")


def test_router_qq_bind_command():
    """/bind 命令 → 生成验证码 → 被动回复"""
    router = _make_router_with_qq()
    adapter = router.get_adapter("qq")

    sent_responses = []
    async def mock_send(resp):
        sent_responses.append(resp)
        return True
    adapter.send_response = mock_send

    # Mock DB: get_system_user_id → None, create_bind_code → "A1B2C3"
    mock_db = MagicMock()
    mock_mappings = MagicMock()
    mock_pending = MagicMock()

    mock_mappings.find_one = AsyncMock(return_value=None)
    mock_pending.delete_many = AsyncMock()
    mock_pending.insert_one = AsyncMock()

    mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
        "user_identity_mappings": mock_mappings,
        "gateway_pending_bindings": mock_pending,
    }.get(k, MagicMock()))

    body = _make_c2c_body("/bind", user_openid="new_user_001")

    resp, code = run(
        router.handle_webhook("qq", HEADERS_OK, body, mock_db)
    )
    assert code == 200
    assert resp == {"op": 12}
    assert len(sent_responses) == 1
    assert "绑定验证码" in sent_responses[0].content
    print("✅ test_router_qq_bind_command passed")


def test_router_qq_unbound_user_guide():
    """未绑定用户发消息 → 发送引导消息"""
    router = _make_router_with_qq()
    adapter = router.get_adapter("qq")

    sent_responses = []
    async def mock_send(resp):
        sent_responses.append(resp)
        return True
    adapter.send_response = mock_send

    # Mock DB: get_system_user_id → None
    mock_db = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
        "user_identity_mappings": mock_mappings,
    }.get(k, MagicMock()))

    body = _make_c2c_body("分析贵州茅台")

    resp, code = run(
        router.handle_webhook("qq", HEADERS_OK, body, mock_db)
    )
    assert code == 200
    assert resp == {"op": 12}
    assert len(sent_responses) == 1
    assert "/bind" in sent_responses[0].content
    print("✅ test_router_qq_unbound_user_guide passed")


@patch("core.gateway.router.GatewayRouter._invoke_assistant")
def test_router_qq_bound_user_message(mock_invoke):
    """已绑定用户发消息 → 调用助理 → 被动回复 → op=12 ACK"""
    router = _make_router_with_qq()
    adapter = router.get_adapter("qq")

    sent_responses = []
    async def mock_send(resp):
        sent_responses.append(resp)
        return True
    adapter.send_response = mock_send

    # Mock DB: get_system_user_id → "sys_user_001"
    mock_db = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.find_one = AsyncMock(return_value={
        "user_id": "sys_user_001",
        "platform": "qq",
        "platform_identity": "bound_user_001",
        "is_active": True,
    })
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
        "user_identity_mappings": mock_mappings,
    }.get(k, MagicMock()))

    # Mock _invoke_assistant
    mock_invoke.return_value = GatewayResponse(
        channel_type="qq",
        channel_id="c2c:bound_user_001",
        response_type="markdown",
        content="贵州茅台分析结果：PE 35x...",
        metadata={"msg_id": "msg_bound_001", "scene": "c2c", "user_openid": "bound_user_001"},
    )

    body = _make_c2c_body("分析贵州茅台", user_openid="bound_user_001", msg_id="msg_bound_001")

    resp, code = run(
        router.handle_webhook("qq", HEADERS_OK, body, mock_db)
    )
    assert code == 200
    assert resp == {"op": 12}
    assert len(sent_responses) == 1
    assert "贵州茅台" in sent_responses[0].content
    assert sent_responses[0].metadata.get("msg_id") == "msg_bound_001"
    mock_invoke.assert_called_once()
    print("✅ test_router_qq_bound_user_message passed")


# ------------------------------------------------------------------ #
# 运行全部测试
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    tests = [
        test_ed25519_validation,
        test_verify_normal_event,
        test_verify_bad_appid,
        test_parse_c2c_message,
        test_parse_group_message,
        test_parse_non_dispatch_event,
        test_router_unsupported_platform,
        test_router_qq_validation_challenge,
        test_router_qq_ack_for_non_dispatch,
        test_router_qq_help_command,
        test_router_qq_bind_command,
        test_router_qq_unbound_user_guide,
        test_router_qq_bound_user_message,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"总计: {passed + failed} | 通过: {passed} | 失败: {failed}")
    if failed == 0:
        print("🎉 全部测试通过！")
    else:
        sys.exit(1)

