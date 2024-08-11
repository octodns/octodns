#
# This file describes the SVCB records as defined in RFC 9460
# It also supports the 'ech' SvcParam as defined in draft-ietf-tls-svcb-ech-02
#

from base64 import b64decode
from binascii import Error as binascii_error
from ipaddress import AddressValueError, IPv4Address, IPv6Address

from fqdn import FQDN

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .chunked import _ChunkedValue
from .rr import RrParseError

SUPPORTED_PARAMS = {}


def validate_svcparam_port(svcparamvalue):
    reasons = []
    try:
        port = int(svcparamvalue)
        if 0 < port > 65535:
            reasons.append(f'port {port} is not a valid number')
    except ValueError:
        reasons.append('port is not a number')
    return reasons


def validate_list(svcparamkey, svcparamvalue):
    if not isinstance(svcparamvalue, list):
        return [f'{svcparamkey} is not a list']
    return list()


def validate_svcparam_alpn(svcparamvalue):
    reasons = validate_list('alpn', svcparamvalue)
    if len(reasons) != 0:
        return reasons
    for alpn in svcparamvalue:
        reasons += _ChunkedValue.validate(alpn, 'SVCB')
    return reasons


def validate_svcparam_iphint(ip_version, svcparamvalue):
    reasons = validate_list(f'ipv{ip_version}hint', svcparamvalue)
    if len(reasons) != 0:
        return reasons
    for address in svcparamvalue:
        try:
            if ip_version == 4:
                IPv4Address(address)
            if ip_version == 6:
                IPv6Address(address)
        except AddressValueError:
            reasons.append(
                f'ipv{ip_version}hint "{address}" is not a valid IPv{ip_version} address'
            )
    return reasons


def validate_svcparam_ipv4hint(svcparamvalue):
    return validate_svcparam_iphint(4, svcparamvalue)


def validate_svcparam_ipv6hint(svcparamvalue):
    return validate_svcparam_iphint(6, svcparamvalue)


def validate_svcparam_mandatory(svcparamvalue):
    reasons = validate_list('mandatory', svcparamvalue)
    if len(reasons) != 0:
        return reasons
    for mandatory in svcparamvalue:
        if (
            mandatory not in SUPPORTED_PARAMS.keys()
            and not mandatory.startswith('key')
        ):
            reasons.append(f'unsupported SvcParam "{mandatory}" in mandatory')
        if mandatory.startswith('key'):
            reasons += validate_svckey_number(mandatory)
    return reasons


def validate_svcparam_ech(svcparamvalue):
    try:
        b64decode(svcparamvalue, validate=True)
    except binascii_error:
        return ['ech SvcParam is invalid Base64']


def validate_svckey_number(paramkey):
    try:
        paramkeynum = int(paramkey[3:])
        if 7 < paramkeynum > 65535:
            return [f'SvcParam key "{paramkey}" has wrong key number']
    except ValueError:
        return [f'SvcParam key "{paramkey}" has wrong format']
    return []


def parse_rdata_text_svcparamvalue_list(svcparamvalue):
    if svcparamvalue.startswith('"'):
        svcparamvalue = svcparamvalue[1:-1]
    return svcparamvalue.split(',')


def svcparamkeysort(svcparamkey):
    if svcparamkey.startswith('key'):
        return int(svcparamkey[3:])
    return SUPPORTED_PARAMS[svcparamkey]['key_num']


# cc https://datatracker.ietf.org/doc/html/rfc9460#keys
SUPPORTED_PARAMS = {
    'no-default-alpn': {'key_num': 2, 'has_arg': False},
    'alpn': {
        'key_num': 1,
        'validate': validate_svcparam_alpn,
        'parse_rdata_text': parse_rdata_text_svcparamvalue_list,
    },
    'port': {'key_num': 3, 'validate': validate_svcparam_port},
    'ipv4hint': {
        'key_num': 4,
        'validate': validate_svcparam_ipv4hint,
        'parse_rdata_text': parse_rdata_text_svcparamvalue_list,
    },
    'ipv6hint': {
        'key_num': 6,
        'validate': validate_svcparam_ipv6hint,
        'parse_rdata_text': parse_rdata_text_svcparamvalue_list,
    },
    'mandatory': {
        'key_num': 0,
        'validate': validate_svcparam_mandatory,
        'parse_rdata_text': parse_rdata_text_svcparamvalue_list,
    },
    'ech': {'key_num': 5, 'validate': validate_svcparam_ech},
}


