import { useEffect, useState } from "react";
import { socket } from "../socket";

export interface ControlState {
  controllingSid: string | null;
  socketioSID: string | undefined;
}

export function useControlState(): ControlState {
  const [controllingSid, setControllingSid] = useState<string | null>(null);
  const [socketioSID, setSocketioSID] = useState<string | undefined>();

  useEffect(() => {
    const handleConnect = () => setSocketioSID(socket.id);
    const handleControlState = (data: { controlling_sid: string | null }) =>
      setControllingSid(data.controlling_sid);
    const handleDisconnect = () => {
      setSocketioSID(undefined);
      setControllingSid(null);
    };

    socket.on("connect", handleConnect);
    socket.on("control_state", handleControlState);
    socket.on("disconnect", handleDisconnect);

    return () => {
      socket.off("connect", handleConnect);
      socket.off("control_state", handleControlState);
      socket.off("disconnect", handleDisconnect);
    };
  }, []);

  return { controllingSid, socketioSID };
}
