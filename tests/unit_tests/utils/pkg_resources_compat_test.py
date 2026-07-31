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

import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest
from pytest_mock import MockerFixture

from superset.utils import pkg_resources_compat


@pytest.fixture(name="no_pkg_resources")
def no_pkg_resources_fixture(mocker: MockerFixture) -> None:
    """Pretend setuptools >= 82 is installed: no importable ``pkg_resources``."""
    mocker.patch.dict(sys.modules)
    sys.modules.pop(pkg_resources_compat.MODULE_NAME, None)
    mocker.patch.object(pkg_resources_compat, "find_spec", return_value=None)


def test_install_registers_stand_in(no_pkg_resources: None) -> None:
    """install() makes ``import pkg_resources`` work again."""
    assert pkg_resources_compat.install() is True

    import pkg_resources  # noqa: PLC0415

    assert pkg_resources.get_distribution("apache-superset").project_name == (
        "apache-superset"
    )
    assert pkg_resources.parse_version("1.2.3") < pkg_resources.parse_version("1.10")
    assert issubclass(pkg_resources.DistributionNotFound, Exception)


def test_install_is_idempotent(no_pkg_resources: None) -> None:
    """A second call leaves the already-registered module alone."""
    assert pkg_resources_compat.install() is True
    registered = sys.modules[pkg_resources_compat.MODULE_NAME]

    assert pkg_resources_compat.install() is False
    assert sys.modules[pkg_resources_compat.MODULE_NAME] is registered


def test_install_defers_to_real_pkg_resources(mocker: MockerFixture) -> None:
    """On setuptools < 82 the real module wins and nothing is registered."""
    real = ModuleType(pkg_resources_compat.MODULE_NAME)
    mocker.patch.dict(sys.modules)
    sys.modules.pop(pkg_resources_compat.MODULE_NAME, None)
    mocker.patch.object(
        pkg_resources_compat,
        "find_spec",
        return_value=ModuleSpec(pkg_resources_compat.MODULE_NAME, loader=None),
    )

    assert pkg_resources_compat.install() is False

    sys.modules[pkg_resources_compat.MODULE_NAME] = real
    assert pkg_resources_compat.install() is False
    assert sys.modules[pkg_resources_compat.MODULE_NAME] is real


def test_unsupported_attribute_points_at_this_module(no_pkg_resources: None) -> None:
    """Names the shim does not provide fail with an actionable message."""
    pkg_resources_compat.install()
    module = sys.modules[pkg_resources_compat.MODULE_NAME]

    with pytest.raises(AttributeError, match="pkg_resources_compat"):
        module.working_set  # noqa: B018


def test_get_distribution_reports_version_and_missing_packages() -> None:
    dist = pkg_resources_compat.get_distribution("apache-superset")
    assert dist.version
    assert dist.parsed_version == pkg_resources_compat.parse_version(dist.version)

    with pytest.raises(pkg_resources_compat.DistributionNotFound):
        pkg_resources_compat.get_distribution("not-a-real-distribution")


def test_resource_filename_resolves_package_data() -> None:
    """Resources resolve next to the package, as sqlalchemy-redshift expects."""
    path = Path(
        pkg_resources_compat.resource_filename("superset", "static/version_info.json")
    )
    assert path == Path(pkg_resources_compat.__file__).parents[1] / (
        "static/version_info.json"
    )


def test_resource_filename_resolves_module_data() -> None:
    """A module (not package) name resolves against its containing directory."""
    path = Path(
        pkg_resources_compat.resource_filename(
            "superset.utils.pkg_resources_compat", "data.crt"
        )
    )
    assert path == Path(pkg_resources_compat.__file__).parent / "data.crt"
