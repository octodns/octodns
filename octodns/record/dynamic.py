#
#
#

import re
from collections import defaultdict
from logging import getLogger

from .change import Update
from .geo import GeoCodes
from .subnet import Subnets


class _DynamicPool(object):
    log = getLogger('_DynamicPool')

    def __init__(self, _id, data, value_type):
        self._id = _id

        values = [
            {
                'value': value_type(d['value']),
                'weight': d.get('weight', 1),
                'status': d.get('status', 'obey'),
            }
            for d in data['values']
        ]
        values.sort(key=lambda d: d['value'])

        # normalize weight of a single-value pool
        if len(values) == 1:
            weight = data['values'][0].get('weight', 1)
            if weight != 1:
                self.log.warning(
                    'Using weight=1 instead of %s for single-value pool %s',
                    weight,
                    _id,
                )
                values[0]['weight'] = 1

        fallback = data.get('fallback', None)
        self.data = {
            'fallback': fallback if fallback != 'default' else None,
            'values': values,
        }

    def _data(self):
        return self.data

    def __eq__(self, other):
        if not isinstance(other, _DynamicPool):
            return False
        return self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f'{self.data}'


class _DynamicRule(object):
    def __init__(self, i, data):
        self.i = i

        self.data = {}
        try:
            self.data['pool'] = data['pool']
        except KeyError:
            pass
        try:
            self.data['geos'] = sorted(data['geos'])
        except KeyError:
            pass
        try:
            self.data['subnets'] = sorted(data['subnets'])
        except KeyError:
            pass

    def _data(self):
        return self.data

    def __eq__(self, other):
        if not isinstance(other, _DynamicRule):
            return False
        return self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f'{self.data}'


class _Dynamic(object):
    def __init__(self, pools, rules):
        self.pools = pools
        self.rules = rules

    def _data(self):
        pools = {}
        for _id, pool in self.pools.items():
            pools[_id] = pool._data()
        rules = []
        for rule in self.rules:
            rules.append(rule._data())
        return {'pools': pools, 'rules': rules}

    def __eq__(self, other):
        if not isinstance(other, _Dynamic):
            return False
        ret = self.pools == other.pools and self.rules == other.rules
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f'{self.pools}, {self.rules}'


