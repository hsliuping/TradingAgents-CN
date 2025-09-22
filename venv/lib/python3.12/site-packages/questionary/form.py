from typing import Any
from typing import Dict
from typing import NamedTuple
from typing import Sequence

from questionary.constants import DEFAULT_KBI_MESSAGE
from questionary.question import Question


class FormField(NamedTuple):
    """
    Represents a question within a form

    Args:
        key: The name of the form field.
        question: The question to ask in the form field.
    """

    key: str
    question: Question


def form(**kwargs: Question) -> "Form":
    """Create a form with multiple questions.

    The parameter name of a question will be the key for the answer in
    the returned dict.

    Args:
        kwargs: Questions to ask in the form.
    """
    return Form(*(FormField(k, q) for k, q in kwargs.items()))


class Form:
    """Multi question prompts. Questions are asked one after another.

    All the answers are returned as a dict with one entry per question.

    This class should not be invoked directly, instead use :func:`form`.
    """

    form_fields: Sequence[FormField]

    def __init__(self, *form_fields: FormField) -> None:
        self.form_fields = form_fields

    def unsafe_ask(self, patch_stdout: bool = False) -> Dict[str, Any]:
        """Ask the questions synchronously and return user response.

        Does not catch keyboard interrupts.

        Args:
            patch_stdout: Ensure that the prompt renders correctly if other threads
                          are printing to stdout.

        Returns:
            The answers from the form.
        """
        return {f.key: f.question.unsafe_ask(patch_stdout) for f in self.form_fields}

    async def unsafe_ask_async(self, patch_stdout: bool = False) -> Dict[str, Any]:
        """Ask the questions using asyncio and return user response.

        Does not catch keyboard interrupts.

        Args:
            patch_stdout: Ensure that the prompt renders correctly if other threads
                          are printing to stdout.

        Returns:
            The answers from the form.
        """
        return {
            f.key: await f.question.unsafe_ask_async(patch_stdout)
            for f in self.form_fields
        }

    def ask(
        self, patch_stdout: bool = False, kbi_msg: str = DEFAULT_KBI_MESSAGE
    ) -> Dict[str, Any]:
        """Ask the questions synchronously and return user response.

        Args:
            patch_stdout: Ensure that the prompt renders correctly if other threads
                          are printing to stdout.

            kbi_msg: The message to be printed on a keyboard interrupt.

        Returns:
            The answers from the form.
        """
        try:
            return self.unsafe_ask(patch_stdout)
        except KeyboardInterrupt:
            print(kbi_msg)
            return {}

    async def ask_async(
        self, patch_stdout: bool = False, kbi_msg: str = DEFAULT_KBI_MESSAGE
    ) -> Dict[str, Any]:
        """Ask the questions using asyncio and return user response.

        Args:
            patch_stdout: Ensure that the prompt renders correctly if other threads
                          are printing to stdout.

            kbi_msg: The message to be printed on a keyboard interrupt.

        Returns:
            The answers from the form.
        """
        try:
            return await self.unsafe_ask_async(patch_stdout)
        except KeyboardInterrupt:
            print(kbi_msg)
            return {}
