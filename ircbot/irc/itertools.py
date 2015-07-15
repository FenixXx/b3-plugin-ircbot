import six

def always_iterable(item):
    """
    Given an object, always return an iterable. If the item is not
    already iterable, return a tuple containing only the item. If item is
    None, an empty iterable is returned.

    >>> always_iterable([1,2,3])
    [1, 2, 3]
    >>> always_iterable('foo')
    ('foo',)
    >>> always_iterable(None)
    ()
    >>> always_iterable(range(10))
    range(0, 10)
    >>> def _test_func(): yield "I'm iterable"
    >>> print(next(always_iterable(_test_func())))
    I'm iterable
    """
    if item is None:
        item = ()
    if isinstance(item, six.string_types) or not hasattr(item, '__iter__'):
        item = item,
    return item