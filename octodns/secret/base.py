#
#
#

from logging import getLogger


class BaseSecrets:
    def __init__(self, name):
        self.log = getLogger(f'{self.__class__.__name__}[{name}]')
        self.name = name
