import {
  MruSelectionTree,
  emptySelectionHistory,
} from "../../src/utils/MruSelectionTree";

const defaultLeaf = () => "DEFAULT";

const makeManager = (depth: number) =>
  new MruSelectionTree<string>(depth, defaultLeaf, emptySelectionHistory());

describe("MruSelectionTree", () => {
  describe("resolve", () => {
    it("returns empty keys and the default leaf for an empty manager", () => {
      const { path, leafKey, leaf } = makeManager(2).resolve([undefined, undefined]);
      expect(path).toEqual(["", ""]);
      expect(leafKey).toBe("");
      expect(leaf).toBe("DEFAULT");
    });

    it("recalls the deeper levels and leaf from history when given a prefix", () => {
      const mgr = makeManager(2).update(["ns", "dg"], "pid", "LEAF");
      const { path, leafKey, leaf } = mgr.resolve(["ns", undefined]);
      expect(path).toEqual(["ns", "dg"]);
      expect(leafKey).toBe("pid");
      expect(leaf).toBe("LEAF");
    });

    it("cascades all the way down when nothing is provided", () => {
      const mgr = makeManager(2).update(["ns", "dg"], "pid", "LEAF");
      const { path, leafKey, leaf } = mgr.resolve([undefined, undefined]);
      expect(path).toEqual(["ns", "dg"]);
      expect(leafKey).toBe("pid");
      expect(leaf).toBe("LEAF");
    });

    it("uses provided keys over history and falls back to default for unseen paths", () => {
      const mgr = makeManager(2).update(["ns", "dg"], "pid", "LEAF");
      const { path, leafKey, leaf } = mgr.resolve(["other", undefined]);
      expect(path).toEqual(["other", ""]);
      expect(leafKey).toBe("");
      expect(leaf).toBe("DEFAULT");
    });

    it("remembers a distinct last child per path", () => {
      const mgr = makeManager(2)
        .update(["nsA", "dg1"], "p1", "A1")
        .update(["nsB", "dg2"], "p2", "B2");
      expect(mgr.resolve(["nsA", undefined]).leaf).toBe("A1");
      expect(mgr.resolve(["nsB", undefined]).leaf).toBe("B2");
    });
  });

  describe("lookupLeaf", () => {
    it("returns a stored leaf and undefined for a miss", () => {
      const mgr = makeManager(2).update(["ns", "dg"], "pid", "LEAF");
      expect(mgr.lookupLeaf("pid")).toBe("LEAF");
      expect(mgr.lookupLeaf("missing")).toBeUndefined();
    });
  });

  describe("update", () => {
    it("returns a new instance and leaves the original unchanged (immutability)", () => {
      const original = makeManager(2);
      const updated = original.update(["ns", "dg"], "pid", "LEAF");
      expect(updated).not.toBe(original);
      expect(original.lookupLeaf("pid")).toBeUndefined();
      expect(original.serialize()).toEqual(emptySelectionHistory());
    });

    it("overwrites the leaf and the last-key when the same path is updated again", () => {
      const mgr = makeManager(2)
        .update(["ns", "dg"], "p1", "V1")
        .update(["ns", "dg"], "p2", "V2");
      const { leafKey, leaf } = mgr.resolve(["ns", "dg"]);
      expect(leafKey).toBe("p2");
      expect(leaf).toBe("V2");
      // earlier leaf value is still retrievable by its key
      expect(mgr.lookupLeaf("p1")).toBe("V1");
    });
  });

  describe("serialize", () => {
    it("round-trips: a manager constructed from serialized data resolves identically", () => {
      const mgr = makeManager(2)
        .update(["nsA", "dg1"], "p1", "A1")
        .update(["nsB", "dg2"], "p2", "B2");
      const data = mgr.serialize();
      const restored = new MruSelectionTree<string>(2, defaultLeaf, data);
      expect(restored.serialize()).toEqual(data);
      expect(restored.resolve(["nsA", undefined]).leaf).toBe("A1");
    });
  });

  describe("genericity (arbitrary depth and leaf type)", () => {
    it("works at depth 1", () => {
      const mgr = new MruSelectionTree<number>(
        1,
        () => -1,
        emptySelectionHistory(),
      ).update(["only"], "k", 42);
      const { path, leafKey, leaf } = mgr.resolve([undefined]);
      expect(path).toEqual(["only"]);
      expect(leafKey).toBe("k");
      expect(leaf).toBe(42);
    });

    it("works at depth 3 with an object leaf", () => {
      interface Leaf {
        v: number;
      }
      const mgr = new MruSelectionTree<Leaf>(
        3,
        () => ({ v: 0 }),
        emptySelectionHistory(),
      ).update(["a", "b", "c"], "leafKey", { v: 7 });
      const { path, leaf } = mgr.resolve(["a", undefined, undefined]);
      expect(path).toEqual(["a", "b", "c"]);
      expect(leaf).toEqual({ v: 7 });
    });
  });
});
