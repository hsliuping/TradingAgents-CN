"""Middleware for making it easier to do distributed tracing."""


class TracingMiddleware:
    """Middleware for propagating distributed tracing context using LangSmith.

    This middleware checks for the 'langsmith-trace' header and propagates the
    tracing context if present. It does not start new traces by default.
    It is designed to work with ASGI applications.

    Attributes:
        app: The ASGI application being wrapped.
    """

    def __init__(self, app):
        """Initialize the middleware."""
        from langsmith.run_helpers import tracing_context  # type: ignore

        self._with_headers = tracing_context
        self.app = app

    async def __call__(self, scope: dict, receive, send):
        """Handle incoming requests and propagate tracing context if applicable.

        Args:
            scope: A dict containing ASGI connection scope.
            receive: An awaitable callable for receiving ASGI events.
            send: An awaitable callable for sending ASGI events.

        If the request is HTTP and contains the 'langsmith-trace' header,
        it propagates the tracing context before calling the wrapped application.
        Otherwise, it calls the application directly without modifying the context.
        """
        if scope["type"] == "http" and "headers" in scope:
            headers = dict(scope["headers"])
            if b"langsmith-trace" in headers:
                with self._with_headers(parent=headers):
                    await self.app(scope, receive, send)
                return
        await self.app(scope, receive, send)
