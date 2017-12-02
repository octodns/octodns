#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from StringIO import StringIO
from logging import INFO, getLogger


class UnsafePlan(Exception):
    pass


class Plan(object):
    log = getLogger('Plan')

    MAX_SAFE_UPDATE_PCENT = .3
    MAX_SAFE_DELETE_PCENT = .3
    MIN_EXISTING_RECORDS = 10

    def __init__(self, existing, desired, changes,
                 update_pcent_threshold=MAX_SAFE_UPDATE_PCENT,
                 delete_pcent_threshold=MAX_SAFE_DELETE_PCENT):
        self.existing = existing
        self.desired = desired
        self.changes = changes
        self.update_pcent_threshold = update_pcent_threshold
        self.delete_pcent_threshold = delete_pcent_threshold

        change_counts = {
            'Create': 0,
            'Delete': 0,
            'Update': 0
        }
        for change in changes:
            change_counts[change.__class__.__name__] += 1
        self.change_counts = change_counts

        try:
            existing_n = len(self.existing.records)
        except AttributeError:
            existing_n = 0

        self.log.debug('__init__: Creates=%d, Updates=%d, Deletes=%d'
                       'Existing=%d',
                       self.change_counts['Create'],
                       self.change_counts['Update'],
                       self.change_counts['Delete'], existing_n)

    def raise_if_unsafe(self):
        # TODO: what is safe really?
        if self.existing and \
           len(self.existing.records) >= self.MIN_EXISTING_RECORDS:

            existing_record_count = len(self.existing.records)
            update_pcent = self.change_counts['Update'] / existing_record_count
            delete_pcent = self.change_counts['Delete'] / existing_record_count

            if update_pcent > self.update_pcent_threshold:
                raise UnsafePlan('Too many updates, {} is over {} percent'
                                 '({}/{})'.format(
                                     update_pcent,
                                     self.MAX_SAFE_UPDATE_PCENT * 100,
                                     self.change_counts['Update'],
                                     existing_record_count))
            if delete_pcent > self.delete_pcent_threshold:
                raise UnsafePlan('Too many deletes, {} is over {} percent'
                                 '({}/{})'.format(
                                     delete_pcent,
                                     self.MAX_SAFE_DELETE_PCENT * 100,
                                     self.change_counts['Delete'],
                                     existing_record_count))

    def __repr__(self):
        return 'Creates={}, Updates={}, Deletes={}, Existing Records={}' \
            .format(self.change_counts['Create'], self.change_counts['Update'],
                    self.change_counts['Delete'],
                    len(self.existing.records))


class PlanLogger(object):

    def __init__(self, log, level=INFO):
        self.log = log
        self.level = level

    def run(self, plans):
        hr = '*************************************************************' \
            '*******************\n'
        buf = StringIO()
        buf.write('\n')
        if plans:
            current_zone = None
            for target, plan in plans:
                if plan.desired.name != current_zone:
                    current_zone = plan.desired.name
                    buf.write(hr)
                    buf.write('* ')
                    buf.write(current_zone)
                    buf.write('\n')
                    buf.write(hr)

                buf.write('* ')
                buf.write(target.id)
                buf.write(' (')
                buf.write(target)
                buf.write(')\n*   ')
                for change in plan.changes:
                    buf.write(change.__repr__(leader='* '))
                    buf.write('\n*   ')

                buf.write('Summary: ')
                buf.write(plan)
                buf.write('\n')
        else:
            buf.write(hr)
            buf.write('No changes were planned\n')
        buf.write(hr)
        buf.write('\n')
        self.log.log(self.level, buf.getvalue())
