#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Parser for XAS spectra recorded through SpecsLab Prodigy XY exports.

Wraps ``pynxtools_xps``'s ``SPECSXYParser`` (the format-parsing logic is
identical — SPECS Prodigy is used at several synchrotron beamlines to record
XPS spectra, but also electron-yield NEXAFS scans) and adapts its
xarray-based, detector-channel-aware ``ParsedSpectrum`` into the flat
energy/intensity shape XAS entries need.
"""

import re
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from pynxtools_xps.parsers.base import ParsedSpectrum as _XPSParsedSpectrum
from pynxtools_xps.parsers.specs.xy.parser import SPECSXYParser as _XPSSpecsXYParser

from pynxtools_xas.parsers.base import ParsedSpectrum, VendorType, _XASParser
from pynxtools_xas.parsers.datetime_utils import parse_datetime

# SPECS Prodigy region names conventionally encode the probed element/edge,
# e.g. "O-K_134" (Oxygen, K-edge, auto-numbered for uniqueness) or "Fe-L3".
_ELEMENT_EDGE_RE = re.compile(r"^([A-Z][a-z]?)-([A-Za-z0-9]+?)(?:_\d+)?$")

# The region name only gives the shell letter, not the NXabsorption_edge/name
# sub-shell enumeration. A shell letter alone (no digit) is unambiguous for K,
# but L and M are spin-orbit split; a single scan region spanning >30 eV
# covers both split components, matching the "L2,3"/"M4,5" combined-edge
# enumeration values rather than a lone sub-edge.
_EDGE_CANONICALIZATION = {"L": "L2,3", "M": "M4,5"}


def _sanitize_entry_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", name.strip()) or "entry"


def _element_and_edge(region_name: str) -> tuple[str | None, str | None]:
    match = _ELEMENT_EDGE_RE.match(region_name)
    if match is None:
        return None, None
    element, edge = match.group(1), match.group(2)
    return element, _EDGE_CANONICALIZATION.get(edge, edge)


def _to_xas_spectrum(spectrum: _XPSParsedSpectrum) -> ParsedSpectrum:
    n_repeats = spectrum.data.sizes.get("cycle", 1) * spectrum.data.sizes.get("scan", 1)
    energy_dim = next(d for d in spectrum.data.dims if d not in ("cycle", "scan"))

    metadata = dict(spectrum.metadata)
    region_name = str(metadata.get("region_name", ""))
    element, edge = _element_and_edge(region_name)
    if element is not None:
        metadata["element_name"] = element
    if edge is not None:
        metadata["edge_name"] = edge
    metadata["title"] = region_name or metadata.get("group_name", "")

    # The export header states "Time Zone Format: UTC"; the timestamp itself
    # is written without an offset, so make it explicit for ISO8601 compliance.
    time_stamp = metadata.get("time_stamp")
    if isinstance(time_stamp, str):
        metadata["time_stamp"] = parse_datetime(time_stamp)

    # "External Channel Data" carries the beam-monitor (I0 mirror) current
    # alongside the primary spectrum; collapse its (cycle, scan, energy)
    # shape to match our flat energy/intensity convention.
    i0_mirror = metadata.get("external_i_mirror")
    if i0_mirror is not None:
        metadata["i0_mirror"] = np.asarray(i0_mirror).reshape(-1)

    return ParsedSpectrum(
        energy=np.asarray(spectrum.data.coords[energy_dim].values),
        intensity=np.asarray(spectrum.average().values),
        intensity_errors=(
            np.asarray(spectrum.errors().values) if n_repeats > 1 else None
        ),
        metadata=metadata,
    )


class SpecsXYParser(_XASParser):
    """Parser for XAS spectra in SpecsLab Prodigy XY export format."""

    config_file: ClassVar[str] = "config_specs_xy.json"
    supported_vendor: ClassVar[VendorType | None] = "specs"
    supported_file_extensions: ClassVar[tuple[str, ...]] = (".xy",)

    def matches_file(self, file: Path) -> bool:
        return _XPSSpecsXYParser().matches_file(file)

    def _parse(self, file: Path, **kwargs: Any) -> None:
        xps_parser = _XPSSpecsXYParser()
        xps_parser.parse(file, **kwargs)
        self._data = {
            _sanitize_entry_name(entry_name): _to_xas_spectrum(spectrum)
            for entry_name, spectrum in xps_parser.data.items()
        }
