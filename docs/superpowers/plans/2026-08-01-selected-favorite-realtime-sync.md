# Selected Favorite Realtime Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users synchronize real-time quotes for selected favorites with an explicit AKShare or Tushare choice and truthful result counts.

**Architecture:** Add real-time support to the existing `/api/stock-sync/batch` contract and its Favorites batch dialog. Normalize service results into `success_count` and `error_count`; convert a selected-symbol empty result into explicit per-symbol failures before the response is rendered.

**Tech Stack:** Vue 3, TypeScript, FastAPI, Pydantic, pytest.

## Global Constraints

- Do not change the user's selected data source.
- A real-time operation only receives the selected symbols.
- API responses must report failures with `error_count`; frontend must not substitute a missing field with zero.

---

### Task 1: Return truthful selected real-time synchronization results

**Files:**
- Create: `tests/test_favorites_realtime_sync_results.py`
- Modify: `app/routers/stock_sync.py`
- Modify: `app/routers/favorites.py`

**Interfaces:**
- Consumes: `BatchStockSyncRequest.sync_realtime: bool` and `BatchStockSyncRequest.symbols: List[str]`.
- Produces: `realtime_sync` with `total_processed`, `success_count`, `error_count`, and `errors`.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_selected_realtime_sync_preserves_requested_symbols_and_data_source():
    response = await sync_batch_stocks(
        BatchStockSyncRequest(symbols=["000001", "000002"], sync_realtime=True, data_source="akshare"),
        background_tasks=BackgroundTasks(), current_user={"id": "user-1"},
    )
    assert response["data"]["realtime_sync"]["success_count"] == 2

@pytest.mark.asyncio
async def test_empty_tushare_realtime_result_counts_each_selected_symbol_as_failed():
    result = await normalize_realtime_result(["000001", "000002"], {"success_count": 0, "error_count": 0, "errors": [{"error": "rt_k permission denied"}]})
    assert result["error_count"] == 2
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_favorites_realtime_sync_results.py -q`

Expected: FAIL because the batch request and result normalization do not yet expose real-time synchronization.

- [ ] **Step 3: Implement the minimal backend contract**

```python
class BatchStockSyncRequest(BaseModel):
    symbols: List[str]
    sync_realtime: bool = False

if request.sync_realtime:
    service = await get_akshare_sync_service() if request.data_source == "akshare" else await get_tushare_sync_service()
    result["realtime_sync"] = await service.sync_realtime_quotes(symbols=request.symbols, force=True)
```

Normalize no-quote results so `error_count` equals the count of requested symbols not represented by `success_count`.

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/test_favorites_realtime_sync_results.py -q`

Expected: PASS.

### Task 2: Expose selected real-time sync in the Favorites dialog

**Files:**
- Modify: `frontend/src/views/Favorites/index.vue`
- Modify: `frontend/src/api/stockSync.ts`

**Interfaces:**
- Consumes: `BatchStockSyncRequest.sync_realtime` and `BatchStockSyncResponse.data.realtime_sync`.
- Produces: a checked “实时行情” option and a completion message with real-time success/error counts.

- [ ] **Step 1: Write failing frontend type/test coverage**

```ts
expect(batchPayload).toMatchObject({
  symbols: ['000001', '000002'],
  sync_realtime: true,
  data_source: 'akshare',
})
```

- [ ] **Step 2: Verify test fails**

Run: `npm run test -- Favorites`

Expected: FAIL because neither the type nor the form supplies `sync_realtime`.

- [ ] **Step 3: Implement the UI and type changes**

```vue
<el-checkbox label="realtime">实时行情</el-checkbox>
```

```ts
sync_realtime: batchSyncForm.value.syncTypes.includes('realtime')
```

Show `data.realtime_sync.success_count` and `data.realtime_sync.error_count` in the result message, including the first returned error when failures occur.

- [ ] **Step 4: Verify UI build and tests pass**

Run: `npm run build`

Expected: exit code 0.
