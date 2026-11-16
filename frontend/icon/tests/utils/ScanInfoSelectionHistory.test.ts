import {
  ScanInfoSelectionHistory,
  emptyScanInfoHistory,
} from "../../src/utils/ScanInfoSelectionHistory";
import { ScanParameterGenerationSpec } from "../../src/types/ScanParameterGenerationSpec";
import { ScanParameterInfo, ScanPattern } from "../../src/types/ScanParameterInfo";

const gen = (
  start: number,
  stop: number,
  points = 2,
  pattern: ScanPattern = "linear",
): ScanParameterGenerationSpec => ({ start, stop, points, pattern });

const spanGen = (
  start: number,
  stop: number,
  points = 2,
  pattern: ScanPattern = "linear",
): ScanParameterGenerationSpec => ({
  ...gen(start, stop, points, pattern),
  inputMode: "spanCenter",
});

/** Input mode as shown, an unset one being Start/Stop */
const modeOf = (p: ScanParameterInfo) => p.generation.inputMode ?? "startStop";

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
      const history = record(emptyScanInfoHistory, param("E", "grp", "p1", gen(2, 8)));
      const current = param("E", "grp", "pX", gen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, { id: "p1" });
      expect(updatedParam).toEqual(param("E", "grp", "p1", gen(2, 8)));
    });

    it("falls back to the default generator for an unknown id", () => {
      const current = param("E", "grp", "pX", gen(0, 1));
      const { updatedParam } = mkMgr().handleParamUpdate(current, { id: "unknown" });
      expect(updatedParam).toEqual(param("E", "grp", "unknown", defaultGen));
    });

    it("recentring on a live value keeps the recalled parameter's own points/pattern/span", () => {
      // A was scanned with span 10, 5 points, linear; B was scanned 0-1, 100 points, scatter.
      let history = record(
        emptyScanInfoHistory,
        param("E", "grp", "A", spanGen(10, 20, 5, "linear")),
      );
      history = record(history, param("E", "grp", "B", gen(0, 1, 100, "scatter")));
      const current = param("E", "grp", "B", gen(0, 1, 100, "scatter"));

      // Switch back to A while re-centring on A's live value (15.5).
      const { updatedParam } = mkMgr(history).handleParamUpdate(
        current,
        { id: "A" },
        15.5,
      );

      // Span (10) and A's own points/pattern are preserved; only start/stop shift.
      expect(updatedParam).toEqual(
        param("E", "grp", "A", spanGen(10.5, 20.5, 5, "linear")),
      );
    });

    it("does not recentre a parameter that comes back in Start/Stop mode", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E", "grp", "A", gen(10, 20, 5)),
      );
      const current = param("E", "grp", "B", spanGen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(
        current,
        { id: "A" },
        30,
      );
      expect(updatedParam).toEqual(param("E", "grp", "A", gen(10, 20, 5)));
    });

    it("keeps the current input mode for a parameter not scanned before", () => {
      // A has never been recorded, so it has no memorized inputMode.
      const history = record(emptyScanInfoHistory, param("E", "grp", "B", gen(0, 1)));
      const current: ScanParameterInfo = {
        ...param("E", "grp", "B", gen(0, 1)),
        generation: { ...gen(0, 1), inputMode: "spanCenter" },
      };

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, { id: "A" });
      expect(updatedParam.generation.inputMode).toBe("spanCenter");
    });

    it("restores the mode a parameter was last scanned in, with that mode's settings", () => {
      // A was last scanned in Center/Span mode (30-40/3/scatter); its own Start/Stop
      // settings (10-20/5/linear) are stashed in otherModeSpec — exactly what
      // ParameterCard leaves behind after a mode toggle.
      const history = record(
        emptyScanInfoHistory,
        param("E", "grp", "A", {
          start: 30,
          stop: 40,
          points: 3,
          pattern: "scatter",
          inputMode: "spanCenter",
          otherModeSpec: { start: 10, stop: 20, points: 5, pattern: "linear" },
        }),
      );
      const current: ScanParameterInfo = {
        ...param("E", "grp", "B", gen(0, 1)),
        generation: { ...gen(0, 1), inputMode: "startStop" },
      };

      // Switching to A while the card is in Start/Stop mode brings A back in
      // Center/Span mode with its Center/Span numbers (30-40/3/scatter).
      const { updatedParam } = mkMgr(history).handleParamUpdate(current, { id: "A" });
      expect(updatedParam.generation).toMatchObject({
        start: 30,
        stop: 40,
        points: 3,
        pattern: "scatter",
        inputMode: "spanCenter",
      });
      // And A's Start/Stop settings stay stashed, ready to be restored if the card is
      // toggled.
      expect(updatedParam.generation.otherModeSpec).toEqual({
        start: 10,
        stop: 20,
        points: 5,
        pattern: "linear",
      });
    });

    it("brings a parameter last scanned by Start/Stop back in Start/Stop mode from Span mode", () => {
      // A has only been used in Start/Stop mode, so it has no inputMode stored.
      const history = record(
        emptyScanInfoHistory,
        param("E", "grp", "A", gen(10, 20, 5)),
      );
      const current = param("E", "grp", "B", spanGen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, { id: "A" });
      expect(updatedParam.generation).toMatchObject({ start: 10, stop: 20, points: 5 });
      expect(modeOf(updatedParam)).toBe("startStop");
    });

    it("remembers the mode per parameter when switching back and forth", () => {
      let history = record(emptyScanInfoHistory, param("E", "grp", "A", spanGen(0, 4)));
      history = record(history, param("E", "grp", "B", gen(1, 2)));

      const toA = mkMgr(history).handleParamUpdate(param("E", "grp", "B", gen(1, 2)), {
        id: "A",
      });
      expect(toA.updatedParam.generation.inputMode).toBe("spanCenter");
      const backToB = mkMgr(toA.updatedScanInfoHistory).handleParamUpdate(
        toA.updatedParam,
        { id: "B" },
      );
      expect(modeOf(backToB.updatedParam)).toBe("startStop");
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

    it("restores the mode the recalled parameter was last scanned in", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E2", "grpB", "pB", gen(3, 9)),
      );
      const current = param("E1", "grpA", "pA", spanGen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, {
        namespace: "E2",
      });
      expect(modeOf(updatedParam)).toBe("startStop");
    });

    it("keeps the current input mode for a namespace without a remembered parameter", () => {
      const current = param("E1", "grpA", "pA", spanGen(0, 1));

      const { updatedParam } = mkMgr().handleParamUpdate(current, {
        namespace: "E2",
      });
      expect(updatedParam.generation.inputMode).toBe("spanCenter");
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

    it("restores Center/Span mode of the recalled parameter after switching display group", () => {
      const history = record(
        emptyScanInfoHistory,
        param("E2", "grpB", "pB", spanGen(3, 9)),
      );
      const current = param("E2", "grpA", "pA", gen(0, 1));

      const { updatedParam } = mkMgr(history).handleParamUpdate(current, {
        deviceNameOrDisplayGroup: "grpB",
      });
      expect(updatedParam.generation.inputMode).toBe("spanCenter");
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

    it("recalls a device parameter's generator when id, namespace and device change together", () => {
      // As a search pick does, coming from an experiment parameter.
      const history = record(
        emptyScanInfoHistory,
        param("Devices", "LaserA", "frequency", gen(5, 6)),
      );
      const { updatedParam } = mkMgr(history).handleParamUpdate(
        param("E", "grp", "p1", gen(0, 1)),
        { id: "frequency", namespace: "Devices", deviceNameOrDisplayGroup: "LaserA" },
      );
      expect(updatedParam).toEqual(param("Devices", "LaserA", "frequency", gen(5, 6)));
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
