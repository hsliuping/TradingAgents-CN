from typing import Any
from typing import Dict
from typing import Optional
from typing import Sequence
from typing import Union

from prompt_toolkit.styles import Style

from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.constants import DEFAULT_SELECTED_POINTER
from questionary.prompts import select
from questionary.prompts.common import Choice
from questionary.question import Question


def rawselect(
    message: str,
    choices: Sequence[Union[str, Choice, Dict[str, Any]]],
    default: Optional[str] = None,
    qmark: str = DEFAULT_QUESTION_PREFIX,
    pointer: Optional[str] = DEFAULT_SELECTED_POINTER,
    style: Optional[Style] = None,
    **kwargs: Any,
) -> Question:
    """Ask the user to select one item from a list of choices using shortcuts.

    The user can only select one option.

    Example:
        >>> import questionary
        >>> questionary.rawselect(
        ...     "What do you want to do?",
        ...     choices=[
        ...         "Order a pizza",
        ...         "Make a reservation",
        ...         "Ask for opening hours"
        ...     ]).ask()
        ? What do you want to do? Order a pizza
        'Order a pizza'

    .. image:: ../images/rawselect.gif

    This is just a really basic example, the prompt can be customised using the
    parameters.

    Args:
        message: Question text.

        choices: Items shown in the selection, this can contain :class:`Choice` or
                 or :class:`Separator` objects or simple items as strings. Passing
                 :class:`Choice` objects, allows you to configure the item more
                 (e.g. preselecting it or disabling it).

        default: Default return value (single value).

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``.

        pointer: Pointer symbol in front of the currently highlighted element.
                 By default this is a ``»``.
                 Use ``None`` to disable it.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """
    return select.select(
        message,
        choices,
        default,
        qmark,
        pointer,
        style,
        use_shortcuts=True,
        use_arrow_keys=False,
        **kwargs,
    )
