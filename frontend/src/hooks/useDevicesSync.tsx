import { useEffect, useRef, Dispatch } from "react";
import { useLocation } from "react-router";
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

function isDevicesRoute(pathname: string): boolean {
  return pathname === "/devices" || pathname.startsWith("/devices/");
}

function refreshDeviceState(stateDispatch: Dispatch<StateAction>) {
  runMethod("serialize", [], {}, (ack) => {
    stateDispatch({
      type: "SET",
      data: deserialize(ack as SerializedObject) as DeviceState,
    });
  });
}

/**
 * React hook that synchronizes the devices state with the backend.
 *
 * This hook:
 * - Fetches the device states using `serialize`.
 * - Fetches the initial list of registered devices using `devices.get_devices_by_status`.
 * - Applies live `notify` value updates only while the Devices page is open, so chatty
 *   devices cannot freeze the rest of the UI. Connection reachability updates are
 *   always applied (they are rare and cheap).
 * - Refreshes full device state when navigating to the Devices page.
 * - Listens for `device.new` / `device.update` events.
 * - Cleans up socket listeners on unmount.
 *
 * @param stateDispatch - A React dispatch function for the device state reducer.
 * @param infoDispatch - A React dispatch function for the device info reducer.
 */
export function useDevicesSync(
  stateDispatch: Dispatch<StateAction>,
  infoDispatch: Dispatch<Action>,
) {
  const { pathname } = useLocation();
  const liveDeviceStateUpdatesRef = useRef(isDevicesRoute(pathname));
  liveDeviceStateUpdatesRef.current = isDevicesRoute(pathname);

  useEffect(() => {
    function onNotify(data: UpdateMessage) {
      const { full_access_path: fullAccessPath, value: newValue } = data.data;

      if (!fullAccessPath.startsWith("devices.device_proxies")) return;

      // Detect status changes: e.g. devices.device_proxies["Test"].connected
      const statusMatch = fullAccessPath.match(
        /^devices\.device_proxies\["([^"]+)"\]\.connected$/,
      );
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

      // High-rate attribute updates only matter on the Devices page. Skipping them
      // elsewhere avoids App-wide re-renders from chatty device telemetry.
      if (!liveDeviceStateUpdatesRef.current) return;

      stateDispatch({ type: "UPDATE", fullAccessPath: fullAccessPath, newValue });
    }

    refreshDeviceState(stateDispatch);

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

  useEffect(() => {
    if (!isDevicesRoute(pathname)) return;
    refreshDeviceState(stateDispatch);
  }, [pathname, stateDispatch]);
}
