import pytest

from app.services.tags_service import TagsService


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, _fields):
        return self

    async def to_list(self, length=None):
        return list(self.documents)


class FakeUserTags:
    def __init__(self):
        self.documents = []

    async def create_index(self, *_args, **_kwargs):
        return None

    async def update_one(self, query, update, upsert=False):
        if not any(doc["user_id"] == query["user_id"] and doc["name"] == query["name"] for doc in self.documents):
            self.documents.append({"_id": len(self.documents) + 1, **update["$setOnInsert"]})

    def find(self, query):
        return FakeCursor([doc for doc in self.documents if doc["user_id"] == query["user_id"]])


class FakeFavorites:
    async def find_one(self, _query, _projection):
        return {
            "favorites": [
                {"tags": ["封测", "PCB"]},
                {"tags": ["PCB", "  "]},
            ]
        }


class FakeDatabase:
    def __init__(self):
        self.user_tags = FakeUserTags()
        self.user_favorites = FakeFavorites()


@pytest.mark.asyncio
async def test_list_tags_migrates_tags_from_existing_favorites():
    """Removing legacy-favorite migration must make existing dropdown values disappear."""
    service = TagsService()
    service.db = FakeDatabase()

    tags = await service.list_tags("user-1")

    assert {tag["name"] for tag in tags} == {"封测", "PCB"}
