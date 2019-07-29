#
#
#

from logging import getLogger

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
            reasons.append('{}invalid geo code "{}"'.format(prefix, code))
        elif n > 0 and pieces[0] not in geo_data:
            reasons.append('{}unknown continent code "{}"'
                           .format(prefix, code))
        elif n > 1 and pieces[1] not in geo_data[pieces[0]]:
            reasons.append('{}unknown country code "{}"'.format(prefix, code))
        elif n > 2 and \
                pieces[2] not in geo_data[pieces[0]][pieces[1]]['provinces']:
            reasons.append('{}unknown province code "{}"'.format(prefix, code))

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
                return '{}-{}'.format(continent, country)
        cls.log.warn('country_to_code: unrecognized country "%s"', country)
        return

    @classmethod
    def province_to_code(cls, province):
        # We get to cheat on this one since we only support provinces in NA-US
        if province not in geo_data['NA']['US']['provinces']:
            cls.log.warn('country_to_code: unrecognized province "%s"',
                         province)
            return
        return 'NA-US-{}'.format(province)
