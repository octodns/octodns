#
#
#

from os.path import dirname, join

from natsort import natsort_keygen
from yaml import SafeDumper, SafeLoader, dump, load
from yaml.constructor import ConstructorError
from yaml.representer import SafeRepresenter

from .context import ContextDict

# as of python 3.13 functools.partial is a method descriptor and must be wrapped
# in staticmethod() to preserve the behavior natsort is expecting it to have
_natsort_key = staticmethod(natsort_keygen())


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
        keys_sorted = sorted(keys, key=self.KEYGEN)
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


class NaturalSortEnforcingLoader(SortEnforcingLoader):
    KEYGEN = _natsort_key


NaturalSortEnforcingLoader.add_constructor(
    SortEnforcingLoader.DEFAULT_MAPPING_TAG,
    NaturalSortEnforcingLoader._construct,
)


class SimpleSortEnforcingLoader(SortEnforcingLoader):
    KEYGEN = lambda _, s: s


SimpleSortEnforcingLoader.add_constructor(
    SortEnforcingLoader.DEFAULT_MAPPING_TAG,
    SimpleSortEnforcingLoader._construct,
)


_loaders = {
    'natural': NaturalSortEnforcingLoader,
    'simple': SimpleSortEnforcingLoader,
}


class InvalidOrder(Exception):

    def __init__(self, order_mode):
        options = '", "'.join(_loaders.keys())
        super().__init__(
            f'Invalid order_mode, "{order_mode}", options are "{options}"'
        )


def safe_load(stream, enforce_order=True, order_mode='natural'):
    if enforce_order:
        try:
            loader = _loaders[order_mode]
        except KeyError as e:
            raise InvalidOrder(order_mode) from e
    else:
        loader = ContextLoader

    return load(stream, loader)


class SortingDumper(SafeDumper):
    '''
    This sorts keys alphanumerically in a "natural" manner where things with
    the number 2 come before the number 12.

    See https://www.xormedia.com/natural-sort-order-with-zero-padding/ for
    more info
    '''

    def _representer(self, data):
        data = sorted(data.items(), key=self.KEYGEN)
        return self.represent_mapping(self.DEFAULT_MAPPING_TAG, data)


SortingDumper.add_representer(dict, SortingDumper._representer)
# This should handle all the record value types which are ultimately either str
# or dict at some point in their inheritance hierarchy
SortingDumper.add_multi_representer(str, SafeRepresenter.represent_str)
SortingDumper.add_multi_representer(dict, SortingDumper._representer)


class NaturalSortingDumper(SortingDumper):
    KEYGEN = _natsort_key


class SimpleSortingDumper(SortingDumper):
    KEYGEN = lambda _, s: s


_dumpers = {'natural': NaturalSortingDumper, 'simple': SimpleSortingDumper}


def safe_dump(data, fh, order_mode='natural', **options):
    kwargs = {
        'canonical': False,
        'indent': 2,
        'default_style': '',
        'default_flow_style': False,
        'explicit_start': True,
    }
    kwargs.update(options)
    try:
        dumper = _dumpers[order_mode]
    except KeyError as e:
        raise InvalidOrder(order_mode) from e
    dump(data, fh, dumper, **kwargs)
