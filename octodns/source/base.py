#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals


class BaseSource(object):

    def __init__(self, id):
        self.id = id
        if not getattr(self, 'log', False):
            raise NotImplementedError('Abstract base class, log property '
                                      'missing')
        if not hasattr(self, 'SUPPORTS_GEO'):
            raise NotImplementedError('Abstract base class, SUPPORTS_GEO '
                                      'property missing')
        if not hasattr(self, 'SUPPORTS'):
            raise NotImplementedError('Abstract base class, SUPPORTS '
                                      'property missing')

    def populate(self, zone, target=False, lenient=False):
        '''
        Loads all zones the provider knows about

        When `target` is True the populate call is being made to load the
        current state of the provider.

        When `lenient` is True the populate call may skip record validation and
        do a "best effort" load of data. That will allow through some common,
        but not best practices stuff that we otherwise would reject. E.g. no
        trailing . or mising escapes for ;.
        '''
        raise NotImplementedError('Abstract base class, populate method '
                                  'missing')

    def supports(self, record):
        return record._type in self.SUPPORTS

    def __repr__(self):
        return self.__class__.__name__
