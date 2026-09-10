# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
"""Shared datetime normalization for XAS parsers.

Each parser knows the fixed timezone its source format's timestamps are
recorded in (or that it's already timezone-aware) and passes that in as
*tzinfo*.
"""

import datetime


def parse_datetime(
    datetime_string: str,
    possible_date_formats: list[str] | None = None,
    tzinfo: datetime.tzinfo = datetime.timezone.utc,
) -> str:
    """Convert *datetime_string* to ISO 8601, attaching *tzinfo* if it has none.

    An already timezone-aware ISO 8601 string is returned unchanged. A naive
    ISO 8601 string, or one matching an entry in *possible_date_formats*, is
    localized with *tzinfo*.

    Raises:
        ValueError: *datetime_string* matches neither ISO 8601 nor any of
            *possible_date_formats*.
    """
    try:
        datetime_obj = datetime.datetime.fromisoformat(datetime_string.strip())
    except ValueError:
        datetime_obj = None
        for date_fmt in possible_date_formats or []:
            try:
                datetime_obj = datetime.datetime.strptime(datetime_string, date_fmt)
                break
            except ValueError:
                continue
        if datetime_obj is None:
            raise ValueError(
                f"Datetime {datetime_string!r} could not be converted to ISO 8601 "
                f"format; it matches neither ISO 8601 nor any of "
                f"{possible_date_formats}."
            ) from None

    if tzinfo is not None and datetime_obj.tzinfo is None:
        datetime_obj = datetime_obj.replace(tzinfo=tzinfo)

    return datetime_obj.isoformat()
