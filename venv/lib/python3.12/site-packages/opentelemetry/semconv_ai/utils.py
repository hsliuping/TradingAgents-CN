import logging


def dont_throw(func):
    """
    A decorator that wraps the passed in function and logs exceptions instead of throwing them.

    @param func: The function to wrap
    @return: The wrapper function
    """
    # Obtain a logger specific to the function's module
    logger = logging.getLogger(func.__module__)

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                "Failed to execute %s, error: %s", func.__name__, str(e)
            )  # TODO: posthog instead
            logger.warning(
                "Failed to set attributes for openai span, error: %s", str(e)
            )

    return wrapper
