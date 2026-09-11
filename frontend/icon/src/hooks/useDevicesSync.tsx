import { useEffect, Dispatch } from "react";
import { runMethod, getValue, socket } from "../socket";
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

const CONNECTED_PATH_REGEX = /^devices\.device_proxies\["([^"]+)"\]\.connected$/;

/**
 * React hook that synchronizes the registered device list with the backend.
 *
 * This hook:
 * - Fetches the initial list of registered devices using `devices.get_devices_by_status`.
 * - Listens for `device.new` / `device.update` events.
 * - Cleans up its own socket listeners on unmount.
 *
 * @param infoDispatch - A React dispatch function for the device info reducer.
 */
export function useDeviceInfoSync(infoDispatch: Dispatch<Action>) {
  useEffect(() => {
    function onNotify(data: UpdateMessage) {
      const { full_access_path: fullAccessPath, value: newValue } = data.data;

      const statusMatch = fullAccessPath.match(CONNECTED_PATH_REGEX);
      if (!statusMatch) return;

      infoDispatch({
        type: "UPDATE",
        payload: {
          device_name: statusMatch[1],
          updated_properties: {
            reachable: deserialize(newValue),
          },
        },
      });
    }

    function onDeviceNew(data: NewDeviceEvent) {
      infoDispatch({ type: "ADD", payload: data.device });
    }

    function onDeviceUpdate(data: DeviceUpdate) {
      infoDispatch({ type: "UPDATE", payload: data });
    }

    runMethod("devices.get_devices_by_status", [], {}, (ack) => {
      infoDispatch({ type: "SET", payload: deserialize(ack as SerializedObject) });
    });

    socket.on("notify", onNotify);
    socket.on("device.new", onDeviceNew);
    socket.on("device.update", onDeviceUpdate);

    return () => {
      socket.off("notify", onNotify);
      socket.off("device.new", onDeviceNew);
      socket.off("device.update", onDeviceUpdate);
    };
  }, [infoDispatch]);
}

/**
 * React hook that synchronizes the device state for a single device with the backend.
 *
 * This hook:
 * - Fetches the specific device state `devices.device_proxies[deviceName]`.
 * - Applies live `notify` value updates for the given `deviceName`.
 * - Joins the device-updates room for as long as it is mounted.
 * - Cleans up its own socket listeners on unmount.
 *
 * @param stateDispatch - A React dispatch function for the device state reducer.
 * @param deviceName - Name of the device whose state is synchronized.
 */
export function useDeviceStateSync(
  stateDispatch: Dispatch<StateAction>,
  deviceName: string,
) {
  useEffect(() => {
    const prefix = `devices.device_proxies["${deviceName}"].`;

    function onNotify(data: UpdateMessage) {
      const { full_access_path: fullAccessPath, value: newValue } = data.data;

      if (!fullAccessPath.startsWith(prefix)) return;

      stateDispatch({ type: "UPDATE", fullAccessPath: fullAccessPath, newValue });
    }

    function subscribe() {
      socket.emit("subscribe_device_updates", deviceName);
      getValue(`devices.device_proxies["${deviceName}"]`, (ack) => {
        const device_proxy_state = ack as SerializedObject;
        const devstate: DeviceState = {
          value: {
            devices: {
              value: {
                device_proxies: {
                  type: "dict",
                  full_access_path: `devices.device_proxies`,
                  doc: null,
                  readonly: false,
                  value: { [deviceName]: device_proxy_state },
                },
              },
            },
          },
        };
        stateDispatch({
          type: "SET",
          data: devstate,
        });
      });
    }

    socket.on("notify", onNotify);
    socket.on("connect", subscribe);
    subscribe();

    return () => {
      socket.off("notify", onNotify);
      socket.off("connect", subscribe);
      socket.emit("unsubscribe_device_updates", deviceName);
    };
  }, [stateDispatch, deviceName]);
}
