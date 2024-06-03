#
# This file describes the SVCB and HTTPS records as defined in RFC 9460
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


def validate_svcparam_alpn(svcparamvalue):
    reasons = []
    alpns = svcparamvalue.split(',')
    for alpn in alpns:
        reasons += _ChunkedValue.validate(alpn, 'SVCB')
    return reasons


def validate_svcparam_iphint(ip_version, svcparamvalue):
    reasons = []
    addresses = svcparamvalue.split(',')
    for address in addresses:
        try:
            if ip_version == 4:
                IPv4Address(address)
            if ip_version == 6:
                IPv6Address(address)
        except AddressValueError:
            reasons.append(
                f'ip{ip_version}hint "{address}" is not a valid IPv{ip_version} address'
            )
    return reasons


def validate_svcparam_ip4hint(svcparamvalue):
    return validate_svcparam_iphint(4, svcparamvalue)


def validate_svcparam_ip6hint(svcparamvalue):
    return validate_svcparam_iphint(6, svcparamvalue)


def validate_svcparam_mandatory(svcparamvalue):
    reasons = []
    mandatories = svcparamvalue.split(',')
    for mandatory in mandatories:
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


# cc https://datatracker.ietf.org/doc/html/rfc9460#keys
SUPPORTED_PARAMS = {
    'no-default-alpn': {'has_arg': False},
    'alpn': {'validate': validate_svcparam_alpn},
    'port': {'validate': validate_svcparam_port},
    'ipv4hint': {'validate': validate_svcparam_ip4hint},
    'ipv6hint': {'validate': validate_svcparam_ip6hint},
    'mandatory': {'validate': validate_svcparam_mandatory},
    'ech': {'validate': validate_svcparam_ech},
}


class SvcbValue(EqualityTupleMixin, dict):

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            # XXX: Should we split params into the specific ParamKeys and ParamValues?
            (svcpriority, targetname, *svcparams) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            svcpriority = int(svcpriority)
        except ValueError:
            pass
        targetname = unquote(targetname)
        return {
            'svcpriority': svcpriority,
            'targetname': targetname,
            'svcparams': svcparams,
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
                svcparams = value.get('svcparams', list())
                if svcpriority == 0 and len(svcparams) != 0:
                    reasons.append('svcparams set on AliasMode SVCB record')
                for param in svcparams:
                    # XXX: Should we test for keys existing when set in 'mandatory'?
                    paramkey, *paramvalue = param.split('=')
                    if paramkey.startswith('key'):
                        reasons += validate_svckey_number(paramkey)
                        continue
                    if (
                        paramkey not in SUPPORTED_PARAMS.keys()
                        and not paramkey.startswith('key')
                    ):
                        reasons.append(f'Unknown SvcParam {paramkey}')
                        continue
                    if SUPPORTED_PARAMS[paramkey].get('has_arg', True):
                        reasons += SUPPORTED_PARAMS[paramkey]['validate'](
                            paramvalue[0]
                        )
                    if (
                        not SUPPORTED_PARAMS[paramkey].get('has_arg', True)
                        and len(paramvalue) != 0
                    ):
                        reasons.append(
                            f'SvcParam {paramkey} has value when it should not'
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
                'svcparams': value.get('svcparams', list()),
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
        if len(self.svcparams) != 0:
            params = f' {" ".join(self.svcparams)}'
        return f'{self.svcpriority} {self.targetname}{params}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.svcpriority, self.targetname, self.svcparams)

    def __repr__(self):
        return f"'{self.rdata_text}'"


class SvcbRecord(ValuesMixin, Record):
    _type = 'SVCB'
    _value_type = SvcbValue


class HttpsRecord(ValuesMixin, Record):
    _type = 'HTTPS'
    _value_type = SvcbValue


Record.register_type(SvcbRecord)
Record.register_type(HttpsRecord)
