import { runMethod } from "../socket";

export const updateConfiguration = (
  key: string,
  value: string | number | boolean | object | null,
) => {
  return runMethod("config.update_config_option", [], { key, value });
};
