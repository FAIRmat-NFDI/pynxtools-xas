# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Reader implementation for X-ray Absorption Spectroscopy (XAS) data."""

import datetime
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pynxtools.dataconverter.readers.multi.reader import MultiFormatReader
from pynxtools.dataconverter.readers.utils import parse_yml

from pynxtools_xas.parsers import (
    EsrfFluoParser,
    EsrfTransParser,
    MySpotParser,
    OscarsXdiParser,
    ParsedSpectrum,
    SpecsXYParser,
    _XASParser,
)
from pynxtools_xas.parsers.hdf5_utils import sanitize_entry_name

logger = logging.getLogger("pynxtools")

_CONVERT_DICT: dict[str, str] = {
    "unit": "@units",
    "sample": "SAMPLE[sample]",
}


def _collect_supported_extensions(parser_classes: list[type[_XASParser]]) -> list[str]:
    """Collect unique supported_file_extensions, preserving first occurrence order."""
    seen: set[str] = set()
    extensions: list[str] = []
    for parser in parser_classes:
        for ext in parser.supported_file_extensions:
            if ext not in seen:
                seen.add(ext)
                extensions.append(ext)
    return extensions


class XASReader(MultiFormatReader):
    """Reader for XAS."""

    # NXxas itself is a valid standalone application definition; the
    # technique-specific subclasses extend it with detection-mode semantics.
    supported_nxdls: list[str] = [
        "NXxas",
        "NXxas_tey",
        "NXxas_trans",
        "NXxas_herfd",
        "NXxas_pey",
        "NXxas_pfy",
        "NXxas_tfy",
    ]

    reader_dir: Path = Path(__file__).parent
    config_file: str | Path | None = None

    parsers: list[type[_XASParser]] = [
        EsrfFluoParser,
        EsrfTransParser,
        MySpotParser,
        OscarsXdiParser,
        SpecsXYParser,
    ]
    supported_file_extensions: list[str] = _collect_supported_extensions(parsers)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.data: dict[str, ParsedSpectrum] = {}
        self.eln_data: dict[str, Any] = {}
        self._active_parsers: list[_XASParser] = []
        # parsed spectra per input file, keyed by the resolved file path
        self._parsed_files: dict[Path, dict[str, ParsedSpectrum]] = {}
        self.extensions: dict[str, Any] = {
            ".yml": self.handle_eln_file,
            ".yaml": self.handle_eln_file,
            ".json": self.set_config_file,
        }
        for ext in self.supported_file_extensions:
            self.extensions[ext] = self.handle_data_file

        self.processing_order: list[str] = list(self.extensions.keys())

    def set_config_file(
        self, file_path: str | Path | None, replace: bool = True
    ) -> dict[str, Any]:
        if not file_path:
            return {}

        if replace:
            if self.config_file is not None and file_path != self.config_file:
                logger.info(
                    f"Config file already set. Replaced by the new file {file_path}."
                )
            self.config_file = file_path
        elif self.config_file is None:
            self.config_file = file_path

        return {}

    def handle_eln_file(self, file_path: str) -> dict[str, Any]:
        """Load ELN file into ``self.eln_data``."""
        eln_data = parse_yml(
            file_path,
            convert_dict=_CONVERT_DICT,
            parent_key="/ENTRY",
        )
        for key, value in eln_data.items():
            if isinstance(value, datetime.datetime):
                value = value.isoformat()
            self.eln_data[key] = value
        return {}

    def handle_data_file(self, file_path: str) -> dict[str, Any]:
        """Dispatch *file_path* to the matching parser."""
        file = Path(file_path)
        if file.resolve() in self._parsed_files:
            logger.warning(f"{file_path} was given more than once; reading it once.")
            return {}
        matches = [P for P in self.parsers if P.is_mainfile(file)]

        if not matches:
            reasons = [
                f"  - {P.__name__}: {P.match_failure_reason(file)}"
                for P in self.parsers
            ]
            logger.warning(
                "No parser matches file: %s\n%s", file_path, "\n".join(reasons)
            )
            return {}

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous file format: {len(matches)} parsers match '{file.name}'."
            )

        parser = matches[0]()
        parser.parse(file_path, **(self.kwargs or {}))

        self.set_config_file(
            XASReader.reader_dir.joinpath("config", parser.config_file),
            replace=False,
        )

        self._parsed_files[file.resolve()] = parser.data
        self.data = self._combine_entries()
        self._active_parsers.append(parser)

        return {}

    def _combine_entries(self) -> dict[str, ParsedSpectrum]:
        """
        Collect the spectra of all input files under unique entry names.

        An entry is named after its scan inside the file. If several files
        contain a scan with the same name, the file name (without extension) is
        prepended with "__", and then parent folder names, one level at a time,
        until the names are unique (first.h5 and second.h5 give
        first__scan_1 and second__scan_1; a/data.h5 and b/data.h5 give
        a__data__scan_1 and b__data__scan_1).
        """
        # one item per (file, scan); its prefix parts are the folders and the stem
        items = [
            (path.parent.parts[1:] + (path.stem,), scan, spectrum)
            for path, spectra in self._parsed_files.items()
            for scan, spectrum in spectra.items()
        ]
        depth = [0] * len(items)

        def name(index: int) -> str:
            parts, scan, _ = items[index]
            if depth[index] == 0:
                return scan
            return sanitize_entry_name("__".join(parts[-depth[index] :] + (scan,)))

        while True:
            counts = Counter(name(i) for i in range(len(items)))
            clashing = [i for i in range(len(items)) if counts[name(i)] > 1]
            if not clashing:
                return {name(i): items[i][2] for i in range(len(items))}
            for i in clashing:
                if depth[i] == len(items[i][0]):
                    raise ValueError(
                        f"Could not find a unique entry name for scan '{items[i][1]}'."
                    )
                depth[i] += 1

    def get_entry_names(self) -> list[str]:
        """Returns the entry names constructed from the parsed data."""
        return list(self.data.keys()) or ["entry"]

    def _search_metadata(self, metadata: dict[str, Any], path: str) -> Any:
        """Suffix-match ``path`` in a flat metadata dict."""
        _sentinel = object()
        value = metadata.get(path, _sentinel)
        if value is _sentinel:
            value = next(
                (v for k, v in metadata.items() if k.endswith(f"/{path}")), None
            )
        if value is None or str(value) in {"None", ""}:
            return None
        return value.isoformat() if isinstance(value, datetime.datetime) else value

    def get_attr(self, key: str, path: str) -> Any:
        """Return metadata stored in the parsed spectrum for the current entry."""
        spectrum = self.data.get(self.callbacks.entry_name)
        if spectrum is None:
            return None
        return self._search_metadata(spectrum.metadata, path)

    def get_eln_data(self, key: str, path: str) -> Any:
        """Return data from the given ELN path.

        Falls back to the entry-agnostic ``/ENTRY/...`` key when no
        entry-specific ``/ENTRY[<entry_name>]/...`` value was provided,
        since ELN files are shared across all entries by default.
        """
        if key in self.eln_data:
            return self.eln_data.get(key)
        generic_key = re.sub(r"(/ENTRY)\[[^\]]+\]", r"\1", key)
        return self.eln_data.get(generic_key)

    def get_data_dims(self, key: str, path: str) -> list[str]:
        """Return data dimensions for a given template key-path pair.

        Currently this is not in use.
        """
        return []

    def get_data(self, key: str, path: str) -> Any | None:
        """Retrieve XAS spectral data for the current entry by path token."""
        spectrum = self.data.get(self.callbacks.entry_name)
        if spectrum is None:
            return None

        data_handlers = {
            "energy": lambda s: s.energy,
            "intensity": lambda s: s.intensity,
            "intensity_errors": lambda s: s.intensity_errors,
        }
        if path in data_handlers:
            return data_handlers[path](spectrum)
        return None

    def post_process(self) -> None:
        """Do postprocessing after all files and the config file are read.

        Currently this is not in use.
        """

    def read(
        self,
        template: dict = None,
        file_paths: tuple[str] = None,
        objects: tuple[Any] | None = None,
        **kwargs,
    ) -> dict:
        self.set_config_file(kwargs.get("config_file", self.config_file))

        template = super().read(template, file_paths, objects, suppress_warning=True)

        # generate_template_from_nxdl() pre-seeds NXDL-declared @link defaults
        # (e.g. NXxas's NXdata/energy link) under the generic "/ENTRY[entry]/"
        # placeholder before this reader runs. Real entry names never being
        # literally "entry" here, that skeleton residue survives as a bogus
        # extra entry unless dropped explicitly.
        entry_names = set(self.get_entry_names())
        for key in [k for k in template if re.search(r"/ENTRY\[entry\]/", k)]:
            if "entry" not in entry_names:
                del template[key]

        return template


READER = XASReader
