import {
  ScanInfoSelectionHistory,
  emptyScanInfoHistory,
} from "../../src/utils/ScanInfoSelectionHistory";
import { ScanParameterGenerationSpec } from "../../src/types/ScanParameterGenerationSpec";
import { ScanParameterInfo } from "../../src/types/ScanParameterInfo";

const gen = (
  start: number,
  stop: number,
  points = 2,
  pattern: ScanParameterGenerationSpec["pattern"] = "linear",
): ScanParameterGenerationSpec => ({ start, stop, points, pattern });

const defaultGen = gen(0, 1);
const mkMgr = (history = emptyScanInfoHistory) =>
  new ScanInfoSelectionHistory(() => defaultGen, history);

const param = (
  namespace: string,
  deviceNameOrDisplayGroup: string,
  id: string,
  generation: ScanParameterGenerationSpec,
): ScanParameterInfo => ({ namespace, deviceNameOrDisplayGroup, id, generation });

// Record a fully-specified parameter into history by replaying a "generation" update.
const record = (history: typeof emptyScanInfoHistory, p: ScanParameterInfo) =>
  mkMgr(history).handleParamUpdate(p, { generation: p.generation })
    .updatedScanInfoHistory;

describe("ScanInfoSelectionHistory.handleParamUpdate", () => {
  describe("generation provided", () => {
    it("merges the new generator and records it in history", () => {
      const current = param("E", "grp", "p1", gen(0, 1));
      const { updatedParam, updatedScanInfoHistory } = mkMgr().handleParamUpdate(
        current,
        { generation: gen(5, 10, 4) },
      );

      expect(updatedParam).toEqual(param("E", "grp", "p1", gen(5, 10, 4)));
      // history now recalls the new generator for p1
      expect(
        mkMgr(updatedScanInfoHistory).handleParamUpdate(current, { id: "p1" })
          .updatedParam.generation,
      ).toEqual(gen(5, 10, 4));
    });
  });

  describe("id provided", () => {
    it("recalls the stored generator for a known parameter id", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E", "grp", "p1", gen(2, 8)),
      );
      const current = param("E", "grp", "pX", gen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, { id: "p1" });
      expect(updatedParam).toEqual(param("E", "grp", "p1", gen(2, 8)));
    });

    it("falls back to the default generator for an unknown id", () => {
      const current = param("E", "grp", "pX", gen(0, 1));
      const { updatedParam } = mkMgr().handleParamUpdate(current, { id: "unknown" });
      expect(updatedParam).toEqual(param("E", "grp", "unknown", defaultGen));
    });
  });

  describe("namespace change", () => {
    it("cascades back the last display group, parameter and generator for that namespace", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E2", "grpB", "pB", gen(3, 9)),
      );
      const current = param("E1", "grpA", "pA", gen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, {
        namespace: "E2",
      });
      expect(updatedParam).toEqual(param("E2", "grpB", "pB", gen(3, 9)));
    });
  });

  describe("display group change", () => {
    it("recalls the last parameter and generator for that group", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E2", "grpB", "pB", gen(3, 9)),
      );
      const current = param("E2", "grpA", "pA", gen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, {
        deviceNameOrDisplayGroup: "grpB",
      });
      expect(updatedParam).toEqual(param("E2", "grpB", "pB", gen(3, 9)));
    });

    it("treats an explicit empty display group as a cleared selection (presence vs truthiness)", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E2", "grpB", "pB", gen(3, 9)),
      );
      const current = param("E2", "grpB", "pB", gen(3, 9));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, {
        deviceNameOrDisplayGroup: "",
      });
      // explicit "" is honoured (not recalled), so the leaf resolves to empty/default
      expect(updatedParam).toEqual(param("E2", "", "", defaultGen));
    });
  });

  describe("recall scenario", () => {
    it("restores a namespace's full selection after navigating away and back", () => {
      let history = emptyScanInfoHistory;
      history = record(history, param("E1", "grpA", "pA", gen(1, 2)));
      history = record(history, param("E2", "grpB", "pB", gen(3, 4)));

      // navigate to E1 from E2 ...
      const toE1 = mkMgr(history).handleParamUpdate(
        param("E2", "grpB", "pB", gen(3, 4)),
        { namespace: "E1" },
      );
      expect(toE1.updatedParam).toEqual(param("E1", "grpA", "pA", gen(1, 2)));

      // ... then back to E2, still recalling its last selection
      const backToE2 = mkMgr(toE1.updatedScanInfoHistory).handleParamUpdate(
        toE1.updatedParam,
        { namespace: "E2" },
      );
      expect(backToE2.updatedParam).toEqual(param("E2", "grpB", "pB", gen(3, 4)));
    });
  });

  describe("Devices namespace", () => {
    it("keeps generators separate for same-named params on different devices", () => {
      let history = emptyScanInfoHistory;
      history = record(history, param("Devices", "LaserA", "frequency", gen(1, 2)));
      history = record(history, param("Devices", "LaserB", "frequency", gen(3, 4)));

      // switch back to LaserA — must recall LaserA's generator, not LaserB's
      const { updatedParam } = mkMgr(history).handleParamUpdate(
        param("Devices", "LaserB", "frequency", gen(3, 4)),
        { deviceNameOrDisplayGroup: "LaserA" },
      );
      expect(updatedParam).toEqual(param("Devices", "LaserA", "frequency", gen(1, 2)));
    });

    it("recalls a stored generator by bare id for a device parameter", () => {
      const history = record(
        emptyScanInfoHistory,
        param("Devices", "LaserA", "frequency", gen(5, 6)),
      );
      const { updatedParam } = mkMgr(history).handleParamUpdate(
        param("Devices", "LaserA", "other", gen(0, 1)),
        { id: "frequency" },
      );
      expect(updatedParam).toEqual(param("Devices", "LaserA", "frequency", gen(5, 6)));
    });
  });

  it("does not mutate the input parameter", () => {
    const current = param("E", "grp", "p1", gen(0, 1));
    const snapshot = JSON.parse(JSON.stringify(current));
    mkMgr().handleParamUpdate(current, { namespace: "E2" });
    expect(current).toEqual(snapshot);
  });
});
