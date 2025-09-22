# Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved

"""Lock and Condition classes vendored from https://github.com/python/cpython/blob/main/Lib/asyncio/locks.py
to port 3.13 fixes to older versions of Python.
Can be removed once we drop Python 3.12 support."""

from __future__ import annotations

import collections
import threading
from asyncio import events, exceptions
from typing import Any, Coroutine, Optional

_global_lock = threading.Lock()


class _LoopBoundMixin:
    _loop = None

    def _get_loop(self) -> Any:
        loop = events._get_running_loop()

        if self._loop is None:
            with _global_lock:
                if self._loop is None:
                    self._loop = loop
        if loop is not self._loop:
            raise RuntimeError(f"{self!r} is bound to a different event loop")
        return loop


class _ContextManagerMixin:
    async def __aenter__(self) -> None:
        await self.acquire()  # type: ignore[attr-defined]
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()  # type: ignore[attr-defined]


class Lock(_ContextManagerMixin, _LoopBoundMixin):
    """Primitive lock objects.

    A primitive lock is a synchronization primitive that is not owned
    by a particular task when locked.  A primitive lock is in one
    of two states, 'locked' or 'unlocked'.

    It is created in the unlocked state.  It has two basic methods,
    acquire() and release().  When the state is unlocked, acquire()
    changes the state to locked and returns immediately.  When the
    state is locked, acquire() blocks until a call to release() in
    another task changes it to unlocked, then the acquire() call
    resets it to locked and returns.  The release() method should only
    be called in the locked state; it changes the state to unlocked
    and returns immediately.  If an attempt is made to release an
    unlocked lock, a RuntimeError will be raised.

    When more than one task is blocked in acquire() waiting for
    the state to turn to unlocked, only one task proceeds when a
    release() call resets the state to unlocked; successive release()
    calls will unblock tasks in FIFO order.

    Locks also support the asynchronous context management protocol.
    'async with lock' statement should be used.

    Usage:

        lock = Lock()
        ...
        await lock.acquire()
        try:
            ...
        finally:
            lock.release()

    Context manager usage:

        lock = Lock()
        ...
        async with lock:
             ...

    Lock objects can be tested for locking state:

        if not lock.locked():
           await lock.acquire()
        else:
           # lock is acquired
           ...

    """

    def __init__(self) -> None:
        self._waiters: Optional[collections.deque] = None
        self._locked = False

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = "locked" if self._locked else "unlocked"
        if self._waiters:
            extra = f"{extra}, waiters:{len(self._waiters)}"
        return f"<{res[1:-1]} [{extra}]>"

    def locked(self) -> bool:
        """Return True if lock is acquired."""
        return self._locked

    async def acquire(self) -> bool:
        """Acquire a lock.

        This method blocks until the lock is unlocked, then sets it to
        locked and returns True.
        """
        # Implement fair scheduling, where thread always waits
        # its turn. Jumping the queue if all are cancelled is an optimization.
        if not self._locked and (
            self._waiters is None or all(w.cancelled() for w in self._waiters)
        ):
            self._locked = True
            return True

        if self._waiters is None:
            self._waiters = collections.deque()
        fut = self._get_loop().create_future()
        self._waiters.append(fut)

        try:
            try:
                await fut
            finally:
                self._waiters.remove(fut)
        except exceptions.CancelledError:
            # Currently the only exception designed be able to occur here.

            # Ensure the lock invariant: If lock is not claimed (or about
            # to be claimed by us) and there is a Task in waiters,
            # ensure that the Task at the head will run.
            if not self._locked:
                self._wake_up_first()
            raise

        # assert self._locked is False
        self._locked = True
        return True

    def release(self) -> None:
        """Release a lock.

        When the lock is locked, reset it to unlocked, and return.
        If any other tasks are blocked waiting for the lock to become
        unlocked, allow exactly one of them to proceed.

        When invoked on an unlocked lock, a RuntimeError is raised.

        There is no return value.
        """
        if self._locked:
            self._locked = False
            self._wake_up_first()
        else:
            raise RuntimeError("Lock is not acquired")

    def _wake_up_first(self) -> None:
        """Ensure that the first waiter will wake up."""
        if not self._waiters:
            return
        try:
            fut = next(iter(self._waiters))
        except StopIteration:
            return

        # .done() means that the waiter is already set to wake up.
        if not fut.done():
            fut.set_result(True)


