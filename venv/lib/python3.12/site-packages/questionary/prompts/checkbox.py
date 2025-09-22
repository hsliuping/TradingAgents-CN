import string
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

from questionary import utils
from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.constants import DEFAULT_SELECTED_POINTER
from questionary.constants import INVALID_INPUT
from questionary.prompts import common
from questionary.prompts.common import Choice
from questionary.prompts.common import InquirerControl
from questionary.prompts.common import Separator
from questionary.question import Question
from questionary.styles import merge_styles_default


def checkbox(
    message: str,
    choices: Sequence[Union[str, Choice, Dict[str, Any]]],
    default: Optional[str] = None,
    validate: Callable[[List[str]], Union[bool, str]] = lambda a: True,
    qmark: str = DEFAULT_QUESTION_PREFIX,
    pointer: Optional[str] = DEFAULT_SELECTED_POINTER,
    style: Optional[Style] = None,
    initial_choice: Optional[Union[str, Choice, Dict[str, Any]]] = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: Union[str, bool, None] = False,
    instruction: Optional[str] = None,
    show_description: bool = True,
    **kwargs: Any,
) -> Question:
    """Ask the user to select from a list of items.

    This is a multiselect, the user can choose one, none or many of the
    items.

    Example:
        >>> import questionary
        >>> questionary.checkbox(
        ...    'Select toppings',
        ...    choices=[
        ...        "Cheese",
        ...        "Tomato",
        ...        "Pineapple",
        ...    ]).ask()
        ? Select toppings done (2 selections)
        ['Cheese', 'Pineapple']

    .. image:: ../images/checkbox.gif

    This is just a really basic example, the prompt can be customised using the
    parameters.


    Args:
        message: Question text

        choices: Items shown in the selection, this can contain :class:`Choice` or
                 or :class:`Separator` objects or simple items as strings. Passing
                 :class:`Choice` objects, allows you to configure the item more
                 (e.g. preselecting it or disabling it).

        default: Default return value (single value). If you want to preselect
                 multiple items, use ``Choice("foo", checked=True)`` instead.

        validate: Require the entered value to pass a validation. The
                  value can not be submitted until the validator accepts
                  it (e.g. to check minimum password length).

                  This should be a function accepting the input and
                  returning a boolean. Alternatively, the return value
                  may be a string (indicating failure), which contains
                  the error message to be displayed.

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``.

        pointer: Pointer symbol in front of the currently highlighted element.
                 By default this is a ``»``.
                 Use ``None`` to disable it.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

        initial_choice: A value corresponding to a selectable item in the choices,
                        to initially set the pointer position to.

        use_arrow_keys: Allow the user to select items from the list using
                        arrow keys.

        use_jk_keys: Allow the user to select items from the list using
                     `j` (down) and `k` (up) keys.

        use_emacs_keys: Allow the user to select items from the list using
                        `Ctrl+N` (down) and `Ctrl+P` (up) keys.

        use_search_filter: Flag to enable search filtering. Typing some string will
                           filter the choices to keep only the ones that contain the
                           search string.
                           Note that activating this option disables "vi-like"
                           navigation as "j" and "k" can be part of a prefix and
                           therefore cannot be used for navigation

        instruction: A message describing how to navigate the menu.

        show_description: Display description of current selection if available.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """

    if not (use_arrow_keys or use_jk_keys or use_emacs_keys):
        raise ValueError(
            "Some option to move the selection is required. Arrow keys or j/k or "
            "Emacs keys."
        )

    if use_jk_keys and use_search_filter:
        raise ValueError(
            "Cannot use j/k keys with prefix filter search, since j/k can be part of the prefix."
        )

    merged_style = merge_styles_default(
        [
            # Disable the default inverted colours bottom-toolbar behaviour (for
            # the error message). However it can be re-enabled with a custom
            # style.
            Style([("bottom-toolbar", "noreverse")]),
            style,
        ]
    )

    if not callable(validate):
        raise ValueError("validate must be callable")

    ic = InquirerControl(
        choices,
        default,
        pointer=pointer,
        initial_choice=initial_choice,
        show_description=show_description,
    )

    def get_prompt_tokens() -> List[Tuple[str, str]]:
        tokens = []

        tokens.append(("class:qmark", qmark))
        tokens.append(("class:question", " {} ".format(message)))

        if ic.is_answered:
            nbr_selected = len(ic.selected_options)
            if nbr_selected == 0:
                tokens.append(("class:answer", "done"))
            elif nbr_selected == 1:
                if isinstance(ic.get_selected_values()[0].title, list):
                    ts = ic.get_selected_values()[0].title
                    tokens.append(
                        (
                            "class:answer",
                            "".join([token[1] for token in ts]),  # type:ignore
                        )
                    )
                else:
                    tokens.append(
                        (
                            "class:answer",
                            "[{}]".format(ic.get_selected_values()[0].title),
                        )
                    )
            else:
                tokens.append(
                    ("class:answer", "done ({} selections)".format(nbr_selected))
                )
        else:
            if instruction is not None:
                tokens.append(("class:instruction", instruction))
            else:
                tokens.append(
                    (
                        "class:instruction",
                        "(Use arrow keys to move, "
                        "<space> to select, "
                        f"<{'ctrl-a' if use_search_filter else 'a'}> to toggle, "
                        f"<{'ctrl-a' if use_search_filter else 'i'}> to invert"
                        f"{', type to filter' if use_search_filter else ''})",
                    )
                )
        return tokens

    def get_selected_values() -> List[Any]:
        return [c.value for c in ic.get_selected_values()]

    def perform_validation(selected_values: List[str]) -> bool:
        verdict = validate(selected_values)
        valid = verdict is True

        if not valid:
            if verdict is False:
                error_text = INVALID_INPUT
            else:
                error_text = str(verdict)

            error_message = FormattedText([("class:validation-toolbar", error_text)])

        ic.error_message = (
            error_message if not valid and ic.submission_attempted else None  # type: ignore[assignment]
        )

        return valid

    layout = common.create_inquirer_layout(ic, get_prompt_tokens, **kwargs)

    bindings = KeyBindings()

    @bindings.add(Keys.ControlQ, eager=True)
    @bindings.add(Keys.ControlC, eager=True)
    def _(event):
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    @bindings.add(" ", eager=True)
    def toggle(_event):
        pointed_choice = ic.get_pointed_at().value
        if pointed_choice in ic.selected_options:
            ic.selected_options.remove(pointed_choice)
        else:
            ic.selected_options.append(pointed_choice)

        perform_validation(get_selected_values())

    @bindings.add(Keys.ControlI if use_search_filter else "i", eager=True)
    def invert(_event):
        inverted_selection = [
            c.value
            for c in ic.choices
            if not isinstance(c, Separator)
            and c.value not in ic.selected_options
            and not c.disabled
        ]
        ic.selected_options = inverted_selection

        perform_validation(get_selected_values())

    @bindings.add(Keys.ControlA if use_search_filter else "a", eager=True)
    def all(_event):
        all_selected = True  # all choices have been selected
        for c in ic.choices:
            if (
                not isinstance(c, Separator)
                and c.value not in ic.selected_options
                and not c.disabled
            ):
                # add missing ones
                ic.selected_options.append(c.value)
                all_selected = False
        if all_selected:
            ic.selected_options = []

        perform_validation(get_selected_values())

    def move_cursor_down(event):
        ic.select_next()
        while not ic.is_selection_valid():
            ic.select_next()

    def move_cursor_up(event):
        ic.select_previous()
        while not ic.is_selection_valid():
            ic.select_previous()

    if use_search_filter:

        def search_filter(event):
            ic.add_search_character(event.key_sequence[0].key)

        for character in string.printable:
            if character in string.whitespace:
                continue
            bindings.add(character, eager=True)(search_filter)
        bindings.add(Keys.Backspace, eager=True)(search_filter)

    if use_arrow_keys:
        bindings.add(Keys.Down, eager=True)(move_cursor_down)
        bindings.add(Keys.Up, eager=True)(move_cursor_up)

    if use_jk_keys:
        bindings.add("j", eager=True)(move_cursor_down)
        bindings.add("k", eager=True)(move_cursor_up)

    if use_emacs_keys:
        bindings.add(Keys.ControlN, eager=True)(move_cursor_down)
        bindings.add(Keys.ControlP, eager=True)(move_cursor_up)

    @bindings.add(Keys.ControlM, eager=True)
    def set_answer(event):
        selected_values = get_selected_values()
        ic.submission_attempted = True

        if perform_validation(selected_values):
            ic.is_answered = True
            event.app.exit(result=selected_values)

    @bindings.add(Keys.Any)
    def other(_event):
        """Disallow inserting other text."""

    return Question(
        Application(
            layout=layout,
            key_bindings=bindings,
            style=merged_style,
            **utils.used_kwargs(kwargs, Application.__init__),
        )
    )
