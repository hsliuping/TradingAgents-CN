# Favorite Tag Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure newly entered favorite-stock tags are also available from the user's tag library.

**Architecture:** The favorite service remains the entry point for add-favorite requests. It normalizes non-empty tag names and performs idempotent upserts into `user_tags` before persisting the favorite, keeping existing tag metadata untouched.

**Tech Stack:** Python, FastAPI service layer, Motor/MongoDB, pytest.

## Global Constraints

- Do not alter or backfill existing favorite documents.
- Preserve user-defined tag color and sort order when a tag already exists.
- Keep the external add-favorite API payload unchanged.

---

### Task 1: Synchronize tags while adding a favorite

**Files:**
- Create: `tests/test_favorites_service_tag_sync.py`
- Modify: `app/services/favorites_service.py`

**Interfaces:**
- Consumes: `FavoritesService.add_favorite(user_id, stock_code, stock_name, market, tags, notes, alert_price_high, alert_price_low) -> bool`
- Produces: a favorite record and exactly one `user_tags` record per non-empty tag name for that user.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_add_favorite_persists_new_tags_to_the_user_tag_library():
    service = FavoritesService()
    service.db = fake_db

    await service.add_favorite(
        user_id="user-1", stock_code="000001", stock_name="平安银行",
        tags=["价值", "观察"],
    )

    assert fake_db.user_tags.names_for("user-1") == {"价值", "观察"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_favorites_service_tag_sync.py -q`

Expected: FAIL because `add_favorite` does not write to `user_tags`.

- [ ] **Step 3: Write minimal implementation**

```python
for tag_name in {tag.strip() for tag in (tags or []) if tag and tag.strip()}:
    await db.user_tags.update_one(
        {"user_id": str(user_id), "name": tag_name},
        {"$setOnInsert": {"user_id": str(user_id), "name": tag_name,
                           "color": "#409EFF", "sort_order": 0,
                           "created_at": now, "updated_at": now}},
        upsert=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_favorites_service_tag_sync.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/favorites_service.py tests/test_favorites_service_tag_sync.py docs/superpowers
git commit -m "fix: sync favorite tags to tag library"
```
