# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""
Deprecated: use ``pynxtools.dataconverter.readers.parsers.versioning``.

This module only re-exports the version helpers from pynxtools core so that
old imports keep working. It will be removed in a future release.
"""

import warnings

from pynxtools.dataconverter.readers.parsers.versioning import (
    VersionRange,
    VersionTuple,
    format_version,
    format_version_ranges,
    is_version_supported,
    normalize_version,
    version_ranges_overlap,
)

warnings.warn(
    "pynxtools_xas.parsers.versioning is deprecated and will be removed in a "
    "future release. Import from pynxtools.dataconverter.readers.parsers.versioning "
    "instead.",
    DeprecationWarning,
    stacklevel=2,
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
