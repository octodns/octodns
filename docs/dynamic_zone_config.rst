.. _dynamic-zone-config:

Dynamic Zone Config
===================

Dynamic zone configuration is a powerful tool for reducing the
configuration required to run octoDNS, specifically the *zones* section. Rather
than an exhaustive list of every zone and its corresponding sources and targets
it's possible to define the pattern once with a wildcard.

This is most commonly done with a `YamlProvider`_ which will result in building
the list of zones managed at runtime from the yaml zone files in it's
directory, but any provider that supports the
:py:meth:`octodns.provider.yaml.YamlProvider.list_zones` method can be used.

Any zone name configured in the *zones* section with a leading * is considered
dynamic and the information in this document applies. It is possible to include
multiple dynamic zone configurations in advanced setups utilizing
distinct sources and/or carefully crafted matching as described below.

Matching
--------

There are three types of matching supported: legacy, file-glob, and regular
expression. This ultimately results in very flexible and powerful options, but
makes it pretty easy to build a foot-gun. The matching process has thorough
info and debug logging that can be enabled with **--debug** and should be the
first step in debugging a dynamic zone configuration.

Legacy
......

This is the default mode and the only one supported in versions prior to
1.14.0. It is in effect a catch-all in that any zones returned by the sources'
:py:meth:`octodns.provider.yaml.YamlProvider.list_zones`.

This generally means that it only makes sense to have multiple legacy matchers
when they have distinct sources, otherwise the first one configured will claim
all the zones leaving nothing available.

.. _file-glob:

File-glob
.........

This mode uses Unix shell style matching using the `fnmatch`_ module and is
generally the place to start when trying to apply configs to zones in a single
source or set of sources as it's relatively easy to understand and predict the
behavior of it.

A public and private setup where the public zones are also pushed internally is
a good starting example. If the following zone YAML files are in the *config*
provider's directory::

  company.com.
  foundation.org
  internal.net.
  jobs.company.com.
  other.com
  support.company.com.
  us-east-1.internal.net.
  us-west-2.internal.net.

The following octoDNS configuration would match them as described in comments::

  ---
  ...

  zones:

    # the names here do not really matter beyond starting with a *, it is a
    # reccomended best practice to match the glob, but not required. It will be
    # used in logging to aid in debugging.

    # they are applied in the order defined and once claimed a zone is no
    # longer available for matching

    # everytyhing is available for matching
    '*internal.net':
      # we only want the private zones here and they are all under
      # internet.net. so this glob will claim them.
      glob: '*internal.net.'
      sources:
        - config
      targets:
        # only push it to the private provider
        - private

    # legacy style match everything that's left, all our various public zones
    '*':
      # legacy style match everything that's left, all our various public zones
      sources:
        - config
      targets:
        # push it to the public dns
        - public
        # and private
        - private

This does mean that things are public by default so care would need to be taken
if a new internal zone naming pattern is added.

.. _fnmatch: https://docs.python.org/3/library/fnmatch.html

.. versionadded:: 1.14.0
   File-glob matching support was added in 1.14.0

.. _regular-expression:

Regular Expression
..................

Regular expression mode works similarly to :ref:`file-glob` with the matching
performed by the python regular expression engine `re`_. It enables much more
complex and powerful matching logic with the trade-off of having to work with
regular expressions.

Continuing on with the public/private split, adding in the wrinkles of multiple
internal domain names and the desire to split the regions pushing only to the
co-located DNS servers. All of our internal zones end in .net., anything else
is public::

  company.com.
  foundation.org
  jobs.company.com.
  other.com
  support.company.com.
  us-east-1.hosts.net.
  us-east-1.network.net.
  us-east-1.services.net.
  us-west-2.hosts.net.
  us-west-2.network.net.
  us-west-2.services.net.

The following octoDNS configuration would match them as described in comments::

  ---
  ...

  zones:

    # regexes are too ugly to use as names, so these have useful info for
    # logging/debugging

    # everytyhing is available for matching
    '*us-east-1':
      # we only want the private zones here and they are all under
      # internet.net. So this regex will claim them, yes this could be done
      # with a glob, but ...
      regex: '^.*us-east-1.*.net.$'
      sources:
        - config
      targets:
        # only push it to the us-east-1 provider
        - us-east-1

    # everytyhing with the exception of the us-east-1 .net zones are available
    '*us-west-2':
      regex: '^.*us-west-2.*.net.$'
      sources:
        - config
      targets:
        # only push it to the us-east-1 provider
        - us-west-2

    # legacy style match everything that's left, all our various public zones
    '*':
      sources:
        - config
      targets:
        # push it to the public dns
        - public
        # and private
        - private

.. _re: https://docs.python.org/3/library/re.html

.. versionadded:: 1.14.0
   Regular expression matching support was added in 1.14.0

.. _YamlProvider: /octodns/provider/yaml.py
