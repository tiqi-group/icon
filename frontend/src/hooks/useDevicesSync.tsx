import { useEffect, Dispatch } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { DeviceState, StateAction } from "../contexts/DeviceStateContext";
import { Action, DeviceUpdate } from "../contexts/DeviceInfoContext";
import { DeviceInfo } from "../types/DeviceInfo";

interface UpdateMessage {
  data: { full_access_path: string; value: SerializedObject };
}
interface NewDeviceEvent {
  device: DeviceInfo;
}

/**
 * React hook that synchronizes the devices state with the backend.
 *
 * This hook:
 * - Fetches the device states usign `devices.serialize`.
 * - Fetches the initial list of registered devices using `devices.get_devices_by_status`.
 * - Listens for `notify` events and dispatches `UPDATE` actions.
 * - Listens for `device.new` events and dispatches `ADD` actions.
 * - Listens for `device.update` events and dispatches `UPDATE` actions.
 * - Cleans up socket listeners on unmount.
 *
 * @param stateDispatch - A React dispatch function for the device state reducer.
 * @param infoDispatch - A React dispatch function for the device info reducer.
 */
export function useDevicesSync(
  stateDispatch: Dispatch<StateAction>,
  infoDispatch: Dispatch<Action>,
) {
  function onNotify(data: UpdateMessage) {
    const { full_access_path: fullAccessPath, value: newValue } = data.data;

    if (!fullAccessPath.startsWith("devices.device_proxies")) return;

    const accessPath = fullAccessPath.substring(8);
    stateDispatch({ type: "UPDATE", fullAccessPath: accessPath, newValue });

    // Detect status changes: e.g. devices.device_proxies["Test"].connected
    const statusMatch = accessPath.match(/^device_proxies\["([^"]+)"\]\.connected$/);
    if (statusMatch) {
      const deviceName = statusMatch[1];
      infoDispatch({
        type: "UPDATE",
        payload: {
          device_name: deviceName,
          updated_properties: {
            reachable: deserialize(newValue),
          },
        },
      });
    }
  }

  useEffect(() => {
    runMethod("devices.serialize", [], {}, (ack) => {
      stateDispatch({
        type: "SET",
        data: deserialize(ack as SerializedObject) as DeviceState,
      });
    });

    runMethod("devices.get_devices_by_status", [], {}, (ack) => {
      infoDispatch({ type: "SET", payload: deserialize(ack as SerializedObject) });
    });

    socket.on("notify", onNotify);

    socket.on("device.new", (data: NewDeviceEvent) => {
      infoDispatch({ type: "ADD", payload: data.device });
    });
    socket.on("device.update", (data: DeviceUpdate) => {
      infoDispatch({ type: "UPDATE", payload: data });
    });

    return () => {
      socket.off("notify");
      socket.off("device.new");
      socket.off("device.update");
    };
  }, [stateDispatch, infoDispatch]);
}
