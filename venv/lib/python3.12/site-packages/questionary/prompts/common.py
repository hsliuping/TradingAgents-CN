import inspect
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union

from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Always
from prompt_toolkit.filters import Condition
from prompt_toolkit.filters import IsDone
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import ConditionalContainer
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.layout import HSplit
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError
from prompt_toolkit.validation import Validator

from questionary.constants import DEFAULT_SELECTED_POINTER
from questionary.constants import DEFAULT_STYLE
from questionary.constants import INDICATOR_SELECTED
from questionary.constants import INDICATOR_UNSELECTED
from questionary.constants import INVALID_INPUT

# This is a cut-down version of `prompt_toolkit.formatted_text.AnyFormattedText`
# which does not exist in v2 of prompt_toolkit
FormattedText = Union[
    str,
    List[Tuple[str, str]],
    List[Tuple[str, str, Callable[[Any], None]]],
    None,
]


class Choice:
    """One choice in a :meth:`select`, :meth:`rawselect` or :meth:`checkbox`.

    Args:
        title: Text shown in the selection list.

        value: Value returned, when the choice is selected. If this argument
               is `None` or unset, then the value of `title` is used.

        disabled: If set, the choice can not be selected by the user. The
                  provided text is used to explain, why the selection is
                  disabled.

        checked: Preselect this choice when displaying the options.

        shortcut_key: Key shortcut used to select this item.

        description: Optional description of the item that can be displayed.
    """

    title: FormattedText
    """Display string for the choice"""

    value: Optional[Any]
    """Value of the choice"""

    disabled: Optional[str]
    """Whether the choice can be selected"""

    checked: Optional[bool]
    """Whether the choice is initially selected"""

    __shortcut_key: Optional[Union[str, bool]]

    description: Optional[str]
    """Choice description"""

    def __init__(
        self,
        title: FormattedText,
        value: Optional[Any] = None,
        disabled: Optional[str] = None,
        checked: Optional[bool] = False,
        shortcut_key: Optional[Union[str, bool]] = True,
        description: Optional[str] = None,
    ) -> None:
        self.disabled = disabled
        self.title = title
        self.shortcut_key = shortcut_key
        # self.auto_shortcut is set by the self.shortcut_key setter
        self.checked = checked if checked is not None else False
        self.description = description

        if value is not None:
            self.value = value
        elif isinstance(title, list):
            self.value = "".join([token[1] for token in title])
        else:
            self.value = title

    @staticmethod
    def build(c: Union[str, "Choice", Dict[str, Any]]) -> "Choice":
        """Create a choice object from different representations.

        Args:
            c: Either a :obj:`str`, :class:`Choice` or :obj:`dict` with
               ``name``, ``value``, ``disabled``, ``checked`` and
               ``key`` properties.

        Returns:
            An instance of the :class:`Choice` object.
        """

        if isinstance(c, Choice):
            return c
        elif isinstance(c, str):
            return Choice(c, c)
        else:
            return Choice(
                c.get("name"),
                c.get("value"),
                c.get("disabled", None),
                c.get("checked"),
                c.get("key"),
                c.get("description", None),
            )

    @property
    def shortcut_key(self) -> Optional[Union[str, bool]]:
        """A shortcut key for the choice"""
        return self.__shortcut_key

    @shortcut_key.setter
    def shortcut_key(self, key: Optional[Union[str, bool]]):
        if key is not None:
            if isinstance(key, bool):
                self.__auto_shortcut = key
                self.__shortcut_key = None
            else:
                self.__shortcut_key = str(key)
                self.__auto_shortcut = False
        else:
            self.__shortcut_key = None
            self.__auto_shortcut = True

    @shortcut_key.deleter
    def shortcut_key(self):
        self.__shortcut_key = None
        self.__auto_shortcut = True

    def get_shortcut_title(self):
        if self.shortcut_key is None:
            return "-) "
        else:
            return "{}) ".format(self.shortcut_key)

    @property
    def auto_shortcut(self) -> bool:
        """Whether to assign a shortcut key to the choice

        Keys are assigned starting with numbers and proceeding
        through the ASCII alphabet.
        """
        return self.__auto_shortcut

    @auto_shortcut.setter
    def auto_shortcut(self, should_assign: bool):
        self.__auto_shortcut = should_assign
        if self.__auto_shortcut:
            self.__shortcut_key = None

    @auto_shortcut.deleter
    def auto_shortcut(self):
        self.__auto_shortcut = False


