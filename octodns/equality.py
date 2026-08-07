#
#
#


class EqualityTupleMixin(object):
    '''
    Provides equality, ordering, and hashing based on the tuple returned by
    a subclass's `_equality_tuple` method.

    Subclasses are treated as value objects: two instances are equal (and
    hash equal) exactly when their `_equality_tuple()`s are equal.
    `_equality_tuple()` must return a tuple of hashable values only, e.g.
    no `set` or `list` members, since it backs both equality and `__hash__`.
    As with any hashable object, an instance's `_equality_tuple()` must not
    change while the instance is a member of a `set` or used as a `dict`
    key.
    '''

    def _equality_tuple(self):
        raise NotImplementedError('_equality_tuple method not implemented')

    def __hash__(self):
        return hash(self._equality_tuple())

    def __eq__(self, other):
        return self._equality_tuple() == other._equality_tuple()

    def __ne__(self, other):
        return self._equality_tuple() != other._equality_tuple()

    def __lt__(self, other):
        return self._equality_tuple() < other._equality_tuple()

    def __le__(self, other):
        return self._equality_tuple() <= other._equality_tuple()

    def __gt__(self, other):
        return self._equality_tuple() > other._equality_tuple()

    def __ge__(self, other):
        return self._equality_tuple() >= other._equality_tuple()
