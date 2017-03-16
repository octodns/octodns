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

    def populate(self, zone, target=False):
        '''
        Loads all zones the provider knows about
        '''
        raise NotImplementedError('Abstract base class, populate method '
                                  'missing')

    def supports(self, record):
        # Unless overriden and handled appropriaitely we'll assume that all
        # record types are supported
        return True

    def __repr__(self):
        return self.__class__.__name__
