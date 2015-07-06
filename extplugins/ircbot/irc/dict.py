from __future__ import unicode_literals, absolute_import

import six
from . import strings


class KeyTransformingDict(dict):
    """
    A dict subclass that transforms the keys before they're used.
    Subclasses may override the default transform_key to customize behavior.
    """
    @staticmethod
    def transform_key(key):
        return key

    def __init__(self, *args, **kargs):
        super(KeyTransformingDict, self).__init__()
        # build a dictionary using the default constructs
        d = dict(*args, **kargs)
        # build this dictionary using transformed keys.
        for item in d.items():
            self.__setitem__(*item)

    def __setitem__(self, key, val):
        key = self.transform_key(key)
        super(KeyTransformingDict, self).__setitem__(key, val)

    def __getitem__(self, key):
        key = self.transform_key(key)
        return super(KeyTransformingDict, self).__getitem__(key)

    def __contains__(self, key):
        key = self.transform_key(key)
        return super(KeyTransformingDict, self).__contains__(key)

    def __delitem__(self, key):
        key = self.transform_key(key)
        return super(KeyTransformingDict, self).__delitem__(key)

    def setdefault(self, key, *args, **kwargs):
        key = self.transform_key(key)
        return super(KeyTransformingDict, self).setdefault(key, *args, **kwargs)

    def pop(self, key, *args, **kwargs):
        key = self.transform_key(key)
        return super(KeyTransformingDict, self).pop(key, *args, **kwargs)

    def matching_key_for(self, key):
        """
        Given a key, return the actual key stored in self that matches.
        Raise KeyError if the key isn't found.
        """
        try:
            return next(e_key for e_key in self.keys() if e_key == key)
        except StopIteration:
            raise KeyError(key)
        
        
class IRCDict(KeyTransformingDict):
    """
    A dictionary of names whose keys are case-insensitive according to the
    IRC RFC rules.

    >>> d = IRCDict({'[This]': 'that'}, A='foo')

    The dict maintains the original case:

    >>> '[This]' in ''.join(d.keys())
    True

    But the keys can be referenced with a different case

    >>> d['a'] == 'foo'
    True

    >>> d['{this}'] == 'that'
    True

    >>> d['{THIS}'] == 'that'
    True

    >>> '{thiS]' in d
    True

    This should work for operations like delete and pop as well.

    >>> d.pop('A') == 'foo'
    True
    >>> del d['{This}']
    >>> len(d)
    0
    """
    @staticmethod
    def transform_key(key):
        if isinstance(key, six.string_types):
            key = strings.IRCFoldedCase(key)
        return key
