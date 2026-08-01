from unittest.mock import AsyncMock

import pytest

from app.services.favorites_service import FavoritesService


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def update_one(self, query, update, upsert=False):
        if "favorites" in update.get("$push", {}):
            self.documents.append(update["$push"]["favorites"])
        return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1, "upserted_id": None})()


class FakeTagCollection:
    def __init__(self):
        self.documents = {}

    async def update_one(self, query, update, upsert=False):
        key = (query["user_id"], query["name"])
        if key not in self.documents and upsert:
            self.documents[key] = update["$setOnInsert"]
        return type("UpdateResult", (), {"matched_count": int(key in self.documents), "modified_count": 1, "upserted_id": None})()

    def names_for(self, user_id):
        return {name for (stored_user_id, name) in self.documents if stored_user_id == user_id}

    def document_for(self, user_id, name):
        return self.documents[(user_id, name)]


class FakeDatabase:
    def __init__(self):
        self.user_favorites = FakeCollection()
        self.user_tags = FakeTagCollection()


@pytest.mark.asyncio
async def test_add_favorite_persists_new_tags_to_the_user_tag_library():
    """Removing tag-library persistence must make this test fail."""
    service = FavoritesService()
    fake_db = FakeDatabase()
    fake_db.user_tags.documents[("user-1", "观察")] = {
        "user_id": "user-1", "name": "观察", "color": "#F56C6C", "sort_order": 3,
    }
    service.db = fake_db

    result = await service.add_favorite(
        user_id="user-1",
        stock_code="000001",
        stock_name="平安银行",
        tags=["价值", "观察", "价值", "  "],
    )

    assert result is True
    assert fake_db.user_tags.names_for("user-1") == {"价值", "观察"}
    assert fake_db.user_tags.document_for("user-1", "观察")["color"] == "#F56C6C"
    assert fake_db.user_tags.document_for("user-1", "观察")["sort_order"] == 3
