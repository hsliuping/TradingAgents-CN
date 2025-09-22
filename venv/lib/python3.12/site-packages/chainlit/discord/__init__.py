import importlib.util

if importlib.util.find_spec("discord") is None:
    raise ValueError(
        "The discord package is required to integrate Chainlit with a Discord app. Run `pip install discord --upgrade`"
    )
