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


def encode(s):
    if s.isascii():
        return s
    # there's non-ascii char we need to try and idna deocde it
    return _encode(s).decode('utf-8')


def idna_encode(name):
    # based on urllib3's util.url._normalize_host
    # https://github.com/urllib3/urllib3/blob/6e0e96c76fedec21a7189342f59cd39a1d8e7086/src/urllib3/util/url.py#L323-L326
    try:
        # individually process each label, that allows a mixture of idna and
        # ascii sections where more is allowed in the ascii sections, e.g. '*'
        # and '_'
        return '.'.join(encode(p) for p in name.lower().split('.'))
    except _IDNAError as e:
        raise IdnaError(e)


def decode(s):
    if s.startswith('xn--'):
        # appears to be encoded idna so decode it
        return _decode(s)
    return s


def idna_decode(name):
    try:
        # similar to idna_encode, process things by label
        return '.'.join(decode(p) for p in name.lower().split('.'))
    except _IDNAError as e:
        raise IdnaError(e)


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
