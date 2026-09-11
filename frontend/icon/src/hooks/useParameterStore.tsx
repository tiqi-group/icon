import { useEffect, useRef } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { createParameterStore } from "../stores/parmeterStore";
import { ParameterValueType } from "../types/ExperimentMetadata";

interface ParameterUpdate {
  id: string;
  value: ParameterValueType;
}

/**
 * React hook that synchronizes the local parameter store with the backend.
 *
 * This hook:
 * - Initializes a new parameter store (stable across renders).
 * - Fetches the full parameter set from the backend (`parameters.get_all_parameters`)
 *   and seeds the store with it.
 * - Subscribes to `parameter.update` events over the socket to update individual values.
 * - Cleans up its socket listener when the component unmounts.
 *
 * @returns A stable reference to the parameter store instance.
 */
export function useParameterStore() {
  const parameterStore = useRef(createParameterStore()).current;

  useEffect(() => {
    const handleUpdate = ({ id, value }: ParameterUpdate) => {
      parameterStore.set(id, value);
    };

    socket.on("parameter.update", handleUpdate);

    runMethod("parameters.get_all_parameters", [], {}, (ack) => {
      try {
        const parameterMapping = deserialize(ack as SerializedObject) as Record<
          string,
          ParameterValueType
        >;
        if (parameterMapping && typeof parameterMapping === "object") {
          parameterStore.bulkSet(parameterMapping);
        }
      } catch (err) {
        console.error("Failed to initialize parameter store:", err);
      }
    });

    return () => {
      socket.off("parameter.update", handleUpdate);
    };
  }, [parameterStore]);

  return parameterStore;
}
