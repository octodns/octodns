#
#
#


from .validator import ValueValidator


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
            return ['missing value(s)']
        reasons = []
        for value in data:
            if value == '':
                reasons.append('empty value')
            elif value is None:
                reasons.append('missing value(s)')
            else:
                try:
                    value_cls._address_type(str(value))
                except Exception:
                    addr_name = value_cls._address_name
                    reasons.append(f'invalid {addr_name} address "{value}"')
        return reasons


class _IpValue(str):
    VALIDATORS = [IpValueValidator('ip-value-rfc', sets={'legacy', 'strict'})]

    @classmethod
    def parse_rdata_text(cls, value):
        return value

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

    @property
    def rdata_text(self):
        return self

    def template(self, params):
        return self


_IpAddress = _IpValue
