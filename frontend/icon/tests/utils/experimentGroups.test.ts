import {
  DEFAULT_GROUP,
  DEFAULT_GROUP_LABEL,
  MAX_GROUP_NAME_LENGTH,
  ExperimentGroupsState,
  assignToGroup,
  emptyExperimentGroupsState,
  groupExperiments,
  parseExperimentGroupsState,
  removeGroup,
  renameGroup,
  toggleCollapsed,
  validateGroupName,
} from "../../src/utils/experimentGroups";

const id = (name: string) => `lib.experiments.Exp (${name})`;

describe("experimentGroups: groupExperiments", () => {
  it("returns only the default group when nothing is assigned", () => {
    expect(groupExperiments([id("b"), id("a")], {})).toEqual([
      { name: DEFAULT_GROUP, experimentIds: [id("a"), id("b")] },
    ]);
  });

  it("sorts groups in ascending order with the default group last", () => {
    const groups = groupExperiments([id("a"), id("b"), id("c"), id("d")], {
      [id("a")]: "Group 10",
      [id("b")]: "Group 2",
      [id("c")]: "Cooling",
    });
    expect(groups.map((group) => group.name)).toEqual([
      "Cooling",
      "Group 2",
      "Group 10",
      DEFAULT_GROUP,
    ]);
  });

  it("omits the default group when every experiment is assigned", () => {
    expect(groupExperiments([id("a")], { [id("a")]: "Cooling" })).toEqual([
      { name: "Cooling", experimentIds: [id("a")] },
    ]);
  });

  it("ignores assignments of experiments that no longer exist", () => {
    expect(groupExperiments([id("a")], { [id("gone")]: "Cooling" })).toEqual([
      { name: DEFAULT_GROUP, experimentIds: [id("a")] },
    ]);
  });
});

describe("experimentGroups: validateGroupName", () => {
  it("accepts a new name", () => {
    expect(validateGroupName(" Cooling ", ["Detection"])).toBeNull();
  });

  it("rejects empty and whitespace-only names", () => {
    expect(validateGroupName("", [])).not.toBeNull();
    expect(validateGroupName("   ", [])).not.toBeNull();
  });

  it("applies the maximum length to the trimmed name", () => {
    const longest = "x".repeat(MAX_GROUP_NAME_LENGTH);
    expect(validateGroupName(` ${longest} `, [])).toBeNull();
    expect(validateGroupName(`${longest}x`, [])).not.toBeNull();
  });

  it("rejects existing names and the default group label regardless of case", () => {
    expect(validateGroupName(" Cooling ", ["Cooling"])).not.toBeNull();
    expect(validateGroupName("cooling", ["Cooling"])).not.toBeNull();
    expect(validateGroupName(DEFAULT_GROUP_LABEL.toUpperCase(), [])).not.toBeNull();
  });
});

describe("experimentGroups: state updates", () => {
  const state: ExperimentGroupsState = {
    assignments: { [id("a")]: "Cooling", [id("b")]: "Cooling", [id("c")]: "Detection" },
    collapsed: ["Cooling", "Detection", DEFAULT_GROUP],
  };

  it("assigns several experiments at once and expands the target group", () => {
    expect(assignToGroup(state, [id("c"), id("d")], "Cooling")).toEqual({
      assignments: {
        [id("a")]: "Cooling",
        [id("b")]: "Cooling",
        [id("c")]: "Cooling",
        [id("d")]: "Cooling",
      },
      collapsed: [DEFAULT_GROUP],
    });
  });

  it("removes experiments from their group by assigning the default group", () => {
    expect(assignToGroup(state, [id("c")], DEFAULT_GROUP)).toEqual({
      assignments: { [id("a")]: "Cooling", [id("b")]: "Cooling" },
      collapsed: ["Cooling"],
    });
  });

  it("renames a group and keeps its collapsed state", () => {
    expect(renameGroup(state, "Cooling", "Doppler")).toEqual({
      assignments: {
        [id("a")]: "Doppler",
        [id("b")]: "Doppler",
        [id("c")]: "Detection",
      },
      collapsed: ["Doppler", "Detection", DEFAULT_GROUP],
    });
  });

  it("changes the case of a group name", () => {
    expect(renameGroup(state, "Cooling", "cooling")).toEqual({
      assignments: {
        [id("a")]: "cooling",
        [id("b")]: "cooling",
        [id("c")]: "Detection",
      },
      collapsed: ["cooling", "Detection", DEFAULT_GROUP],
    });
  });

  it("adopts the new case for a hidden group that differs only by case", () => {
    const hidden: ExperimentGroupsState = {
      assignments: { [id("gone")]: "cooling", [id("c")]: "Detection" },
      collapsed: ["cooling"],
    };
    expect(assignToGroup(hidden, [id("a")], "Cooling")).toEqual({
      assignments: {
        [id("gone")]: "Cooling",
        [id("c")]: "Detection",
        [id("a")]: "Cooling",
      },
      collapsed: [],
    });
    expect(renameGroup(hidden, "Detection", "Cooling")).toEqual({
      assignments: { [id("gone")]: "Cooling", [id("c")]: "Cooling" },
      collapsed: [],
    });
  });

  it("removes a group", () => {
    expect(removeGroup(state, "Cooling")).toEqual({
      assignments: { [id("c")]: "Detection" },
      collapsed: ["Detection", DEFAULT_GROUP],
    });
  });

  it("toggles the collapsed state", () => {
    const expanded = toggleCollapsed(state, "Cooling");
    expect(expanded.collapsed).toEqual(["Detection", DEFAULT_GROUP]);
    expect(toggleCollapsed(expanded, "Cooling").collapsed).toContain("Cooling");
  });

  it("does not mutate the given state", () => {
    const snapshot = JSON.parse(JSON.stringify(state));
    assignToGroup(state, [id("a")], "Detection");
    renameGroup(state, "Cooling", "Doppler");
    removeGroup(state, "Cooling");
    toggleCollapsed(state, "Cooling");
    expect(state).toEqual(snapshot);
  });
});

describe("experimentGroups: parseExperimentGroupsState", () => {
  it("round-trips a stored state", () => {
    const state = { assignments: { [id("a")]: "Cooling" }, collapsed: ["Cooling"] };
    expect(parseExperimentGroupsState(JSON.stringify(state))).toEqual(state);
  });

  it("falls back to the empty state for missing or malformed data", () => {
    expect(parseExperimentGroupsState(null)).toEqual(emptyExperimentGroupsState);
    expect(parseExperimentGroupsState("not json")).toEqual(emptyExperimentGroupsState);
    expect(parseExperimentGroupsState('{"assignments":[]}')).toEqual(
      emptyExperimentGroupsState,
    );
  });
});
