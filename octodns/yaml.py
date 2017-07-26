#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from natsort import natsort_keygen
from yaml import SafeDumper, SafeLoader, load, dump
from yaml.constructor import ConstructorError


_natsort_key = natsort_keygen()


# Found http://stackoverflow.com/a/21912744 which guided me on how to hook in
# here
class SortEnforcingLoader(SafeLoader):

    def _construct(self, node):
        self.flatten_mapping(node)
        ret = self.construct_pairs(node)
        keys = [d[0] for d in ret]
        keys_sorted = sorted(keys, key=_natsort_key)
        for key in keys:
            expected = keys_sorted.pop(0)
            if key != expected:
                raise ConstructorError(None, None, 'keys out of order: '
                                       'expected {} got {} at {}'
                                       .format(expected, key, node.start_mark))
        return dict(ret)


SortEnforcingLoader.add_constructor(SortEnforcingLoader.DEFAULT_MAPPING_TAG,
                                    SortEnforcingLoader._construct)


def safe_load(stream, enforce_order=True):
    return load(stream, SortEnforcingLoader if enforce_order else SafeLoader)


class SortingDumper(SafeDumper):
    '''
    This sorts keys alphanumerically in a "natural" manner where things with
    the number 2 come before the number 12.

    See https://www.xormedia.com/natural-sort-order-with-zero-padding/ for
    more info
    '''

    def _representer(self, data):
        data = data.items()
        data.sort(key=lambda d: _natsort_key(d[0]))
        return self.represent_mapping(self.DEFAULT_MAPPING_TAG, data)


SortingDumper.add_representer(dict, SortingDumper._representer)


def safe_dump(data, fh, **options):
    kwargs = {
        'canonical': False,
        'indent': 2,
        'default_style': '',
        'default_flow_style': False,
        'explicit_start': True
    }
    kwargs.update(options)
    dump(data, fh, SortingDumper, **kwargs)
