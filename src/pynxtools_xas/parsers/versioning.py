# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Version helpers, re-exported from pynxtools core.

They live in ``pynxtools.dataconverter.readers.parsers.versioning``. This
module stays so that existing imports keep working.
"""

from pynxtools.dataconverter.readers.parsers.versioning import (
    VersionRange,
    VersionTuple,
    format_version,
    format_version_ranges,
    is_version_supported,
    normalize_version,
    version_ranges_overlap,
)

__all__ = [
    "VersionRange",
    "VersionTuple",
    "format_version",
    "format_version_ranges",
    "is_version_supported",
    "normalize_version",
    "version_ranges_overlap",
]
