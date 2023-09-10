#
#
#

from os.path import dirname, join

from natsort import natsort_keygen
from yaml import SafeDumper, SafeLoader, dump, load
from yaml.constructor import ConstructorError
from yaml.representer import SafeRepresenter

from .context import ContextDict

_natsort_key = natsort_keygen()


class ContextLoader(SafeLoader):
    def _pairs(self, node):
        self.flatten_mapping(node)
        pairs = self.construct_pairs(node)
        start_mark = node.start_mark
        context = f'{start_mark.name}, line {start_mark.line+1}, column {start_mark.column+1}'
        return ContextDict(pairs, context=context), pairs, context

    def _construct(self, node):
        return self._pairs(node)[0]

    def include(self, node):
        mark = self.get_mark()
        directory = dirname(mark.name)

        filename = join(directory, self.construct_scalar(node))

        with open(filename, 'r') as fh:
            return safe_load(fh, self.__class__)


ContextLoader.add_constructor('!include', ContextLoader.include)
ContextLoader.add_constructor(
    ContextLoader.DEFAULT_MAPPING_TAG, ContextLoader._construct
)


# Found http://stackoverflow.com/a/21912744 which guided me on how to hook in
# here
class SortEnforcingLoader(ContextLoader):
    def _construct(self, node):
        ret, pairs, context = self._pairs(node)

        keys = [d[0] for d in pairs]
        keys_sorted = sorted(keys, key=_natsort_key)
        for key in keys:
            expected = keys_sorted.pop(0)
            if key != expected:
                raise ConstructorError(
                    None,
                    None,
                    'keys out of order: '
                    f'expected {expected} got {key} at {context}',
                )

        return ret


SortEnforcingLoader.add_constructor(
    SortEnforcingLoader.DEFAULT_MAPPING_TAG, SortEnforcingLoader._construct
)


def safe_load(stream, enforce_order=True):
    return load(stream, SortEnforcingLoader if enforce_order else ContextLoader)


class SortingDumper(SafeDumper):
    '''
    This sorts keys alphanumerically in a "natural" manner where things with
    the number 2 come before the number 12.

    See https://www.xormedia.com/natural-sort-order-with-zero-padding/ for
    more info
    '''

    def _representer(self, data):
        data = sorted(data.items(), key=lambda d: _natsort_key(d[0]))
        return self.represent_mapping(self.DEFAULT_MAPPING_TAG, data)


SortingDumper.add_representer(dict, SortingDumper._representer)
# This should handle all the record value types which are ultimately either str
# or dict at some point in their inheritance hierarchy
SortingDumper.add_multi_representer(str, SafeRepresenter.represent_str)
SortingDumper.add_multi_representer(dict, SortingDumper._representer)


def safe_dump(data, fh, **options):
    kwargs = {
        'canonical': False,
        'indent': 2,
        'default_style': '',
        'default_flow_style': False,
        'explicit_start': True,
    }
    kwargs.update(options)
    dump(data, fh, SortingDumper, **kwargs)
