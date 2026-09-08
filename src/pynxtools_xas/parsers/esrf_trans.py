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
"""Parser for ESRF BM beamline transmission EXAFS HDF5 scans.

Each top-level group is one raw beamline scan (named by its Bliss/SPEC scan
number, e.g. ``"10.1"``), holding hundreds of positioner/monitor channels
alongside the handful of fields relevant for NXxas_trans (element/edge
metadata, the energy axis, and the i0/itrans/iref transmission channels).
The whole subtree is flattened regardless — the unused channels are simply
never referenced by the config.
"""

from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from pynxtools_xas.parsers.base import ParsedSpectrum, VendorType, _XASParser
from pynxtools_xas.parsers.datetime_utils import parse_datetime
from pynxtools_xas.parsers.hdf5_utils import flatten_hdf5_group, sanitize_entry_name

# ESRF is in Grenoble, France. Timestamps in this format have consistently
# carried their own UTC offset (e.g. "+01:00"), so this only matters as a
# fallback if a future export omits it.
_ESRF_TIMEZONE = ZoneInfo("Europe/Paris")


class EsrfTransParser(_XASParser):
    """Parser for ESRF transmission EXAFS HDF5 scans."""

    config_file: ClassVar[str] = "config_xas_trans.json"
    supported_vendor: ClassVar[VendorType | None] = "esrf"
    supported_file_extensions: ClassVar[tuple[str, ...]] = (".h5", ".hdf5")

    metadata_field_map: ClassVar[dict[str, str]] = {
        "element_name": "instrument/ExafsElement/Element",
        "edge_name": "instrument/ExafsElement/Edge",
        "edge_energy": "instrument/ExafsElement/EdgeEnergy",
        "sample_name": "sample/name",
        "i0_data": "instrument/I0/data",
        "itrans_data": "instrument/I1/data",
        "iref_data": "instrument/I2/data",
    }

    def matches_file(self, file: Path) -> bool:
        try:
            with h5py.File(file, "r") as h5_file:
                return any(
                    isinstance(group, h5py.Group) and "instrument/ExafsElement" in group
                    for group in h5_file.values()
                )
        except Exception:
            return False

    def _parse(self, file: Path, **kwargs: Any) -> None:
        with h5py.File(file, "r") as h5_file:
            for group_name, group in h5_file.items():
                if (
                    not isinstance(group, h5py.Group)
                    or "instrument/ExafsElement" not in group
                ):
                    continue
                metadata = flatten_hdf5_group(group)
                # instrument/Emono/value carries units="keV" (its HDF5 attribute);
                # NXxas declares energy as NX_ENERGY, and the rest of this config
                # (and EdgeEnergy, already in eV) assumes eV.
                energy = np.asarray(metadata.pop("instrument/Emono/value")) * 1000.0
                intensity = np.asarray(metadata.pop("instrument/mu_trans/data"))
                start_time = metadata.get("start_time")
                if isinstance(start_time, str):
                    metadata["start_time"] = parse_datetime(
                        start_time, tzinfo=_ESRF_TIMEZONE
                    )
                self.map_metadata_fields(metadata)
                self._data[sanitize_entry_name(group_name)] = ParsedSpectrum(
                    energy=energy,
                    intensity=intensity,
                    metadata=metadata,
                )
