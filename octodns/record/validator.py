#
#
#


class RecordValidator:
    '''
    Base class for record-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the record is
    valid.
    '''

    @classmethod
    def validate(cls, name, fqdn, data):
        return []


class ValueValidator:
    '''
    Base class for value-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the value is
    valid.
    '''

    @classmethod
    def validate(cls, data, _type):
        return []
