import { Dispatch, useEffect } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { DeviceUpdate, Action } from "../contexts/DevicesContext";
import { SerializedObject } from "../types/SerializedObject";
import { Device } from "../types/Device";

interface NewDeviceEvent {
  device: Device;
}

/**
 * React hook that synchronizes the devices state with the backend.
 *
 * This hook:
 * - Fetches the initial list of registered devices using `devices.get_devices_by_status`.
 * - Listens for `new_device` events and dispatches `ADD` actions.
 * - Listens for `update_device` events and dispatches `UPDATE` actions.
 * - Cleans up socket listeners on unmount.
 *
 * @param dispatch - A React dispatch function for the devices reducer (DevicesContext).
 */
export function useDevicesSync(dispatch: Dispatch<Action>) {
  useEffect(() => {
    runMethod("devices.get_devices_by_status", [], {}, (ack) => {
      dispatch({ type: "SET", payload: deserialize(ack as SerializedObject) });
    });

    socket.on("device.new", (data: NewDeviceEvent) =>
      dispatch({ type: "ADD", payload: data.device }),
    );
    socket.on("device.update", (data: DeviceUpdate) =>
      dispatch({ type: "UPDATE", payload: data }),
    );

    return () => {
      socket.off("device.new");
      socket.off("device.update");
    };
  }, [dispatch]);
}
