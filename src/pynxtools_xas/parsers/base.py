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
"""Base classes and typed intermediate representation for XAS parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

import numpy as np

from pynxtools_xas.parsers.versioning import (
    VersionRange,
    VersionTuple,
    _format_version,
    is_version_supported,
)

VendorType = Literal["specs", "esrf", "oscars", "myspot", "various"]


@dataclass
class ParsedSpectrum:
    """Intermediate representation for one XAS spectrum.

    Parsers return ``dict[str, ParsedSpectrum]`` where keys are NeXus entry
    names.

    Attributes:
        energy: 1D energy axis, shape ``(nEnergy,)``.
        intensity: 1D intensity values, same shape as ``energy``.
        intensity_errors: Optional per-point errors, same shape as ``energy``.
        metadata: Flat key-value metadata for ``@attrs:`` lookups in config
            files.
    """

    energy: np.ndarray
    intensity: np.ndarray
    intensity_errors: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        n = self.energy.size if self.energy is not None else 0
        lines = ["ParsedSpectrum", f"  energy:    ({n},)", f"  intensity: ({n},)"]
        lines.append(f"  metadata ({len(self.metadata)} keys):")
        for k, v in sorted(self.metadata.items()):
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:57] + "..."
            lines.append(f"    {k:<50}  {v_str}")
        return "\n".join(lines)


class _Parser(ABC):
    """
    Abstract base class for all XAS file parsers.

    Subclasses define the structural and semantic rules required to
    identify and parse a specific XAS file format variant.

    Class Variables:
        supported_vendor: String of supported instrument/facility vendor.
        supported_file_extensions: Tuple of supported file extensions
            (e.g., (".xy", ".xdi")).
        supported_versions: Tuple of supported version ranges (half-open
            intervals). If empty, all files are accepted regardless of
            whether they carry a version. If non-empty, only files whose
            detected version falls within one of the declared ranges are
            accepted; files without a version are implicitly rejected.

    ``supported_file_extensions`` must be set by subclasses.
    ``supported_versions`` can be optionally set for version-aware parsers.

    Subclasses must implement:
        - matches_file()
        - _parse()
    """

    supported_vendor: ClassVar[VendorType | None] = None
    supported_file_extensions: ClassVar[tuple[str, ...]] = ()
    supported_versions: ClassVar[tuple[VersionRange, ...]] = ()

    @classmethod
    def file_ext_err_msg(cls, file: Path) -> str:
        suffix = file.suffix or "<no extension>"
        allowed = ", ".join(cls.supported_file_extensions) or "<none>"

        return (
            f"Cannot process file '{file.name}' (detected extension: '{suffix}'). "
            f"{cls.__name__} supports only the following file extensions: {allowed}."
        )

    @classmethod
    def file_version_err_msg(
        cls,
        file: str | Path,
        version: VersionTuple | None,
    ) -> str:
        path = Path(file)
        file_name = path.name
        version_str = _format_version(version) if version is not None else "<unknown>"

        ranges: list[str] = []
        for lower, upper in cls.supported_versions:
            lower_str = _format_version(lower)
            if upper is None:
                ranges.append(f">= {lower_str}")
            else:
                upper_str = _format_version(upper)
                ranges.append(f"{lower_str} – {upper_str}")

        supported_str = ", ".join(ranges) if ranges else "<none>"

        if version is None:
            return (
                f"File '{file_name}' does not specify a version, "
                f"but {cls.__name__} requires one. "
                f"Supported versions: {supported_str}."
            )

        return (
            f"File '{file_name}' has version {version_str}, which is not supported "
            f"by {cls.__name__}. Supported versions: {supported_str}."
        )

    @classmethod
    def matches_file_warning(cls, file: str | Path) -> str:
        path = Path(file)
        file_name = path.name

        return (
            f"File '{file_name}' does not match the expected format for {cls.__name__}."
        )

    @classmethod
    def is_extension_supported(cls, file: Path) -> bool:
        suffix = file.suffix.lower()
        return any(suffix == ext.lower() for ext in cls.supported_file_extensions)

    @classmethod
    def is_version_supported(
        cls,
        version: VersionTuple | None,
    ) -> bool:
        return is_version_supported(version, cls.supported_versions)

    @classmethod
    def is_mainfile(cls, file: str | Path) -> bool:
        """
        Check whether this parser supports the given file.

        This performs extension and structural validation
        without raising exceptions.

        Args:
            file: Path to the candidate file.

        Returns:
            True if the file can be parsed by this class, otherwise False.
        """
        return cls.match_failure_reason(file) is None

    @classmethod
    def match_failure_reason(cls, file: str | Path) -> str | None:
        """
        Explain why this parser rejects *file*, without raising.

        Used for on-demand diagnostics once every registered parser has
        rejected a file — `is_mainfile` itself must stay silent, since it
        is probed speculatively against each candidate parser and a
        negative result there is the expected outcome for all but one.

        Args:
            file: Path to the candidate file.

        Returns:
            The rejection reason, or None if this parser matches the file.
        """
        try:
            parser = cls()
            parser._is_mainfile(Path(file))
            return None
        except ValueError as error:
            return str(error)

    def __init__(self) -> None:
        self.file: Path
        self._data: dict[str, ParsedSpectrum] = {}

    def __repr__(self) -> str:
        try:
            file_str = f"{self.file.name}"
        except AttributeError:
            file_str = ""
        n = len(self._data)
        lines = [f"{self.__class__.__name__}"]
        lines.append(f"File name: {file_str}")
        lines.append(f"Number of parsed entries: {n}")
        lines.append("Entries:")
        for entry_name in self._data:
            lines.append(f"    '{entry_name}'")
        return "\n".join(lines)

    @property
    def data(self) -> dict[str, ParsedSpectrum]:
        """Parsed spectra keyed by NeXus entry name."""
        return self._data

    def _is_mainfile(self, file: Path) -> None:
        """
        Check whether this parser supports the given file.

        This performs extension, version, and structural validation
        and raises exceptions.

        Args:
            file: Path to the candidate file.
        """
        if not self.is_extension_supported(file):
            raise ValueError(self.file_ext_err_msg(file))

        version = self.detect_version(file)

        if not self.is_version_supported(version):
            raise ValueError(self.file_version_err_msg(file, version))

        if not self.matches_file(file):
            raise ValueError(self.matches_file_warning(file))

    def detect_version(self, file: Path) -> VersionTuple | None:
        """
        Detect the version of the given file.

        This method may be overridden by subclasses that extract
        version information from file headers or metadata.

        Args:
            file: Path to the file.

        Returns:
            A version tuple (e.g., (4, 63, 1)) if detected, otherwise None.
        """
        return None

    @abstractmethod
    def matches_file(self, file: Path) -> bool:
        """
        Return True if the file structurally matches this parser's format.

        Implementations must perform positive identification — not just
        extension checks or negative exclusions. The check should be fast
        (read at most a few KB), and always catch all exceptions and return
        False rather than propagating them.

        Args:
            file: Path to the candidate file.

        Returns:
            True if the file matches this parser's format, otherwise False.
        """

    def parse(self, file: str | Path, **kwargs) -> None:
        """
        Parse the given file and populate the parser's data attribute.

        After parsing, stamp file provenance into every spectrum's metadata.

        Args:
            file: Path to the file to parse.
            **kwargs: Additional parser-specific keyword arguments.

        Raises:
            ValueError: If the file is not supported by this parser.
        """
        file = Path(file)
        self.file = file
        self._is_mainfile(file)
        self._parse(file, **kwargs)
        for spectrum in self._data.values():
            spectrum.metadata["File"] = str(self.file)
            spectrum.metadata["file_ext"] = self.file.suffix

    @abstractmethod
    def _parse(self, file: Path, **kwargs) -> None:
        """
        Perform the actual parsing implementation.

        Subclasses must implement this method to extract structured
        data from the validated file and populate ``self._data``.

        Args:
            file: Path to the validated file.
            **kwargs: Additional parser-specific options.
        """
        ...


class _XASParser(_Parser):
    """Abstract base class for all XAS file parsers.

    Subclasses define the structural and semantic rules required to identify
    and parse a specific XAS file format variant.

    Subclasses must set ``config_file`` and implement ``_parse()``, which
    should populate ``self._data`` — a ``dict[str, ParsedSpectrum]``
    mapping NeXus entry names to typed spectral data.

    The ``data`` property exposes this mapping to ``XASReader``.
    File provenance (``File``, ``file_ext``) is stamped into every spectrum's
    metadata by ``parse()`` immediately after parsing completes.
    """

    config_file: ClassVar[str] = ""
    _metadata_exclude_keys: ClassVar[frozenset[str]] = frozenset()

    # Maps canonical metadata keys (the ones config_xas_trans.json /
    # config_specs_xy.json address via "@attrs:") to this parser's own raw
    # flattened keys. Subclasses set this; entries whose raw key is absent
    # from *metadata* simply alias to None.
    metadata_field_map: ClassVar[dict[str, str]] = {}

    def __init__(self) -> None:
        super().__init__()

    def _filter_metadata(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Return *raw* with all ``_metadata_exclude_keys`` removed."""
        return {k: v for k, v in raw.items() if k not in self._metadata_exclude_keys}

    def map_metadata_fields(self, metadata: dict[str, Any]) -> None:
        """Add ``metadata_field_map`` keys to *metadata* (in place), aliasing
        each to the value at its mapped raw key."""
        for canonical_key, raw_key in self.metadata_field_map.items():
            metadata[canonical_key] = metadata.get(raw_key)
