# TTL Control in ionpulse_sdk_core

## Overview

Each of the 32 (on the RFSoC it think it's 16?) TTL output channels can be in one of three states:

| State | Name | Behavior |
|---|---|---|
| 0 | OFF | Ionizer forces the line **LOW** (static override) |
| 1 | ON | Ionizer forces the line **HIGH** (static override) |
| 2 | CONTROL | sdk_core pulse sequence controls the line dynamically |

State 2 is what Ionizer shows in **blue** — it means the FPGA pulse sequence owns that channel. States 0 and 1 are static overrides that the pulse sequence cannot override.

---

## Hardware Mechanism: The Two-Mask System

The FPGA exposes two 32-bit registers via RPC:

```
setTTLMasks(uint32 high_mask, uint32 low_mask)
ttlMasks()  →  (uint32 high_mask, uint32 low_mask)
```

For each bit position `n` (TTL channel n):

| `high_mask[n]` | `low_mask[n]` | Result |
|---|---|---|
| 0 | 1 | Line forced **LOW** (state 0) |
| 1 | 0 | Line forced **HIGH** (state 1) |
| 0 | 0 | Line under **pulse sequence control** (state 2) |
| 1 | 1 | Undefined — do not use |

Setting a channel to state 2 means clearing **both** its bits in both masks. The FPGA pulse sequence then drives that line as programmed in the waveform.

### Per-channel helper logic

To set channel `n` to a given state, read the current masks, modify the two bits, then write back:

```python
def set_ttl_state(n, state, high_mask, low_mask):
    bit = 1 << n
    if state == 0:   # forced LOW
        high_mask &= ~bit
        low_mask  |=  bit
    elif state == 1: # forced HIGH
        high_mask |=  bit
        low_mask  &= ~bit
    elif state == 2: # pulse-sequence control
        high_mask &= ~bit
        low_mask  &= ~bit
    return high_mask, low_mask
```

Reading the current state back:

```python
def get_ttl_state(n, high_mask, low_mask):
    bit = 1 << n
    if low_mask  & bit: return 0  # forced LOW
    if high_mask & bit: return 1  # forced HIGH
    return 2                       # pulse-sequence control
```

---

## RPC API Reference

These are msgpack-RPC calls on the sdk_core server:

```
# Read current override masks
(high_mask, low_mask) = rpc.call("ttlMasks")

# Write override masks (affects all 32 channels at once)
rpc.call("setTTLMasks", high_mask, low_mask)
```

Both masks must be sent together. Always do a read-modify-write when changing individual channels to avoid clobbering others.

---

## Pulse-Level Control (sdk_core side)

When a TTL channel is in state 2 (CONTROL), the pulse sequence drives it. Each pulse step in the waveform carries two TTL fields:

- **`ttl_pattern`** (uint32): The desired output state — which channels should be HIGH during this step.
- **`ttl_line_mask`** (uint32): Which channels are actually updated by this step. Channels not in the mask keep their previous value.

Only channels in state 2 (both override bits clear) respond to these pulse-sequence commands. Channels held in state 0 or 1 are statically overridden at the hardware level and will not follow the pulse sequence regardless of `ttl_pattern`.

---

## What to Implement in Your Server

1. **On startup / connect**: call `ttlMasks()` to read the current hardware state.
2. **Per-channel state control**: implement read-modify-write using `setTTLMasks` to set individual channels to state 0, 1, or 2.
3. **Expose three operations per channel**:
   - Force LOW (state 0)
   - Force HIGH (state 1)
   - Release to pulse sequence (state 2 — the "blue" / CONTROL mode)
4. **Pulse sequence**: when building waveforms, pass `ttl_pattern` and `ttl_line_mask` per step. Only channels in state 2 will respond.
5. **Persistence**: save the mask state so it can be restored on reconnect (the hardware forgets on power cycle).

---

## Ionizer UI Mapping (for reference)

| Ionizer element | Meaning |
|---|---|
| StateButton **red** | Channel in state 0 (forced LOW) |
| StateButton **green** | Channel in state 1 (forced HIGH) |
| ControlButton **blue** (PI / "397 0th") | Channel in state 2 (pulse-sequence control) |
| ControlButton **black** | Ionizer is in manual override mode (state 0 or 1) |

The ControlButton is what switches between static override and pulse-sequence control. The StateButton only has effect when the ControlButton is not active.

Key source files: `FPGAConnection.cpp:96–120` (mask logic), `ExperimentsSheet.cpp:747–786` (UI handlers), `api.h:141–147` (RPC method names), `bp_dds.h:112–165` (pulse-level TTL fields).
