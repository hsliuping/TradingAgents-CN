import os
from typing import Any
from typing import Callable
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.completion import Completion
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.completion.base import Completer
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.shortcuts.prompt import PromptSession
from prompt_toolkit.styles import Style

from questionary.constants import DEFAULT_QUESTION_PREFIX
from questionary.prompts.common import build_validator
from questionary.question import Question
from questionary.styles import merge_styles_default


class GreatUXPathCompleter(PathCompleter):
    """Wraps :class:`prompt_toolkit.completion.PathCompleter`.

    Makes sure completions for directories end with a path separator. Also make sure
    the right path separator is used. Checks if `get_paths` returns list of existing
    directories.
    """

    def __init__(
        self,
        only_directories: bool = False,
        get_paths: Optional[Callable[[], List[str]]] = None,
        file_filter: Optional[Callable[[str], bool]] = None,
        min_input_len: int = 0,
        expanduser: bool = False,
    ) -> None:
        """Adds validation of 'get_paths' to :class:`prompt_toolkit.completion.PathCompleter`.

        Args:
            only_directories (bool): If True, only directories will be
                returned, but no files. Defaults to False.
            get_paths (Callable[[], List[str]], optional): Callable which
                returns a list of directories to look into when the user enters a
                relative path. If None, set to (lambda: ["."]). Defaults to None.
            file_filter (Callable[[str], bool], optional): Callable which
                takes a filename and returns whether this file should show up in the
                completion. ``None`` when no filtering has to be done. Defaults to None.
            min_input_len (int): Don't do autocompletion when the input string
                is shorter. Defaults to 0.
            expanduser (bool): If True, tilde (~) is expanded. Defaults to
                False.

        Raises:
            ValueError: If any of the by `get_paths` returned directories does not
                exist.
        """
        # if get_paths is None, make it return the current working dir
        get_paths = get_paths or (lambda: ["."])
        # validation of get_paths
        for current_path in get_paths():
            if not os.path.isdir(current_path):
                raise (
                    ValueError(
                        "\n Completer for file paths 'get_paths' must return only existing directories, but"
                        f" '{current_path}' does not exist."
                    )
                )
        # call PathCompleter __init__
        super().__init__(
            only_directories=only_directories,
            get_paths=get_paths,
            file_filter=file_filter,
            min_input_len=min_input_len,
            expanduser=expanduser,
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions.

        Wraps :class:`prompt_toolkit.completion.PathCompleter`. Makes sure completions
        for directories end with a path separator. Also make sure the right path
        separator is used.
        """
        completions = super(GreatUXPathCompleter, self).get_completions(
            document, complete_event
        )

        for completion in completions:
            # check if the display value ends with a path separator.
            # first check if display is properly set
            styled_display = completion.display[0]
            # styled display is a formatted text (a tuple of the text and its style)
            # second tuple entry is the text
            if styled_display[1][-1] == "/":
                # replace separator with the OS specific one
                display_text = styled_display[1][:-1] + os.path.sep
                # update the styled display with the modified text
                completion.display[0] = (styled_display[0], display_text)
                # append the separator to the text as well - unclear why the normal
                # path completer omits it from the text. this improves UX for the
                # user, as they don't need to type the separator after auto-completing
                # a directory
                completion.text += os.path.sep
            yield completion


def path(
    message: str,
    default: str = "",
    qmark: str = DEFAULT_QUESTION_PREFIX,
    validate: Any = None,
    completer: Optional[Completer] = None,
    style: Optional[Style] = None,
    only_directories: bool = False,
    get_paths: Optional[Callable[[], List[str]]] = None,
    file_filter: Optional[Callable[[str], bool]] = None,
    complete_style: CompleteStyle = CompleteStyle.MULTI_COLUMN,
    **kwargs: Any,
) -> Question:
    """A text input for a file or directory path with autocompletion enabled.

    Example:
        >>> import questionary
        >>> questionary.path(
        >>>    "What's the path to the projects version file?"
        >>> ).ask()
        ? What's the path to the projects version file? ./pyproject.toml
        './pyproject.toml'

    .. image:: ../images/path.gif

    This is just a really basic example, the prompt can be customized using the
    parameters.

    Args:
        message: Question text.

        default: Default return value (single value).

        qmark: Question prefix displayed in front of the question.
               By default this is a ``?``.

        complete_style: How autocomplete menu would be shown, it could be ``COLUMN``
                        ``MULTI_COLUMN`` or ``READLINE_LIKE`` from
                        :class:`prompt_toolkit.shortcuts.CompleteStyle`.

        validate: Require the entered value to pass a validation. The
                  value can not be submitted until the validator accepts
                  it (e.g. to check minimum password length).

                  This can either be a function accepting the input and
                  returning a boolean, or an class reference to a
                  subclass of the prompt toolkit Validator class.

        completer: A custom completer to use in the prompt. For more information,
                   see `this <https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#a-custom-completer>`_.

        style: A custom color and style for the question parts. You can
               configure colors as well as font types for different elements.

        only_directories: Only show directories in auto completion. This option
                          does not do anything if a custom ``completer`` is
                          passed.

        get_paths: Set a callable to generate paths to traverse for suggestions. This option
                   does not do anything if a custom ``completer`` is
                   passed.

        file_filter: Optional callable to filter suggested paths. Only paths
                     where the passed callable evaluates to ``True`` will show up in
                     the suggested paths. This does not validate the typed path, e.g.
                     it is still possible for the user to enter a path manually, even
                     though this filter evaluates to ``False``. If in addition to
                     filtering suggestions you also want to validate the result, use
                     ``validate`` in combination with the ``file_filter``.

    Returns:
        :class:`Question`: Question instance, ready to be prompted (using ``.ask()``).
    """  # noqa: W505, E501
    merged_style = merge_styles_default([style])

    def get_prompt_tokens() -> List[Tuple[str, str]]:
        return [("class:qmark", qmark), ("class:question", " {} ".format(message))]

    validator = build_validator(validate)

    completer = completer or GreatUXPathCompleter(
        get_paths=get_paths,
        only_directories=only_directories,
        file_filter=file_filter,
        expanduser=True,
    )

    bindings = KeyBindings()

    @bindings.add(Keys.ControlM, eager=True)
    def set_answer(event: KeyPressEvent):
        if event.current_buffer.complete_state is not None:
            event.current_buffer.complete_state = None
        elif event.app.current_buffer.validate(set_cursor=True):
            # When the validation succeeded, accept the input.
            result_path = event.app.current_buffer.document.text
            if result_path.endswith(os.path.sep):
                result_path = result_path[:-1]

            event.app.exit(result=result_path)
            event.app.current_buffer.append_to_history()

    @bindings.add(os.path.sep, eager=True)
    def next_segment(event: KeyPressEvent):
        b = event.app.current_buffer

        if b.complete_state:
            b.complete_state = None

        current_path = b.document.text
        if not current_path.endswith(os.path.sep):
            b.insert_text(os.path.sep)

        b.start_completion(select_first=False)

    p: PromptSession = PromptSession(
        get_prompt_tokens,
        lexer=SimpleLexer("class:answer"),
        style=merged_style,
        completer=completer,
        validator=validator,
        complete_style=complete_style,
        key_bindings=bindings,
        **kwargs,
    )
    p.default_buffer.reset(Document(default))

    return Question(p.app)
