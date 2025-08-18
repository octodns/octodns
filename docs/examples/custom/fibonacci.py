#
#
#

from logging import getLogger

from octodns.record import Record
from octodns.source.base import BaseSource


# Based on https://stackoverflow.com/a/3954407
def _fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b


class FibonacciProvider(BaseSource):
    # Here only TXT records are supported
    SUPPORTS = ('TXT',)
    # Do-not support (deprecated) GEO records
    SUPPORTS_GEO = False

    #  This is pretty much boilerplate, create a logger with a standard name,
    #  call up to the parent class BaseSource's __init__, store our
    #  attributes, and then calculate our fibonacci sequence
    def __init__(self, id, n, ttl=3600):
        klass = self.__class__.__name__
        self.log = getLogger(f'{klass}[{id}]')
        self.log.debug(
            '__init__: id=%s, variable=%s, name=%s, ttl=%d', id, n, ttl
        )
        super().__init__(id)
        self.n = n
        self.ttl = ttl

        # calculate the requested number of values
        self.values = list(_fibonacci(n))

    def populate(self, zone, target=False, lenient=False):
        # This is the method adding records to the zone. For a source it's the
        # only thing that needs to be implemented. Again there's some best
        # practices wrapping our custom logic, mostly for logging/debug
        # purposes.
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)

        # This is where the logic of the source lives. Here it's simply
        # translated the previously calculated fibonacci sequence into
        # corresponding TXT records. It could be anything: reading data from
        # disk, calling APIs, ...
        for i, value in enumerate(self.values):
            # If there's a chance the generated record may result in validation
            # errors it would make sense to pass lenient to new
            txt = Record.new(
                zone,
                f'fibonacci-{i}',
                {'value': str(value), 'ttl': self.ttl, 'type': 'TXT'},
            )
            # lenient should always be passed to add_record.  If there's a
            # chance the source will create records that conflict with
            # something previously added by another provider it may make sense
            # to include `replace` here, possibly with an additional provider
            # parameter `populate_should_replace`
            zone.add_record(txt, lenient=lenient)

        self.log.info(
            'populate:   found %s records, exists=False',
            len(zone.records) - before,
        )
