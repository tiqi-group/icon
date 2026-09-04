import { runMethod } from "../socket";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "./deserializer";

export const updateConfiguration = async (
  key: string,
  value: string | number | boolean | object | null,
): Promise<Error | null> => {
  return new Promise((resolve) => {
    runMethod("config.update_config_option", [], { key, value }, (data) => {
      const result = deserialize(data as SerializedObject);
      resolve(result);
    });
  });
};
