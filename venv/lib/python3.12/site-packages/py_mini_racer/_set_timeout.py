"""An implementation of setTimeout and clearTimeout using only the ECMA standard lib.

V8 does not include an implementation of the setTimeout or clearTimeout APIs, because
they are web APIs (defined in the DOM and Web Worker spec), not ECMAScript APIs.
Nonetheless they are hugely useful and generally taken for granted, so let's go ahead
and install a basic implementation.

We base this on the Atomics.waitAsync API, which *is* part of the ECMAScript spec.
(It would be possible for MiniRacer to implement this on the C++ side instead, but
this way seems simpler.)
"""

INSTALL_SET_TIMEOUT = """
class __TimerManager {
  constructor() {
    this.next_idx = 0;
    this.pending = new Set();
  }

  setTimeout(func, delay) {
    const id = this.next_idx++;

    const shared = new SharedArrayBuffer(8);
    const view = new Int32Array(shared);

    const args = Array.prototype.slice.call(arguments, 2);

    let callback = () => {
        if (this.pending.has(id)) {
            this.pending.delete(id);
            func(...args);
        }
    };

    this.pending.add(id);
    Atomics.waitAsync(view, 0, 0, delay).value.then(() => callback());

    return id;
  }

  clearTimeout(timeout_id) {
    this.pending.delete(timeout_id);
  }
}

var __timer_manager = new __TimerManager();
var setTimeout = (...arguments) => __timer_manager.setTimeout(...arguments);
var clearTimeout = (...arguments) => __timer_manager.clearTimeout(...arguments);
"""
