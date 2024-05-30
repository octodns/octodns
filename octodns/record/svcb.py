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
            # XXX: these are called SvcPriority, TargetName, and SvcParams in RFC 9460 section 2.
            #       Should we mirror these names, or are priority, target and params good enough?
            # XXX: Should we split params into the specific ParamKeys and ParamValues?
            (priority, target, *params) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            priority = int(priority)
        except ValueError:
            pass
        target = unquote(target)
        return {'priority': priority, 'target': target, 'params': params}

    @classmethod
    def validate(cls, data, _):
        reasons = []
        for value in data:
            priority = -1
            if 'priority' not in value:
                reasons.append('missing priority')
            else:
                try:
                    priority = int(value.get('priority', 0))
                    if priority < 0 or priority > 65535:
                        reasons.append(f'invalid priority ' f'"{priority}"')
                except ValueError:
                    reasons.append(
                        f'invalid priority ' f'"{value["priority"]}"'
                    )

            if 'target' not in value or value['target'] == '':
                reasons.append('missing target')
            else:
                target = str(value.get('target', ''))
                target = idna_encode(target)
                if not target.endswith('.'):
                    reasons.append(f'SVCB value "{target}" missing trailing .')
                if target != '.' and not FQDN(target).is_valid:
                    reasons.append(
                        f'Invalid SVCB target "{target}" is not a valid FQDN.'
                    )

            if 'params' in value:
                params = value.get('params', list())
                if priority == 0 and len(params) != 0:
                    reasons.append('params set on AliasMode SVCB record')
                for param in params:
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
                'priority': int(value['priority']),
                'target': idna_encode(value['target']),
                'params': value.get('params', list()),
            }
        )

    @property
    def priority(self):
        return self['priority']

    @priority.setter
    def priority(self, value):
        self['priority'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def params(self):
        return self['params']

    @params.setter
    def params(self, value):
        self['params'] = value

    @property
    def rdata_text(self):
        params = ''
        if len(self.params) != 0:
            params = f' {" ".join(self.params)}'
        return f'{self.priority} {self.target}{params}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.target, self.params)

    def __repr__(self):
        params = ''
        if len(self.params) != 0:
            params = f' {" ".join(self.params)}'
        return f"'{self.priority} {self.target}{params}'"


class SvcbRecord(ValuesMixin, Record):
    _type = 'SVCB'
    _value_type = SvcbValue


class HttpsRecord(ValuesMixin, Record):
    _type = 'HTTPS'
    _value_type = SvcbValue


Record.register_type(SvcbRecord)
Record.register_type(HttpsRecord)
