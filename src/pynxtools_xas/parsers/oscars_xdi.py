# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Parser for the OSCARS-prepared XDI-derived transmission XAS HDF5 format.

Each top-level group in the file is one XAS entry, already shaped close to
NXxas_trans (``energy``, ``computed_mu``, ``element/symbol``, ``edge/name``,
``instrument/i0/data``, ``instrument/itrans/data``, ...) — this format is a
pre-mapped intermediate, not a raw beamline dump, so parsing is a flatten of
each group's subtree rather than vendor-specific extraction logic.
"""

from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from pynxtools_xas.parsers.base import ParsedSpectrum, VendorType, _XASParser
from pynxtools_xas.parsers.datetime_utils import parse_datetime
from pynxtools_xas.parsers.hdf5_utils import flatten_hdf5_group, sanitize_entry_name

# APS (Advanced Photon Source) is in Argonne, Illinois. Every entry this
# parser produces is an APS scan, so this is a fixed timezone for this format.
_APS_TIMEZONE = ZoneInfo("America/Chicago")


class OscarsXdiParser(_XASParser):
    """Parser for OSCARS-prepared XDI transmission XAS HDF5 files."""

    config_file: ClassVar[str] = "config_xas_trans.json"
    supported_vendor: ClassVar[VendorType | None] = "oscars"
    supported_file_extensions: ClassVar[tuple[str, ...]] = (".h5", ".hdf5")

    metadata_field_map: ClassVar[dict[str, str]] = {
        "start_time": "scan/start_time",
        "element_name": "element/symbol",
        "edge_name": "edge/name",
        "edge_energy": "scan/edge_energy",
        "sample_name": "sample/name",
        "source_name": "instrument/source/name",
        "source_type": "instrument/source/type",
        "source_probe": "instrument/source/probe",
        "i0_data": "instrument/i0/data",
        "itrans_data": "instrument/itrans/data",
        "normalized_intensity": "intensity",
        "process_program": "process/program",
        "process_version": "process/version",
        "process_notes": "process/notes/data",
    }

    def matches_file(self, file: Path) -> bool:
        try:
            with h5py.File(file, "r") as h5_file:
                return any(
                    isinstance(group, h5py.Group) and "computed_mu" in group
                    for group in h5_file.values()
                )
        except Exception:
            return False

    def _parse(self, file: Path, **kwargs: Any) -> None:
        with h5py.File(file, "r") as h5_file:
            for group_name, group in h5_file.items():
                if not isinstance(group, h5py.Group) or "computed_mu" not in group:
                    continue
                metadata = flatten_hdf5_group(group)
                energy = np.asarray(metadata.pop("energy"))
                intensity = np.asarray(metadata.pop("computed_mu"))
                self._data[sanitize_entry_name(group_name)] = ParsedSpectrum(
                    energy=energy,
                    intensity=intensity,
                    metadata=metadata,
                )
        self._fill_missing_edge_energies()
        for spectrum in self._data.values():
            start_time = spectrum.metadata.get("scan/start_time")
            if isinstance(start_time, str):
                spectrum.metadata["scan/start_time"] = parse_datetime(
                    start_time, tzinfo=_APS_TIMEZONE
                )
            self.map_metadata_fields(spectrum.metadata)

    def _fill_missing_edge_energies(self) -> None:
        """Backfill a missing ``scan/edge_energy`` from a sibling entry.

        Some entries in this file lack their own tabulated edge energy. Other
        entries in the same file that probe the same element/edge transition
        share the same physical edge energy, so reuse theirs rather than
        leave the field empty.
        """
        by_edge: dict[tuple[str, str], float] = {}
        for spectrum in self._data.values():
            element = spectrum.metadata.get("element/symbol")
            edge = spectrum.metadata.get("edge/name")
            edge_energy = spectrum.metadata.get("scan/edge_energy")
            if element and edge and edge_energy is not None:
                by_edge.setdefault((element, edge), edge_energy)

        for spectrum in self._data.values():
            if spectrum.metadata.get("scan/edge_energy") is not None:
                continue
            element = spectrum.metadata.get("element/symbol")
            edge = spectrum.metadata.get("edge/name")
            fallback = by_edge.get((element, edge))
            if fallback is not None:
                spectrum.metadata["scan/edge_energy"] = fallback
