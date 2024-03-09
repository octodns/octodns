#
#
#

from os import environ

from .base import BaseSecrets
from .exception import SecretException


class EnvironSecretException(SecretException):
    pass


class EnvironSecrets(BaseSecrets):
    def fetch(self, name, source):
        # expand env variables
        try:
            v = environ[name]
        except KeyError:
            self.log.exception('Invalid provider config')
            raise EnvironSecretException(
                f'Incorrect provider config, missing env var {name}, {source.context}'
            )
        try:
            # try converting the value to a number to see if it
            # converts
            v = float(v)
        except ValueError:
            pass

        return v