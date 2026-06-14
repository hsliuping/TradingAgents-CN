"""ThreadSafeState / BoundedCache / make_thread_safe_getter 单元测试"""
import threading
import time
from app.core.singleton import ThreadSafeState, BoundedCache, make_thread_safe_getter


# ---------------------------------------------------------------------------
# ThreadSafeState
# ---------------------------------------------------------------------------

class TestThreadSafeState:
    def test_basic_read_write(self):
        s = ThreadSafeState({"a": 1})
        assert s["a"] == 1
        s["b"] = 2
        assert s["b"] == 2

    def test_get_default(self):
        s = ThreadSafeState()
        assert s.get("missing", 42) == 42

    def test_contains(self):
        s = ThreadSafeState({"x": 10})
        assert "x" in s
        assert "y" not in s

    def test_atomic_update(self):
        s = ThreadSafeState()
        s.update({"a": 1, "b": 2})
        assert s["a"] == 1 and s["b"] == 2

    def test_snapshot_isolation(self):
        s = ThreadSafeState({"k": "v"})
        snap = s.snapshot()
        s["k"] = "changed"
        assert snap["k"] == "v"

    def test_snapshot_is_copy(self):
        s = ThreadSafeState({"k": [1, 2]})
        snap = s.snapshot()
        snap["k"].append(3)
        assert s["k"] == [1, 2]

    def test_clear(self):
        s = ThreadSafeState({"a": 1})
        s.clear()
        assert len(s.keys()) == 0

    def test_keys(self):
        s = ThreadSafeState({"a": 1, "b": 2})
        assert set(s.keys()) == {"a", "b"}

    def test_concurrent_reads_writes(self):
        s = ThreadSafeState({"counter": 0})
        errors = []

        def writer():
            for i in range(100):
                s["counter"] = i

        def reader():
            for _ in range(100):
                _ = s["counter"]

        threads = [threading.Thread(target=writer) for _ in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # no crash = success; value is some valid int
        assert isinstance(s["counter"], int)


# ---------------------------------------------------------------------------
# BoundedCache
# ---------------------------------------------------------------------------

class TestBoundedCache:
    def test_basic_set_get(self):
        c = BoundedCache(max_size=10, ttl=60)
        c["k"] = "v"
        assert c.get("k") == "v"

    def test_get_default(self):
        c = BoundedCache()
        assert c.get("missing", "default") == "default"

    def test_contains(self):
        c = BoundedCache()
        c["k"] = 1
        assert "k" in c

    def test_ttl_expiry(self):
        c = BoundedCache(max_size=10, ttl=0.05)
        c["k"] = "v"
        time.sleep(0.1)
        assert c.get("k") is None
        assert "k" not in c

    def test_capacity_eviction(self):
        c = BoundedCache(max_size=3, ttl=60)
        c["a"] = 1
        time.sleep(0.01)
        c["b"] = 2
        time.sleep(0.01)
        c["c"] = 3
        time.sleep(0.01)
        c["d"] = 4  # should evict "a" (LRU)
        assert "a" not in c
        assert "d" in c

    def test_lru_order(self):
        c = BoundedCache(max_size=3, ttl=60)
        c["a"] = 1
        time.sleep(0.01)
        c["b"] = 2
        time.sleep(0.01)
        c["c"] = 3
        time.sleep(0.01)
        c.get("a")  # touch "a" so it's no longer LRU
        time.sleep(0.01)
        c["d"] = 4  # should evict "b" (oldest access)
        assert "a" in c
        assert "b" not in c

    def test_len(self):
        c = BoundedCache()
        c["a"] = 1
        c["b"] = 2
        assert len(c) == 2

    def test_overwrite(self):
        c = BoundedCache()
        c["k"] = 1
        c["k"] = 2
        assert c.get("k") == 2

    def test_concurrent_access(self):
        c = BoundedCache(max_size=500, ttl=60)
        errors = []

        def writer(start):
            for i in range(100):
                try:
                    c[f"k_{start}_{i}"] = i
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# make_thread_safe_getter
# ---------------------------------------------------------------------------

class TestMakeThreadSafeGetter:
    def test_single_creation(self):
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return "instance"

        getter = make_thread_safe_getter(factory)
        assert getter() == "instance"
        assert getter() == "instance"
        assert call_count == 1

    def test_concurrent_creation(self):
        call_count = 0
        instances = []

        def factory():
            nonlocal call_count
            call_count += 1
            time.sleep(0.05)
            return object()

        getter = make_thread_safe_getter(factory)

        def caller():
            instances.append(getter())

        threads = [threading.Thread(target=caller) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert call_count == 1
        assert all(inst is instances[0] for inst in instances)
