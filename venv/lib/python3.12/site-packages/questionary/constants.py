from questionary import Style

# Value to display as an answer when "affirming" a confirmation question
YES = "Yes"

# Value to display as an answer when "denying" a confirmation question
NO = "No"

# Instruction text for a confirmation question (yes is default)
YES_OR_NO = "(Y/n)"

# Instruction text for a confirmation question (no is default)
NO_OR_YES = "(y/N)"

# Instruction for multiline input
INSTRUCTION_MULTILINE = "(Finish with 'Alt+Enter' or 'Esc then Enter')\n>"

# Selection token used to indicate the selection cursor in a list
DEFAULT_SELECTED_POINTER = "»"

# Item prefix to identify selected items in a checkbox list
INDICATOR_SELECTED = "●"

# Item prefix to identify unselected items in a checkbox list
INDICATOR_UNSELECTED = "○"

# Prefix displayed in front of questions
DEFAULT_QUESTION_PREFIX = "?"

# Message shown when a user aborts a question prompt using CTRL-C
DEFAULT_KBI_MESSAGE = "\nCancelled by user\n"

# Default text shown when the input is invalid
INVALID_INPUT = "Invalid input"

# Default message style
DEFAULT_STYLE = Style(
    [
        ("qmark", "fg:#5f819d"),  # token in front of the question
        ("question", "bold"),  # question text
        ("answer", "fg:#FF9D00 bold"),  # submitted answer text behind the question
        (
            "search_success",
            "noinherit fg:#00FF00 bold",
        ),  # submitted answer text behind the question
        (
            "search_none",
            "noinherit fg:#FF0000 bold",
        ),  # submitted answer text behind the question
        ("pointer", ""),  # pointer used in select and checkbox prompts
        ("selected", ""),  # style for a selected item of a checkbox
        ("separator", ""),  # separator in lists
        ("instruction", ""),  # user instructions for select, rawselect, checkbox
        ("text", ""),  # any other text
        ("instruction", ""),  # user instructions for select, rawselect, checkbox
    ]
)
