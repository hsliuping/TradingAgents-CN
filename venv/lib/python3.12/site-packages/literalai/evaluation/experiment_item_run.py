import inspect
import uuid
from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional

from literalai.context import active_experiment_item_run_id_var
from literalai.environment import EnvContextManager
from literalai.observability.step import StepContextManager

if TYPE_CHECKING:
    from literalai.client import BaseLiteralClient


class ExperimentItemRunContextManager(EnvContextManager, StepContextManager):
    def __init__(
        self,
        client: "BaseLiteralClient",
    ):
        self.client = client
        EnvContextManager.__init__(self, client=client, env="experiment")

    def __call__(self, func):
        return experiment_item_run_decorator(
            self.client,
            func=func,
            ctx_manager=self,
        )

    async def __aenter__(self):
        id = str(uuid.uuid4())
        StepContextManager.__init__(
            self, client=self.client, name="Experiment Run", type="run", id=id
        )
        active_experiment_item_run_id_var.set(id)
        await EnvContextManager.__aenter__(self)
        step = await StepContextManager.__aenter__(self)
        return step

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await StepContextManager.__aexit__(self, exc_type, exc_val, exc_tb)
        await self.client.event_processor.aflush()
        await EnvContextManager.__aexit__(self, exc_type, exc_val, exc_tb)
        active_experiment_item_run_id_var.set(None)

    def __enter__(self):
        id = str(uuid.uuid4())
        StepContextManager.__init__(
            self, client=self.client, name="Experiment Run", type="run", id=id
        )
        active_experiment_item_run_id_var.set(id)
        EnvContextManager.__enter__(self)
        step = StepContextManager.__enter__(self)
        return step

    def __exit__(self, exc_type, exc_val, exc_tb):
        StepContextManager.__exit__(self, exc_type, exc_val, exc_tb)
        self.client.event_processor.flush()
        EnvContextManager.__exit__(self, exc_type, exc_val, exc_tb)
        active_experiment_item_run_id_var.set(None)


def experiment_item_run_decorator(
    client: "BaseLiteralClient",
    func: Callable,
    ctx_manager: Optional[ExperimentItemRunContextManager] = None,
    **decorator_kwargs,
):
    if not ctx_manager:
        ctx_manager = ExperimentItemRunContextManager(
            client=client,
            **decorator_kwargs,
        )

    # Handle async decorator
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with ctx_manager:
                result = await func(*args, **kwargs)
                return result

        return async_wrapper
    else:
        # Handle sync decorator
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with ctx_manager:
                return func(*args, **kwargs)

        return sync_wrapper
