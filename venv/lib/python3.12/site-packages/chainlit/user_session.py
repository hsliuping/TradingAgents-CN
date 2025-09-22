from typing import Callable, Dict, Generic, Optional, TypeVar

from chainlit.context import context

user_sessions: Dict[str, Dict] = {}

T = TypeVar("T")


class UserSession:
    """
    Developer facing user session class.
    Useful for the developer to store user specific data between calls.
    """

    def get(self, key, default=None):
        if not context.session:
            return default

        if context.session.id not in user_sessions:
            # Create a new user session
            user_sessions[context.session.id] = {}

        user_session = user_sessions[context.session.id]

        # Copy important fields from the session
        user_session["id"] = context.session.id
        user_session["env"] = context.session.user_env
        user_session["chat_settings"] = context.session.chat_settings
        user_session["user"] = context.session.user
        user_session["chat_profile"] = context.session.chat_profile
        user_session["client_type"] = context.session.client_type

        return user_session.get(key, default)

    def set(self, key, value):
        if not context.session:
            return None

        if context.session.id not in user_sessions:
            user_sessions[context.session.id] = {}

        user_session = user_sessions[context.session.id]
        user_session[key] = value

    def create_accessor(
        self, key: str, default: T, *, apply_fn: Optional[Callable[[T], T]] = None
    ) -> "SessionAccessor[T]":
        """
        Create a typed session accessor object for the given key and default value.

        #### Note: Creates the accessor configuration. The session value itself is only stored/updated when `.set()`, `.reset()`, or `.apply()` are called.

        Parameters
        ----------
        key : str
            The session dictionary key to store the value under
        default : T
            Default value to return when key is not present in session
        apply_fn : Optional[Callable[[T], T]], default None
            Optional function to transform the value when apply() is called

        Returns
        -------
        SessionAccessor[T]
            A typed accessor object bound to the specified session key

        Examples
        --------

        ```python
        count = cl.user_session.create_accessor("count", 0)
        count.get() # returns 0
        count.set(5)  # type-safe setter
        count.get() # returns 5

        # With transform function
        counter = cl.user_session.create_accessor("counter", 0, apply_fn=lambda x: x + 1)
        counter.apply() # increments value and returns new value (1)

        @cl.on_message
        async def on_message(message: cl.Message):
            await cl.Message(content=f"You sent {counter.apply()} messages").send() # You sent 2 messages
        ```
        """
        return SessionAccessor(key, default, apply_fn=apply_fn)


user_session = UserSession()


class SessionAccessor(Generic[T]):
    """
    Extended session accessor class to store user specific data between calls with type safety.

    Provides a typed wrapper around user_session dictionary access with default values
    and optional transform functions. The session value is only stored in memory when
    explicitly modified through `.set()`, `.reset()`, or `.apply()` methods.

    Examples
    --------
    ```python
    count = cl.user_session.create_accessor("count", 0)
    count.get() # returns 0
    count.set(5)  # type-safe setter
    count.get() # returns 5

    # With transform function
    counter = cl.user_session.create_accessor("counter", 0, apply_fn=lambda x: x + 1)
    counter.apply() # increments value and returns new value (1)

    @cl.on_message
    async def on_message(message: cl.Message):
        await cl.Message(content=f"You sent {counter.apply()} messages").send() # You sent 2 messages
    ```
    """

    def __init__(
        self, key: str, default: T, *, apply_fn: Optional[Callable[[T], T]] = None
    ):
        self._key = key
        self._default = default
        self._apply_fn = apply_fn

    def get(self) -> T:
        """
        Get the current value of the accessor.
        """
        return user_session.get(self._key, self._default)

    def set(self, value: T) -> None:
        """
        Set the value of the accessor.
        """
        return user_session.set(self._key, value)

    def reset(self) -> None:
        """
        Reset the value to the default.
        """
        return self.set(self._default)

    def apply(self) -> T:
        """
        Apply the transform function to the current value, store the result, and return it.

        Returns the current value if no transform function is provided.
        """
        value = self.get()
        if self._apply_fn:
            value = self._apply_fn(value)
        self.set(value)
        return value
