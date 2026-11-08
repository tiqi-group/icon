import {
  availableFavorites,
  parseExperimentFavorites,
  toggleExperimentFavorites,
} from "../../src/utils/experimentFavorites";

test("stored preferences tolerate invalid data and duplicate IDs", () => {
  expect(parseExperimentFavorites(null)).toEqual([]);
  expect(parseExperimentFavorites("broken")).toEqual([]);
  expect(parseExperimentFavorites('{"other":1}')).toEqual([]);
  expect(parseExperimentFavorites('["a",2,"",null,"a","b"]')).toEqual(["a", "b"]);
});
test("multi-selection pins missing favorites or unpins an entirely pinned selection", () => {
  expect(toggleExperimentFavorites(["a", "absent"], ["a", "b"])).toEqual([
    "a",
    "absent",
    "b",
  ]);
  expect(toggleExperimentFavorites(["a", "absent", "b"], ["a", "b"])).toEqual([
    "absent",
  ]);
  expect(toggleExperimentFavorites(["a"], [])).toEqual(["a"]);
});
test("only available experiments appear, in stable alphabetical order", () => {
  const stored = ["pkg.Z", "pkg.A", "missing"];
  expect(availableFavorites(["pkg.Z", "pkg.B", "pkg.A"], stored)).toEqual([
    "pkg.A",
    "pkg.Z",
  ]);
  expect(stored).toEqual(["pkg.Z", "pkg.A", "missing"]);
});
