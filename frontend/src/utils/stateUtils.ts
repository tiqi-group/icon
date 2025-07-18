import { SerializedObject } from "../types/SerializedObject";

export interface State {
  type: string;
  name: string;
  value: Record<string, SerializedObject> | null;
  readonly: boolean;
  doc: string | null;
}

/**
 * Splits a full access path into its atomic parts, separating attribute names, numeric
 * indices (including floating points), and string keys within indices.
 *
 * @param path The full access path string to be split into components.
 * @returns An array of components that make up the path, including attribute names,
 *          numeric indices, and string keys as separate elements.
 */
export function parseFullAccessPath(path: string): string[] {
  // The pattern matches:
  // \w+ - Words
  // \[\d+\.\d+\] - Floating point numbers inside brackets
  // \[\d+\] - Integers inside brackets
  // \["[^"]*"\] - Double-quoted strings inside brackets
  // \['[^']*'\] - Single-quoted strings inside brackets
  const pattern = /\w+|\[\d+\.\d+\]|\[\d+\]|\["[^"]*"\]|\['[^']*'\]/g;
  const matches = path.match(pattern);

  return matches ?? []; // Return an empty array if no matches found
}

/**
 * Parse a serialized key and convert it to an appropriate type (number or string).
 *
 * @param serializedKey The serialized key, which might be enclosed in brackets and quotes.
 * @returns The processed key as a number or an unquoted string.
 *
 * Examples:
 * console.log(parseSerializedKey("attr_name"));  // Outputs: attr_name  (string)
 * console.log(parseSerializedKey("[123]"));      // Outputs: 123  (number)
 * console.log(parseSerializedKey("[12.3]"));     // Outputs: 12.3  (number)
 * console.log(parseSerializedKey("['hello']"));  // Outputs: hello  (string)
 * console.log(parseSerializedKey('["12.34"]'));  // Outputs: "12.34"  (string)
 * console.log(parseSerializedKey('["complex"]'));// Outputs: "complex"  (string)
 */
function parseSerializedKey(serializedKey: string): string | number {
  // Strip outer brackets if present
  if (serializedKey.startsWith("[") && serializedKey.endsWith("]")) {
    serializedKey = serializedKey.slice(1, -1);
  }

  // Strip quotes if the resulting string is quoted
  if (
    (serializedKey.startsWith("'") && serializedKey.endsWith("'")) ||
    (serializedKey.startsWith('"') && serializedKey.endsWith('"'))
  ) {
    return serializedKey.slice(1, -1);
  }

  // Try converting to a number if the string is not quoted
  const parsedNumber = parseFloat(serializedKey);
  if (!isNaN(parsedNumber)) {
    return parsedNumber;
  }

  // Return the original string if it's not a valid number
  return serializedKey;
}

function getOrCreateItemInContainer(
  container: Record<string | number, SerializedObject> | SerializedObject[],
  key: string | number,
  allowAddKey: boolean,
): SerializedObject {
  // Check if the key exists and return the item if it does
  if (key in container) {
    /* @ts-expect-error Key is in the correct form but converted to type any for some reason */
    return container[key];
  }

  // Handling the case where the key does not exist
  if (Array.isArray(container)) {
    // Handling arrays
    if (allowAddKey && key === container.length) {
      container.push(createEmptySerializedObject());
      return container[key];
    }
    throw new Error(`Index out of bounds: ${key}`);
  } else {
    // Handling objects
    if (allowAddKey) {
      container[key] = createEmptySerializedObject();
      return container[key];
    }
    throw new Error(`Key not found: ${key}`);
  }
}

/**
 * Retrieve an item from a container specified by the passed key. Add an item to the
 * container if allowAppend is set to True.
 *
 * @param container Either a dictionary or list of serialized objects.
 * @param key The key name or index (as a string) representing the attribute in the container.
 * @param allowAppend Whether to allow appending a new entry if the specified index is out of range by exactly one position.
 * @returns The serialized object corresponding to the specified key.
 * @throws SerializationPathError If the key is invalid or leads to an access error without append permissions.
 * @throws SerializationValueError If the expected structure is incorrect.
 */
function getContainerItemByKey(
  container: Record<string, SerializedObject> | SerializedObject[],
  key: string,
  allowAppend = false,
): SerializedObject {
  const processedKey = parseSerializedKey(key);

  try {
    return getOrCreateItemInContainer(container, processedKey, allowAppend);
  } catch (error) {
    if (error instanceof RangeError) {
      throw new Error(`Index '${processedKey}': ${error.message}`);
    } else if (error instanceof Error) {
      throw new Error(`Key '${processedKey}': ${error.message}`);
    }
    throw error; // Re-throw if it's not a known error type
  }
}

export function setNestedValueByPath(
  serializationDict: Record<string, SerializedObject>,
  path: string,
  serializedValue: SerializedObject,
): Record<string, SerializedObject> {
  const pathParts = parseFullAccessPath(path);
  const newSerializationDict: Record<string, SerializedObject> = JSON.parse(
    JSON.stringify(serializationDict),
  );

  let currentDict = newSerializationDict;

  try {
    for (let i = 0; i < pathParts.length - 1; i++) {
      const pathPart = pathParts[i];
      const nextLevelSerializedObject = getContainerItemByKey(
        currentDict,
        pathPart,
        false,
      );
      currentDict = nextLevelSerializedObject["value"] as Record<
        string,
        SerializedObject
      >;
    }

    const finalPart = pathParts[pathParts.length - 1];
    const finalObject = getContainerItemByKey(currentDict, finalPart, true);

    Object.assign(finalObject, serializedValue);

    return newSerializationDict;
  } catch (error) {
    console.error(`Error occurred trying to change ${path}: ${error}`);
  }
  return {};
}

function createEmptySerializedObject(): SerializedObject {
  return {
    full_access_path: "",
    value: null,
    type: "None",
    doc: null,
    readonly: false,
  };
}

export function getNestedDictByPath(
  serializationDict: Record<string, SerializedObject>,
  path: string,
): SerializedObject {
  const pathParts = parseFullAccessPath(path);
  let currentDict: Record<string, SerializedObject> = serializationDict;

  for (let i = 0; i < pathParts.length - 1; i++) {
    const pathPart = pathParts[i];
    const nextLevelSerializedObject = getContainerItemByKey(
      currentDict,
      pathPart,
      false,
    );

    if (
      typeof nextLevelSerializedObject.value !== "object" ||
      nextLevelSerializedObject.value === null
    ) {
      throw new Error(`Invalid structure at path part: ${pathPart}`);
    }

    currentDict = nextLevelSerializedObject.value as Record<string, SerializedObject>;
  }

  return getContainerItemByKey(currentDict, pathParts[pathParts.length - 1], false);
}
