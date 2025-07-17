import { SignJsonWebKeyInput } from "crypto";
import {
  SerializedDataService,
  SerializedDict,
  SerializedEnum,
  SerializedException,
  SerializedList,
  SerializedObject,
} from "../types/SerializedObject";

type DeserializedValue =
  any; /* eslint-disable-line @typescript-eslint/no-explicit-any */

class Deserializer {
  private static typeHandler: Record<
    SerializedObject["type"],
    | ((
        serializedObject: any /* eslint-disable-line @typescript-eslint/no-explicit-any */,
      ) => DeserializedValue)
    | undefined
  > = {
    int: Deserializer.deserializePrimitive,
    float: Deserializer.deserializePrimitive,
    bool: Deserializer.deserializePrimitive,
    str: Deserializer.deserializePrimitive,
    NoneType: Deserializer.deserializePrimitive,
    Enum: Deserializer.deserializeEnum,
    ColouredEnum: Deserializer.deserializeEnum,
    list: Deserializer.deserializeList,
    dict: Deserializer.deserializeDict,
    None: Deserializer.deserializePrimitive,
    DataService: Deserializer.deserializeDataService,
    Image: Deserializer.deserializeDataService,
    NumberSlider: Deserializer.deserializeDataService,
    DeviceConnection: Deserializer.deserializeDataService,
    Task: Deserializer.deserializeDataService,
    Exception: Deserializer.deserializeException,
    Quantity: undefined,
  };

  static deserialize(serializedObject: SerializedObject): DeserializedValue {
    const handler = this.typeHandler[serializedObject.type];
    if (handler) {
      return handler(serializedObject);
    }

    console.warn(`Unknown type: ${serializedObject.type}`);
    return null;
  }

  private static deserializePrimitive(
    serializedObject: SerializedObject,
  ): DeserializedValue {
    if (serializedObject.type === "float") {
      return parseFloat(serializedObject.value as unknown as string);
    }
    return serializedObject.value;
  }

  private static deserializeException(serializedObject: SerializedException): Error {
    const error = new Error(serializedObject.value);
    error.name = serializedObject.name;
    return error;
  }

  private static deserializeEnum(serializedObject: SerializedEnum): DeserializedValue {
    const { enum: enumValues, value } = serializedObject;
    return enumValues[value];
  }

  private static deserializeList(serializedObject: SerializedList): DeserializedValue {
    return serializedObject.value.map((item) => Deserializer.deserialize(item));
  }

  private static deserializeDict(serializedObject: SerializedDict): DeserializedValue {
    const deserialized: Record<string, DeserializedValue> = {};
    for (const [key, value] of Object.entries(serializedObject.value)) {
      deserialized[key] = Deserializer.deserialize(value);
    }
    return deserialized;
  }

  private static deserializeDataService(
    serializedObject: SerializedDataService,
  ): DeserializedValue {
    const proxy: Record<string, DeserializedValue> = {};
    for (const [key, value] of Object.entries(serializedObject.value)) {
      proxy[key] = Deserializer.deserialize(value);
    }
    return proxy;
  }
}

// Usage
export function deserialize(serializedObject: SerializedObject): DeserializedValue {
  return Deserializer.deserialize(serializedObject);
}