class Separator(Choice):
    """Used to space/separate choices group."""

    default_separator: str = "-" * 15
    """The default separator used if none is specified"""

    line: str
    """The string being used as a separator"""

    def __init__(self, line: Optional[str] = None) -> None:
        """Create a separator in a list.

        Args:
            line: Text to be displayed in the list, by default uses ``---``.
        """

        self.line = line or self.default_separator
        super().__init__(self.line, None, "-")


class InquirerControl(FormattedTextControl):
    SHORTCUT_KEYS = [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "0",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
    ]

    choices: List[Choice]
    default: Optional[Union[str, Choice, Dict[str, Any]]]
    selected_options: List[Any]
    search_filter: Union[str, None] = None
    use_indicator: bool
    use_shortcuts: bool
    use_arrow_keys: bool
    pointer: Optional[str]
    pointed_at: int
    is_answered: bool
    show_description: bool

    def __init__(
        self,
        choices: Sequence[Union[str, Choice, Dict[str, Any]]],
        default: Optional[Union[str, Choice, Dict[str, Any]]] = None,
        pointer: Optional[str] = DEFAULT_SELECTED_POINTER,
        use_indicator: bool = True,
        use_shortcuts: bool = False,
        show_selected: bool = False,
        show_description: bool = True,
        use_arrow_keys: bool = True,
        initial_choice: Optional[Union[str, Choice, Dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        self.use_indicator = use_indicator
        self.use_shortcuts = use_shortcuts
        self.show_selected = show_selected
        self.show_description = show_description
        self.use_arrow_keys = use_arrow_keys
        self.default = default
        self.pointer = pointer

        if isinstance(default, Choice):
            default = default.value

        choices_values = [
            choice.value for choice in choices if isinstance(choice, Choice)
        ]

        if (
            default is not None
            and default not in choices
            and default not in choices_values
        ):
            raise ValueError(
                f"Invalid `default` value passed. The value (`{default}`) "
                f"does not exist in the set of choices. Please make sure the "
                f"default value is one of the available choices."
            )

        if initial_choice is None:
            pointed_at = None
        elif initial_choice in choices:
            pointed_at = choices.index(initial_choice)
        elif initial_choice in choices_values:
            for k, choice in enumerate(choices):
                if isinstance(choice, Choice):
                    if choice.value == initial_choice:
                        pointed_at = k
                        break

        else:
            raise ValueError(
                f"Invalid `initial_choice` value passed. The value "
                f"(`{initial_choice}`) does not exist in "
                f"the set of choices. Please make sure the initial value is "
                f"one of the available choices."
            )

        self.is_answered = False
        self.choices = []
        self.submission_attempted = False
        self.error_message = None
        self.selected_options = []
        self.found_in_search = False

        self._init_choices(choices, pointed_at)
        self._assign_shortcut_keys()

        super().__init__(self._get_choice_tokens, **kwargs)

        if not self.is_selection_valid():
            raise ValueError(
                f"Invalid 'initial_choice' value ('{initial_choice}'). "
                f"It must be a selectable value."
            )

    def _is_selected(self, choice: Choice):
        if isinstance(self.default, Choice):
            compare_default = self.default == choice
        else:
            compare_default = self.default == choice.value
        return choice.checked or compare_default and self.default is not None

    def _assign_shortcut_keys(self):
        available_shortcuts = self.SHORTCUT_KEYS[:]

        # first, make sure we do not double assign a shortcut
        for c in self.choices:
            if c.shortcut_key is not None:
                if c.shortcut_key in available_shortcuts:
                    available_shortcuts.remove(c.shortcut_key)
                else:
                    raise ValueError(
                        "Invalid shortcut '{}'"
                        "for choice '{}'. Shortcuts "
                        "should be single characters or numbers. "
                        "Make sure that all your shortcuts are "
                        "unique.".format(c.shortcut_key, c.title)
                    )

        shortcut_idx = 0
        for c in self.choices:
            if c.auto_shortcut and not c.disabled:
                c.shortcut_key = available_shortcuts[shortcut_idx]
                shortcut_idx += 1

            if shortcut_idx == len(available_shortcuts):
                break  # fail gracefully if we run out of shortcuts

    def _init_choices(
        self,
        choices: Sequence[Union[str, Choice, Dict[str, Any]]],
        pointed_at: Optional[int],
    ):
        # helper to convert from question format to internal format
        self.choices = []

        if pointed_at is not None:
            self.pointed_at = pointed_at

        for i, c in enumerate(choices):
            choice = Choice.build(c)

            if self._is_selected(choice):
                self.selected_options.append(choice.value)

            if pointed_at is None and not choice.disabled:
                # find the first (available) choice
                self.pointed_at = pointed_at = i

            self.choices.append(choice)

    @property
    def filtered_choices(self):
        if not self.search_filter:
            return self.choices
        filtered = [
            c for c in self.choices if self.search_filter.lower() in c.title.lower()
        ]
        self.found_in_search = len(filtered) > 0
        return filtered if self.found_in_search else self.choices

    @property
    def choice_count(self) -> int:
        return len(self.filtered_choices)

    def _get_choice_tokens(self):
        tokens = []

        def append(index: int, choice: Choice):
            # use value to check if option has been selected
            selected = choice.value in self.selected_options

            if index == self.pointed_at:
                if self.pointer is not None:
                    tokens.append(("class:pointer", " {} ".format(self.pointer)))
                else:
                    tokens.append(("class:text", " " * 3))

                tokens.append(("[SetCursorPosition]", ""))
            else:
                pointer_length = len(self.pointer) if self.pointer is not None else 1
                tokens.append(("class:text", " " * (2 + pointer_length)))

            if isinstance(choice, Separator):
                tokens.append(("class:separator", "{}".format(choice.title)))
            elif choice.disabled:  # disabled
                if isinstance(choice.title, list):
                    tokens.append(
                        ("class:selected" if selected else "class:disabled", "- ")
                    )
                    tokens.extend(choice.title)
                else:
                    tokens.append(
                        (
                            "class:selected" if selected else "class:disabled",
                            "- {}".format(choice.title),
                        )
                    )

                tokens.append(
                    (
                        "class:selected" if selected else "class:disabled",
                        "{}".format(
                            ""
                            if isinstance(choice.disabled, bool)
                            else " ({})".format(choice.disabled)
                        ),
                    )
                )
            else:
                shortcut = choice.get_shortcut_title() if self.use_shortcuts else ""

                if selected:
                    if self.use_indicator:
                        indicator = INDICATOR_SELECTED + " "
                    else:
                        indicator = ""

                    tokens.append(("class:selected", "{}".format(indicator)))
                else:
                    if self.use_indicator:
                        indicator = INDICATOR_UNSELECTED + " "
                    else:
                        indicator = ""

                    tokens.append(("class:text", "{}".format(indicator)))

                if isinstance(choice.title, list):
                    tokens.extend(choice.title)
                elif selected:
                    tokens.append(
                        ("class:selected", "{}{}".format(shortcut, choice.title))
                    )
                elif index == self.pointed_at:
                    tokens.append(
                        ("class:highlighted", "{}{}".format(shortcut, choice.title))
                    )
                else:
                    tokens.append(("class:text", "{}{}".format(shortcut, choice.title)))

            tokens.append(("", "\n"))

        # prepare the select choices
        for i, c in enumerate(self.filtered_choices):
            append(i, c)

        current = self.get_pointed_at()

        if self.show_selected:
            answer = current.get_shortcut_title() if self.use_shortcuts else ""

            answer += (
                current.title if isinstance(current.title, str) else current.title[0][1]
            )

            tokens.append(("class:text", "  Answer: {}".format(answer)))

        show_description = self.show_description and current.description is not None
        if show_description:
            tokens.append(
                ("class:text", "  Description: {}".format(current.description))
            )

        if not (self.show_selected or show_description):
            tokens.pop()  # Remove last newline.

        return tokens

    def is_selection_a_separator(self) -> bool:
        selected = self.choices[self.pointed_at]
        return isinstance(selected, Separator)

    def is_selection_disabled(self) -> Optional[str]:
        return self.choices[self.pointed_at].disabled

    def is_selection_valid(self) -> bool:
        return not self.is_selection_disabled() and not self.is_selection_a_separator()

    def select_previous(self) -> None:
        self.pointed_at = (self.pointed_at - 1) % self.choice_count

    def select_next(self) -> None:
        self.pointed_at = (self.pointed_at + 1) % self.choice_count

    def get_pointed_at(self) -> Choice:
        return self.filtered_choices[self.pointed_at]

    def get_selected_values(self) -> List[Choice]:
        # get values not labels
        return [
            c
            for c in self.choices
            if (not isinstance(c, Separator) and c.value in self.selected_options)
        ]

    def add_search_character(self, char: Keys) -> None:
        """Adds a character to the search filter"""
        if char == Keys.Backspace:
            self.remove_search_character()
        else:
            if self.search_filter is None:
                self.search_filter = str(char)
            else:
                self.search_filter += str(char)

        # Make sure that the selection is in the bounds of the filtered list
        self.pointed_at = 0

    def remove_search_character(self) -> None:
        if self.search_filter and len(self.search_filter) > 1:
            self.search_filter = self.search_filter[:-1]
        else:
            self.search_filter = None

    def get_search_string_tokens(self):
        if self.search_filter is None:
            return None

        return [
            ("", "\n"),
            ("class:question-mark", "/ "),
            (
                "class:search_success" if self.found_in_search else "class:search_none",
                self.search_filter,
            ),
            ("class:question-mark", "..."),
        ]


def build_validator(validate: Any) -> Optional[Validator]:
    if validate:
        if inspect.isclass(validate) and issubclass(validate, Validator):
            return validate()
        elif isinstance(validate, Validator):
            return validate
        elif callable(validate):

            class _InputValidator(Validator):
                def validate(self, document):
                    verdict = validate(document.text)
                    if verdict is not True:
                        if verdict is False:
                            verdict = INVALID_INPUT
                        raise ValidationError(
                            message=verdict, cursor_position=len(document.text)
                        )

            return _InputValidator()
    return None


def _fix_unecessary_blank_lines(ps: PromptSession) -> None:
    """This is a fix for additional empty lines added by prompt toolkit.

    This assumes the layout of the default session doesn't change, if it
    does, this needs an update."""

    default_container = ps.layout.container

    default_buffer_window = (
        default_container.get_children()[0].content.get_children()[1].content  # type: ignore[attr-defined]
    )

    assert isinstance(default_buffer_window, Window)
    # this forces the main window to stay as small as possible, avoiding
    # empty lines in selections
    default_buffer_window.dont_extend_height = Always()
    default_buffer_window.always_hide_cursor = Always()


def create_inquirer_layout(
    ic: InquirerControl,
    get_prompt_tokens: Callable[[], List[Tuple[str, str]]],
    **kwargs: Any,
) -> Layout:
    """Create a layout combining question and inquirer selection."""

    ps: PromptSession = PromptSession(
        get_prompt_tokens, reserve_space_for_menu=0, **kwargs
    )
    _fix_unecessary_blank_lines(ps)

    @Condition
    def has_search_string():
        return ic.get_search_string_tokens() is not None

    validation_prompt: PromptSession = PromptSession(
        bottom_toolbar=lambda: ic.error_message, **kwargs
    )

    return Layout(
        HSplit(
            [
                ps.layout.container,
                ConditionalContainer(Window(ic), filter=~IsDone()),
                ConditionalContainer(
                    Window(
                        height=LayoutDimension.exact(2),
                        content=FormattedTextControl(ic.get_search_string_tokens),
                    ),
                    filter=has_search_string & ~IsDone(),
                ),
                ConditionalContainer(
                    validation_prompt.layout.container,
                    filter=Condition(lambda: ic.error_message is not None),
                ),
            ]
        )
    )


def print_formatted_text(text: str, style: Optional[str] = None, **kwargs: Any) -> None:
    """Print formatted text.

    Sometimes you want to spice up your printed messages a bit,
    :meth:`questionary.print` is a helper to do just that.

    Example:

        >>> import questionary
        >>> questionary.print("Hello World 🦄", style="bold italic fg:darkred")
        Hello World 🦄

    .. image:: ../images/print.gif

    Args:
        text: Text to be printed.
        style: Style used for printing. The style argument uses the
            prompt :ref:`toolkit style strings <prompt_toolkit:styling>`.
    """
    from prompt_toolkit import print_formatted_text as pt_print
    from prompt_toolkit.formatted_text import FormattedText as FText

    if style is not None:
        text_style = Style([("text", style)])
    else:
        text_style = DEFAULT_STYLE

    pt_print(FText([("class:text", text)]), style=text_style, **kwargs)
