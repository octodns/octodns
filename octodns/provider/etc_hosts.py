#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os import makedirs
from os.path import isdir, join
import logging

from .base import BaseProvider


class EtcHostsProvider(BaseProvider):
    '''
    Provider that creates a "best effort" static/emergency content that can be
    used in /etc/hosts to resolve things. A, AAAA records are supported and
    ALIAS and CNAME records will be included when they can be mapped within the
    zone.

    config:
        class: octodns.provider.etc_hosts.EtcHostsProvider
        # The output director for the hosts file <zone>.hosts
        directory: ./hosts
    '''
    SUPPORTS_GEO = False
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CNAME'))

    def __init__(self, id, directory, *args, **kwargs):
        self.log = logging.getLogger('EtcHostsProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, directory=%s', id, directory)
        super(EtcHostsProvider, self).__init__(id, *args, **kwargs)
        self.directory = directory

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        # We never act as a source, at least for now, if/when we do we still
        # need to noop `if target`
        return False

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))
        cnames = {}
        values = {}
        for record in sorted([c.new for c in changes]):
            # Since we don't have existing we'll only see creates
            fqdn = record.fqdn[:-1]
            if record._type in ('ALIAS', 'CNAME'):
                # Store cnames so we can try and look them up in a minute
                cnames[fqdn] = record.value[:-1]
            elif record._type == 'AAAA' and fqdn in values:
                # We'll prefer A over AAAA, skipping rather than replacing an
                # existing A
                pass
            else:
                # If we're here it's and A or AAAA and we want to record it's
                # value (maybe replacing if it's an A and we have a AAAA
                values[fqdn] = record.values[0]

        if not isdir(self.directory):
            makedirs(self.directory)

        filename = '{}hosts'.format(join(self.directory, desired.name))
        self.log.info('_apply: filename=%s', filename)
        with open(filename, 'w') as fh:
            fh.write('########################################\n')
            fh.write('# octoDNS ')
            fh.write(self.id)
            fh.write('\n')
            fh.write('########################################\n\n')
            if values:
                fh.write('## A & AAAA\n\n')
                for fqdn, value in sorted(values.items()):
                    if fqdn[0] == '*':
                        fh.write('# ')
                    fh.write(value)
                    fh.write('\t')
                    fh.write(fqdn)
                    fh.write('\n\n')

            if cnames:
                fh.write('\n')
                fh.write('## CNAME (mapped)\n\n')
                for fqdn, value in sorted(cnames.items()):
                    # Print out a comment of the first level
                    fh.write('# ')
                    fh.write(fqdn)
                    fh.write(' -> ')
                    fh.write(value)
                    fh.write('\n')
                    # No loop protection :-/
                    while True:
                        try:
                            value = values[value]
                            # If we're here we've found the target, print it
                            # and break the loop
                            fh.write(value)
                            fh.write('\t')
                            fh.write(fqdn)
                            fh.write('\n')
                            break
                        except KeyError:
                            # Try and step down one level
                            orig = value
                            value = cnames.get(value, None)
                            # Print out this step
                            fh.write('# ')
                            fh.write(orig)
                            fh.write(' -> ')
                            if value:
                                fh.write(value)
                            else:
                                # Don't have anywhere else to go
                                fh.write('**unknown**')
                                break
                            fh.write('\n')
                    fh.write('\n')
