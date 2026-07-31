---
title: pkg_resources Migration Guide
sidebar_position: 9
---

<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# pkg_resources Deprecation and Migration Guide

## Background

The `pkg_resources` API was deprecated in setuptools 81.0.0 and removed in setuptools 82.0.0. Any package that imports it fails with `ModuleNotFoundError: No module named 'pkg_resources'` on setuptools 82 and later. This affects several packages in the Python ecosystem.

## Current Status

### Superset Codebase

The Superset codebase has already migrated away from `pkg_resources` to the modern `importlib.metadata` API:

- `superset/db_engine_specs/__init__.py` - Uses `from importlib.metadata import entry_points`
- All entry point loading uses the modern API

Superset pins a `pkg_resources`-free setuptools:

```python
# requirements/base.in
setuptools>=83.0.0
```

The floor is required by PYSEC-2026-3447 / GHSA-h35f-9h28-mq5c, fixed in setuptools 83.0.0.

### Production Dependencies

Some third-party dependencies may still use `pkg_resources`. Monitor your dependency tree for packages that haven't migrated yet.

#### Known incompatibility: the `redshift` extra

`sqlalchemy-redshift<0.9` imports `pkg_resources` in both `sqlalchemy_redshift/__init__.py` and `sqlalchemy_redshift/dialect.py`, so connecting to a `redshift://` database raises `ModuleNotFoundError` on setuptools 82 or later. Its `pkg_resources`-free 1.0.0 release requires SQLAlchemy 2.0, which Superset does not yet support (`sqlalchemy>=1.4.43,<2`), so the extra cannot simply be bumped.

Until Superset moves to SQLAlchemy 2.0, deployments that use the Redshift dialect must pin an older setuptools in their own image:

```bash
pip install "apache-superset[redshift]" "setuptools<82"
```

Such deployments remain exposed to PYSEC-2026-3447, which only affects building source distributions with `MANIFEST.in` exclusions — not the Superset runtime.

## Migration Path

### Long-term Solution

Update all dependencies to use `importlib.metadata` instead of `pkg_resources`:

#### Migration Example

**Old (deprecated):**
```python
import pkg_resources

version = pkg_resources.get_distribution("package_name").version
entry_points = pkg_resources.iter_entry_points("group_name")
```

**New (recommended):**
```python
from importlib.metadata import version, entry_points

pkg_version = version("package_name")
eps = entry_points(group="group_name")
```

## Action Items

### For Superset Maintainers
1. The Superset codebase already uses `importlib.metadata`
2. Monitor third-party dependencies for updates
3. Move the `redshift` extra to `sqlalchemy-redshift>=1.0` once Superset supports SQLAlchemy 2.0

### For Extension Developers
1. **Update your packages** to use `importlib.metadata` instead of `pkg_resources`
2. **Test with setuptools >= 82.0.0**, where `pkg_resources` is no longer importable

## References

- [setuptools pkg_resources deprecation notice](https://setuptools.pypa.io/en/latest/pkg_resources.html)
- [importlib.metadata documentation](https://docs.python.org/3/library/importlib.metadata.html)
- [Migration guide](https://setuptools.pypa.io/en/latest/deprecated/pkg_resources.html)
