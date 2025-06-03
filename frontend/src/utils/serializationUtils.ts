import { SerializedObject } from "../types/SerializedObject";

const serializePrimitive = (
  obj: number | boolean | string | null,
  accessPath: string,
): SerializedObject => {
  if (typeof obj === "number") {
    return {
      full_access_path: accessPath,
      doc: null,
      readonly: false,
      type: Number.isInteger(obj) ? "int" : "float",
      value: obj,
    };
  } else if (typeof obj === "boolean") {
    return {
      full_access_path: accessPath,
      doc: null,
      readonly: false,
      type: "bool",
      value: obj,
    };
  } else if (typeof obj === "string") {
    return {
      full_access_path: accessPath,
      doc: null,
      readonly: false,
      type: "str",
      value: obj,
    };
  } else if (obj === null) {
    return {
      full_access_path: accessPath,
      doc: null,
      readonly: false,
      type: "None",
      value: null,
    };
  } else {
    throw new Error("Unsupported type for serialization");
  }
};

export const serializeList = (obj: unknown[], accessPath = ""): SerializedObject => {
  const doc = null;
  const value = obj.map((item, index) => {
    const newPath = `${accessPath}[${index}]`;
    if (
      typeof item === "number" ||
      typeof item === "boolean" ||
      typeof item === "string" ||
      item === null
    ) {
      return serializePrimitive(item as number | boolean | string | null, newPath);
    } else if (Array.isArray(item)) {
      return serializeList(item, newPath);
    } else if (typeof item === "object" && item !== null) {
      return serializeDict(item as Record<string, unknown>, newPath);
    } else {
      throw new Error(`Unsupported type in list at path: ${newPath}`);
    }
  });

  return {
    full_access_path: accessPath,
    type: "list",
    value,
    readonly: false,
    doc,
  };
};

export const serializeDict = (
  obj: Record<string, unknown>,
  accessPath = "",
): SerializedObject => {
  const doc = null;
  const value = Object.entries(obj).reduce(
    (acc, [key, val]) => {
      const newPath = `${accessPath}["${key}"]`;
      if (
        typeof val === "number" ||
        typeof val === "boolean" ||
        typeof val === "string" ||
        val === null
      ) {
        acc[key] = serializePrimitive(val as number | boolean | string | null, newPath);
      } else if (Array.isArray(val)) {
        acc[key] = serializeList(val, newPath);
      } else if (typeof val === "object") {
        acc[key] = serializeDict(val as Record<string, unknown>, newPath);
      } else {
        throw new Error(`Unsupported type in dict at path: ${newPath}`);
      }
      return acc;
    },
    {} as Record<string, SerializedObject>,
  );

  return {
    full_access_path: accessPath,
    type: "dict",
    value,
    readonly: false,
    doc,
  };
};