class Condition(_ContextManagerMixin, _LoopBoundMixin):
    """Asynchronous equivalent to threading.Condition.

    This class implements condition variable objects. A condition variable
    allows one or more tasks to wait until they are notified by another
    task.

    A new Lock object is created and used as the underlying lock.
    """

    def __init__(self, lock: Optional[Lock] = None) -> None:
        if lock is None:
            lock = Lock()

        self._lock = lock
        # Export the lock's locked(), acquire() and release() methods.
        self.locked = lock.locked
        self.acquire = lock.acquire
        self.release = lock.release

        self._waiters: collections.deque = collections.deque()

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = "locked" if self.locked() else "unlocked"
        if self._waiters:
            extra = f"{extra}, waiters:{len(self._waiters)}"
        return f"<{res[1:-1]} [{extra}]>"

    async def wait(self) -> bool:
        """Wait until notified.

        If the calling task has not acquired the lock when this
        method is called, a RuntimeError is raised.

        This method releases the underlying lock, and then blocks
        until it is awakened by a notify() or notify_all() call for
        the same condition variable in another task.  Once
        awakened, it re-acquires the lock and returns True.

        This method may return spuriously,
        which is why the caller should always
        re-check the state and be prepared to wait() again.
        """
        if not self.locked():
            raise RuntimeError("cannot wait on un-acquired lock")

        fut = self._get_loop().create_future()
        self.release()
        try:
            try:
                self._waiters.append(fut)
                try:
                    await fut
                    return True
                finally:
                    self._waiters.remove(fut)

            finally:
                # Must re-acquire lock even if wait is cancelled.
                # We only catch CancelledError here, since we don't want any
                # other (fatal) errors with the future to cause us to spin.
                err = None
                while True:
                    try:
                        await self.acquire()
                        break
                    except exceptions.CancelledError as e:
                        err = e

                if err is not None:
                    try:
                        raise err  # Re-raise most recent exception instance.
                    finally:
                        err = None  # Break reference cycles.
        except BaseException:
            # Any error raised out of here _may_ have occurred after this Task
            # believed to have been successfully notified.
            # Make sure to notify another Task instead.  This may result
            # in a "spurious wakeup", which is allowed as part of the
            # Condition Variable protocol.
            self._notify(1)
            raise

    async def wait_for(self, predicate: Any) -> Coroutine:
        """Wait until a predicate becomes true.

        The predicate should be a callable whose result will be
        interpreted as a boolean value.  The method will repeatedly
        wait() until it evaluates to true.  The final predicate value is
        the return value.
        """
        result = predicate()
        while not result:
            await self.wait()
            result = predicate()
        return result

    def notify(self, n: int = 1) -> None:
        """By default, wake up one task waiting on this condition, if any.
        If the calling task has not acquired the lock when this method
        is called, a RuntimeError is raised.

        This method wakes up n of the tasks waiting for the condition
         variable; if fewer than n are waiting, they are all awoken.

        Note: an awakened task does not actually return from its
        wait() call until it can reacquire the lock. Since notify() does
        not release the lock, its caller should.
        """
        if not self.locked():
            raise RuntimeError("cannot notify on un-acquired lock")
        self._notify(n)

    def _notify(self, n: int) -> None:
        idx = 0
        for fut in self._waiters:
            if idx >= n:
                break

            if not fut.done():
                idx += 1
                fut.set_result(False)

    def notify_all(self) -> None:
        """Wake up all tasks waiting on this condition. This method acts
        like notify(), but wakes up all waiting tasks instead of one. If the
        calling task has not acquired the lock when this method is called,
        a RuntimeError is raised.
        """
        self.notify(len(self._waiters))
