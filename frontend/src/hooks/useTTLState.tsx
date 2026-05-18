import { useCallback, useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";

const N_CHANNELS = 32;

function defaultLabels(): string[] {
  return Array.from({ length: N_CHANNELS }, (_, i) => `TTL ${i.toString().padStart(2, "0")}`);
}

interface TTLUpdateEvent {
  channel: number;
  state: number;
}

interface TTLLabelUpdateEvent {
  channel: number;
  label: string;
}

export interface TTLState {
  /** Hardware state per channel: 0=OFF, 1=ON, 2=CONTROL. */
  states: number[];
  /** Per-channel labels (editable). */
  labels: string[];
  /**
   * Remembered manual ON/OFF value per channel, independent of whether the
   * channel is currently in CONTROL mode. Matches ionizer's StateButton state.
   */
  localManualState: number[];
  setState: (channel: number, state: number) => void;
  setLocalManual: (channel: number, manual: 0 | 1) => void;
  setLabel: (channel: number, label: string) => void;
}

export function useTTLState(): TTLState {
  const [states, setStates] = useState<number[]>(Array(N_CHANNELS).fill(2));
  const [labels, setLabels] = useState<string[]>(defaultLabels());
  const [localManualState, setLocalManualState] = useState<number[]>(
    Array(N_CHANNELS).fill(0),
  );

  useEffect(() => {
    runMethod("ttl.get_states", [], {}, (ack) => {
      const fetched = deserialize(ack as SerializedObject) as number[];
      setStates(fetched);
      setLocalManualState(fetched.map((s) => (s === 2 ? 0 : s)));
    });

    runMethod("ttl.get_labels", [], {}, (ack) => {
      setLabels(deserialize(ack as SerializedObject) as string[]);
    });

    function onTTLUpdate(data: TTLUpdateEvent) {
      setStates((prev) => {
        const next = [...prev];
        next[data.channel] = data.state;
        return next;
      });
      if (data.state !== 2) {
        setLocalManualState((prev) => {
          const next = [...prev];
          next[data.channel] = data.state;
          return next;
        });
      }
    }

    function onLabelUpdate(data: TTLLabelUpdateEvent) {
      setLabels((prev) => {
        const next = [...prev];
        next[data.channel] = data.label;
        return next;
      });
    }

    socket.on("ttl.update", onTTLUpdate);
    socket.on("ttl.label_update", onLabelUpdate);

    return () => {
      socket.off("ttl.update", onTTLUpdate);
      socket.off("ttl.label_update", onLabelUpdate);
    };
  }, []);

  const setState = useCallback((channel: number, state: number) => {
    runMethod("ttl.set_state", [channel, state]);
  }, []);

  const setLocalManual = useCallback((channel: number, manual: 0 | 1) => {
    setLocalManualState((prev) => {
      const next = [...prev];
      next[channel] = manual;
      return next;
    });
  }, []);

  const setLabel = useCallback((channel: number, label: string) => {
    runMethod("ttl.set_label", [channel, label]);
  }, []);

  return { states, labels, localManualState, setState, setLocalManual, setLabel };
}
