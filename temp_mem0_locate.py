import mem0, inspect
from mem0 import AsyncMemory
print('mem0_file=', mem0.__file__)
print('asyncmemory_module=', inspect.getmodule(AsyncMemory).__file__)
