# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Parser for ESRF fluorescence-yield XAS HDF5 scans (e.g. ID21 µXANES).

ID21 records fluorescence-yield XAS, but its public HDF5 exports come in more
than one layout, so this parser recognizes each scan entry (a Bliss/SPEC group
marked ``NX_class="NXentry"``) by the way it declares its energy axis and signal:

* **plotselect convention** (older exports): the entry carries a Bliss
  ``plotselect`` ``NXdata`` group whose ``@signal``/``@axes`` name the channel
  the beamline actually plotted (e.g. ``signal="idet"``, ``axes=["enmonound"]``);
  the datasets live directly inside ``plotselect``. This is the file's own
  authoritative declaration of what to plot, so it is preferred.
* **avg convention** (newer exports): the entry has ``instrument/avg_energy`` and
  one or more averaged fluorescence-line detectors
  ``instrument/avg_<element>_<line>`` (e.g. ``avg_P_Ka1``); the sibling
  ``measurement/*`` entries are hardlinks. Here the active fluorescence line
  names the probed edge, so element + edge are inferred from it.

Energy is recorded in keV on ID21; NXxas declares energy as ``NX_ENERGY`` and the
config assumes eV, so the energy axis is converted to eV. The produced NXxas file
is self-contained (an ELN can still override element/edge, which the plotselect
convention often cannot supply from a bare diode signal).
"""

import re
from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from pynxtools_xas.parsers.base import ParsedSpectrum, VendorType, _XASParser
from pynxtools_xas.parsers.datetime_utils import parse_datetime
from pynxtools_xas.parsers.hdf5_utils import sanitize_entry_name

# ESRF is in Grenoble, France. ID21 timestamps carry their own UTC offset;
# this is only a fallback if a future export omits it.
_ESRF_TIMEZONE = ZoneInfo("Europe/Paris")

# Averaged-fluorescence detector name, e.g. "avg_P_Ka1" -> element P, line Ka1.
_AVG_FLUO = re.compile(r"^avg_(?P<element>[A-Z][a-z]?)_(?P<line>[A-Z][a-z]?\d*)$")
# Normalized-corrected fluorescence name, e.g. "PKa_corr_norm0" -> P, Ka.
_CORR_FLUO = re.compile(
    r"^(?P<element>[A-Z][a-z]?)(?P<line>K|L\d?|M)a?\d*_corr_norm\d*$"
)

# Energy-axis channel names seen across ID21 exports, in preference order.
_ENERGY_NAMES = ("avg_energy", "enmonound", "enmono", "energy")


def _emission_line_to_edge(line: str) -> str:
    """Map an emission-line label to the absorption edge it reports on.

    Kα/Kβ emission follows a K-shell core hole (the K edge), L-line emission an
    L edge, etc. Only the shell letter matters here.
    """
    return line[0].upper() if line else ""


def _dataset_1d(node: object) -> np.ndarray | None:
    """Return *node* as a 1-D float array if it is a 1-D dataset of length > 1."""
    if isinstance(node, h5py.Dataset) and node.ndim == 1 and node.shape[0] > 1:
        return np.asarray(node[()], dtype=float)
    return None


def _to_ev(energy: np.ndarray) -> np.ndarray:
    """Normalize an ID21 energy axis to eV.

    ID21 records the monochromator energy in keV (XAS edges are ~2–20 keV), so a
    max below ~100 means keV and is scaled to eV; values already in the thousands
    are left as-is.
    """
    return energy * 1000.0 if np.nanmax(np.abs(energy)) < 100.0 else energy


def _find_energy(group: h5py.Group) -> tuple[str, np.ndarray] | None:
    """Find the energy axis of a scan by the known channel names, in order."""
    for name in _ENERGY_NAMES:
        for container in ("instrument", "measurement"):
            sub = group.get(container)
            if isinstance(sub, h5py.Group) and name in sub:
                # Bliss stores channels as either <name>/data or a bare dataset.
                node = sub[name]
                if isinstance(node, h5py.Group):
                    node = node.get("data")
                array = _dataset_1d(node)
                if array is not None:
                    return name, array
    return None


def _plotselect(group: h5py.Group) -> tuple[np.ndarray, np.ndarray, str] | None:
    """Resolve ``(energy, signal, signal_name)`` from a Bliss ``plotselect`` group.

    The ``plotselect`` NXdata group names the channel the beamline plotted via its
    ``@signal``/``@axes`` attributes and holds those datasets directly.
    """
    plot = group.get("plotselect")
    if not isinstance(plot, h5py.Group):
        return None
    signal_name = plot.attrs.get("signal")
    axes = plot.attrs.get("axes")
    if signal_name is None or axes is None:
        return None
    signal_name = signal_name if isinstance(signal_name, str) else signal_name[0]
    axis_name = axes[0] if isinstance(axes, (list, np.ndarray)) else axes
    signal = _dataset_1d(plot.get(signal_name))
    energy = _dataset_1d(plot.get(axis_name))
    if signal is None or energy is None or signal.shape != energy.shape:
        return None
    return _to_ev(energy), signal, str(signal_name)


def _select_avg_fluorescence(
    group: h5py.Group, energy_len: int
) -> tuple[np.ndarray, str, str] | None:
    """Pick the strongest ``avg_<element>_<line>`` channel; infer element + edge.

    With the avg convention there is normally a single such channel; if several
    are present the one with the largest total absolute signal is taken.
    """
    instrument = group.get("instrument")
    if not isinstance(instrument, h5py.Group):
        return None
    best: tuple[float, np.ndarray, str, str] | None = None
    for name, node in instrument.items():
        match = _AVG_FLUO.match(name)
        if match is None:
            continue
        data = node.get("data") if isinstance(node, h5py.Group) else node
        array = _dataset_1d(data)
        if array is None or array.shape[0] != energy_len:
            continue
        strength = float(np.nansum(np.abs(array)))
        if best is None or strength > best[0]:
            best = (
                strength,
                array,
                match.group("element"),
                _emission_line_to_edge(match.group("line")),
            )
    if best is None:
        return None
    _, array, element, edge = best
    return array, element, edge


def _infer_element_edge(signal_name: str) -> tuple[str | None, str | None]:
    """Infer ``(element, edge)`` from a signal channel name, if it names a line."""
    for pattern in (_AVG_FLUO, _CORR_FLUO):
        match = pattern.match(signal_name)
        if match:
            return match.group("element"), _emission_line_to_edge(match.group("line"))
    return None, None


def _extract_scan(
    group: h5py.Group,
) -> tuple[np.ndarray, np.ndarray, str | None, str | None] | None:
    """Return ``(energy_eV, intensity, element, edge)`` for a scan entry, or None.

    Tries the authoritative ``plotselect`` declaration first, then the
    ``avg_energy``/``avg_<element>_<line>`` convention.
    """
    plot = _plotselect(group)
    if plot is not None:
        energy, signal, signal_name = plot
        element, edge = _infer_element_edge(signal_name)
        return energy, signal, element, edge

    found = _find_energy(group)
    if found is None:
        return None
    _, energy = found
    fluo = _select_avg_fluorescence(group, energy.shape[0])
    if fluo is None:
        return None
    intensity, element, edge = fluo
    return _to_ev(energy), intensity, element, edge


class EsrfFluoParser(_XASParser):
    """Parser for ESRF fluorescence-yield XAS HDF5 scans (ID21 µXANES)."""

    config_file: ClassVar[str] = "config_xas_fluo.json"
    supported_vendor: ClassVar[VendorType | None] = "esrf"
    supported_file_extensions: ClassVar[tuple[str, ...]] = (".h5", ".hdf5")

    def matches_file(self, file: Path) -> bool:
        try:
            with h5py.File(file, "r") as h5_file:
                return any(
                    isinstance(group, h5py.Group)
                    and group.attrs.get("NX_class") == "NXentry"
                    and _extract_scan(group) is not None
                    for group in h5_file.values()
                )
        except Exception:
            return False

    def _parse(self, file: Path, **kwargs: Any) -> None:
        with h5py.File(file, "r") as h5_file:
            for group_name, group in h5_file.items():
                if (
                    not isinstance(group, h5py.Group)
                    or group.attrs.get("NX_class") != "NXentry"
                ):
                    continue
                extracted = _extract_scan(group)
                if extracted is None:
                    continue
                energy, intensity, element, edge = extracted

                metadata: dict[str, Any] = {
                    "element_name": element,
                    "edge_name": edge,
                }
                title = group.get("title")
                if isinstance(title, h5py.Dataset):
                    value = title[()]
                    metadata["title"] = (
                        value.decode("utf-8")
                        if isinstance(value, bytes)
                        else str(value)
                    )
                sample = group.get("sample/name")
                if isinstance(sample, h5py.Dataset):
                    value = sample[()]
                    metadata["sample_name"] = (
                        value.decode("utf-8")
                        if isinstance(value, bytes)
                        else str(value)
                    )
                start = group.get("start_time")
                if isinstance(start, h5py.Dataset):
                    value = start[()]
                    text = (
                        value.decode("utf-8")
                        if isinstance(value, bytes)
                        else str(value)
                    )
                    metadata["start_time"] = parse_datetime(text, tzinfo=_ESRF_TIMEZONE)

                self._data[sanitize_entry_name(group_name)] = ParsedSpectrum(
                    energy=energy,
                    intensity=intensity,
                    metadata=metadata,
                )

        self._propagate_element_edge()

    def _propagate_element_edge(self) -> None:
        """Fill missing element/edge from a sibling entry in the same file.

        A file often holds an averaged scan (avg convention, which names the
        element/edge via its fluorescence line) alongside the individual repeat
        scans it was built from (plotselect convention, whose bare signal — e.g.
        a diode — carries no element). Those repeats measure the same edge, so
        inherit the element/edge the averaged entry resolved rather than emit an
        NXxas that is missing its required element/edge.
        """
        element = next(
            (
                s.metadata["element_name"]
                for s in self._data.values()
                if s.metadata.get("element_name")
            ),
            None,
        )
        edge = next(
            (
                s.metadata["edge_name"]
                for s in self._data.values()
                if s.metadata.get("edge_name")
            ),
            None,
        )
        for spectrum in self._data.values():
            if element and not spectrum.metadata.get("element_name"):
                spectrum.metadata["element_name"] = element
            if edge and not spectrum.metadata.get("edge_name"):
                spectrum.metadata["edge_name"] = edge
