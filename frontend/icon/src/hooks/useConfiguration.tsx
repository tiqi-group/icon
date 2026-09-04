import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { SerializedDict } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";
import { Configuration } from "../types/Configuration";

export const useConfiguration = (): Configuration | null => {
  const [configuration, setConfiguration] = useState<Configuration | null>(null);

  useEffect(() => {
    socket.on("config.update", (result) => {
      setConfiguration(result);
    });

    runMethod("config.get_config", [], {}, (response) => {
      const config = deserialize(response as SerializedDict);
      setConfiguration(config);
    });

    return () => {
      socket.off("config.update");
    };
  }, []);

  return configuration;
};
