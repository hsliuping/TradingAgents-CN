"""Run inside the backend container to initialize an empty authentication DB."""
import asyncio
import json
import logging
import os
from pathlib import Path
import secrets
import urllib.request

from app.services.user_service import user_service

# The legacy image logs newly created passwords; suppress logging here.
logging.disable(logging.CRITICAL)
try:
    if user_service.users_collection.count_documents({}) != 0:
        raise SystemExit("Accounts already exist; refusing to overwrite credentials.")
    password = secrets.token_urlsafe(24)
    path = Path("/app/data/admin-initial-password.txt")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write("URL: http://16.208.96.255\nUsername: admin\nPassword: " + password + "\n")
    user = asyncio.run(user_service.create_admin_user(password=password))
    if user is None:
        raise RuntimeError("Administrator creation failed")
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=json.dumps({"username": "admin", "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
        if not result.get("success") or not result.get("data", {}).get("access_token"):
            raise RuntimeError("Login did not return a successful token response")
        print("Administrator created; login HTTP 200 and token verified.")
finally:
    user_service.close()
