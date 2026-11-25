# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""The version helpers come from pynxtools core."""

import pytest
from pynxtools.dataconverter.readers.parsers import versioning as core_versioning

from pynxtools_xas.parsers import versioning

HELPERS = [
    "VersionRange",
    "VersionTuple",
    "format_version",
    "format_version_ranges",
    "is_version_supported",
    "normalize_version",
    "version_ranges_overlap",
]


@pytest.mark.parametrize("name", HELPERS)
def test_version_helpers_are_the_ones_from_core(name):
    """Each helper is the core object, not a copy."""
    assert getattr(versioning, name) is getattr(core_versioning, name)
