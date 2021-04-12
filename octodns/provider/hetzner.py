#
#
#

from requests import Session


class HetznerClientException(Exception):
    pass


class HetznerClientNotFound(HetznerClientException):

    def __init__(self):
        super(HetznerClientNotFound, self).__init__('Not Found')


class HetznerClient(object):
    '''
    Hetzner DNS Public API v1 client class.

    Zone and Record resources are (almost) fully supported, even if unnecessary
    to future-proof this client. Bulk Record create/update is not supported.

    No support for Primary Servers.
    '''

    BASE_URL = 'https://dns.hetzner.com/api/v1'

    def __init__(self, token):
        session = Session()
        session.headers.update({'Auth-API-Token': token})
        self._session = session

    def _do(self, method, path, params=None, data=None):
        url = self.BASE_URL + path
        response = self._session.request(method, url, params=params, json=data)
        if response.status_code == 404:
            raise HetznerClientNotFound()
        response.raise_for_status()
        return response.json()

    def _do_with_pagination(self, method, path, key, params=None, data=None,
                            per_page=100):
        pagination_params = {'page': 1, 'per_page': per_page}
        if params is not None:
            params = {**params, **pagination_params}
        else:
            params = pagination_params

        items = []
        while True:
            response = self._do(method, path, params, data)
            items += response[key]
            if response['meta']['pagination']['page'] >= \
               response['meta']['pagination']['last_page']:
                break
            params['page'] += 1
        return items

    def zones_get(self, name=None, search_name=None):
        params = {'name': name, 'search_name': search_name}
        return self._do_with_pagination('GET', '/zones', 'zones',
                                        params=params)

    def zone_get(self, zone_id):
        return self._do('GET', '/zones/' + zone_id)['zone']

    def zone_create(self, name, ttl=None):
        data = {'name': name, 'ttl': ttl}
        return self._do('POST', '/zones', data=data)['zone']

    def zone_update(self, zone_id, name, ttl=None):
        data = {'name': name, 'ttl': ttl}
        return self._do('PUT', '/zones/' + zone_id, data=data)['zone']

    def zone_delete(self, zone_id):
        return self._do('DELETE', '/zones/' + zone_id)

    def zone_records_get(self, zone_id):
        params = {'zone_id': zone_id}
        # No need to handle pagination as it returns all records by default.
        return self._do('GET', '/records', params=params)['records']

    def zone_record_get(self, record_id):
        return self._do('GET', '/records/' + record_id)['record']

    def zone_record_create(self, zone_id, name, _type, value, ttl=None):
        data = {'name': name, 'ttl': ttl, 'type': _type, 'value': value,
                'zone_id': zone_id}
        return self._do('POST', '/records', data=data)['record']

    def zone_record_update(self, zone_id, record_id, name, _type, value,
                           ttl=None):
        data = {'name': name, 'ttl': ttl, 'type': _type, 'value': value,
                'zone_id': zone_id}
        return self._do('PUT', '/records/' + record_id, data=data)['record']

    def zone_record_delete(self, zone_id, record_id):
        return self._do('DELETE', '/records/' + record_id)
