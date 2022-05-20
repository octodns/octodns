#
#
#

from idna import decode as _decode, encode as _encode


def idna_encode(name):
    if not name:
        # idna.encode doesn't handle ''
        return name
    elif name.startswith('*'):
        # idna.encode doesn't like the *
        name = _encode(name[2:]).decode('utf-8')
        return f'*.{name}'
    return _encode(name).decode('utf-8')


def idna_decode(name):
    if not name:
        # idna.decode doesn't handle ''
        return name
    elif name.startswith('*'):
        # idna.decode doesn't like the *
        return f'*.{_decode(name[2:])}'
    return _decode(name)
