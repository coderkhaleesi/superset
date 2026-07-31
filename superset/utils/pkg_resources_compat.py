# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Minimal ``pkg_resources`` compatibility shim.

setuptools 82.0.0 removed ``pkg_resources``. Superset's own code uses
``importlib.metadata``, but ``sqlalchemy-redshift`` 0.8.x still needs
``pkg_resources`` in two places:

- ``sqlalchemy_redshift/__init__.py`` imports ``DistributionNotFound``,
  ``get_distribution`` and ``parse_version`` at module scope, so loading the
  ``redshift://`` dialect raises ``ModuleNotFoundError``;
- ``Psycopg2RedshiftDialectMixin.create_connect_args()`` resolves the bundled
  ``redshift-ca-bundle.crt`` (the default ``sslrootcert`` for
  ``sslmode=verify-full``) via ``pkg_resources.resource_filename()``, so
  connecting would fail even if the import were fixed.

Its ``pkg_resources``-free 1.0.0 release requires SQLAlchemy 2.0, which Superset
cannot depend on yet (apache/superset#39750), so the pinned range in
``pyproject.toml`` cannot move.

:func:`install` registers a stand-in ``pkg_resources`` module exposing only the
names that dependency needs, backed by ``importlib.metadata``,
``importlib.util`` and ``packaging.version``. It is a no-op when a real
``pkg_resources`` is importable (i.e. an older setuptools is installed), and any
other attribute access on the stand-in raises ``AttributeError`` naming this
module, so an unrelated consumer fails with a message pointing here.
"""

from __future__ import annotations

import sys
import types
from importlib import import_module
from importlib.machinery import ModuleSpec
from importlib.metadata import PackageNotFoundError, version as metadata_version
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from packaging.version import Version

MODULE_NAME = "pkg_resources"


# Named after the pkg_resources exception dependents catch by name, so the
# "Error" suffix convention cannot apply here.
class DistributionNotFound(Exception):  # noqa: N818
    """The requested distribution is not installed."""


class Distribution:
    """The subset of ``pkg_resources.Distribution`` used by dependents."""

    def __init__(self, project_name: str, version: str) -> None:
        self.project_name = project_name
        self.version = version

    @property
    def parsed_version(self) -> Version:
        return Version(self.version)


def get_distribution(dist: str) -> Distribution:
    """Return metadata for the installed distribution named *dist*."""
    try:
        return Distribution(dist, metadata_version(dist))
    except PackageNotFoundError as ex:
        raise DistributionNotFound(dist) from ex


def parse_version(version: str) -> Version:
    """Parse *version* into an orderable object."""
    return Version(version)


def resource_filename(package_or_requirement: str, resource_name: str) -> str:
    """Return the on-disk path of *resource_name* inside a package or module.

    Mirrors ``pkg_resources.resource_filename()`` for the importable-module
    case: the name resolves relative to the directory holding it, matching how
    ``sqlalchemy_redshift.dialect`` locates its CA bundle. Only filesystem
    (non-zipped) distributions are supported, which is what an installed wheel
    provides.
    """
    module = import_module(package_or_requirement)
    if path := getattr(module, "__path__", None):
        directory = Path(next(iter(path)))
    elif module.__file__:
        directory = Path(module.__file__).parent
    else:  # pragma: no cover - namespace package without a location
        raise FileNotFoundError(
            f"Cannot locate resources of {package_or_requirement!r} on disk"
        )
    return str(directory / resource_name)


def _missing_attribute(name: str) -> Any:
    raise AttributeError(
        f"{MODULE_NAME}.{name} is not available: pkg_resources was removed in "
        "setuptools 82.0.0 and superset.utils.pkg_resources_compat only "
        "provides DistributionNotFound, Distribution, get_distribution, "
        "parse_version and resource_filename. Port the caller to "
        "importlib.metadata / importlib.resources."
    )


def install() -> bool:
    """Register the stand-in ``pkg_resources`` module if none is importable.

    Returns ``True`` when the stand-in was registered by this call. Idempotent,
    so it is safe to call from every entry point that may import
    ``sqlalchemy_redshift``.
    """
    if MODULE_NAME in sys.modules:
        return False

    try:
        if find_spec(MODULE_NAME) is not None:
            return False
    except (ImportError, ValueError):  # pragma: no cover - defensive
        pass

    module = types.ModuleType(MODULE_NAME)
    module.__spec__ = ModuleSpec(MODULE_NAME, loader=None)
    module.__doc__ = (
        "Compatibility stand-in installed by superset.utils.pkg_resources_compat."
    )
    module.DistributionNotFound = DistributionNotFound  # type: ignore[attr-defined]
    module.Distribution = Distribution  # type: ignore[attr-defined]
    module.get_distribution = get_distribution  # type: ignore[attr-defined]
    module.parse_version = parse_version  # type: ignore[attr-defined]
    module.resource_filename = resource_filename  # type: ignore[attr-defined]
    # Module-level __getattr__ (PEP 562) turns any other attribute access into
    # the explanatory AttributeError above.
    module.__getattr__ = _missing_attribute  # type: ignore[method-assign]
    sys.modules[MODULE_NAME] = module
    return True
