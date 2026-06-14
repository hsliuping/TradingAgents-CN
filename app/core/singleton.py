"""
线程安全工具库
提供线程安全的状态管理、缓存和单例模式
"""
import copy
import threading
import time
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

T = TypeVar("T")


class ThreadSafeState:
    """线程安全的状态容器，替代模块级裸 dict

    所有读写操作加锁，支持原子 update() 和快照 snapshot()。
    """

    def __init__(self, initial: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = dict(initial) if initial else {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._data

    def update(self, updates: Dict[str, Any]) -> None:
        """原子更新多个键值对"""
        with self._lock:
            self._data.update(updates)

    def snapshot(self) -> Dict[str, Any]:
        """返回当前状态的深拷贝快照（嵌套对象互不影响）"""
        with self._lock:
            return copy.deepcopy(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def keys(self):
        with self._lock:
            return list(self._data.keys())


class BoundedCache:
    """有界 LRU+TTL 缓存，替代无界全局 dict

    自动淘汰过期/超限条目。
    """

    def __init__(self, max_size: int = 5000, ttl: float = 3600.0):
        self._max_size = max_size
        self._ttl = ttl
        self._data: Dict[str, Any] = {}
        _Sentinel = object
        self._access: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key not in self._data:
                return default
            if self._is_expired(key):
                self._evict(key)
                return default
            self._access[key] = time.monotonic()
            return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self._max_size:
                self._evict_lru()
            now = time.monotonic()
            self._data[key] = value
            self._access[key] = now

    def __contains__(self, key: object) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            if self._is_expired(key):
                self._evict(key)
                return False
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def _is_expired(self, key: str) -> bool:
        return (time.monotonic() - self._access[key]) > self._ttl

    def _evict(self, key: str) -> None:
        self._data.pop(key, None)
        self._access.pop(key, None)

    def _evict_lru(self) -> None:
        if not self._access:
            return
        oldest_key = min(self._access, key=self._access.get)
        self._evict(oldest_key)


def make_thread_safe_getter(factory: Callable[[], T]) -> Callable[[], T]:
    """线程安全懒加载工厂函数

    保证 factory 只被调用一次，即使多个线程同时调用 getter。
    """
    _instance = None
    _lock = threading.Lock()

    def getter() -> T:
        nonlocal _instance
        if _instance is not None:
            return _instance
        with _lock:
            if _instance is None:
                _instance = factory()
        return _instance

    return getter


class ThreadSafeSingleton(Generic[T]):
    """泛型线程安全单例描述符

    用法::

        class MyClass:
            db = ThreadSafeSingleton(Database)
    """

    def __init__(self, cls: type, *args, **kwargs):
        self._cls = cls
        self._args = args
        self._kwargs = kwargs
        self._instance: Optional[T] = None
        self._lock = threading.Lock()

    def __get__(self, obj, objtype=None) -> T:
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = self._cls(*self._args, **self._kwargs)
        return self._instance
