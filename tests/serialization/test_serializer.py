"""Isolated tests for the `IconSerializer` recursion contract.

pydase's base `Serializer` recurses through `cls.serialize_object` classmethods,
so the timezone must be carried on the class, not on an instance. These tests
serialize the nested structures the web server returns to the frontend
(`trigger_method` responses) through that recursion.
"""

import datetime
from typing import Any

import pytz

from icon.serialization.serializer import IconSerializer, dump

ZURICH = pytz.timezone("Europe/Zurich")
UTC = pytz.UTC
IDS = [1, 2, 3]


def test_nested_structures_are_serialized_through_class_recursion() -> None:
    """Nested dicts and lists must survive the base classmethod recursion.

    pydase's `_serialize_dict`/`_serialize_list` call `cls.serialize_object` on every
    element.
    """
    serializer = IconSerializer.with_timezone(ZURICH)
    result = serializer.serialize_object(
        {"jobs": [{"id": 1, "ids": IDS}, {"id": 2, "nested": {}}]}
    )

    assert result["type"] == "dict"
    jobs: Any = result["value"]["jobs"]["value"]
    assert [entry["value"] for entry in jobs[0]["value"]["ids"]["value"]] == IDS
    assert jobs[1]["value"]["nested"]["value"] == {}


def test_recursion_keeps_the_configured_timezone() -> None:
    """A datetime deep in the tree must render in the serializer's timezone.

    This proves the recursion stays on the timezone-carrying subclass rather than
    falling back to the base `Serializer`.
    """
    serializer = IconSerializer.with_timezone(ZURICH)
    result: Any = serializer.serialize_object(
        {"jobs": [{"created": datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)}]}
    )

    created = result["value"]["jobs"]["value"][0]["value"]["created"]
    assert created["type"] == "datetime"
    # 12:00 UTC is 13:00 in Zurich in winter.
    assert created["value"] == "2026-01-01T13:00:00+01:00"


def test_dump_helper_applies_the_given_timezone() -> None:
    """`dump` must apply its argument, not any previously configured state."""
    result: Any = dump(
        {"timestamp": datetime.datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)},
        timezone=ZURICH,
    )

    # 12:00 UTC is 14:00 in Zurich in summer (CEST).
    assert result["value"]["timestamp"]["value"] == "2026-07-01T14:00:00+02:00"
