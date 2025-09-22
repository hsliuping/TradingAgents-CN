def cameltosnake(camel_string: str) -> str:
    if not camel_string:
        return ""
    elif camel_string[0].isupper():
        return f"_{camel_string[0].lower()}{cameltosnake(camel_string[1:])}"
    else:
        return f"{camel_string[0]}{cameltosnake(camel_string[1:])}"


def camel_to_snake(s):
    if len(s) <= 1:
        return s.lower()

    return cameltosnake(s[0].lower() + s[1:])


def is_notebook():
    try:
        from IPython import get_ipython

        ip = get_ipython()
        if ip is None:
            return False
        return True
    except Exception:
        return False
