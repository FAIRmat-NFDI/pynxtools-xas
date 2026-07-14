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


from typing import Any

import h5py
import numpy as np

from pynxtools.dataconverter.readers.multi.reader import MultiFormatReader
from pynxtools.dataconverter.readers.utils import parse_yml


class XASReader(MultiFormatReader):
    supported_nxdls = ["NXxas"]

    CONVERT_DICT = {
        "instrument": "INSTRUMENT[instrument]",
        "sample": "SAMPLE[sample]",
        "element": "element",
        "edge": "edge",
        "unit": "@units",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hdf5_data: dict[str, Any] = {}
        self.eln_data: dict[str, Any] = {}

        self.extensions = {
            ".h5": self.handle_hdf5_file,
            ".hdf5": self.handle_hdf5_file,
            ".yaml": self.handle_eln_file,
            ".yml": self.handle_eln_file,
            ".json": self.set_config_file,
        }

    def handle_hdf5_file(self, file_path: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        with h5py.File(file_path, "r") as h5_file:
            def collect(name: str, obj: Any) -> None:
                if isinstance(obj, h5py.Dataset):
                    # h5py visititems returns names without a leading slash.
                    result[name] = obj[()]
                    for attr_name, attr_value in obj.attrs.items():
                        result[f"{name}/@{attr_name}"] = attr_value

            h5_file.visititems(collect)

        self.hdf5_data = result
        return {}

    def handle_eln_file(self, file_path: str) -> dict[str, Any]:
        # Flatten the YAML into NeXus template paths, e.g.
        # sample/name -> /ENTRY[entry]/SAMPLE[sample]/name.
        self.eln_data = parse_yml(
            file_path,
            convert_dict=dict(self.CONVERT_DICT),
            parent_key="/ENTRY[entry]",
        )
        return {}

    def get_attr(self, key: str, path: str) -> Any:
        return self.hdf5_data.get(path)

    def get_eln_data(self, key: str, path: str) -> Any:
        # With bare "@eln", key is already the flattened target path.
        # An explicit @eln:path is also supported.
        lookup_key = path if path else key
        if lookup_key and not lookup_key.startswith("/"):
            lookup_key = f"/ENTRY[entry]/{lookup_key}"
        return self.eln_data.get(lookup_key)

    def get_data(self, key: str, path: str) -> Any:
        # Config paths must match the names collected by h5py exactly and
        # therefore must not start with '/'.
        value = self.hdf5_data.get(path.lstrip("/"))
        if value is None:
            return None

        # NXxas declares these datasets as NX_FLOAT.
        if key.endswith("/energy") or key.endswith("/intensity"):
            return np.asarray(value, dtype=np.float64)
        return value


READER = XASReader
