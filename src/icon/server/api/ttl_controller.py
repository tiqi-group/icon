import asyncio
import logging

import pydase

from icon.config.config import get_config
from icon.server.data_access.repositories.ttl_repository import TTLRepository
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)

_OFF = 0
_ON = 1
_CONTROL = 2


def _decode_state(channel: int, high_mask: int, low_mask: int) -> int:
    """Return the state (0=OFF, 1=ON, 2=CONTROL) of a single TTL channel."""
    bit = 1 << channel
    if low_mask & bit:
        return _OFF
    if high_mask & bit:
        return _ON
    return _CONTROL


def _encode_state(
    channel: int, state: int, high_mask: int, low_mask: int
) -> tuple[int, int]:
    """Return updated (high_mask, low_mask) after setting channel to state."""
    bit = 1 << channel
    if state == _OFF:
        high_mask &= ~bit
        low_mask |= bit
    elif state == _ON:
        high_mask |= bit
        low_mask &= ~bit
    elif state == _CONTROL:
        high_mask &= ~bit
        low_mask &= ~bit
    else:
        raise ValueError(f"Invalid TTL state {state!r}; must be 0 (OFF), 1 (ON), or 2 (CONTROL)")
    return high_mask, low_mask


class TTLController(pydase.DataService):
    """Per-channel TTL state control for the Zedboard FPGA.

    Each of the n_ttl_channels output channels can be set to one of three states:

    - 0 (OFF): channel forced LOW
    - 1 (ON): channel forced HIGH
    - 2 (CONTROL): channel driven by the pulse sequence

    Mask state is persisted to SQLite so it survives hardware power cycles.
    """

    def __init__(self) -> None:
        super().__init__()
        self._n_channels: int = get_config().hardware.n_ttl_channels
        self._hw = HardwareController(connect=False)
        self._repo = TTLRepository()

    def get_states(self) -> list[int]:
        """Return the current state (0/1/2) for all channels.

        Reads live from the hardware when connected; falls back to the last
        persisted masks if the hardware is unreachable.
        """
        try:
            high_mask, low_mask = self._hw.get_ttl_masks()
        except RuntimeError:
            logger.warning(
                "Hardware unreachable; returning persisted TTL mask state"
            )
            high_mask, low_mask = self._repo.get_masks()
        return [
            _decode_state(ch, high_mask, low_mask)
            for ch in range(self._n_channels)
        ]

    def set_state(self, channel: int, state: int) -> None:
        """Set a single TTL channel to state 0 (OFF), 1 (ON), or 2 (CONTROL).

        Persists the resulting masks to SQLite and emits a ``ttl.update`` event.

        Args:
            channel: Channel index (0 to n_ttl_channels - 1).
            state: 0 = forced LOW, 1 = forced HIGH, 2 = pulse-sequence control.

        Raises:
            ValueError: If channel or state is out of range.
            RuntimeError: If the hardware is unreachable.
        """
        if not (0 <= channel < self._n_channels):
            raise ValueError(
                f"Channel {channel} out of range [0, {self._n_channels - 1}]"
            )
        high_mask, low_mask = self._hw.get_ttl_masks()
        high_mask, low_mask = _encode_state(channel, state, high_mask, low_mask)
        self._hw.set_ttl_masks(high_mask, low_mask)
        self._repo.save_masks(high_mask, low_mask)
        emit_queue.put(
            {
                "event": "ttl.update",
                "data": {
                    "channel": channel,
                    "state": state,
                    "high_mask": high_mask,
                    "low_mask": low_mask,
                },
            }
        )
        logger.info("TTL channel %d set to state %d", channel, state)

    def get_masks(self) -> dict[str, int]:
        """Return the raw ``{'high_mask': ..., 'low_mask': ...}`` from hardware.

        Falls back to persisted masks if the hardware is unreachable.
        """
        try:
            high_mask, low_mask = self._hw.get_ttl_masks()
        except RuntimeError:
            logger.warning(
                "Hardware unreachable; returning persisted TTL masks"
            )
            high_mask, low_mask = self._repo.get_masks()
        return {"high_mask": high_mask, "low_mask": low_mask}

    async def restore_masks(self) -> None:
        """Write the last persisted masks back to the hardware.

        Useful after a hardware power cycle. Runs the RPC call in a thread to
        avoid blocking the event loop.
        """
        high_mask, low_mask = self._repo.get_masks()
        await asyncio.to_thread(self._hw.set_ttl_masks, high_mask, low_mask)
        logger.info(
            "Restored TTL masks to hardware: high=0x%08x low=0x%08x",
            high_mask,
            low_mask,
        )
