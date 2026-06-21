Validators
==========

Record Validators
-----------------

Base classes for record-level and value-level validation. Custom validators
subclass :py:class:`~octodns.record.validator.RecordValidator` or
:py:class:`~octodns.record.validator.ValueValidator` and are registered with
the :py:class:`~octodns.record.validator.ValidatorRegistry`.

.. autosummary::
   :toctree: validators

   octodns.record.validator

Zone Validators
---------------

Base classes and built-in implementations for zone-level validation. Custom
validators subclass :py:class:`~octodns.zone.validator.ZoneValidator` and are
registered via :py:meth:`~octodns.zone.base.Zone.register_zone_validator`.
The :py:class:`~octodns.zone.validator.ZoneValidatorRegistry` activates them
by set name (e.g. ``legacy``, ``strict``, ``best-practice``).

.. autosummary::
   :toctree: validators

   octodns.zone.validator
   octodns.zone.caa
   octodns.zone.cname
   octodns.zone.dname
   octodns.zone.mail
   octodns.zone.ns
   octodns.zone.srv
   octodns.zone.subzone
