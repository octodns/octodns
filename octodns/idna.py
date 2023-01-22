#
#
#

from collections.abc import MutableMapping

from idna import IDNAError as _IDNAError
from idna import decode as _decode
from idna import encode as _encode

# Providers will need to to make calls to these at the appropriate points,
# generally right before they pass names off to api calls. For an example of
# usage see https://github.com/octodns/octodns-ns1/pull/20


class IdnaError(Exception):
    def __init__(self, idna_error):
        super().__init__(str(idna_error))


def idna_encode(name):
    # Based on https://github.com/psf/requests/pull/3695/files
    # #diff-0debbb2447ce5debf2872cb0e17b18babe3566e9d9900739e8581b355bd513f7R39
    name = name.lower()
    try:
        name.encode('ascii')
        # No utf8 chars, just use as-is
        return name
    except UnicodeEncodeError:
        try:
            if name.startswith('*'):
                # idna.encode doesn't like the *
                name = _encode(name[2:]).decode('utf-8')
                return f'*.{name}'
            return _encode(name).decode('utf-8')
        except _IDNAError as e:
            raise IdnaError(e)


def idna_decode(name):
    pieces = name.lower().split('.')
    if any(p.startswith('xn--') for p in pieces):
        try:
            # it's idna
            if name.startswith('*'):
                # idna.decode doesn't like the *
                return f'*.{_decode(name[2:])}'
            return _decode(name)
        except _IDNAError as e:
            raise IdnaError(e)
    # not idna, just return as-is
    return name


class IdnaDict(MutableMapping):
    '''A dict type that is insensitive to case and utf-8/idna encoded strings'''

    def __init__(self, data=None):
        self._data = dict()
        if data is not None:
            self.update(data)

    def __setitem__(self, k, v):
        self._data[idna_encode(k)] = v

    def __getitem__(self, k):
        return self._data[idna_encode(k)]

    def __delitem__(self, k):
        del self._data[idna_encode(k)]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def decoded_keys(self):
        for key in self.keys():
            yield idna_decode(key)

    def decoded_items(self):
        for key, value in self.items():
            yield (idna_decode(key), value)

    def __repr__(self):
        return self._data.__repr__()
