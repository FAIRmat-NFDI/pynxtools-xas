# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""The old versioning module is deprecated and gives the core helpers."""

import importlib

import pytest
from pynxtools.dataconverter.readers.parsers import versioning as core_versioning

HELPERS = [
    "VersionRange",
    "VersionTuple",
    "format_version",
    "format_version_ranges",
    "is_version_supported",
    "normalize_version",
    "version_ranges_overlap",
]


def test_old_versioning_module_warns_and_gives_the_core_helpers():
    """The old module still works, but tells users to import from core."""
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        old_module = importlib.reload(
            importlib.import_module("pynxtools_xas.parsers.versioning")
        )
    for name in HELPERS:
        assert getattr(old_module, name) is getattr(core_versioning, name)
