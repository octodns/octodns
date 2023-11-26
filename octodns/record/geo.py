#
#
#

import re
from logging import getLogger

from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from .base import ValuesMixin
from .change import Update
from .geo_data import geo_data


class GeoCodes(object):
    log = getLogger('GeoCodes')

    @classmethod
    def validate(cls, code, prefix):
        '''
        Validates an octoDNS geo code making sure that it is a valid and
        corresponding:
            * continent
            * continent & country
            * continent, country, & province
        '''
        reasons = []

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
    def parse(cls, code):
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
    def country_to_code(cls, country):
        for continent, countries in geo_data.items():
            if country in countries:
                return f'{continent}-{country}'
        cls.log.warning('country_to_code: unrecognized country "%s"', country)
        return

    @classmethod
    def province_to_code(cls, province):
        # We cheat on this one a little since we only support provinces in
        # NA-US, NA-CA
        if (
            province not in geo_data['NA']['US']['provinces']
            and province not in geo_data['NA']['CA']['provinces']
        ):
            cls.log.warning(
                'country_to_code: unrecognized province "%s"', province
            )
            return
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
    def _validate_geo(cls, code):
        reasons = []
        match = cls.geo_re.match(code)
        if not match:
            reasons.append(f'invalid geo "{code}"')
        return reasons

    def __init__(self, geo, values):
        self.code = geo
        match = self.geo_re.match(geo)
        self.continent_code = match.group('continent_code')
        self.country_code = match.group('country_code')
        self.subdivision_code = match.group('subdivision_code')
        self.values = sorted(values)

    @property
    def parents(self):
        bits = self.code.split('-')[:-1]
        while bits:
            yield '-'.join(bits)
            bits.pop()

    def _equality_tuple(self):
        return (
            self.continent_code,
            self.country_code,
            self.subdivision_code,
            self.values,
        )

    def __repr__(self):
        return (
            f"'Geo {self.continent_code} {self.country_code} "
            "{self.subdivision_code} {self.values}'"
        )


class _GeoMixin(ValuesMixin):
    '''
    Adds GeoDNS support to a record.

    Must be included before `Record`.
    '''

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)
        try:
            geo = dict(data['geo'])
            deprecated(
                '`geo` records are DEPRECATED. `dynamic` records should be used instead. Will be removed in 2.0',
                stacklevel=99,
            )
            for code, values in geo.items():
                reasons.extend(GeoValue._validate_geo(code))
                reasons.extend(cls._value_type.validate(values, cls._type))
        except KeyError:
            pass
        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super().__init__(zone, name, data, *args, **kwargs)
        try:
            self.geo = dict(data['geo'])
        except KeyError:
            self.geo = {}
        for code, values in self.geo.items():
            self.geo[code] = GeoValue(code, values)

    def _data(self):
        ret = super()._data()
        if self.geo:
            geo = {}
            for code, value in self.geo.items():
                geo[code] = value.values
            ret['geo'] = geo
        return ret

    def changes(self, other, target):
        if target.SUPPORTS_GEO:
            if self.geo != other.geo:
                return Update(self, other)
        return super().changes(other, target)

    def __repr__(self):
        if self.geo:
            klass = self.__class__.__name__
            return (
                f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, '
                f'{self.values}, {self.geo}>'
            )
        return super().__repr__()
