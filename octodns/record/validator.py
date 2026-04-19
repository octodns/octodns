#
#
#


class RecordValidator:
    '''
    Base class for record-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the record is
    valid. ``record_cls`` is the concrete Record subclass being validated and
    gives validators access to class-level attributes (``_type``,
    ``_value_type``, etc.) when needed.
    '''

    @classmethod
    def validate(cls, record_cls, name, fqdn, data):
        return []


class ValueValidator:
    '''
    Base class for value-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the value is
    valid. ``value_cls`` is the concrete value class being validated.
    '''

    @classmethod
    def validate(cls, value_cls, data, _type):
        return []
