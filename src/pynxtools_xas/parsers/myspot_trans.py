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
"""Parser for BESSY II mySpot beamline XAS HDF5 scans.

Each top-level group is one Bliss/SPEC-numbered scan (e.g. ``"9.1"``), marked
with ``NX_class="NXentry"`` and a ``measurement/dcm_p_energy`` energy axis —
the double-crystal-monochromator readback, in keV. Unlike the OSCARS/ESRF
formats, the scan file carries no element/edge/sample identification at all;
config_xas_trans.json's attrs-then-``@eln`` fallback covers that gap, so this
parser shares the same config as the other NXxas_trans parsers.
"""

from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from pynxtools_xas.parsers.base import ParsedSpectrum, VendorType, _XASParser
from pynxtools_xas.parsers.datetime_utils import parse_datetime
from pynxtools_xas.parsers.hdf5_utils import flatten_hdf5_group, sanitize_entry_name

# mySpot is at BESSY II, Berlin.
_MYSPOT_TIMEZONE = ZoneInfo("Europe/Berlin")

_ENERGY_KEY = "measurement/dcm_p_energy"
_INTENSITY_KEY = "measurement/normalised_roi_5"


def _is_myspot_scan(group: object) -> bool:
    return (
        isinstance(group, h5py.Group)
        and group.attrs.get("NX_class") == "NXentry"
        and _ENERGY_KEY in group
        and group[_ENERGY_KEY].ndim == 1
        and group[_ENERGY_KEY].shape[0] > 1
    )


class MySpotParser(_XASParser):
    """Parser for BESSY II mySpot beamline XAS HDF5 scans."""

    config_file: ClassVar[str] = "config_xas_trans.json"
    supported_vendor: ClassVar[VendorType | None] = "myspot"
    supported_file_extensions: ClassVar[tuple[str, ...]] = (".h5", ".hdf5")

    def matches_file(self, file: Path) -> bool:
        try:
            with h5py.File(file, "r") as h5_file:
                return any(_is_myspot_scan(group) for group in h5_file.values())
        except Exception:
            return False

    def _parse(self, file: Path, **kwargs: Any) -> None:
        with h5py.File(file, "r") as h5_file:
            for group_name, group in h5_file.items():
                if not _is_myspot_scan(group):
                    continue
                metadata = flatten_hdf5_group(group)
                # dcm_p_energy has no units attribute but is recorded in keV
                # (consistent with the Mo K-edge, ~20 keV, this dataset covers).
                energy = np.asarray(metadata.pop(_ENERGY_KEY)) * 1000.0
                intensity = np.asarray(metadata.pop(_INTENSITY_KEY))

                # SPEC's own scan title is uninformative boilerplate
                # ("Other seq_num -1" on every scan); drop it so config's
                # attrs-then-eln fallback reaches the ELN's real title.
                metadata.pop("title", None)

                start_time = metadata.get("start_time")
                if isinstance(start_time, str):
                    metadata["start_time"] = parse_datetime(
                        start_time, tzinfo=_MYSPOT_TIMEZONE
                    )

                self._data[sanitize_entry_name(group_name)] = ParsedSpectrum(
                    energy=energy,
                    intensity=intensity,
                    metadata=metadata,
                )
