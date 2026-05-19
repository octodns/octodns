#
#
#
#

from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING, Any

from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from .base import ValuesMixin, _process_value_validators
from .change import Update
from .geo_data import geo_data
from .validator import RecordValidator

if TYPE_CHECKING:
    from typing import Sequence


class GeoCodes(object):
    log = getLogger('GeoCodes')

    @classmethod
    def validate(cls, code: str, prefix: str) -> list[str]:
        '''
        Validates an octoDNS geo code making sure that it is a valid and
        corresponding:

          * continent
          * continent & country
          * continent, country, & province
        '''
        reasons: list[str] = []

        pieces = code.split('-')
        n = len(pieces)
        if n > 3:
            reasons.append(f'{prefix}invalid geo code "{code}"')
        elif n > 0 and pieces[0] not in geo_data:
            reasons.append(f'{prefix}unknown continent code "{code}"')
        elif n > 1 and pieces[1] not in geo_data[pieces[0]]:
            reasons.append(f'{prefix}unknown country code "{code}"')
        elif (
            n > 2
            and pieces[2] not in geo_data[pieces[0]][pieces[1]]['provinces']
        ):
            reasons.append(f'{prefix}unknown province code "{code}"')

        return reasons

    @classmethod
    def parse(cls, code: str) -> dict[str, Any | None]:
        pieces = code.split('-')
        try:
            country_code = pieces[1]
        except IndexError:
            country_code = None
        try:
            province_code = pieces[2]
        except IndexError:
            province_code = None
        return {
            'continent_code': pieces[0],
            'country_code': country_code,
            'province_code': province_code,
        }

    @classmethod
    def country_to_code(cls, country: str) -> str | None:
        for continent, countries in geo_data.items():
            if country in countries:
                return f'{continent}-{country}'
        cls.log.warning('country_to_code: unrecognized country "%s"', country)
        return None

    @classmethod
    def province_to_code(cls, province: str) -> str | None:
        # We cheat on this one a little since we only support provinces in
        # NA-US, NA-CA
        if (
            province not in geo_data['NA']['US']['provinces']
            and province not in geo_data['NA']['CA']['provinces']
        ):
            cls.log.warning(
                'country_to_code: unrecognized province "%s"', province
            )
            return None
        if province in geo_data['NA']['US']['provinces']:
            country = 'US'
        if province in geo_data['NA']['CA']['provinces']:
            country = 'CA'
        return f'NA-{country}-{province}'


class GeoValue(EqualityTupleMixin):
    geo_re = re.compile(
        r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
        r'(-(?P<subdivision_code>\w\w))?)?$'
    )

    @classmethod
    def _validate_geo(cls, code: str) -> list[str]:
        reasons: list[str] = []
        match = cls.geo_re.match(code)
        if not match:
            reasons.append(f'invalid geo "{code}"')
        return reasons

    def __init__(self, geo: str, values: Sequence[str]) -> None:
        self.code = geo
        match = self.geo_re.match(geo)
        self.continent_code = match.group('continent_code')  # type: ignore[union-attr]
        self.country_code = match.group('country_code')  # type: ignore[union-attr]
        self.subdivision_code = match.group('subdivision_code')  # type: ignore[union-attr]
        self.values = sorted(values)

    @property
    def parents(self) -> list[str]:
        bits = self.code.split('-')[:-1]
        while bits:
            yield '-'.join(bits)
            bits.pop()

    def _equality_tuple(self) -> tuple[str, str | None, str | None, list[str]]:
        return (
            self.continent_code,
            self.country_code,
            self.subdivision_code,
            self.values,
        )

    def __repr__(self) -> str:
        return (
            f"'Geo {self.continent_code} {self.country_code} "
            "{self.subdivision_code} {self.values}'"
        )


class GeoValidator(RecordValidator):
    '''
    Validates the deprecated ``geo`` block of a record: each key is a
    valid continent/country/subdivision code and each list of values
    passes the record's value-type validation.
    '''

    def validate(
        self, record_cls: Any, name: str, fqdn: str, data: dict[str, Any]
    ) -> list[str]:
        reasons: list[str] = []
        try:
            geo = dict(data['geo'])
            deprecated(
                '`geo` records are DEPRECATED. `dynamic` records should be used instead. Will be removed in 2.0',
                stacklevel=99,
            )
            for code, values in geo.items():
                reasons.extend(GeoValue._validate_geo(code))
                reasons.extend(
                    _process_value_validators(
                        record_cls._value_type, values, record_cls._type  # type: ignore[attr-defined]
                    )
                )
        except KeyError:
            pass
        return reasons


class _GeoMixin(ValuesMixin):
    '''
    Adds GeoDNS support to a record.

    Must be included before `Record`.
    '''

    VALIDATORS: list[Any] = [GeoValidator('geo', sets={'legacy'})]

    @classmethod
    def _schema(cls, value_schema: Any) -> dict[str, Any]:
        '''JSON Schema fragment describing the `geo` block.

        Keys are geo codes (continent, continent-country, or
        continent-country-subdivision); values are lists of record values.
        '''
        return {
            'type': 'object',
            'propertyNames': {'pattern': r'^[A-Z]{2}(-[A-Z]{2}(-[A-Z]{2})?)?$'},
            'additionalProperties': {
                'type': 'array',
                'items': value_schema,
                'minItems': 1,
            },
        }

    def __init__(
        self,
        zone: Any,
        name: str,
        data: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(zone, name, data, *args, **kwargs)
        try:
            self.geo = dict(data['geo'])  # type: ignore[attr-defined]
        except KeyError:
            self.geo = {}  # type: ignore[attr-defined]
        for code, values in self.geo.items():
            self.geo[code] = GeoValue(code, values)  # type: ignore[attr-defined]

    def _data(self) -> dict[str, Any]:
        ret = super()._data()
        if self.geo:
            geo = {}
            for code, value in self.geo.items():
                geo[code] = value.values
            ret['geo'] = geo
        return ret

    def changes(self, other: Any, target: Any) -> Update | None:
        if target.SUPPORTS_GEO:
            if self.geo != other.geo:  # type: ignore[attr-defined]
                return Update(self, other)
        return super().changes(other, target)

    def __repr__(self) -> str:
        if self.geo:
            klass = self.__class__.__name__
            return (
                f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, '  # type: ignore[attr-defined]
                f'{self.values}, {self.geo}>'
            )
        return super().__repr__()
