from typing import List
from typing import Optional

import prompt_toolkit.styles

from questionary.constants import DEFAULT_STYLE


def merge_styles_default(styles: List[Optional[prompt_toolkit.styles.Style]]):
    """Merge a list of styles with the Questionary default style."""
    filtered_styles: list[prompt_toolkit.styles.BaseStyle] = [DEFAULT_STYLE]
    # prompt_toolkit's merge_styles works with ``None`` elements, but it's
    # type-hints says it doesn't.
    filtered_styles.extend([s for s in styles if s is not None])
    return prompt_toolkit.styles.merge_styles(filtered_styles)
