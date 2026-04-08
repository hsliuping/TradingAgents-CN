from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.auth_guard import AuthGuardMiddleware
from app.schemas.embedded_nanobot import EmbeddedNanobotThreadMessagesResponse


def test_embedded_nanobot_response_schema_accepts_datetime_timestamps() -> None:
    now = datetime(2026, 4, 6, 10, 52, 12, 788000, tzinfo=timezone.utc)

    response = EmbeddedNanobotThreadMessagesResponse(
        thread={
            "thread_id": "thread-001",
            "title": "Nanobot 会话",
            "session_key": "embedded:test",
            "created_at": now,
            "updated_at": now,
        },
        messages=[
            {
                "message_id": "msg-001",
                "role": "assistant",
                "content": "hello",
                "created_at": now,
            }
        ],
    )

    assert response.thread is not None
    assert response.thread.created_at == now.isoformat()
    assert response.thread.updated_at == now.isoformat()
    assert response.messages[0].created_at == now.isoformat()


def test_auth_guard_does_not_mask_downstream_http_exception(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(AuthGuardMiddleware)

    @app.get("/api/protected")
    async def protected_route():
        raise HTTPException(status_code=418, detail="teapot")

    from app.services.auth_service import AuthService

    monkeypatch.setattr(AuthService, "verify_token", staticmethod(lambda _token: {"sub": "user-001"}))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/protected", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 418
    assert response.json()["detail"] == "teapot"