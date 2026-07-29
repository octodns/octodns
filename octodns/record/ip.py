#
#
#

from ..deprecation import deprecated
from .validator import ValidationReason, ValueValidator


class IpValueValidator(ValueValidator):
    '''
    Validates IP address values: rejects empty/missing values and
    defers to the value class's ``_address_type`` (``IPv4Address`` or
    ``IPv6Address``) to parse each value.
    '''

    def validate(self, value_cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        if len(data) == 0:
            return [ValidationReason('missing value(s)', validator_id=self.id)]
        reasons = []
        for value in data:
            if value == '':
                reasons.append(
                    ValidationReason('empty value', validator_id=self.id)
                )
            elif value is None:
                reasons.append(
                    ValidationReason('missing value(s)', validator_id=self.id)
                )
            else:
                try:
                    value_cls._address_type(str(value))
                except Exception:
                    addr_name = value_cls._address_name
                    reasons.append(
                        ValidationReason(
                            f'invalid {addr_name} address "{value}"',
                            validator_id=self.id,
                        )
                    )
        return reasons


class _IpValue(str):
    VALIDATORS = [IpValueValidator('ip-value-rfc', sets={'legacy', 'strict'})]

    @classmethod
    def from_rrs(cls, rdata):
        return rdata

    @classmethod
    def parse_rdata_text(cls, value):
        deprecated(
            f'`{cls.__name__}.parse_rdata_text` is DEPRECATED. Use `{cls.__name__}.from_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        return cls.from_rrs(value)

    @classmethod
    def _schema(cls):
        return {'type': 'string', 'format': cls._address_name.lower()}

    @classmethod
    def process(cls, values):
        # Translating None into '' so that the list will be sortable in
        # python3, get everything to str first
        values = [v if v is not None else '' for v in values]
        # Now round trip all non-'' through the address type and back to a str
        # to normalize the address representation.
        return [cls(v) if v != '' else '' for v in values]

    def __new__(cls, v):
        v = str(cls._address_type(v))
        return super().__new__(cls, v)

    def to_rrs(self):
        return self

    @property
    def rdata_text(self):
        deprecated(
            f'`{self.__class__.__name__}.rdata_text` is DEPRECATED. Use `{self.__class__.__name__}.to_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        return self.to_rrs()

    def template(self, params):
        return self


_IpAddress = _IpValue
