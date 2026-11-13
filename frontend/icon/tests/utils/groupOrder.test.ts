import { mergeGroupOrder, parseGroupOrder } from "../../src/utils/groupOrder";

describe("mergeGroupOrder", () => {
  it("keeps the incoming order when nothing is remembered", () => {
    expect(mergeGroupOrder([], ["B", "A", "C"]).shown).toEqual(["B", "A", "C"]);
  });

  it("keeps the remembered order when the groups come in reshuffled", () => {
    expect(mergeGroupOrder(["A", "B", "C"], ["C", "A", "B"]).shown).toEqual([
      "A",
      "B",
      "C",
    ]);
  });

  it("puts a new group on top without moving the others", () => {
    const { shown, remembered } = mergeGroupOrder(
      ["A", "B", "C"],
      ["C", "New", "B", "A"],
    );
    expect(shown).toEqual(["New", "A", "B", "C"]);
    expect(remembered).toEqual(["New", "A", "B", "C"]);
  });

  it("hides a removed group but remembers its place", () => {
    const first = mergeGroupOrder(["A", "B", "C"], ["A", "C"]);
    expect(first.shown).toEqual(["A", "C"]);
    expect(mergeGroupOrder(first.remembered, ["C", "B", "A"]).shown).toEqual([
      "A",
      "B",
      "C",
    ]);
  });
});

describe("parseGroupOrder", () => {
  it("returns an empty order for missing or invalid storage", () => {
    expect(parseGroupOrder(null)).toEqual([]);
    expect(parseGroupOrder("not json")).toEqual([]);
    expect(parseGroupOrder('{"a": 1}')).toEqual([]);
  });

  it("drops entries that aren't names", () => {
    expect(parseGroupOrder('["A", 1, "B"]')).toEqual(["A", "B"]);
  });
});
