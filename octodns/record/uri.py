#
#
#

import re

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import (
    Record,
    ValuesMixin,
    _deprecated_parse_rdata_text,
    _deprecated_rdata_text,
    unquote,
)
from .rr import RdataParseError
from .validator import RecordValidator, ValidationReason, ValueValidator


class UriNameValidator(RecordValidator):
    '''
    Validates that a URI record's name starts with an underscore-prefixed
    service label (RFC 7553 §4.1), either alone (``_kerberos``, as used by
    Kerberos KDC discovery) or followed by more labels (``_ftp._tcp``), or
    is a wildcard with at least one further label.
    '''

    _name_re = re.compile(r'^(\*\.[^\.]+|_[^\.]+(\.|$))')

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        if not self._name_re.match(name):
            return [
                ValidationReason(
                    'invalid name for URI record', validator_id=self.id
                )
            ]
        return []


class UriValueValidator(ValueValidator):
    '''
    Validates URI rdata: priority and weight are present and
    integer-parsable, and target is non-empty.
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            # TODO: validate algorithm and fingerprint_type values
            try:
                int(value['priority'])
            except KeyError:
                reasons.append(
                    ValidationReason('missing priority', validator_id=self.id)
                )
            except ValueError:
                reasons.append(
                    ValidationReason(
                        f'invalid priority "{value["priority"]}"',
                        validator_id=self.id,
                    )
                )
            try:
                int(value['weight'])
            except KeyError:
                reasons.append(
                    ValidationReason('missing weight', validator_id=self.id)
                )
            except ValueError:
                reasons.append(
                    ValidationReason(
                        f'invalid weight "{value["weight"]}"',
                        validator_id=self.id,
                    )
                )
            try:
                target = value['target']
                if not target:
                    reasons.append(
                        ValidationReason('missing target', validator_id=self.id)
                    )
                    continue
                # actual validation of the target is non-trivial and specific
                # to the details of the schema etc. rfc3986 has support for
                # validation, but we don't currently require the module and
                # this seems too esoteric a use case to add it
            except KeyError:
                reasons.append(
                    ValidationReason('missing target', validator_id=self.id)
                )
        return reasons


class UriValueRfcValidator(ValueValidator):
    '''
    Strict URI rdata validator per RFC 7553 §4.

    - ``priority`` must be an integer in [0, 65535] (uint16).
    - ``weight`` must be an integer in [0, 65535] (uint16).

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            for field in ('priority', 'weight'):
                if field not in value:
                    reasons.append(
                        ValidationReason(
                            f'missing {field}', validator_id=self.id
                        )
                    )
                else:
                    try:
                        int_val = int(value[field])
                        if not 0 <= int_val <= 65535:
                            reasons.append(
                                ValidationReason(
                                    f'invalid {field} "{int_val}"; must be 0-65535',
                                    validator_id=self.id,
                                )
                            )
                    except (ValueError, TypeError):
                        reasons.append(
                            ValidationReason(
                                f'invalid {field} "{value[field]}"',
                                validator_id=self.id,
                            )
                        )
            if 'target' not in value:
                reasons.append(
                    ValidationReason('missing target', validator_id=self.id)
                )
        return reasons


class UriValue(EqualityTupleMixin, dict):
    VALIDATORS = [
        UriValueValidator('uri-value', sets={'legacy'}),
        UriValueRfcValidator('uri-value-rfc', sets={'strict'}),
    ]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': ['priority', 'weight', 'target'],
            'properties': {
                'priority': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'weight': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'target': {'type': 'string'},
            },
        }

    @classmethod
    def from_rdata_text(cls, value):
        '''Parse one URI RDATA presentation string into internal field data.

        :param str value: URI RDATA in DNS master-file presentation format
        :returns: octoDNS internal-format URI field mapping
        :rtype: dict
        :raises octodns.record.rr.RdataParseError: if ``value`` is invalid
        '''
        try:
            priority, weight, target = value.split(' ')
        except ValueError:
            raise RdataParseError()
        try:
            priority = int(priority)
        except ValueError:
            pass
        try:
            weight = int(weight)
        except ValueError:
            pass
        target = unquote(target)
        return {'priority': priority, 'weight': weight, 'target': target}

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'priority': int(value['priority']),
                'weight': int(value['weight']),
                'target': idna_encode(value['target']),
            }
        )

    @property
    def priority(self):
        return self['priority']

    @priority.setter
    def priority(self, value):
        self['priority'] = value

    @property
    def weight(self):
        return self['weight']

    @weight.setter
    def weight(self, value):
        self['weight'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def data(self):
        return self

    @classmethod
    def parse_rdata_text(cls, value):
        _deprecated_parse_rdata_text(cls)
        return cls.from_rdata_text(value)

    @property
    def rdata_text(self):
        _deprecated_rdata_text(self)
        return self.to_rdata_text()

    def to_rdata_text(self):
        '''Render this internal URI value as one RDATA presentation string.

        :returns: URI RDATA in DNS master-file presentation format
        :rtype: str
        '''
        return f'{self.priority} {self.weight} "{self.target}"'

    def template(self, params):
        if '{' not in self.target:
            return self
        new = self.__class__(self)
        new.target = new.target.format(**params)
        return new

    def _equality_tuple(self):
        return (self.priority, self.weight, self.target)

    def __repr__(self):
        return f"'{self.priority} {self.weight} \"{self.target}\"'"


class UriNameRfcValidator(RecordValidator):
    '''
    Strict URI owner name validator per RFC 7553 §4.1.

    The name must begin with one or more ``_`` labels, optionally after a
    leading ``*`` wildcard label. Those labels are either an IANA service
    name and protocol (RFC 6335), e.g. ``_ftp._tcp``, or an Enumservice
    type and its subtypes, reversed, one label each (RFC 6117), e.g.
    ``_kerberos`` or ``_c._b._a``. The two forms can't be told apart, so
    each label is checked against the union of both rule sets (RFC 6335
    §5.1, RFC 6116 §3.4.3, RFC 6117 §3.2 and §11.8): 1-32 US-ASCII letters,
    digits, or hyphens, not starting or ending with a hyphen, and not
    starting with ``E2U``. The first label without a leading ``_`` ends
    the run; it and any following labels are the host the service is
    published at, e.g. ``_kerberos.corp``, and aren't checked.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    _label_re = re.compile(r'[A-Za-z0-9]([A-Za-z0-9-]{0,30}[A-Za-z0-9])?')

    @classmethod
    def _is_valid_label(cls, body):
        if not cls._label_re.fullmatch(body):
            return False
        return not body.lower().startswith('e2u')

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        labels = name.split('.') if name else []
        if labels and labels[0] == '*':
            labels = labels[1:]

        service = []
        for label in labels:
            if not label.startswith('_'):
                break
            service.append(label)

        if not service:
            return [
                ValidationReason(
                    'URI name must start with a _service label',
                    validator_id=self.id,
                )
            ]

        return [
            ValidationReason(
                f'invalid URI service label "{label}"', validator_id=self.id
            )
            for label in service
            if not self._is_valid_label(label[1:])
        ]


class UriRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7553',)
    _type = 'URI'
    _value_type = UriValue
    VALIDATORS = [
        UriNameValidator('uri-name', sets={'legacy'}),
        UriNameRfcValidator('uri-name-rfc', sets={'strict'}),
    ]


Record.register_type(UriRecord)
