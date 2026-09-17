import { getExperimentNameFromExperimentId } from "./experimentUtils";

/** Key of the default group. Never a valid user-provided group name. */
export const DEFAULT_GROUP = "";
export const DEFAULT_GROUP_LABEL = "Ungrouped";
export const MAX_GROUP_NAME_LENGTH = 32;

export interface ExperimentGroupsState {
  /** Experiment ID -> group name. Unassigned experiments are in the default group. */
  assignments: Record<string, string>;
  /** Names of the collapsed groups. */
  collapsed: string[];
}

export interface ExperimentGroup {
  name: string;
  experimentIds: string[];
}

export const emptyExperimentGroupsState: ExperimentGroupsState = {
  assignments: {},
  collapsed: [],
};

export function parseExperimentGroupsState(raw: string | null): ExperimentGroupsState {
  if (raw === null) return emptyExperimentGroupsState;
  try {
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.assignments === "object" &&
      parsed.assignments !== null &&
      Array.isArray(parsed.collapsed)
    ) {
      return { assignments: parsed.assignments, collapsed: parsed.collapsed };
    }
  } catch {
    // fall through
  }
  return emptyExperimentGroupsState;
}

/**
 * Groups the given experiments. Named groups are sorted in ascending order, the
 * default group comes last. Groups without any of the given experiments are omitted,
 * so assignments of experiments that no longer exist are ignored.
 */
export function groupExperiments(
  experimentIds: string[],
  assignments: Record<string, string>,
): ExperimentGroup[] {
  const byGroup = new Map<string, string[]>();
  for (const id of experimentIds) {
    const group = assignments[id] ?? DEFAULT_GROUP;
    byGroup.set(group, [...(byGroup.get(group) ?? []), id]);
  }

  return [...byGroup.entries()]
    .map(([name, ids]) => ({
      name,
      experimentIds: ids.sort((a, b) =>
        getExperimentNameFromExperimentId(a).localeCompare(
          getExperimentNameFromExperimentId(b),
        ),
      ),
    }))
    .sort((a, b) => {
      if (a.name === DEFAULT_GROUP) return 1;
      if (b.name === DEFAULT_GROUP) return -1;
      return a.name.localeCompare(b.name, undefined, { numeric: true });
    });
}

/** Group names keep their case but are unique regardless of it. */
const sameGroupName = (a: string, b: string): boolean =>
  a.toLowerCase() === b.toLowerCase();

/**
 * Returns an error message, or null if the name is valid. When renaming a group,
 * leave its current name out of existingNames so that its case can be changed.
 */
export function validateGroupName(
  name: string,
  existingNames: string[],
): string | null {
  const trimmed = name.trim();
  if (trimmed === "") return "Name must not be empty";
  if (trimmed.length > MAX_GROUP_NAME_LENGTH)
    return `Name must be at most ${MAX_GROUP_NAME_LENGTH} characters`;
  if (
    [DEFAULT_GROUP_LABEL, ...existingNames].some((existing) =>
      sameGroupName(existing, trimmed),
    )
  )
    return "Group already exists";
  return null;
}

const mapGroupNames = (
  assignments: Record<string, string>,
  fn: (group: string) => string,
): Record<string, string> =>
  Object.fromEntries(Object.entries(assignments).map(([id, group]) => [id, fn(group)]));

const dropEmptyGroups = (
  assignments: Record<string, string>,
  collapsed: string[],
): string[] => {
  const names = new Set(Object.values(assignments));
  return collapsed.filter((name) => name === DEFAULT_GROUP || names.has(name));
};

/** Moves the experiments to the group and expands it. */
export function assignToGroup(
  state: ExperimentGroupsState,
  experimentIds: string[],
  group: string,
): ExperimentGroupsState {
  // A group that is hidden because its experiments no longer exist may differ in case
  const assignments = mapGroupNames(state.assignments, (name) =>
    sameGroupName(name, group) ? group : name,
  );
  for (const id of experimentIds) {
    if (group === DEFAULT_GROUP) delete assignments[id];
    else assignments[id] = group;
  }
  return {
    assignments,
    collapsed: dropEmptyGroups(
      assignments,
      state.collapsed.filter((name) => !sameGroupName(name, group)),
    ),
  };
}

export function renameGroup(
  state: ExperimentGroupsState,
  oldName: string,
  newName: string,
): ExperimentGroupsState {
  return {
    assignments: mapGroupNames(state.assignments, (name) =>
      name === oldName || sameGroupName(name, newName) ? newName : name,
    ),
    collapsed: state.collapsed
      .filter((name) => name === oldName || !sameGroupName(name, newName))
      .map((name) => (name === oldName ? newName : name)),
  };
}

/** Removes the group. Its experiments fall back to the default group. */
export function removeGroup(
  state: ExperimentGroupsState,
  group: string,
): ExperimentGroupsState {
  return {
    assignments: Object.fromEntries(
      Object.entries(state.assignments).filter(([, name]) => name !== group),
    ),
    collapsed: state.collapsed.filter((name) => name !== group),
  };
}

export function toggleCollapsed(
  state: ExperimentGroupsState,
  group: string,
): ExperimentGroupsState {
  return {
    ...state,
    collapsed: state.collapsed.includes(group)
      ? state.collapsed.filter((name) => name !== group)
      : [...state.collapsed, group],
  };
}
