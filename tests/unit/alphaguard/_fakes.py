"""Small async MongoDB test double for AlphaGuard unit tests."""

from __future__ import annotations

from copy import deepcopy

from bson import ObjectId


def _matches(document, query):
    if not query:
        return True
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, clause) for clause in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$exists" in expected and (key in document) != expected["$exists"]:
                return False
            continue
        if isinstance(actual, list):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


class Result:
    def __init__(
        self,
        *,
        inserted_id=None,
        matched_count=0,
        modified_count=0,
        upserted_id=None,
        deleted_count=0,
    ):
        self.inserted_id = inserted_id
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id
        self.deleted_count = deleted_count


class Cursor:
    def __init__(self, documents):
        self.documents = [deepcopy(document) for document in documents]

    def sort(self, spec, direction=None):
        pairs = spec if isinstance(spec, list) else [(spec, direction)]
        for key, order in reversed(pairs):
            self.documents.sort(
                key=lambda document: (
                    document.get(key) is None,
                    document.get(key),
                ),
                reverse=order < 0,
            )
        return self

    def limit(self, limit):
        self.documents = self.documents[:limit]
        return self

    async def to_list(self, length=None):
        return deepcopy(self.documents if length is None else self.documents[:length])


class Collection:
    def __init__(self):
        self.documents = []
        self.indexes = [{"name": "_id_", "key": {"_id": 1}}]

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return Result(inserted_id=stored["_id"])

    async def find_one(self, query, projection=None, sort=None):
        matches = [document for document in self.documents if _matches(document, query)]
        if sort:
            matches = Cursor(matches).sort(sort).documents
        return deepcopy(matches[0]) if matches else None

    def find(self, query=None, projection=None):
        return Cursor(
            document
            for document in self.documents
            if _matches(document, query or {})
        )

    async def replace_one(self, query, replacement, upsert=False):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                stored = deepcopy(replacement)
                stored.setdefault("_id", document["_id"])
                self.documents[index] = stored
                return Result(matched_count=1, modified_count=1)
        if upsert:
            result = await self.insert_one(replacement)
            return Result(upserted_id=result.inserted_id)
        return Result()

    async def update_one(self, query, update, upsert=False):
        for index, document in enumerate(self.documents):
            if not _matches(document, query):
                continue
            before = deepcopy(document)
            for key, value in update.get("$set", {}).items():
                document[key] = deepcopy(value)
            for key, value in update.get("$push", {}).items():
                document.setdefault(key, []).append(deepcopy(value))
            for key, value in update.get("$addToSet", {}).items():
                document.setdefault(key, [])
                if value not in document[key]:
                    document[key].append(deepcopy(value))
            for key, condition in update.get("$pull", {}).items():
                document[key] = [
                    item
                    for item in document.get(key, [])
                    if not _matches(item, condition)
                ]
            self.documents[index] = document
            return Result(
                matched_count=1,
                modified_count=int(document != before),
            )
        if not upsert:
            return Result()
        created = {
            key: deepcopy(value)
            for key, value in query.items()
            if not key.startswith("$") and not isinstance(value, dict)
        }
        created.update(deepcopy(update.get("$setOnInsert", {})))
        for key, value in update.get("$set", {}).items():
            created[key] = deepcopy(value)
        for key, value in update.get("$push", {}).items():
            created[key] = [deepcopy(value)]
        result = await self.insert_one(created)
        return Result(upserted_id=result.inserted_id)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return Result(deleted_count=1)
        return Result()

    async def delete_many(self, query):
        before = len(self.documents)
        self.documents = [
            document for document in self.documents if not _matches(document, query)
        ]
        return Result(deleted_count=before - len(self.documents))

    def list_indexes(self):
        return Cursor(self.indexes)

    async def create_index(self, keys, name, unique=False):
        self.indexes.append(
            {"name": name, "key": dict(keys), "unique": bool(unique)}
        )
        return name

    def count(self):
        return len(self.documents)


class FakeDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        self.collections.setdefault(name, Collection())
        return self.collections[name]

    def __getattr__(self, name):
        return self[name]
