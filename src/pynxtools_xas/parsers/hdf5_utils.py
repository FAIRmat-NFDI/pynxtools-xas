# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for HDF5-based XAS parsers."""

import re

import h5py
import numpy as np

_INVALID_NAME_CHARS = re.compile(r"[^0-9A-Za-z_]")


def sanitize_entry_name(name: str) -> str:
    """Turn an arbitrary HDF5 group name into a safe NeXus entry name."""
    sanitized = _INVALID_NAME_CHARS.sub("_", name.strip()) or "entry"
    return sanitized if sanitized[0].isalpha() else f"scan_{sanitized}"


def flatten_hdf5_group(group: h5py.Group) -> dict[str, object]:
    """Flatten every dataset under *group* into a dict keyed by relative path.

    Byte-string scalars are decoded to ``str``; everything else (numbers,
    arrays) is passed through as-is.
    """
    flat: dict[str, object] = {}

    def collect(name: str, obj: object) -> None:
        if not isinstance(obj, h5py.Dataset):
            return
        value = obj[()]
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        elif isinstance(value, np.ndarray) and value.dtype.kind == "O":
            value = np.array(
                [v.decode("utf-8") if isinstance(v, bytes) else v for v in value]
            )
        flat[name] = value

    group.visititems(collect)
    return flat
