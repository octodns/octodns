#
#
#

from os.path import dirname, join

from natsort import natsort_keygen
from yaml import SafeDumper, SafeLoader, compose, dump, load
from yaml.constructor import ConstructorError
from yaml.representer import SafeRepresenter

from .context import ContextDict

# as of python 3.13 functools.partial is a method descriptor and must be wrapped
# in staticmethod() to preserve the behavior natsort is expecting it to have
_natsort_key = staticmethod(natsort_keygen())


class ContextLoader(SafeLoader):

    def construct_include(self, node):
        mark = self.get_mark()
        directory = dirname(mark.name)

        filename = join(directory, self.construct_scalar(node))

        with open(filename, 'r') as fh:
            return load(fh, self.__class__)

    def flatten_include(self, node):
        mark = self.get_mark()
        directory = dirname(mark.name)

        filename = join(directory, self.construct_scalar(node))

        with open(filename, 'r') as fh:
            yield compose(fh, self.__class__).value

    def construct_mapping(self, node, deep=False):
        '''
        Calls our parent and wraps the resulting dict with a ContextDict
        '''
        start_mark = node.start_mark
        context = f'{start_mark.name}, line {start_mark.line+1}, column {start_mark.column+1}'
        return ContextDict(
            super().construct_mapping(node, deep), context=context
        )

    # the following 4 methods are ported out of
    # https://github.com/yaml/pyyaml/pull/894 an intended to be used until we
    # can (hopefully) require a version of pyyaml with that PR merged.

    @classmethod
    def add_flattener(cls, tag, flattener):
        if not 'yaml_flatteners' in cls.__dict__:
            cls.yaml_flatteners = {}
        cls.yaml_flatteners[tag] = flattener

    # this overwrites/ignores the built-in version of the method
    def flatten_mapping(self, node):  # pragma: no cover
        merge = []
        for key_node, value_node in node.value:
            if key_node.tag == 'tag:yaml.org,2002:merge':
                flattener = self.yaml_flatteners.get(value_node.tag)
                if flattener:
                    for value in flattener(self, value_node):
                        merge.extend(value)
                else:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "expected a mapping or list of mappings for merging, but found %s"
                        % value_node.id,
                        value_node.start_mark,
                    )
            elif key_node.tag == 'tag:yaml.org,2002:value':
                key_node.tag = 'tag:yaml.org,2002:str'
                merge.append((key_node, value_node))
            else:
                merge.append((key_node, value_node))

        node.value = merge

    def flatten_yaml_seq(self, node):  # pragma: no cover
        submerge = []
        for subnode in node.value:
            # we need to flatten each item in the seq, most likely they'll be mappings,
            # but we need to allow for custom flatteners as well.
            flattener = self.yaml_flatteners.get(subnode.tag)
            if flattener:
                for value in flattener(self, subnode):
                    submerge.append(value)
            else:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "expected a mapping for merging, but found %s" % subnode.id,
                    subnode.start_mark,
                )
        submerge.reverse()
        for value in submerge:
            yield value

    def flatten_yaml_map(self, node):  # pragma: no cover
        self.flatten_mapping(node)
        yield node.value


# These 2 add's are also ported out of the PR
ContextLoader.add_flattener(
    'tag:yaml.org,2002:seq', ContextLoader.flatten_yaml_seq
)
ContextLoader.add_flattener(
    'tag:yaml.org,2002:map', ContextLoader.flatten_yaml_map
)

ContextLoader.add_constructor(
    ContextLoader.DEFAULT_MAPPING_TAG, ContextLoader.construct_mapping
)
ContextLoader.add_constructor('!include', ContextLoader.construct_include)
ContextLoader.add_flattener('!include', ContextLoader.flatten_include)


# Found http://stackoverflow.com/a/21912744 which guided me on how to hook in
# here
class SortEnforcingLoader(ContextLoader):

    def construct_mapping(self, node, deep=False):
        ret = super().construct_mapping(node, deep)

        keys = list(ret.keys())
        keys_sorted = sorted(keys, key=self.KEYGEN)
        for key in keys:
            expected = keys_sorted.pop(0)
            if key != expected:
                start_mark = node.start_mark
                context = f'{start_mark.name}, line {start_mark.line+1}, column {start_mark.column+1}'
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
    NaturalSortEnforcingLoader.construct_mapping,
)


class SimpleSortEnforcingLoader(SortEnforcingLoader):
    KEYGEN = lambda _, s: s


SimpleSortEnforcingLoader.add_constructor(
    SortEnforcingLoader.DEFAULT_MAPPING_TAG,
    SimpleSortEnforcingLoader.construct_mapping,
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
