# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Entry names when several input files contain scans with the same name."""

import shutil
from pathlib import Path

import pytest
from pynxtools.dataconverter.template import Template

from pynxtools_xas.reader import XASReader

# This file contains one scan, which becomes the entry "scan_10_1".
DATA_FILE = (
    Path(__file__).parent
    / "data"
    / "esrf_transmission_exafs"
    / "DAC6-QMo_ambient_10.1.h5"
)


def _copy(tmp_path: Path, relative_path: str) -> str:
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA_FILE, target)
    return str(target)


def _entry_names(file_paths: list[str]) -> list[str]:
    reader = XASReader()
    reader.read(template=Template(), file_paths=tuple(file_paths))
    return sorted(reader.get_entry_names())


@pytest.mark.parametrize(
    "relative_paths, expected",
    [
        pytest.param(["one.h5"], ["scan_10_1"], id="single-file-keeps-scan-name"),
        pytest.param(
            ["first.h5", "second.h5"],
            ["first__scan_10_1", "second__scan_10_1"],
            id="same-scan-name-gets-file-name",
        ),
        pytest.param(
            ["a/data.h5", "b/data.h5"],
            ["a__data__scan_10_1", "b__data__scan_10_1"],
            id="same-file-name-gets-folder-name",
        ),
        pytest.param(
            ["a/data/scan.h5", "b/data/scan.h5"],
            ["a__data__scan__scan_10_1", "b__data__scan__scan_10_1"],
            id="same-folder-name-goes-up-one-more-level",
        ),
    ],
)
def test_same_scan_name_in_several_files(tmp_path, relative_paths, expected):
    """No entry is overwritten when two files contain a scan with the same name."""
    file_paths = [_copy(tmp_path, path) for path in relative_paths]
    assert _entry_names(file_paths) == expected


def test_same_file_given_twice_is_read_once(tmp_path, caplog):
    """The same file given twice gives one entry and a warning."""
    file_path = _copy(tmp_path, "one.h5")
    assert _entry_names([file_path, file_path]) == ["scan_10_1"]
    assert "more than once" in caplog.text
