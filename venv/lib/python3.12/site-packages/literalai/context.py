from contextvars import ContextVar
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from literalai.observability.step import Step
    from literalai.observability.thread import Thread

active_steps_var = ContextVar[Optional[List["Step"]]]("active_steps", default=None)
active_thread_var = ContextVar[Optional["Thread"]]("active_thread", default=None)
active_root_run_var = ContextVar[Optional["Step"]]("active_root_run_var", default=None)

active_experiment_item_run_id_var = ContextVar[Optional[str]](
    "active_experiment_item_run", default=None
)
