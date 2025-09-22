import functools


class LazyProxy(object):
    """Class for proxy objects that delegate to a specified function to evaluate
    the actual object.

    >>> def greeting(name='world'):
    ...     return 'Hello, {}!'.format(name)
    >>> lazy_greeting = LazyProxy(greeting, name='Joe')
    >>> print(lazy_greeting)
    Hello, Joe!
    >>> '  ' + lazy_greeting
    '  Hello, Joe!'
    >>> '({})'.format(lazy_greeting)
    '(Hello, Joe!)'

    This can be used, for example, to implement lazy translation functions that
    delay the actual translation until the string is actually used. The
    rationale for such behavior is that the locale of the user may not always
    be available. In web applications, you only know the locale when processing
    a request.

    The proxy implementation attempts to be as complete as possible, so that
    the lazy objects should mostly work as expected, for example for sorting:

    >>> greetings = [
    ...     LazyProxy(greeting, 'world'),
    ...     LazyProxy(greeting, 'Joe'),
    ...     LazyProxy(greeting, 'universe'),
    ... ]
    >>> greetings.sort()
    >>> for greeting in greetings:
    ...     print(greeting)
    Hello, Joe!
    Hello, universe!
    Hello, world!
    """
    __slots__ = ['_func', '_args', '_kwargs', '_value',
                 '_is_value_cached', '_is_cache_enabled']

    def __init__(self, func, *args, **kwargs):
        is_cache_enabled = kwargs.pop('enable_cache', True)
        # Avoid triggering our own __setattr__ implementation
        object.__setattr__(self, '_func', func)
        object.__setattr__(self, '_args', args)
        object.__setattr__(self, '_kwargs', kwargs)
        object.__setattr__(self, '_is_cache_enabled', is_cache_enabled)
        object.__setattr__(self, '_value', None)
        object.__setattr__(self, '_is_value_cached', False)

    @property
    def value(self):
        if self._is_cache_enabled and self._is_value_cached:
            return self._value
        value = self._func(*self._args, **self._kwargs)
        if self._is_cache_enabled:
            object.__setattr__(self, '_value', value)
            object.__setattr__(self, '_is_value_cached', True)
        return value

    @property
    def __class__(self):
        return self.value.__class__

    def __bool__(self):
        return bool(self.value)

    def __contains__(self, key):
        return key in self.value

    def __nonzero__(self):
        return bool(self.value)

    def __dir__(self):
        return dir(self.value)

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __str__(self):
        return str(self.value)

    def __unicode__(self):
        return unicode(self.value)

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __mod__(self, other):
        return self.value % other

    def __rmod__(self, other):
        return other % self.value

    def __mul__(self, other):
        return self.value * other

    def __rmul__(self, other):
        return other * self.value

    def __call__(self, *args, **kwargs):
        return self.value(*args, **kwargs)

    def __lt__(self, other):
        return self.value < other

    def __le__(self, other):
        return self.value <= other

    def __eq__(self, other):
        return self.value == other

    def __ne__(self, other):
        return self.value != other

    def __gt__(self, other):
        return self.value > other

    def __ge__(self, other):
        return self.value >= other

    def __delattr__(self, name):
        delattr(self.value, name)

    def __getattr__(self, name):
        return getattr(self.value, name)

    def __setattr__(self, name, value):
        setattr(self.value, name, value)

    def __delitem__(self, key):
        del self.value[key]

    def __getitem__(self, key):
        return self.value[key]

    def __setitem__(self, key, value):
        self.value[key] = value

    def __copy__(self):
        return LazyProxy(
            self._func,
            enable_cache=self._is_cache_enabled,
            *self._args,
            **self._kwargs
        )

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return LazyProxy(
            deepcopy(self._func, memo),
            enable_cache=deepcopy(self._is_cache_enabled, memo),
            *deepcopy(self._args, memo),
            **deepcopy(self._kwargs, memo)
        )


def lazify(func):
    """Make the decorated function evaluation lazy.

    The function will return a :py:class:`~LazyProxy` rather than the expected
    result.

    >>> @lazify
    ... def greeting(name='world'):
    ...     return 'Hello, {}!'.format(name)
    >>> lazy_greeting = greeting(name='Joe')
    >>> lazy_greeting
    <__main__.LazyProxy at 0x7f638b680598>
    >>> print(lazy_greeting)
    Hello, Joe!

    Proxy cache can be controlled directly when calling the function:

    >>> lazy_greeting = greeting(name='Joe', enable_cache=False)
    >>> lazy_greeting._is_cache_enabled
    False

    Thus, the decorated function shouldn't have a ``enable_cache`` parameter.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return LazyProxy(func, *args, **kwargs)
    return wrapper


__all__ = ['LazyProxy', 'lazify']
