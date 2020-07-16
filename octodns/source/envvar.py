
import logging
import os

from ..record import Record
from .base import BaseSource


class EnvVarSourceException(Exception):
    pass


class EnvironmentVariableNotFoundException(EnvVarSourceException):
    def __init__(self, data):
        super(EnvironmentVariableNotFoundException, self).__init__(
            'Unknown environment variable {}'.format(data))


class EnvVarSource(BaseSource):
    '''
    This source allows for environment variables to be embedded at octodns
    execution time into zones.  Intended to capture artifacts of deployment to
    facilitate operational objectives.

    The TXT record generated will only have a single value.

    The record name cannot conflict with any other co-existing sources.  If
    this occurs, an exception will be thrown.

    Possible use cases include:
     - Embedding a version number into a TXT record to monitor update
       propagation across authoritative providers.
     - Capturing identifying information about the deployment process to
       record where and when the zone was updated.

    version:
        class: octodns.source.envvar.EnvVarSource
        # The environment variable in question, in this example the username
        # currently executing octodns
        variable: USER
        # The TXT record name to embed the value found at the above
        # environment variable
        record: deployuser
        # The TTL of the TXT record (optional, default 60)
        ttl: 3600

    This source is then combined with other sources in the octodns config
    file:

    zones:
      netflix.com.:
        sources:
          - yaml
          - version
        targets:
          - ultra
          - ns1
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('TXT'))

    DEFAULT_TTL = 60

    def __init__(self, id, variable, record, ttl=DEFAULT_TTL):
        self.log = logging.getLogger('{}[{}]'.format(
            self.__class__.__name__, id))
        self.log.debug('__init__: id=%s, variable=%s, record=%s, '
                       'ttl=%d', id, variable, record, ttl)
        super(EnvVarSource, self).__init__(id)
        self.envvar = variable
        self.record = record
        self.ttl = ttl
        self.value = None

    def _read_variable(self):
        self.value = os.environ.get(self.envvar)
        if self.value is None:
            raise EnvironmentVariableNotFoundException(self.envvar)

        self.log.debug('_read_variable: successfully loaded var=%s val=%s',
                       self.envvar, self.value)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        # if target:
        # TODO: Environment Variable Source cannot act as a target,
        # throw exception?
        # return

        before = len(zone.records)

        self._read_variable()

        # We don't need to worry about conflicting records here because the
        # manager will deconflict sources on our behalf.
        payload = {'ttl': self.ttl, 'type': 'TXT', 'values': [self.value]}
        record = Record.new(zone, self.record, payload, source=self,
                            lenient=lenient)
        zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=False',
                      len(zone.records) - before)
