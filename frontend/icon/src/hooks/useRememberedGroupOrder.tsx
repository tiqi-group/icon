import { useEffect, useMemo } from "react";
import { mergeGroupOrder, parseGroupOrder } from "../utils/groupOrder";

/**
 * Shows groups in the order they were shown before, with new groups on top, so that
 * adding a group to the experiment library doesn't reshuffle the others. The library
 * gives the groups in no stable order.
 *
 * @param storageKey The localStorage key to remember the order under
 * @param groups The group names in the order they come in
 * @returns The group names in the order to show them in
 */
export function useRememberedGroupOrder(storageKey: string, groups: string[]) {
  const groupsKey = JSON.stringify(groups);
  const { shown, remembered } = useMemo(
    () => mergeGroupOrder(parseGroupOrder(localStorage.getItem(storageKey)), groups),
    [storageKey, groupsKey],
  );

  useEffect(() => {
    // Groups not loaded yet: keep what is remembered
    if (groups.length === 0) return;
    localStorage.setItem(storageKey, JSON.stringify(remembered));
  }, [storageKey, groupsKey]);

  return shown;
}
