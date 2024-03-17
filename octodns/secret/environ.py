#
#
#

from os import environ

from .base import BaseSecrets
from .exception import SecretsException


class EnvironSecretsException(SecretsException):
    pass


class EnvironSecrets(BaseSecrets):
    def fetch(self, name, source):
        # expand env variables
        try:
            v = environ[name]
        except KeyError:
            self.log.exception('Invalid provider config')
            raise EnvironSecretsException(
                f'Incorrect provider config, missing env var {name}, {source.context}'
            )

        try:
            if '.' in v:
                # has a dot, try converting it to a float
                v = float(v)
            else:
                # no dot, try converting it to an int
                v = int(v)
        except ValueError:
            # just leave it as a string
            pass

        return v
