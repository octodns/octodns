<img src="https://raw.githubusercontent.com/octodns/octodns/main/docs/assets/octodns-logo.png?" alt="octoDNS Logo" height=251 width=404>

## DNS as code - Tools for managing DNS across multiple providers

In the vein of [infrastructure as
code](https://en.wikipedia.org/wiki/Infrastructure_as_Code) octoDNS provides a set of tools & patterns that make it easy to manage your DNS records across multiple providers. The resulting config can live in a repository and be [deployed](https://github.com/blog/1241-deploying-at-github) just like the rest of your code, maintaining a clear history and using your existing review & workflow.

The architecture is pluggable and the tooling is flexible to make it applicable to a wide variety of use-cases. Effort has been made to make adding new providers as easy as possible. In the simple case that involves writing of a single `class` and a couple hundred lines of code, most of which is translating between the provider's schema and octoDNS's. More on some of the ways we use it and how to go about extending it below and in the [the documentation](https://octodns.readthedocs.io/en/latest/).

## Documentation

For more information on getting started with and using octoDNS, see [the
documentation](https://octodns.readthedocs.io/en/latest/).

## Contributing

Please see our [contributing document](/CONTRIBUTING.md) if you would like to participate!

## Getting help

If you have a problem or suggestion, please [open an issue](https://github.com/octodns/octodns/issues/new) in this repository, and we will do our best to help. Please note that this project adheres to the [Contributor Covenant Code of Conduct](/CODE_OF_CONDUCT.md).

## License

octoDNS is licensed under the [MIT license](LICENSE).

The MIT license grant is not for GitHub's trademarks, which include the logo designs. GitHub reserves all trademark and copyright rights in and to all GitHub trademarks. GitHub's logos include, for instance, the stylized designs that include "logo" in the file title in the following folder: https://github.com/octodns/octodns/tree/main/docs/logos/

GitHub® and its stylized versions and the Invertocat mark are GitHub's Trademarks or registered Trademarks. When using GitHub's logos, be sure to follow the GitHub logo guidelines.

## Authors

octoDNS was designed and authored by [Ross McFarland](https://github.com/ross) and [Joe Williams](https://github.com/joewilliams). See https://github.com/octodns/octodns/graphs/contributors for a complete list of people who've contributed.
