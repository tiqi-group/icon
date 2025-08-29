import { useCallback, useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { ParameterMetadata } from "../types/ExperimentMetadata";

export type GroupsByNamespace = Record<string, Record<string, ParameterMetadata>>;
export type NamespaceToGroups = Record<string, string[]>;

/**
 * Create a mapping from namespaces to their associated display groups.
 *
 * The input `parameterMetadata` is expected to be keyed by strings of the form:
 *   "<namespace> (<displayGroupName>)"
 *
 * Example input:
 *  ```json
 *  {
 *    "ExpA (Cooling)": { ...parameter metadata... },
 *    "ExpA (Heating)": { ...parameter metadata... },
 *    "ExpB (Cooling)": { ...parameter metadata... }
 *  }
 *  ```
 *
 * Output:
 *  ```json
 *  {
 *    "ExpA": ["Cooling", "Heating"]
 *    "ExpB": ["Cooling"],
 *  }
 *  ```
 */
const createNamespaceGroups = (
  parameterMetadata: Record<string, Record<string, ParameterMetadata>>,
) => {
  const namespaceGroups: Record<string, string[]> = {};

  // Group display groups by namespace
  Object.keys(parameterMetadata).forEach((key) => {
    const [namespace, groupName] = key.split(" (");
    const cleanGroupName = groupName.replace(")", "");

    if (!namespaceGroups[namespace]) {
      namespaceGroups[namespace] = [];
    }

    namespaceGroups[namespace].push(cleanGroupName);
  });

  // Sort display groups for each namespace
  Object.keys(namespaceGroups).forEach((namespace) => {
    namespaceGroups[namespace].sort();
  });

  // Sort namespaces alphabetically and return a sorted object
  return Object.fromEntries(
    Object.entries(namespaceGroups).sort(([a], [b]) => a.localeCompare(b)),
  );
};

/**
 * React hook that provides access to parameter display group metadata.
 *
 * This hook:
 * - Fetches the full set of parameter display groups from the backend
 *   using `parameters.get_display_groups`.
 * - Subscribes to `parameters.update` socket events to refresh groups
 *   when the backend notifies of changes.
 * - Cleans up the socket listener automatically on unmount.
 * - Computes a derived mapping from namespaces → display groups using
 *   `createNamespaceGroups`.
 *
 * @returns An object containing:
 *   - `parameterDisplayGroups`: the raw mapping of
 *       { namespace+group → parameter metadata }
 *   - `parameterNamespaceToDisplayGroups`: a derived mapping
 *       { namespace → [display group names] }
 */
export function useParameterDisplayGroups(): {
  parameterDisplayGroups: GroupsByNamespace;
  parameterNamespaceToDisplayGroups: NamespaceToGroups;
} {
  const [groups, setGroups] = useState<GroupsByNamespace>({});

  const fetchGroups = useCallback(() => {
    runMethod("parameters.get_display_groups", [], {}, (ack) => {
      const data = deserialize(ack as SerializedObject) as GroupsByNamespace;
      setGroups(data);
    });
  }, []);

  useEffect(() => {
    fetchGroups();
    socket.on("parameters.update", fetchGroups);

    return () => {
      socket.off("parameters.update", fetchGroups);
    };
  }, []);

  const namespaceToGroups = createNamespaceGroups(groups);

  return {
    parameterDisplayGroups: groups,
    parameterNamespaceToDisplayGroups: namespaceToGroups,
  };
}
