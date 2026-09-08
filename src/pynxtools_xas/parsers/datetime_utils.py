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
