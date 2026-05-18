# TTL Channel Control — Server Implementation

## Background

Each Zedboard FPGA TTL output channel can be in one of three states:

| State | Name | Behavior |
|-------|------|----------|
| 0 | OFF | Channel forced LOW (static override) |
| 1 | ON | Channel forced HIGH (static override) |
| 2 | CONTROL | Pulse sequence owns the channel |

The hardware exposes two RPC calls: `ttlMasks()` (read) and `setTTLMasks(high_mask, low_mask)` (write). Ionizer's C++ client implemented per-channel control via `FPGAConnection::setTTLlogicState()` / `getTTLlogicState()`. This document describes how ICON implements equivalent server-side control.

---

## Why not use `tiqi_zedboard.TTLs`?

The `TTLs` class (v1.3.0, available via the `zedboard` optional extra) exposes only binary ON/OFF control. Its `_set_channel_zedboard()` always writes a 1 into either `high_mask` or `low_mask`, making it impossible to express state 2 (CONTROL — both bits clear). The underlying RPC supports all three states, so `TTLController` works directly with the raw masks via `HardwareController.get_ttl_masks()` / `set_ttl_masks()`. No changes to tiqi-zedboard are required.

---

## Architecture

```
APIService
└── ttl: TTLController (pydase.DataService)
        ├── HardwareController  →  Zedboard RPC (ttlMasks / setTTLMasks)
        └── TTLRepository       →  SQLite ttl_mask_states table (single row)
```

`TTLController` is added to `APIService` alongside the existing `StatusController`, `DevicesController`, etc. It owns a dedicated `HardwareController` connection (same pattern as `StatusController`, i.e. `connect=False` initially) and persists masks through `TTLRepository` backed by a single-row SQLite table.

---

## Mask Encoding

For channel `n`:

| `high_mask[n]` | `low_mask[n]` | State |
|---|---|---|
| 0 | 1 | 0 — forced LOW |
| 1 | 0 | 1 — forced HIGH |
| 0 | 0 | 2 — CONTROL (pulse sequence) |

Helper functions `_decode_state()` and `_encode_state()` in `ttl_controller.py` implement this logic.

---

## Files Changed

| File | Change |
|------|--------|
| `src/icon/config/v1.py` | Added `n_ttl_channels: int = 32` to `HardwareConfig` |
| `src/icon/server/hardware_processing/hardware_controller.py` | Added `get_ttl_masks()` and `set_ttl_masks()` |
| `src/icon/server/data_access/models/sqlite/ttl_mask_state.py` | New — SQLAlchemy model |
| `src/icon/server/data_access/models/sqlite/__init__.py` | Added `TTLMaskState` to `__all__` |
| `src/icon/server/data_access/repositories/ttl_repository.py` | New — upsert/read masks |
| `src/icon/server/api/ttl_controller.py` | New — pydase DataService |
| `src/icon/server/api/api_service.py` | Registered `self.ttl = TTLController()` |
| `src/icon/server/data_access/db_context/sqlite/alembic/versions/a1b2c3d4e5f6_add_ttl_mask_state_table.py` | New — migration |
| `tests/server/__init__.py` | New — missing package marker |
| `tests/server/api/test_ttl_controller.py` | New — unit tests |

---

## API

### `ttl.get_states() -> list[int]`
Returns a list of 32 integers (0/1/2), one per channel, read live from hardware.
Falls back to the last persisted masks if the hardware is unreachable.

### `ttl.set_state(channel: int, state: int) -> None`
Sets one channel to state 0, 1, or 2. Writes to hardware, then persists the
resulting masks to SQLite. Emits a `ttl.update` Socket.IO event.

### `ttl.get_masks() -> dict[str, int]`
Returns `{"high_mask": ..., "low_mask": ...}` from hardware (or DB fallback).

### `ttl.restore_masks() -> None`
Re-applies the last persisted masks to the hardware — useful after a power cycle.

---

## Persistence

The `ttl_mask_states` table holds at most one row (`id=1`):

```sql
CREATE TABLE ttl_mask_states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    high_mask  INTEGER NOT NULL,
    low_mask   INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

Migration: `a1b2c3d4e5f6_add_ttl_mask_state_table.py` (down_revision: `fc9af856df20`).

---

## Configuration

`hardware.n_ttl_channels` in the YAML config (default 32). Set to 16 for RFSoC hardware.

```yaml
hardware:
  host: zedboard.lab
  port: 6007
  n_ttl_channels: 32
```

---

## Manual Verification (with hardware)

```python
# Start ICON server, then from a pydase client:
client.proxy.ttl.get_states()          # read all 32 channel states
client.proxy.ttl.set_state(0, 1)       # force channel 0 HIGH
client.proxy.ttl.set_state(0, 2)       # release channel 0 to pulse sequence
client.proxy.ttl.get_masks()           # inspect raw masks
client.proxy.ttl.restore_masks()       # re-apply persisted masks after power cycle
```

After `set_state()`, confirm the hardware line changes state. After restarting the
server, the masks should be readable from the DB via `get_masks()` (hardware path)
or restored via `restore_masks()`.
