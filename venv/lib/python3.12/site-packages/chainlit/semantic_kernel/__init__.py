from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from chainlit import Step

if TYPE_CHECKING:
    from semantic_kernel import Kernel
    from semantic_kernel.filters import FunctionInvocationContext
    from semantic_kernel.functions import KernelArguments


class SemanticKernelFilter(BaseModel):
    """Semantic Kernel Filter for Chainlit.

    This filter wraps any function calls that are executed and will capture the input and output of that function
    as a Chainlit Step.

    You can pass your kernel into the constructor, or you can call `add_to_kernel` later.

    Args:
        excluded_plugins: a list of plugin_names that will be excluded from displaying steps.
        excluded_functions: a list of function names that will be excluded from displaying steps.
        kernel: the Kernel to add the filter to. If not provided, you can call `add_to_kernel` later.

    Methods:
        add_to_kernel: this method takes a Kernel and adds the filter to that kernel.
        parse_arguments: this method is called with KernelArguments used for the function
            it can be subclassed to customize how to represent the input arguments.

    Example::

        filter = SemanticKernelFilter(kernel=kernel)

        # or when you create your kernel later on:

        filter = SemanticKernelFilter()
        # ...
        # other code, including kernel creation.
        # ...
        filter.add_to_kernel(kernel)
    """

    excluded_plugins: list[str] | None = None
    excluded_functions: list[str] | None = None

    def __init__(
        self,
        excluded_plugins: list[str] | None = None,
        excluded_functions: list[str] | None = None,
        *,
        kernel: "Kernel | None" = None,
    ) -> None:
        super().__init__(
            excluded_plugins=excluded_plugins, excluded_functions=excluded_functions
        )
        if kernel:
            self.add_to_kernel(kernel)

    def add_to_kernel(self, kernel: "Kernel") -> None:
        """Adds the filter to the provided kernel.

        Args:
            kernel: the Kernel to add the filter to.
        """
        kernel.add_filter("function_invocation", self._function_invocation_filter)  # type: ignore[arg-type]

    def parse_arguments(self, arguments: "KernelArguments") -> dict[str, Any] | str:
        """Parse the KernelArguments used for the function.

        This function can be subclassed to easily adopt how the input arguments are displayed.

        Args:
            arguments: KernelArguments

        Returns:
            a dict or string with the input.
        """
        if len(arguments) == 0:
            return ""
        input_dict = {}
        for key, value in arguments.items():
            if isinstance(value, BaseModel):
                input_dict[key] = value.model_dump(exclude_none=True, by_alias=True)
            else:
                input_dict[key] = value
        return input_dict

    async def _function_invocation_filter(
        self,
        context: "FunctionInvocationContext",
        next: Callable[["FunctionInvocationContext"], Awaitable[None]],
    ):
        if (
            self.excluded_plugins
            and context.function.plugin_name in self.excluded_plugins
        ) or (
            self.excluded_functions and context.function.name in self.excluded_functions
        ):
            await next(context)
            return
        async with Step(
            type="tool", name=context.function.fully_qualified_name
        ) as step:
            step.input = self.parse_arguments(context.arguments)
            await step.send()
            await next(context)
            if context.result:
                step.output = context.result.value
            await step.update()
