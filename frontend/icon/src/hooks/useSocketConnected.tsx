import { useEffect, useState } from "react";
import { socket } from "../socket";

/**
 * Hook for websocket connection state.
 *
 * @returns `true` while the socket is connected, `false` before the first connection
 *   has been established and after the connection was lost.
 */
export function useSocketConnected(): boolean {
  const [connected, setConnected] = useState<boolean>(socket.connected);

  useEffect(() => {
    const handleConnect = () => setConnected(true);
    const handleDisconnect = () => setConnected(false);

    // The state may have changed between the initial render and this subscription.
    setConnected(socket.connected);

    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);

    return () => {
      socket.off("connect", handleConnect);
      socket.off("disconnect", handleDisconnect);
    };
  }, []);

  return connected;
}
