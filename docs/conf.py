import json
import os
import sys
from pathlib import Path
from subprocess import DEVNULL, STDOUT, CalledProcessError, check_output

from docutils import nodes

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

print(f"SYS.PATH={sys.path}")

from octodns.__init__ import __version__
from octodns.schema import build_config_schema, build_zone_schema

### sphinx config ###

project = "octoDNS"
copyright = "2017-present"  # noqa
author = "Ross McFarland"
release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "sphinx_rtd_theme",
]


### autodoc ###

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": True,
    "special-members": "__init__, __repr__",
    # "inherited-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}
autodoc_typehints = "both"
autodoc_typehints_description_target = "all"
autodoc_member_order = "bysource"

### extlinks ###

extlinks = {
    "github": ("https://github.com/%s", "%s"),
    "pypi": ("https://pypi.org/project/%s/", "%s"),
}
extlinks_detect_hardcoded_links = True


### intersphinx ###

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
    "dnspython": ("https://dnspython.readthedocs.io/en/stable/", None),
    "six": ("https://six.readthedocs.io/", None),
    "python-dateutil": ("https://dateutil.readthedocs.io/en/stable/", None),
    "fqdn": ("https://fqdn.readthedocs.io/en/latest/", None),
}


### todo ###

todo_include_todos = True


### myst ###

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3


### content ###

master_doc = "index"

templates_path = ["_templates"]
html_static_path = ["_static"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

### theme ###

html_theme = "sphinx_rtd_theme"


### source links ###
# Keep repo-local links in RST so GitHub/local rendering works as expected.
# During Sphinx builds, rewrite those links to GitHub so hosted docs resolve.
#
# This only affects rewritten source links. Read the Docs controls version
# aliases such as "latest" and "stable".
#
# The GitHub base URL is resolved in this order:
#   1. OCTODNS_SOURCE_BASE_URL env var (explicit override, e.g. for forks, like https://github.com/MY_FORK/octodns)
#   2. READTHEDOCS_GIT_IDENTIFIER (ref provided by Read the Docs)
#   3. Local git checkout context (branch, then exact tag, then commit SHA)
#   4. Raise an error if no git ref can be determined
def _detect_git_ref():

    def _git(*args, stderr=DEVNULL):
        try:
            return check_output(
                ["git", *args], stderr=stderr, text=True
            ).strip()
        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(
                f"Unable to run git, cannot resolve docs source ref: {e}"
            ) from e

    # If HEAD points at a branch, use that branch name.
    try:
        branch = _git("symbolic-ref", "--quiet", "--short", "HEAD")
        if branch:
            return branch
    except CalledProcessError:
        pass

    # Detached HEAD may still correspond to an exact tag.
    try:
        tag = _git("describe", "--tags", "--exact-match", "HEAD")
        if tag:
            return tag
    except CalledProcessError:
        pass

    # Last-resort: use the checked-out commit directly.
    try:
        sha = _git("rev-parse", "--short", "HEAD", stderr=STDOUT)
        if sha:
            return sha
    except CalledProcessError as e:
        raise RuntimeError(
            "Unable to determine git ref for docs source links; "
            "set READTHEDOCS_GIT_IDENTIFIER or OCTODNS_SOURCE_BASE_URL "
            f"when building outside a git checkout: {e.output}"
        ) from e

    raise RuntimeError(
        "Unable to determine git ref for docs source links; "
        "git returned an empty ref"
    )


def _detect_docs_ref():
    # RTD controls latest/stable aliases. Use the exact checked-out ref when
    # available so links always match the docs version being built.
    rtd_identifier = os.environ.get("READTHEDOCS_GIT_IDENTIFIER", "").strip()
    if rtd_identifier:
        return rtd_identifier

    return _detect_git_ref()


_source_base = os.environ.get(
    "OCTODNS_SOURCE_BASE_URL", "https://github.com/octodns/octodns"
).rstrip("/")
_source_base = f"{_source_base}/tree/{_detect_docs_ref()}"

_repo_local_link_prefixes = (
    "/octodns/",
    "/CONTRIBUTING.md",
    "/CODE_OF_CONDUCT.md",
    "/LICENSE",
    "/docs/",
)


def _rewrite_repo_local_links(app, doctree, _docname):
    source_base = app.config.octodns_source_base_url.rstrip("/")
    for node in doctree.findall(nodes.reference):
        refuri = node.get("refuri")
        if refuri and refuri.startswith(_repo_local_link_prefixes):
            node["refuri"] = f"{source_base}{refuri}"


### json schema ###
# Generate JSON Schemas at docs-build time so Read the Docs serves per-version
# copies under _static. External consumers (SchemaStore, yaml-language-server
# modelines, editor `yaml.schemas` config) point at the versioned URLs.
#
# The schemas are build artifacts regenerated on every build, so they can't
# drift from the code.
_ZONE_SCHEMA_FILENAME = "octodns-zone.schema.json"
_CONFIG_SCHEMA_FILENAME = "octodns-config.schema.json"
# Legacy alias kept so existing modelines pointing at the old filename keep
# working. Contains the same content as _ZONE_SCHEMA_FILENAME.
_LEGACY_ZONE_SCHEMA_FILENAME = "octodns.schema.json"


def _write_zone_schema(app):
    out_dir = Path(app.srcdir) / "_static"
    out_dir.mkdir(parents=True, exist_ok=True)

    zone_data = json.dumps(build_zone_schema(), indent=2, sort_keys=True) + "\n"
    config_data = (
        json.dumps(build_config_schema(), indent=2, sort_keys=True) + "\n"
    )

    for filename, data in (
        (_ZONE_SCHEMA_FILENAME, zone_data),
        (_CONFIG_SCHEMA_FILENAME, config_data),
        (_LEGACY_ZONE_SCHEMA_FILENAME, zone_data),
    ):
        target = out_dir / filename
        target.write_text(data)
        print(f"wrote {target}")


def setup(app):
    app.add_config_value("octodns_source_base_url", _source_base, "env")
    app.connect("doctree-resolved", _rewrite_repo_local_links)
    app.connect("builder-inited", _write_zone_schema)
