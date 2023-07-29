# Contributing

Hi there! We're thrilled that you'd like to contribute to octoDNS. Your help is essential for keeping it great.

Please note that this project adheres to the [Contributor Covenant Code of Conduct](/CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

If you have questions, or you'd like to check with us before embarking on a major development effort, please [open an issue](https://github.com/octodns/octodns/issues/new).

## How to contribute

This project uses the [GitHub Flow](https://guides.github.com/introduction/flow/). That means that the `main` branch is stable and new development is done in feature branches. Feature branches are merged into the `main` branch via a Pull Request.

0. Fork and clone the repository
0. Configure and install the dependencies: `./script/bootstrap`
0. Activate virtual environment: `source env/bin/activate`
0. Make sure the tests pass on your machine: `./script/test`
0. Create a new branch: `git checkout -b my-branch-name`
0. Make your change, add tests, and make sure the tests still pass
0. Make sure that `./script/lint` passes without any warnings
0. Make sure that coverage is at :100:% `./script/coverage` and open `htmlcov/index.html`
   * You can open PRs for :eyes: & discussion prior to this
0. Push to your fork and submit a pull request

We will handle updating the version, tagging the release, and releasing the gem. Please don't bump the version or otherwise attempt to take on these administrative internal tasks as part of your pull request.

Here are a few things you can do that will increase the likelihood of your pull request being accepted:

* Follow [pep8](https://www.python.org/dev/peps/pep-0008/)

- Write thorough tests. No PRs will be merged without :100:% code coverage. More than that tests should be very thorough and cover as many (edge) cases as possible. We're working with DNS here and bugs can have a major impact so we need to do as much as reasonably possible to ensure quality. While :100:% doesn't even begin to mean there are no bugs, getting there often requires close inspection & a relatively complete understanding of the code. More times than not the endeavor will uncover at least minor problems.

- Bug fixes require specific tests covering the addressed behavior.

- Write or update documentation. If you have added a feature or changed an existing one, please make appropriate changes to the docs. Doc-only PRs are always welcome.

- Keep your change as focused as possible. If there are multiple changes you would like to make that are not dependent upon each other, consider submitting them as separate pull requests.

- We target Python 3, support for Python 2 has been dropped.

- Write a [good commit message](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html).

## Development setup

```
./script/bootstrap
source env/bin/activate
```

See the [`script/`](/script) if you'd like to run tests and coverage ([`script/coverage`](/script/coverage)) and coverage ([`script/lint`](/script/lint)). After bootstrapping and sourcing the `env/` commands in the [`octodns/cmds/`](/octodns/cmds) directory can be run with `PYTHONPATH=. ./octodns/cmds/sync.py ...`

## License note

We can only accept contributions that are compatible with the MIT license.

It's OK to depend on gems licensed under either Apache 2.0 or MIT, but we cannot add dependencies on any gems that are licensed under GPL.

Any contributions you make must be under the MIT license.

## Resources

- [Contributing to Open Source on GitHub](https://guides.github.com/activities/contributing-to-open-source/)
- [Using Pull Requests](https://help.github.com/articles/using-pull-requests/)
- [GitHub Help](https://help.github.com)
