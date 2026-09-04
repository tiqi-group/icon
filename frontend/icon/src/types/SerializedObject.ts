import { QuantityMap } from "./QuantityMap";

interface SerializedObjectBase {
  full_access_path: string;
  doc: string | null;
  readonly: boolean;
}

export type SerializedInteger = SerializedObjectBase & {
  value: number;
  type: "int";
};

export type SerializedFloat = SerializedObjectBase & {
  value: number;
  type: "float";
};

export type SerializedQuantity = SerializedObjectBase & {
  value: QuantityMap;
  type: "Quantity";
};

export type SerializedBool = SerializedObjectBase & {
  value: boolean;
  type: "bool";
};

export type SerializedString = SerializedObjectBase & {
  value: string;
  type: "str";
};

export type SerializedEnum = SerializedObjectBase & {
  name: string;
  value: string;
  type: "Enum" | "ColouredEnum";
  enum: Record<string, string>;
};

export type SerializedList = SerializedObjectBase & {
  value: SerializedObject[];
  type: "list";
};

export type SerializedDict = SerializedObjectBase & {
  value: Record<string, SerializedObject>;
  type: "dict";
};

export type SerializedNoneType = SerializedObjectBase & {
  value: null;
  type: "NoneType";
};

export type SerializedNoValue = SerializedObjectBase & {
  value: null;
  type: "None";
};

export type SerializedException = SerializedObjectBase & {
  name: string;
  value: string;
  type: "Exception";
};

type DataServiceTypes =
  | "DataService"
  | "Image"
  | "NumberSlider"
  | "DeviceConnection"
  | "Task";

export type SerializedDataService = SerializedObjectBase & {
  name: string;
  value: Record<string, SerializedObject>;
  type: DataServiceTypes;
};

export type SerializedObject =
  | SerializedBool
  | SerializedFloat
  | SerializedInteger
  | SerializedString
  | SerializedList
  | SerializedDict
  | SerializedNoneType
  | SerializedException
  | SerializedDataService
  | SerializedEnum
  | SerializedQuantity
  | SerializedNoValue;
