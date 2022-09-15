#
#
#


class EqualityTupleMixin(object):
    def _equality_tuple(self):
        raise NotImplementedError('_equality_tuple method not implemented')

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