class _DynamicMixin(object):
    geo_re = re.compile(
        r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
        r'(-(?P<subdivision_code>\w\w))?)?$'
    )

    @classmethod
    def _validate_pools(cls, pools):
        reasons = []
        pools_exist = set()
        pools_seen_as_fallback = set()
        if not isinstance(pools, dict):
            reasons.append('pools must be a dict')
        elif not pools:
            reasons.append('missing pools')
        else:
            for _id, pool in sorted(pools.items()):
                if not isinstance(pool, dict):
                    reasons.append(f'pool "{_id}" must be a dict')
                    continue
                try:
                    values = pool['values']
                except KeyError:
                    reasons.append(f'pool "{_id}" is missing values')
                    continue

                pools_exist.add(_id)

                for i, value in enumerate(values):
                    value_num = i + 1
                    try:
                        weight = value['weight']
                        weight = int(weight)
                        if weight < 1 or weight > 100:
                            reasons.append(
                                f'invalid weight "{weight}" in '
                                f'pool "{_id}" value {value_num}'
                            )
                    except KeyError:
                        pass
                    except ValueError:
                        reasons.append(
                            f'invalid weight "{weight}" in '
                            f'pool "{_id}" value {value_num}'
                        )

                    try:
                        status = value['status']
                        if status not in ['up', 'down', 'obey']:
                            reasons.append(
                                f'invalid status "{status}" in '
                                f'pool "{_id}" value {value_num}'
                            )
                    except KeyError:
                        pass

                    try:
                        value = value['value']
                        reasons.extend(
                            cls._value_type.validate(value, cls._type)
                        )
                    except KeyError:
                        reasons.append(
                            f'missing value in pool "{_id}" '
                            f'value {value_num}'
                        )

                if len(values) == 1 and values[0].get('weight', 1) != 1:
                    reasons.append(
                        f'pool "{_id}" has single value with weight!=1'
                    )

                fallback = pool.get('fallback', None)
                if fallback is not None:
                    if fallback in pools:
                        pools_seen_as_fallback.add(fallback)
                    else:
                        reasons.append(
                            f'undefined fallback "{fallback}" '
                            f'for pool "{_id}"'
                        )

                # Check for loops
                fallback = pools[_id].get('fallback', None)
                seen = [_id, fallback]
                while fallback is not None:
                    # See if there's a next fallback
                    fallback = pools.get(fallback, {}).get('fallback', None)
                    if fallback in seen:
                        loop = ' -> '.join(seen)
                        reasons.append(f'loop in pool fallbacks: {loop}')
                        # exit the loop
                        break
                    seen.append(fallback)

        return reasons, pools_exist, pools_seen_as_fallback

    @classmethod
    def _validate_rules(cls, pools, rules):
        reasons = []
        pools_seen = set()

        subnets_seen = defaultdict(dict)
        geos_seen = {}

        if not isinstance(rules, (list, tuple)):
            reasons.append('rules must be a list')
        elif not rules:
            reasons.append('missing rules')
        else:
            seen_default = False

            for i, rule in enumerate(rules):
                rule_num = i + 1
                try:
                    pool = rule['pool']
                except KeyError:
                    reasons.append(f'rule {rule_num} missing pool')
                    continue

                subnets = rule.get('subnets', [])
                geos = rule.get('geos', [])

                if not isinstance(pool, str):
                    reasons.append(f'rule {rule_num} invalid pool "{pool}"')
                else:
                    if pool not in pools:
                        reasons.append(
                            f'rule {rule_num} undefined pool ' f'"{pool}"'
                        )
                    elif pool in pools_seen and (subnets or geos):
                        reasons.append(
                            f'rule {rule_num} invalid, target '
                            f'pool "{pool}" reused'
                        )
                    pools_seen.add(pool)

                if i > 0:
                    # validate that rules are ordered as:
                    # subnets-only > subnets + geos > geos-only
                    previous_subnets = rules[i - 1].get('subnets', [])
                    previous_geos = rules[i - 1].get('geos', [])
                    if subnets and geos:
                        if not previous_subnets and previous_geos:
                            reasons.append(
                                f'rule {rule_num} with subnet(s) and geo(s) should appear before all geo-only rules'
                            )
                    elif subnets:
                        if previous_geos:
                            reasons.append(
                                f'rule {rule_num} with only subnet targeting should appear before all geo targeting rules'
                            )

                if not (subnets or geos):
                    if seen_default:
                        reasons.append(f'rule {rule_num} duplicate default')
                    seen_default = True

                if not isinstance(subnets, (list, tuple)):
                    reasons.append(f'rule {rule_num} subnets must be a list')
                else:
                    for subnet in subnets:
                        reasons.extend(
                            Subnets.validate(subnet, f'rule {rule_num} ')
                        )
                    networks = []
                    for subnet in subnets:
                        try:
                            networks.append(Subnets.parse(subnet))
                        except:
                            # previous loop will log any invalid subnets, here we
                            # process only valid ones and skip invalid ones
                            pass

                    # sort subnets from largest to smallest so that we can
                    # detect rule that have needlessly targeted a more specific
                    # subnet along with a larger subnet that already contains it
                    sorted_networks = sorted(
                        networks, key=lambda n: (n.version, n)
                    )
                    for subnet in sorted_networks:
                        subnets_seen_version = subnets_seen[subnet.version]
                        for seen, where in subnets_seen_version.items():
                            if subnet == seen:
                                reasons.append(
                                    f'rule {rule_num} targets subnet {subnet} which has previously been seen in rule {where}'
                                )
                            elif subnet.subnet_of(seen):
                                reasons.append(
                                    f'rule {rule_num} targets subnet {subnet} which is more specific than the previously seen {seen} in rule {where}'
                                )

                        subnets_seen_version[subnet] = rule_num

                if not isinstance(geos, (list, tuple)):
                    reasons.append(f'rule {rule_num} geos must be a list')
                else:
                    # sorted so that NA would come before NA-US so that the code
                    # below can detect rules that have needlessly targeted a
                    # more specific location along with it's parent/ancestor
                    for geo in sorted(geos):
                        reasons.extend(
                            GeoCodes.validate(geo, f'rule {rule_num} ')
                        )

                        # have we ever seen a broader version of the geo we're
                        # currently looking at, e.g. geo=NA-US and there was a
                        # previous rule with NA
                        for seen, where in geos_seen.items():
                            if geo == seen:
                                reasons.append(
                                    f'rule {rule_num} targets geo {geo} which has previously been seen in rule {where}'
                                )
                            elif geo.startswith(seen):
                                reasons.append(
                                    f'rule {rule_num} targets geo {geo} which is more specific than the previously seen {seen} in rule {where}'
                                )

                        geos_seen[geo] = rule_num

            if rules[-1].get('subnets') or rules[-1].get('geos'):
                reasons.append(
                    'final rule has "subnets" and/or "geos" and is not catchall'
                )

        return reasons, pools_seen

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)

        if 'dynamic' not in data:
            return reasons
        elif 'geo' in data:
            reasons.append('"dynamic" record with "geo" content')

        try:
            pools = data['dynamic']['pools']
        except KeyError:
            pools = {}

        pool_reasons, pools_exist, pools_seen_as_fallback = cls._validate_pools(
            pools
        )
        reasons.extend(pool_reasons)

        try:
            rules = data['dynamic']['rules']
        except KeyError:
            rules = []

        rule_reasons, pools_seen = cls._validate_rules(pools, rules)
        reasons.extend(rule_reasons)

        unused = pools_exist - pools_seen - pools_seen_as_fallback
        if unused:
            unused = '", "'.join(sorted(unused))
            reasons.append(f'unused pools: "{unused}"')

        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super().__init__(zone, name, data, *args, **kwargs)

        self.dynamic = {}

        if 'dynamic' not in data:
            return

        # pools
        try:
            pools = dict(data['dynamic']['pools'])
        except:
            pools = {}

        for _id, pool in sorted(pools.items()):
            pools[_id] = _DynamicPool(_id, pool, self._value_type)

        # rules
        try:
            rules = list(data['dynamic']['rules'])
        except:
            rules = []

        parsed = []
        for i, rule in enumerate(rules):
            parsed.append(_DynamicRule(i, rule))

        # dynamic
        self.dynamic = _Dynamic(pools, parsed)

    def _data(self):
        ret = super()._data()
        if self.dynamic:
            ret['dynamic'] = self.dynamic._data()
        return ret

    def changes(self, other, target):
        if target.SUPPORTS_DYNAMIC:
            if self.dynamic != other.dynamic:
                return Update(self, other)
        return super().changes(other, target)

    def __repr__(self):
        # TODO: improve this whole thing, we need multi-line...
        if self.dynamic:
            # TODO: this hack can't going to cut it, as part of said
            # improvements the value types should deal with serializing their
            # value
            try:
                values = self.values
            except AttributeError:
                values = self.value

            klass = self.__class__.__name__
            return (
                f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, '
                f'{values}, {self.dynamic}>'
            )
        return super().__repr__()
