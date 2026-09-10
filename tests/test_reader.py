# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pynxtools reader plugin."""

import os
from typing import Any

import pytest
from pynxtools.dataconverter.convert import get_reader
from pynxtools.testing.nexus_conversion import ReaderTest

READER_NAME = "xas"
READER_CLASS = get_reader(READER_NAME)

# Define lines/sections to be ignored in _all_ test cases
ignore_lines_all_tests: list = []
ignore_sections_all_tests: dict = {}

# Each fixture folder targets exactly one NXDL application definition (the
# one its parser's config declares under "definition"), not the full cross
# product of the reader's supported_nxdls.
# Test cases should be [("folder", "nxdl", ignore_lines, ignore_sections, "test-id")]
test_cases: list[tuple[str, str, list[Any], dict[Any, Any], str]] = [
    ("specs_xy_aey", "NXxas", [], {}, "specs-xy-aey"),
    ("esrf_transmission_exafs", "NXxas_trans", [], {}, "esrf-transmission-exafs"),
    ("esrf_fluorescence_id21", "NXxas", [], {}, "esrf-fluorescence-id21"),
    ("oscars_xdi_transmission", "NXxas_trans", [], {}, "oscars-xdi-transmission"),
]

test_params: list[Any] = [
    pytest.param(
        test_case[1],
        test_case[0],
        test_case[2],
        test_case[3],
        id=test_case[4],
    )
    for test_case in test_cases
]


@pytest.mark.parametrize(
    "nxdl, sub_reader_data_dir, ignore_lines, ignore_sections",
    test_params,
)
def test_nexus_conversion(  # noqa: PLR0913, PLR0917
    nxdl, sub_reader_data_dir, ignore_lines, ignore_sections, tmp_path, caplog
):
    """
    Test XAS reader

    Parameters
    ----------
    nxdl : str
        Name of the NXDL application definition that is to be tested by
        this reader plugin.
    sub_reader_data_dir : str
        Test data directory that contains all the files required for running the data
        conversion through one of the sub-readers. All of these data dirs
        are placed within tests/data/...
    ignore_lines: dict[str, list[str]]
        Lines within the log files to ignore.
    ignore_sections: dict[str, list[str]]
        Subsections of the log files to ignore.
    tmp_path : pathlib.PosixPath
        Pytest fixture variable, used to clean up the files generated during
        the test.
    caplog : _pytest.logging.LogCaptureFixture
        Pytest fixture variable, used to capture the log messages during the
        test.

    Returns
    -------
    None.

    """
    caplog.clear()

    files_or_dir = os.path.join(
        *[os.path.dirname(__file__), "data", sub_reader_data_dir]
    )

    ignore_lines: list[str] = ignore_lines_all_tests + ignore_lines
    ignore_sections: dict[str, list[str]] = ignore_sections_all_tests | ignore_sections

    test = ReaderTest(
        nxdl=nxdl,
        reader_name=READER_NAME,
        files_or_dir=files_or_dir,
        tmp_path=tmp_path,
        caplog=caplog,
    )
    test.convert_to_nexus(caplog_level="WARNING", ignore_undocumented=True)
    test.check_reproducibility_of_nexus(
        ignore_lines=ignore_lines, ignore_sections=ignore_sections
    )