class SvcbValue(EqualityTupleMixin, dict):

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            (svcpriority, targetname, *svcparams) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            svcpriority = int(svcpriority)
        except ValueError:
            pass
        targetname = unquote(targetname)
        params = dict()
        for svcparam in svcparams:
            paramkey, *paramvalue = svcparam.split('=')
            if paramkey in params.keys():
                raise RrParseError(f'{paramkey} is specified twice')
            if len(paramvalue) != 0:
                parse_rdata_text = SUPPORTED_PARAMS.get(paramkey, {}).get(
                    'parse_rdata_text', None
                )
                if parse_rdata_text is None:
                    v = paramvalue[0]
                    if v.startswith('"'):
                        v = v[1:-1]
                    params[paramkey] = v
                else:
                    params[paramkey] = parse_rdata_text(paramvalue[0])
            else:
                params[paramkey] = None
        return {
            'svcpriority': svcpriority,
            'targetname': targetname,
            'svcparams': params,
        }

    @classmethod
    def validate(cls, data, _):
        reasons = []
        for value in data:
            svcpriority = -1
            if 'svcpriority' not in value:
                reasons.append('missing svcpriority')
            else:
                try:
                    svcpriority = int(value.get('svcpriority', 0))
                    if svcpriority < 0 or svcpriority > 65535:
                        reasons.append(f'invalid priority ' f'"{svcpriority}"')
                except ValueError:
                    reasons.append(f'invalid priority "{value["svcpriority"]}"')

            if 'targetname' not in value or value['targetname'] == '':
                reasons.append('missing targetname')
            else:
                targetname = str(value.get('targetname', ''))
                targetname = idna_encode(targetname)
                if not targetname.endswith('.'):
                    reasons.append(
                        f'SVCB value "{targetname}" missing trailing .'
                    )
                if targetname != '.' and not FQDN(targetname).is_valid:
                    reasons.append(
                        f'Invalid SVCB target "{targetname}" is not a valid FQDN.'
                    )

            if 'svcparams' in value:
                svcparams = value.get('svcparams', dict())
                if svcpriority == 0 and len(svcparams) != 0:
                    reasons.append('svcparams set on AliasMode SVCB record')
                for svcparamkey, svcparamvalue in svcparams.items():
                    # XXX: Should we test for keys existing when set in 'mandatory'?
                    if svcparamkey.startswith('key'):
                        reasons += validate_svckey_number(svcparamkey)
                        continue
                    if (
                        svcparamkey not in SUPPORTED_PARAMS.keys()
                        and not svcparamkey.startswith('key')
                    ):
                        reasons.append(f'Unknown SvcParam {svcparamkey}')
                        continue
                    if SUPPORTED_PARAMS[svcparamkey].get('has_arg', True):
                        reasons += SUPPORTED_PARAMS[svcparamkey]['validate'](
                            svcparamvalue
                        )
                    if (
                        not SUPPORTED_PARAMS[svcparamkey].get('has_arg', True)
                        and svcparamvalue is not None
                    ):
                        reasons.append(
                            f'SvcParam {svcparamkey} has value when it should not'
                        )

        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'svcpriority': int(value['svcpriority']),
                'targetname': idna_encode(value['targetname']),
                'svcparams': value.get('svcparams', dict()),
            }
        )

    @property
    def svcpriority(self):
        return self['svcpriority']

    @svcpriority.setter
    def svcpriority(self, value):
        self['svcpriority'] = value

    @property
    def targetname(self):
        return self['targetname']

    @targetname.setter
    def targetname(self, value):
        self['targetname'] = value

    @property
    def svcparams(self):
        return self['svcparams']

    @svcparams.setter
    def svcparams(self, value):
        self['svcparams'] = value

    @property
    def rdata_text(self):
        params = ''
        sorted_svcparamkeys = sorted(self.svcparams, key=svcparamkeysort)
        for svcparamkey in sorted_svcparamkeys:
            params += f' {svcparamkey}'
            svcparamvalue = self.svcparams.get(svcparamkey, None)
            if svcparamvalue is not None:
                if isinstance(svcparamvalue, list):
                    params += f'={",".join(svcparamvalue)}'
                else:
                    params += f'={svcparamvalue}'
        return f'{self.svcpriority} {self.targetname}{params}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        params = set()
        for svcparamkey, svcparamvalue in self.svcparams.items():
            if svcparamvalue is not None:
                if isinstance(svcparamvalue, list):
                    params.add(f'{svcparamkey}={",".join(svcparamvalue)}')
                else:
                    params.add(f'{svcparamkey}={svcparamvalue}')
            else:
                params.add(f'{svcparamkey}')
        return (self.svcpriority, self.targetname, params)

    def __repr__(self):
        return f"'{self.rdata_text}'"


class SvcbRecord(ValuesMixin, Record):
    _type = 'SVCB'
    _value_type = SvcbValue


Record.register_type(SvcbRecord)
