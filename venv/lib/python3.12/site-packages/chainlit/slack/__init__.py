import importlib.util

if importlib.util.find_spec("slack_bolt") is None:
    raise ValueError(
        "The slack_bolt package is required to integrate Chainlit with a Slack app. Run `pip install slack_bolt --upgrade`"
    )
