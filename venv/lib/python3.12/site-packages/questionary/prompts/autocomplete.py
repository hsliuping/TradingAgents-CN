from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.shortcuts.prompt import PromptSession
from prompt_toolkit.styles import Style

from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.prompts.common import build_validator
from questionary.question import Question
from questionary.styles import merge_styles_default


class WordCompleter(Completer):
    choices_source: Union[List[str], Callable[[], List[str]]]
    ignore_case: bool
    meta_information: Dict[str, Any]
    match_middle: bool

    def __init__(
        self,
        choices: Union[List[str], Callable[[], List[str]]],
        ignore_case: bool = True,
        meta_information: Optional[Dict[str, Any]] = None,
        match_middle: bool = True,
    ) -> None:
        self.choices_source = choices
        self.ignore_case = ignore_case
        self.meta_information = meta_information or {}
        self.match_middle = match_middle

    def _choices(self) -> Iterable[str]:
        return (
            self.choices_source()
            if callable(self.choices_source)
            else self.choices_source
        )

    def _choice_matches(self, word_before_cursor: str, choice: str) -> int:
        """Match index if found, -1 if not."""

        if self.ignore_case:
            choice = choice.lower()

        if self.match_middle:
            return choice.find(word_before_cursor)
        elif choice.startswith(word_before_cursor):
            return 0
        else:
            return -1

    @staticmethod
    def _display_for_choice(choice: str, index: int, word_before_cursor: str) -> HTML:
        return HTML("{}<b><u>{}</u></b>{}").format(
            choice[:index],
            choice[index : index + len(word_before_cursor)],  # noqa: E203
            choice[index + len(word_before_cursor) : len(choice)],  # noqa: E203
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        choices = self._choices()

        # Get word/text before cursor.
        word_before_cursor = document.text_before_cursor

        if self.ignore_case:
            word_before_cursor = word_before_cursor.lower()

        for choice in choices:
            index = self._choice_matches(word_before_cursor, choice)
            if index == -1:
                # didn't find a match
                continue

            display_meta = self.meta_information.get(choice, "")
            display = self._display_for_choice(choice, index, word_before_cursor)

            yield Completion(
                choice,
                start_position=-len(choice),
                display=display.formatted_text,
                display_meta=display_meta,
                style="class:answer",
                selected_style="class:selected",
            )


def autocomplete(
    message: str,
    choices: List[str],
    default: str = "",
    qmark: str = DEFAULT_QUESTION_PREFIX,
    completer: Optional[Completer] = None,
    meta_information: Optional[Dict[str, Any]] = None,
    ignore_case: bool = True,
    match_middle: bool = True,
    complete_style: CompleteStyle = CompleteStyle.COLUMN,
    validate: Any = None,
    style: Optional[Style] = None,
    **kwargs: Any,
) -> Question:
    """Prompt the user to enter a message with autocomplete help.

    Example:
        >>> import questionary
        >>> questionary.autocomplete(
        ...    'Choose ant species',
        ...    choices=[
        ...         'Camponotus pennsylvanicus',
        ...         'Linepithema humile',
        ...         'Eciton burchellii',
        ...         "Atta colombica",
        ...         'Polyergus lucidus',
        ...         'Polyergus rufescens',
        ...    ]).ask()
        ? Choose ant species Atta colombica
        'Atta colombica'

    .. image:: ../images/autocomplete.gif

    This is just a really basic example, the prompt can be customised using the
    parameters.


    Args:
        message: Question text

        choices: Items shown in the selection, this contains items as strings

        default: Default return value (single value).

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``

        completer: A prompt_toolkit :class:`prompt_toolkit.completion.Completion`
                   implementation. If not set, a questionary completer implementation
                   will be used.

        meta_information: A dictionary with information/anything about choices.

        ignore_case: If true autocomplete would ignore case.

        match_middle: If true autocomplete would search in every string position
                      not only in string begin.

        complete_style: How autocomplete menu would be shown, it could be ``COLUMN``
                        ``MULTI_COLUMN`` or ``READLINE_LIKE`` from
                        :class:`prompt_toolkit.shortcuts.CompleteStyle`.

        validate: Require the entered value to pass a validation. The
                  value can not be submitted until the validator accepts
                  it (e.g. to check minimum password length).

                  This can either be a function accepting the input and
                  returning a boolean, or an class reference to a
                  subclass of the prompt toolkit Validator class.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """
    merged_style = merge_styles_default([style])

    def get_prompt_tokens() -> List[Tuple[str, str]]:
        return [("class:qmark", qmark), ("class:question", " {} ".format(message))]

    def get_meta_style(meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if meta:
            for key in meta:
                meta[key] = HTML("<text>{}</text>").format(meta[key])

        return meta

    validator = build_validator(validate)

    if completer is None:
        if not choices:
            raise ValueError("No choices is given, you should use Text question.")
        # use the default completer
        completer = WordCompleter(
            choices,
            ignore_case=ignore_case,
            meta_information=get_meta_style(meta_information),
            match_middle=match_middle,
        )

    p: PromptSession = PromptSession(
        get_prompt_tokens,
        lexer=SimpleLexer("class:answer"),
        style=merged_style,
        completer=completer,
        validator=validator,
        complete_style=complete_style,
        **kwargs,
    )
    p.default_buffer.reset(Document(default))

    return Question(p.app)
