from __future__ import absolute_import, print_function, unicode_literals

import functools
import collections
import time

def save_method_args(method):
    """
    Wrap a method such that when it is called, the args and kwargs are
    saved on the method.

    >>> class MyClass(object):
    ...     @save_method_args
    ...     def method(self, a, b):
    ...         print(a, b)
    >>> my_ob = MyClass()
    >>> my_ob.method(1, 2)
    1 2
    >>> my_ob._saved_method.args
    (1, 2)
    >>> my_ob._saved_method.kwargs
    {}
    >>> my_ob.method(a=3, b='foo')
    3 foo
    >>> my_ob._saved_method.args
    ()
    >>> my_ob._saved_method.kwargs == dict(a=3, b='foo')
    True

    The arguments are stored on the instance, allowing for
    different instance to save different args.

    >>> your_ob = MyClass()
    >>> your_ob.method({str('x'): 3}, b=[4])
    {'x': 3} [4]
    >>> your_ob._saved_method.args
    ({'x': 3},)
    >>> my_ob._saved_method.args
    ()
    """
    args_and_kwargs = collections.namedtuple('args_and_kwargs', 'args kwargs')
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        attr_name = '_saved_' + method.__name__
        attr = args_and_kwargs(args, kwargs)
        setattr(self, attr_name, attr)
        return method(self, *args, **kwargs)
    return wrapper


class Throttler(object):
    """
    Rate-limit a function (or other callable)
    """
    def __init__(self, func, max_rate=float('Inf')):
        if isinstance(func, Throttler):
            func = func.func
        self.func = func
        self.max_rate = max_rate
        self.reset()

    def reset(self):
        self.last_called = 0

    def __call__(self, *args, **kwargs):
        self._wait()
        return self.func(*args, **kwargs)

    def _wait(self):
        """ensure at least 1/max_rate seconds from last call"""
        elapsed = time.time() - self.last_called
        must_wait = 1 / self.max_rate - elapsed
        time.sleep(max(0, must_wait))
        self.last_called = time.time()

    def __get__(self, obj, type=None):
        return first_invoke(self._wait, functools.partial(self.func, obj))
    
    
def first_invoke(func1, func2):
    """
    Return a function that when invoked will invoke func1 without
    any parameters (for its side-effect) and then invoke func2
    with whatever parameters were passed, returning its result.
    """
    def wrapper(*args, **kwargs):
        func1()
        return func2(*args, **kwargs)
    return wrapper
