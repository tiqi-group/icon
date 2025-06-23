// useDeviceStateSync.tsx
import { useEffect, Dispatch } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { DeviceState, StateAction } from "../contexts/DeviceStateContext";

interface UpdateMessage {
  data: { full_access_path: string; value: SerializedObject };
}

function onNotify(value: UpdateMessage, dispatch: Dispatch<StateAction>) {
  const { full_access_path: fullAccessPath, value: newValue } = value.data;

  if (!fullAccessPath.startsWith("devices.device_proxies")) {
    return;
  }
  const accessPath = fullAccessPath.substring(8);

  dispatch({
    type: "UPDATE",
    fullAccessPath: accessPath,
    newValue,
  });
}

export function useDeviceStateSync(dispatch: Dispatch<StateAction>) {
  useEffect(() => {
    runMethod("devices.serialize", [], {}, (ack) => {
      dispatch({
        type: "SET",
        data: deserialize(ack as SerializedObject) as DeviceState,
      });
    });

    socket.on("notify", (data: UpdateMessage) => onNotify(data, dispatch));

    return () => {
      socket.off("notify");
    };
  }, [dispatch]);
}
