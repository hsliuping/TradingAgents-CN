import secrets
import string

# Using punctuation, without chars that can break in the cli (quotes, backslash, backtick...)
chars = string.ascii_letters + string.digits + "$%*,-./:=>?@^_~"


def random_secret(length: int = 64):
    return "".join(secrets.choice(chars) for i in range(length))
