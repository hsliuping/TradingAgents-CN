# -*- coding: utf-8 -*-

import string
from typing import Any
from typing import Dict
from typing import Optional
from typing import Sequence
from typing import Union

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

from questionary import utils
from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.constants import DEFAULT_SELECTED_POINTER
from questionary.prompts import common
from questionary.prompts.common import Choice
from questionary.prompts.common import InquirerControl
from questionary.prompts.common import Separator
from questionary.question import Question
from questionary.styles import merge_styles_default


def select(
    message: str,
    choices: Sequence[Union[str, Choice, Dict[str, Any]]],
    default: Optional[Union[str, Choice, Dict[str, Any]]] = None,
    qmark: str = DEFAULT_QUESTION_PREFIX,
    pointer: Optional[str] = DEFAULT_SELECTED_POINTER,
    style: Optional[Style] = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: Optional[str] = None,
    **kwargs: Any,
) -> Question:
    """A list of items to select **one** option from.

    The user can pick one option and confirm it (if you want to allow
    the user to select multiple options, use :meth:`questionary.checkbox` instead).

    Example:
        >>> import questionary
        >>> questionary.select(
        ...     "What do you want to do?",
        ...     choices=[
        ...         "Order a pizza",
        ...         "Make a reservation",
        ...         "Ask for opening hours"
        ...     ]).ask()
        ? What do you want to do? Order a pizza
        'Order a pizza'

    .. image:: ../images/select.gif

    This is just a really basic example, the prompt can be customised using the
    parameters.


    Args:
        message: Question text

        choices: Items shown in the selection, this can contain :class:`Choice` or
                 or :class:`Separator` objects or simple items as strings. Passing
                 :class:`Choice` objects, allows you to configure the item more
                 (e.g. preselecting it or disabling it).

        default: A value corresponding to a selectable item in the choices,
                 to initially set the pointer position to.

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``.

        pointer: Pointer symbol in front of the currently highlighted element.
                 By default this is a ``»``.
                 Use ``None`` to disable it.

        instruction: A hint on how to navigate the menu.
                     It's ``(Use shortcuts)`` if only ``use_shortcuts`` is set
                     to True, ``(Use arrow keys or shortcuts)`` if ``use_arrow_keys``
                     & ``use_shortcuts`` are set and ``(Use arrow keys)`` by default.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

        use_indicator: Flag to enable the small indicator in front of the
                       list highlighting the current location of the selection
                       cursor.

        use_shortcuts: Allow the user to select items from the list using
                       shortcuts. The shortcuts will be displayed in front of
                       the list items. Arrow keys, j/k keys and shortcuts are
                       not mutually exclusive.

        use_arrow_keys: Allow the user to select items from the list using
                        arrow keys. Arrow keys, j/k keys and shortcuts are not
                        mutually exclusive.

        use_jk_keys: Allow the user to select items from the list using
                     `j` (down) and `k` (up) keys. Arrow keys, j/k keys and
                     shortcuts are not mutually exclusive.

        use_emacs_keys: Allow the user to select items from the list using
                        `Ctrl+N` (down) and `Ctrl+P` (up) keys. Arrow keys, j/k keys,
                        emacs keys and shortcuts are not mutually exclusive.

        use_search_filter: Flag to enable search filtering. Typing some string will
                           filter the choices to keep only the ones that contain the
                           search string.
                           Note that activating this option disables "vi-like"
                           navigation as "j" and "k" can be part of a prefix and
                           therefore cannot be used for navigation

        show_selected: Display current selection choice at the bottom of list.

        show_description: Display description of current selection if available.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """
    if not (use_arrow_keys or use_shortcuts or use_jk_keys or use_emacs_keys):
        raise ValueError(
            (
                "Some option to move the selection is required. "
                "Arrow keys, j/k keys, emacs keys, or shortcuts."
            )
        )

    if use_jk_keys and use_search_filter:
        raise ValueError(
            "Cannot use j/k keys with prefix filter search, since j/k can be part of the prefix."
        )

    if use_shortcuts and use_jk_keys:
        if any(getattr(c, "shortcut_key", "") in ["j", "k"] for c in choices):
            raise ValueError(
                "A choice is trying to register j/k as a "
                "shortcut key when they are in use as arrow keys "
                "disable one or the other."
            )

    if choices is None or len(choices) == 0:
        raise ValueError("A list of choices needs to be provided.")

    if use_shortcuts:
        real_len_of_choices = sum(1 for c in choices if not isinstance(c, Separator))
        if real_len_of_choices > len(InquirerControl.SHORTCUT_KEYS):
            raise ValueError(
                "A list with shortcuts supports a maximum of {} "
                "choices as this is the maximum number "
                "of keyboard shortcuts that are available. You "
                "provided {} choices!"
                "".format(len(InquirerControl.SHORTCUT_KEYS), real_len_of_choices)
            )

    merged_style = merge_styles_default([style])

    ic = InquirerControl(
        choices,
        default,
        pointer=pointer,
        use_indicator=use_indicator,
        use_shortcuts=use_shortcuts,
        show_selected=show_selected,
        show_description=show_description,
        use_arrow_keys=use_arrow_keys,
        initial_choice=default,
    )

    def get_prompt_tokens():
        # noinspection PyListCreation
        tokens = [("class:qmark", qmark), ("class:question", " {} ".format(message))]

        if ic.is_answered:
            if isinstance(ic.get_pointed_at().title, list):
                tokens.append(
                    (
                        "class:answer",
                        "".join([token[1] for token in ic.get_pointed_at().title]),
                    )
                )
            else:
                tokens.append(("class:answer", ic.get_pointed_at().title))
        else:
            if instruction:
                tokens.append(("class:instruction", instruction))
            else:
                if use_shortcuts and use_arrow_keys:
                    instruction_msg = f"(Use shortcuts or arrow keys{', type to filter' if use_search_filter else ''})"
                elif use_shortcuts and not use_arrow_keys:
                    instruction_msg = f"(Use shortcuts{', type to filter' if use_search_filter else ''})"
                else:
                    instruction_msg = f"(Use arrow keys{', type to filter' if use_search_filter else ''})"
                tokens.append(("class:instruction", instruction_msg))

        return tokens

    layout = common.create_inquirer_layout(ic, get_prompt_tokens, **kwargs)

    bindings = KeyBindings()

    @bindings.add(Keys.ControlQ, eager=True)
    @bindings.add(Keys.ControlC, eager=True)
    def _(event):
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    if use_shortcuts:
        # add key bindings for choices
        for i, c in enumerate(ic.choices):
            if c.shortcut_key is None and not c.disabled and not use_arrow_keys:
                raise RuntimeError(
                    "{} does not have a shortcut and arrow keys "
                    "for movement are disabled. "
                    "This choice is not reachable.".format(c.title)
                )
            if isinstance(c, Separator) or c.shortcut_key is None or c.disabled:
                continue

            # noinspection PyShadowingNames
            def _reg_binding(i, keys):
                # trick out late evaluation with a "function factory":
                # https://stackoverflow.com/a/3431699
                @bindings.add(keys, eager=True)
                def select_choice(event):
                    ic.pointed_at = i

            _reg_binding(i, c.shortcut_key)

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
        ic.is_answered = True
        event.app.exit(result=ic.get_pointed_at().value)

    @bindings.add(Keys.Any)
    def other(event):
        """Disallow inserting other text."""

    return Question(
        Application(
            layout=layout,
            key_bindings=bindings,
            style=merged_style,
            **utils.used_kwargs(kwargs, Application.__init__),
        )
    )
