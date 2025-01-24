import { deserialize } from "../deserializer";
import {
  SerializedInteger,
  SerializedFloat,
  SerializedBool,
  SerializedString,
  SerializedEnum,
  SerializedList,
  SerializedDict,
  SerializedNoneType,
  SerializedDataService,
} from "../../types/SerializedObject";

describe("Deserializer", () => {
  test("should deserialize a SerializedInteger", () => {
    const input: SerializedInteger = {
      full_access_path: "test.integer",
      doc: null,
      readonly: false,
      value: 42,
      type: "int",
    };

    const result = deserialize(input);
    expect(result).toBe(42);
  });

  test("should deserialize a SerializedFloat", () => {
    const input: SerializedFloat = {
      full_access_path: "test.float",
      doc: null,
      readonly: false,
      value: 3.14,
      type: "float",
    };

    const result = deserialize(input);
    expect(result).toBe(3.14);
  });

  test("should deserialize a SerializedBool", () => {
    const input: SerializedBool = {
      full_access_path: "test.bool",
      doc: null,
      readonly: false,
      value: true,
      type: "bool",
    };

    const result = deserialize(input);
    expect(result).toBe(true);
  });

  test("should deserialize a SerializedString", () => {
    const input: SerializedString = {
      full_access_path: "test.string",
      doc: null,
      readonly: false,
      value: "hello",
      type: "str",
    };

    const result = deserialize(input);
    expect(result).toBe("hello");
  });

  test("should deserialize a SerializedEnum", () => {
    const input: SerializedEnum = {
      full_access_path: "test.enum",
      doc: null,
      readonly: false,
      name: "TestEnum",
      value: "OPTION_A",
      type: "Enum",
      enum: {
        OPTION_A: "Option A",
        OPTION_B: "Option B",
      },
    };

    const result = deserialize(input);
    expect(result).toBe("Option A");
  });

  test("should deserialize a SerializedList", () => {
    const input: SerializedList = {
      full_access_path: "my_list",
      doc: null,
      readonly: false,
      value: [
        {
          full_access_path: "my_list[0]",
          doc: null,
          readonly: false,
          value: 1,
          type: "int",
        },
        {
          full_access_path: "my_list[1]",
          doc: null,
          readonly: false,
          value: "item",
          type: "str",
        },
      ],
      type: "list",
    };

    const result = deserialize(input);
    expect(result).toEqual([1, "item"]);
  });

  test("should deserialize a SerializedDict", () => {
    const input: SerializedDict = {
      full_access_path: "test.dict",
      doc: null,
      readonly: false,
      value: {
        key1: {
          full_access_path: "test.int",
          doc: null,
          readonly: false,
          value: 1,
          type: "int",
        },
        key2: {
          full_access_path: "test.str",
          doc: null,
          readonly: false,
          value: "value",
          type: "str",
        },
      },
      type: "dict",
    };

    const result = deserialize(input);
    expect(result).toEqual({ key1: 1, key2: "value" });
  });

  test("should deserialize a SerializedNoneType", () => {
    const input: SerializedNoneType = {
      full_access_path: "test.none",
      doc: null,
      readonly: false,
      value: null,
      type: "NoneType",
    };

    const result = deserialize(input);
    expect(result).toBeNull();
  });

  test("should deserialize a SerializedDataService", () => {
    const input: SerializedDataService = {
      full_access_path: "test.dataservice",
      doc: null,
      readonly: false,
      name: "MyService",
      value: {
        property1: {
          full_access_path: "test.property1",
          doc: null,
          readonly: false,
          value: "value1",
          type: "str",
        },
      },
      type: "DataService",
    };

    const result = deserialize(input);
    expect(result.property1).toBe("value1");
  });
});
