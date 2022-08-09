#
#
#

from idna import decode as _decode, encode as _encode

# Providers will need to to make calls to these at the appropriate points,
# generally right before they pass names off to api calls. For an example of
# usage see https://github.com/octodns/octodns-ns1/pull/20


def idna_encode(name):
    # Based on https://github.com/psf/requests/pull/3695/files
    # #diff-0debbb2447ce5debf2872cb0e17b18babe3566e9d9900739e8581b355bd513f7R39
    try:
        name.encode('ascii')
        # No utf8 chars, just use as-is
        return name
    except UnicodeEncodeError:
        if name.startswith('*'):
            # idna.encode doesn't like the *
            name = _encode(name[2:]).decode('utf-8')
            return f'*.{name}'
        return _encode(name).decode('utf-8')


def idna_decode(name):
    pieces = name.lower().split('.')
    if any(p.startswith('xn--') for p in pieces):
        # it's idna
        if name.startswith('*'):
            # idna.decode doesn't like the *
            return f'*.{_decode(name[2:])}'
        return _decode(name)
    # not idna, just return as-is
    return name
