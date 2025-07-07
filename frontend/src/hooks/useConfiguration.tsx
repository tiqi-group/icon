import { useEffect, useState } from "react";
import { runMethod } from "../socket";
import { SerializedDict } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";

export const useConfiguration = (): Record<string, unknown> => {
  const [configuration, setConfiguration] = useState<Record<string, unknown>>({});

  useEffect(() => {
    runMethod("config.get_config", [], {}, (response) => {
      const config = deserialize(response as SerializedDict);
      setConfiguration(config);
    });
  }, []);

  return configuration;
};
