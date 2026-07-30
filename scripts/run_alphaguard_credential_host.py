#!/usr/bin/env python3
"""Run the existing AlphaGuard API with a host-Keychain-only lifespan.

This entrypoint reuses the production FastAPI app, authentication, routers,
database, and safety guards.  It intentionally does not start schedulers,
workers, startup backfill, or data synchronization.  Its only purpose is to
let the local macOS process access Keychain for administrator credential
management while the regular Compose services continue their own work.
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import sys
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
import uvicorn


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_host_app():
    from app.core.alphaguard_config import (
        validate_alphaguard_startup_safety,
    )
    from app.core.database import close_db, init_db
    from app.core.startup_validator import validate_startup_config
    from app.main import app
    from app.services.alphaguard.model_secret_store import (
        default_secret_store,
    )

    if not default_secret_store().available:
        raise RuntimeError("macOS Keychain Secret Store is unavailable")

    @asynccontextmanager
    async def credential_host_lifespan(_app):
        validate_startup_config()
        validate_alphaguard_startup_safety()
        await init_db()
        try:
            yield
        finally:
            try:
                from app.services.user_service import user_service

                user_service.close()
            finally:
                await close_db()

    @app.middleware("http")
    async def credential_host_scope_guard(
        request: Request,
        call_next,
    ):
        path = request.url.path
        method = request.method.upper()
        if path == "/api/system/config/validate":
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "credential host blocks the legacy configuration "
                        "bridge"
                    )
                },
            )
        if method not in {"GET", "HEAD", "OPTIONS"}:
            auth_allowed = path in {
                "/api/auth/login",
                "/api/auth/logout",
                "/api/auth/refresh",
            }
            model_allowed = path.startswith(
                "/api/alphaguard/models/"
            )
            if not (auth_allowed or model_allowed):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "credential host permits only authentication "
                            "and model credential operations"
                        )
                    },
                )
        return await call_next(request)

    app.router.lifespan_context = credential_host_lifespan
    return app


def main(*, execute: bool, host: str, port: int) -> int:
    print("mode=execute" if execute else "mode=dry-run")
    print(
        "scope=credential-host scheduler=false workers=false "
        "backfill=false data_sync=false live=false"
    )
    print(f"api=http://{host}:{port}")
    if not execute:
        print("dry-run: no server started; pass --execute to run")
        return 0
    uvicorn.run(
        build_host_app(),
        host=host,
        port=port,
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    raise SystemExit(
        main(execute=args.execute, host=args.host, port=args.port)
    )
