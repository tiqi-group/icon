"""Tests for the JSON encoding of scan parameter values (pydase Quantities)."""

import json

import pydase.units as u

from icon.server.data_access.models.sqlite.scan_parameter import (
    SpecialEncoder,
    special_decoder,
)


def test_quantity_roundtrip() -> None:
    values = [
        0.0,
        u.convert_to_quantity(100, "V"),
        u.convert_to_quantity(111.111111, "V"),
    ]
    encoded = json.dumps(values, cls=SpecialEncoder)
    assert json.loads(encoded, object_hook=special_decoder) == values
