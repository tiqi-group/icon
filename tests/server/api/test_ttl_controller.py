"""Tests for TTLController mask encoding/decoding and state management."""

from unittest.mock import MagicMock, patch

import pytest

from icon.server.api.ttl_controller import (
    TTLController,
    _decode_state,
    _encode_state,
)


class TestDecodeState:
    def test_off_when_low_bit_set(self) -> None:
        assert _decode_state(0, high_mask=0b00, low_mask=0b01) == 0

    def test_on_when_high_bit_set(self) -> None:
        assert _decode_state(0, high_mask=0b01, low_mask=0b00) == 1

    def test_control_when_both_bits_clear(self) -> None:
        assert _decode_state(0, high_mask=0b00, low_mask=0b00) == 2

    def test_channel_31_off(self) -> None:
        low_mask = 1 << 31
        assert _decode_state(31, high_mask=0, low_mask=low_mask) == 0

    def test_channel_31_on(self) -> None:
        high_mask = 1 << 31
        assert _decode_state(31, high_mask=high_mask, low_mask=0) == 1

    def test_channel_31_control(self) -> None:
        assert _decode_state(31, high_mask=0, low_mask=0) == 2

    def test_independent_of_other_channels(self) -> None:
        # Channel 0 is ON; channel 1 is in CONTROL — decoding ch1 should give 2
        high_mask = 0b01  # ch0 ON
        low_mask = 0b00
        assert _decode_state(1, high_mask, low_mask) == 2


class TestEncodeState:
    def test_set_off(self) -> None:
        high, low = _encode_state(0, state=0, high_mask=0b01, low_mask=0b00)
        assert not (high & 1)  # high bit cleared
        assert low & 1  # low bit set

    def test_set_on(self) -> None:
        high, low = _encode_state(0, state=1, high_mask=0b00, low_mask=0b01)
        assert high & 1  # high bit set
        assert not (low & 1)  # low bit cleared

    def test_set_control(self) -> None:
        high, low = _encode_state(0, state=2, high_mask=0b01, low_mask=0b01)
        assert not (high & 1)  # high bit cleared
        assert not (low & 1)  # low bit cleared

    def test_does_not_affect_other_channels(self) -> None:
        # Channel 1 is ON (bit 1 set in high_mask)
        high, low = _encode_state(0, state=0, high_mask=0b10, low_mask=0b00)
        assert high & 0b10  # channel 1 still ON

    def test_invalid_state_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid TTL state"):
            _encode_state(0, state=3, high_mask=0, low_mask=0)

    def test_channel_31(self) -> None:
        high, low = _encode_state(31, state=1, high_mask=0, low_mask=0)
        assert high == (1 << 31)
        assert low == 0


class TestTTLController:
    def _make_controller(self, hw_masks=(0, 0)):
        with (
            patch("icon.server.api.ttl_controller.HardwareController") as MockHW,
            patch("icon.server.api.ttl_controller.TTLRepository") as MockRepo,
            patch("icon.server.api.ttl_controller.get_config") as MockConfig,
        ):
            MockConfig.return_value.hardware.n_ttl_channels = 32
            hw = MockHW.return_value
            hw.get_ttl_masks.return_value = hw_masks
            repo = MockRepo.return_value
            repo.get_masks.return_value = hw_masks
            ctrl = TTLController()
            ctrl._hw = hw
            ctrl._repo = repo
            ctrl._n_channels = 32
        return ctrl, hw, repo

    def test_get_states_all_control_when_masks_zero(self) -> None:
        ctrl, hw, _ = self._make_controller((0, 0))
        states = ctrl.get_states()
        assert all(s == 2 for s in states)
        assert len(states) == 32

    def test_get_states_channel_0_on(self) -> None:
        ctrl, hw, _ = self._make_controller((0b01, 0b00))
        states = ctrl.get_states()
        assert states[0] == 1
        assert states[1] == 2

    def test_get_states_falls_back_to_db_on_error(self) -> None:
        ctrl, hw, repo = self._make_controller()
        hw.get_ttl_masks.side_effect = RuntimeError("no hardware")
        repo.get_masks.return_value = (0b01, 0b00)
        states = ctrl.get_states()
        assert states[0] == 1

    def test_set_state_writes_to_hw_and_persists(self) -> None:
        ctrl, hw, repo = self._make_controller((0, 0))
        with patch("icon.server.api.ttl_controller.emit_queue"):
            ctrl.set_state(0, 1)
        hw.set_ttl_masks.assert_called_once_with(0b01, 0b00)
        repo.save_masks.assert_called_once_with(0b01, 0b00)

    def test_set_state_invalid_channel_raises(self) -> None:
        ctrl, _, _ = self._make_controller()
        with pytest.raises(ValueError, match="out of range"):
            ctrl.set_state(32, 1)

    def test_get_masks_returns_dict(self) -> None:
        ctrl, hw, _ = self._make_controller((0xAB, 0xCD))
        result = ctrl.get_masks()
        assert result == {"high_mask": 0xAB, "low_mask": 0xCD}
