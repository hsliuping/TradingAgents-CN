from datetime import datetime, timedelta

from app.services.session_service import SessionService


class _FakeDeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class _FakeCollection:
    def __init__(self):
        self.docs: list[dict] = []

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, doc):
        self.docs.append(dict(doc))

    def find_one(self, filter_doc):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in filter_doc.items()):
                return doc
        return None

    def update_one(self, filter_doc, update_doc):
        doc = self.find_one(filter_doc)
        if not doc:
            return None
        if "$set" in update_doc:
            doc.update(update_doc["$set"])
        return None

    def delete_one(self, filter_doc):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in filter_doc.items()):
                self.docs.pop(index)
                return _FakeDeleteResult(1)
        return _FakeDeleteResult(0)


class _FakeDb:
    def __init__(self):
        self.user_sessions = _FakeCollection()


def test_verify_session_renews_expiration_for_active_user():
    db = _FakeDb()
    service = SessionService(db)

    session_id = service.create_session(user_id="user-1", expires_in_seconds=60)
    session_doc = db.user_sessions.find_one({"session_id": session_id})
    session_doc["created_at"] = session_doc["created_at"] - timedelta(seconds=30)
    session_doc["last_activity"] = session_doc["created_at"]
    session_doc["expires_at"] = session_doc["created_at"] + timedelta(seconds=60)
    original_expires_at = session_doc["expires_at"]

    service.verify_session(session_id, update_activity=True)

    renewed_doc = db.user_sessions.find_one({"session_id": session_id})
    assert renewed_doc is not None
    assert renewed_doc["expires_at"] > original_expires_at
    assert renewed_doc["last_activity"] >= session_doc["created_at"]


def test_verify_session_uses_inferred_ttl_for_legacy_session_documents():
    db = _FakeDb()
    service = SessionService(db)

    created_at = datetime.utcnow() - timedelta(seconds=90)
    expires_at = created_at + timedelta(seconds=120)
    db.user_sessions.insert_one({
        "session_id": "legacy-session",
        "user_id": "user-legacy",
        "created_at": created_at,
        "expires_at": expires_at,
        "last_activity": created_at,
        "ip_address": None,
        "user_agent": None,
    })

    service.verify_session("legacy-session", update_activity=True)

    renewed_doc = db.user_sessions.find_one({"session_id": "legacy-session"})
    assert renewed_doc is not None
    assert renewed_doc["expires_at"] > expires_at