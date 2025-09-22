from typing import Any
from typing import Optional

from questionary import Style
from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.prompts import text
from questionary.question import Question


def password(
    message: str,
    default: str = "",
    validate: Any = None,
    qmark: str = DEFAULT_QUESTION_PREFIX,
    style: Optional[Style] = None,
    **kwargs: Any,
) -> Question:
    """A text input where a user can enter a secret which won't be displayed on the CLI.

    This question type can be used to prompt the user for information
    that should not be shown in the command line. The typed text will be
    replaced with ``*``.

    Example:
        >>> import questionary
        >>> questionary.password("What's your secret?").ask()
        ? What's your secret? ********
        'secret42'

    .. image:: ../images/password.gif

    This is just a really basic example, the prompt can be customised using the
    parameters.

    Args:
        message: Question text.

        default: Default value will be returned if the user just hits
                 enter.

        validate: Require the entered value to pass a validation. The
                  value can not be submitted until the validator accepts
                  it (e.g. to check minimum password length).

                  This can either be a function accepting the input and
                  returning a boolean, or an class reference to a
                  subclass of the prompt toolkit Validator class.

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """

    return text.text(
        message, default, validate, qmark, style, is_password=True, **kwargs
    )
