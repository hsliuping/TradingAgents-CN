"""
MCP Server 端到端测试脚本

用法: python tests/test_mcp_endpoint.py
"""

import json
import requests

BASE = "http://127.0.0.1:8000/mcp/"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def mcp_post(payload: dict, session_id: str | None = None) -> tuple[int, dict | str, str | None]:
    """发送 MCP JSON-RPC 请求，返回 (status, body, session_id)"""
    hdrs = {**HEADERS}
    if session_id:
        hdrs["Mcp-Session-Id"] = session_id
    resp = requests.post(BASE, json=payload, headers=hdrs, timeout=15)
    sid = resp.headers.get("Mcp-Session-Id") or session_id
    ct = resp.headers.get("content-type", "")
    if "text/event-stream" in ct:
        # 解析 SSE 事件
        body = parse_sse(resp.text)
    else:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    return resp.status_code, body, sid


def parse_sse(text: str) -> dict | str:
    """从 SSE 流中提取最后一个 JSON-RPC 响应"""
    last_data = None
    for line in text.split("\n"):
        if line.startswith("data: "):
            last_data = line[6:]
    if last_data:
        try:
            return json.loads(last_data)
        except Exception:
            return last_data
    return text


def test_initialize_and_list_tools():
    print("=" * 60)
    print("🧪 MCP 端到端测试")
    print("=" * 60)

    # Step 1: initialize
    print("\n📤 Step 1: initialize ...")
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"},
        },
    }
    status, body, sid = mcp_post(init_payload)
    print(f"   Status: {status}")
    print(f"   Session: {sid}")
    if isinstance(body, dict):
        server_info = body.get("result", {}).get("serverInfo", {})
        print(f"   Server: {server_info.get('name')} v{server_info.get('version')}")
        caps = body.get("result", {}).get("capabilities", {})
        print(f"   Capabilities: {list(caps.keys())}")
    else:
        print(f"   Body: {str(body)[:200]}")
    assert status == 200, f"❌ initialize 失败: {status}"
    print("   ✅ initialize 成功")

    # Step 1.5: initialized notification
    print("\n📤 Step 1.5: notifications/initialized ...")
    notif_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    status2, _, _ = mcp_post(notif_payload, session_id=sid)
    print(f"   Status: {status2} (202/204 expected for notification)")

    # Step 2: tools/list
    print("\n📤 Step 2: tools/list ...")
    list_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    status, body, sid = mcp_post(list_payload, session_id=sid)
    print(f"   Status: {status}")
    if isinstance(body, dict):
        tools = body.get("result", {}).get("tools", [])
        print(f"   工具数量: {len(tools)}")
        for t in tools:
            desc = (t.get("description") or "")[:50]
            print(f"   📦 {t['name']}: {desc}...")
    else:
        print(f"   Body: {str(body)[:300]}")
    assert status == 200, f"❌ tools/list 失败: {status}"
    print("   ✅ tools/list 成功")

    print("\n" + "=" * 60)
    print("🎉 所有测试通过！MCP Server 工作正常。")
    print(f"   端点: {BASE}")
    print(f"   Session ID: {sid}")
    print("=" * 60)


if __name__ == "__main__":
    test_initialize_and_list_tools()

