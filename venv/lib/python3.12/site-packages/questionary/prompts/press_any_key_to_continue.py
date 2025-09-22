from typing import Any
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

from questionary.question import Question
from questionary.styles import merge_styles_default


def press_any_key_to_continue(
    message: Optional[str] = None,
    style: Optional[Style] = None,
    **kwargs: Any,
):
    """Wait until user presses any key to continue.

    Example:
        >>> import questionary
        >>> questionary.press_any_key_to_continue().ask()
         Press any key to continue...
        ''

    Args:
        message: Question text. Defaults to ``"Press any key to continue..."``

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """
    merged_style = merge_styles_default([style])

    if message is None:
        message = "Press any key to continue..."

    def get_prompt_tokens():
        tokens = []

        tokens.append(("class:question", f" {message} "))

        return to_formatted_text(tokens)

    def exit_with_result(event):
        event.app.exit(result=None)

    bindings = KeyBindings()

    @bindings.add(Keys.Any)
    def any_key(event):
        exit_with_result(event)

    return Question(
        PromptSession(
            get_prompt_tokens, key_bindings=bindings, style=merged_style, **kwargs
        ).app
    )
