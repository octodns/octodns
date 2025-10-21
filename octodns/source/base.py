#
#
#


class BaseSource(object):
    '''
    Base class for all octoDNS sources and providers.

    Sources are responsible for loading DNS records from various backends into
    octoDNS zones. They implement the ``populate`` method to read DNS data from
    their respective data stores (YAML files, APIs, databases, etc.) and add
    records to the provided zone.

    Subclasses must define the following class attributes either statically or
    prior to calling ``super().__init__``:

    - **SUPPORTS**: Set of supported record types (e.g., ``{'A', 'AAAA', 'CNAME'}``)
    - **SUPPORTS_GEO**: Boolean indicating if the source supports GeoDNS records
    - **log**: Logger instance for the source

    Optional class attributes:

    - **SUPPORTS_MULTIVALUE_PTR**: Support for multiple PTR records (default: False)
    - **SUPPORTS_POOL_VALUE_STATUS**: Support for pool value status flags (default: False)
    - **SUPPORTS_ROOT_NS**: Support for root NS records (default: False)
    - **SUPPORTS_DYNAMIC_SUBNETS**: Support for dynamic subnet-based routing (default: False)

    Example usage::

      sources:
        config:
          class: octodns.provider.yaml.YamlProvider
          directory: ./config

      zones:
        example.com.:
          sources:
            - config
          targets:
            - route53

    See Also:
        - :class:`octodns.provider.yaml.YamlProvider`
        - :class:`octodns.source.tinydns.TinyDnsFileSource`
        - :class:`octodns.source.envvar.EnvVarSource`
    '''

    SUPPORTS_MULTIVALUE_PTR = False
    SUPPORTS_POOL_VALUE_STATUS = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS_DYNAMIC_SUBNETS = False

    def __init__(self, id):
        '''
        Initialize the source.

        :param id: Unique identifier for this source instance. Used in logging
                   and configuration references.
        :type id: str

        :raises NotImplementedError: If required class attributes (``log``,
                                     ``SUPPORTS_GEO``, or ``SUPPORTS``) are not
                                     defined in the subclass.
        '''

        self.id = id
        if not getattr(self, 'log', False):
            raise NotImplementedError(
                'Abstract base class, log property missing'
            )
        if not hasattr(self, 'SUPPORTS_GEO'):
            raise NotImplementedError(
                'Abstract base class, SUPPORTS_GEO property missing'
            )
        if not hasattr(self, 'SUPPORTS'):
            raise NotImplementedError(
                'Abstract base class, SUPPORTS property missing'
            )

    @property
    def SUPPORTS_DYNAMIC(self):
        '''
        Indicates whether this source supports dynamic records.

        Dynamic records include advanced routing features like GeoDNS pools,
        health checks, and weighted responses. Most sources do not support
        dynamic records.

        :return: True if dynamic records are supported, False otherwise.
        :rtype: bool
        '''
        return False

    def populate(self, zone, target=False, lenient=False):
        '''
        Load DNS records from the source into the provided zone.

        This method is responsible for reading DNS data from the source's
        backend and adding records to the zone using ``zone.add_record()``.
        Subclasses must implement this method.

        :param zone: The zone to populate with records from this source.
        :type zone: octodns.zone.Zone
        :param target: If True, the populate call is loading the current state
                       from a target provider (for comparison during sync). If
                       False, loading desired state from a source.
        :type target: bool
        :param lenient: If True, skip strict record validation and do a "best
                        effort" load of data. This allows some non-best-practice
                        configurations through (e.g., missing trailing dots or
                        unescaped semicolons).
        :type lenient: bool

        :return: When ``target`` is True (loading current state), should return
                 True if the zone exists in the target or False if it does not.
                 When ``target`` is False (loading desired state), return value
                 is ignored and may be None.
        :rtype: bool or None

        :raises NotImplementedError: This base class method must be overridden
                                     by subclasses.

        .. important::
           - Must use ``zone.add_record()`` to add records to the zone.
           - Should not modify the zone name or other zone properties.
           - When ``target=True``, must return a boolean indicating zone existence.
           - When ``lenient=True``, should relax validation to handle common
             non-standard configurations.
        '''
        raise NotImplementedError(
            'Abstract base class, populate method missing'
        )

    def supports(self, record):
        '''
        Check if this source supports the given record type.

        :param record: The DNS record to check for support.
        :type record: octodns.record.base.Record

        :return: True if the record type is supported, False otherwise.
        :rtype: bool
        '''
        return record._type in self.SUPPORTS

    def __repr__(self):
        '''
        Return a string representation of this source.

        :return: The class name of this source instance.
        :rtype: str
        '''
        return self.__class__.__name__
