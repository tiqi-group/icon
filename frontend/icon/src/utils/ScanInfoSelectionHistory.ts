import {
  MruSelectionTree,
  SerializedMruSelectionTree,
  emptySelectionHistory,
} from "./MruSelectionTree";
import { makeScannedParamKey, extractScannedParamId } from "./scanUtils";
import { ScanParameterGenerationSpec } from "../types/ScanParameterGenerationSpec";
import { ScanParameterInfo, ScanInputMode } from "../types/ScanParameterInfo";

export type SerializedScanInfoSelectionHistory =
  SerializedMruSelectionTree<ScanParameterGenerationSpec>;

export const emptyScanInfoHistory =
  emptySelectionHistory<ScanParameterGenerationSpec>();

const leafFromParam = (p: ScanParameterInfo): ScanParameterGenerationSpec =>
  p.generation;

const paramFromLeaf = (
  namespace: string,
  deviceNameOrDisplayGroup: string,
  id: string,
  leaf: ScanParameterGenerationSpec,
): ScanParameterInfo => ({
  namespace,
  deviceNameOrDisplayGroup,
  id,
  generation: {
    start: leaf.start,
    stop: leaf.stop,
    points: leaf.points,
    pattern: leaf.pattern,
    inputMode: leaf.inputMode,
    otherModeSpec: leaf.otherModeSpec,
  },
});

/**
 * The input mode (Start/Stop or Span) to show a parameter in: the one it was last
 * scanned in, or the card's current mode for a parameter not scanned before.
 */
const modeFor = (
  remembered: ScanParameterGenerationSpec | undefined,
  current: ScanParameterInfo,
): ScanInputMode =>
  remembered
    ? (remembered.inputMode ?? "startStop")
    : (current.generation.inputMode ?? "startStop");

/**
 * Re-expresses a leaf so its active start/stop/points/pattern belong to
 * `targetMode`, without recomputing one mode's numbers from the other's.
 *
 * If the leaf was already recorded in `targetMode`, it's returned as-is (just
 * relabelled). Otherwise its active quadruple and `otherModeSpec` are swapped —
 * mirroring the swap the UI performs when the user toggles modes directly — so
 * a parameter not scanned before takes over the card's mode with its own settings
 * for *that* mode, not whichever quadruple happened to be active when it was saved.
 */
const alignLeafToMode = (
  leaf: ScanParameterGenerationSpec,
  targetMode: ScanInputMode,
): ScanParameterGenerationSpec => {
  const leafMode = leaf.inputMode ?? "startStop";
  if (leafMode === targetMode) return leaf;

  const ownModeSpec = {
    start: leaf.start,
    stop: leaf.stop,
    points: leaf.points,
    pattern: leaf.pattern,
  };
  // No snapshot yet: reuse the numbers, but keep a copy as the other mode's own.
  if (!leaf.otherModeSpec) {
    return { ...leaf, inputMode: targetMode, otherModeSpec: ownModeSpec };
  }

  return { ...leaf.otherModeSpec, inputMode: targetMode, otherModeSpec: ownModeSpec };
};

/**
 * Remembers the last-selected {@link ScanParameterGenerationSpec} for each
 * scan parameter across navigation changes.
 *
 * Specializes {@link MruSelectionTree} with a two-level selection hierarchy:
 * (namespace/deviceNameOrDisplayGroup) {@link ScanParameterGenerationSpec}
 * as leaf types. {@link makeScannedParamKey} is used to generate non-ambiguous
 * leafKeys which uniquely identify the selected parameter for the given selection.
 *
 * Use `handleParamUpdate` to apply partial updates to a `ScanParameterInfo`
 * and get back the updated parameter plus the updated history.
 */
export class ScanInfoSelectionHistory extends MruSelectionTree<ScanParameterGenerationSpec> {
  constructor(
    defaultLeaf: () => ScanParameterGenerationSpec,
    history: SerializedScanInfoSelectionHistory = emptyScanInfoHistory,
  ) {
    super(2, defaultLeaf, history);
  }

  /**
   * @param recenterOn Live value of the parameter switched to, to centre its range on
   *   if it comes back in Span mode
   */
  handleParamUpdate(
    current: ScanParameterInfo,
    update: Partial<ScanParameterInfo>,
    recenterOn?: number,
  ): {
    updatedParam: ScanParameterInfo;
    updatedScanInfoHistory: SerializedScanInfoSelectionHistory;
  } {
    let updatedParam: ScanParameterInfo;
    let updatedScanInfoHistory: SerializedScanInfoSelectionHistory;

    if (update.generation) {
      // Generation parameter provided. Update the leaf node.
      updatedParam = { ...current, ...update };
      updatedScanInfoHistory = this.update(
        [updatedParam.namespace, updatedParam.deviceNameOrDisplayGroup],
        makeScannedParamKey(
          updatedParam.id,
          updatedParam.namespace,
          updatedParam.deviceNameOrDisplayGroup,
        ),
        leafFromParam(updatedParam),
      ).serialize();
    } else if (update.id) {
      // Parameter id provided. Lookup leaf node by its globally-unique scanned key
      // to restore that parameter's own remembered start/stop/points/pattern.
      const namespace = update.namespace ?? current.namespace;
      const deviceNameOrDisplayGroup =
        update.deviceNameOrDisplayGroup ?? current.deviceNameOrDisplayGroup;
      const leafKey = makeScannedParamKey(
        update.id,
        namespace,
        deviceNameOrDisplayGroup,
      );
      const remembered = this.lookupLeaf(leafKey);
      // Each parameter comes back in the input mode (Start/Stop or Span) it was last
      // scanned in, with that mode's settings.
      const mode = modeFor(remembered, current);
      let leaf = alignLeafToMode(remembered ?? this.defaultLeaf(), mode);
      if (recenterOn !== undefined && mode === "spanCenter") {
        // Recentre on the new parameter's live value while keeping its own
        // remembered span (and, since only start/stop change, its own points
        // and pattern too).
        const span = leaf.stop - leaf.start;
        leaf = { ...leaf, start: recenterOn - span / 2, stop: recenterOn + span / 2 };
      }
      updatedParam = paramFromLeaf(
        namespace,
        deviceNameOrDisplayGroup,
        update.id,
        leaf,
      );
      updatedScanInfoHistory = this.update(
        [namespace, deviceNameOrDisplayGroup],
        leafKey,
        leaf,
      ).serialize();
    } else {
      // No id or generation parameter. Resolve leaf from partial path.
      const partialPath: (string | undefined)[] = [
        update.namespace ?? current.namespace,
        "deviceNameOrDisplayGroup" in update
          ? update.deviceNameOrDisplayGroup
          : undefined,
      ];
      const { path, leafKey, leaf: resolvedLeaf } = this.resolve(partialPath);
      const id = extractScannedParamId(leafKey, path[0], path[1]);
      // The resolved parameter comes back in the mode it was last scanned in
      const leaf = alignLeafToMode(
        resolvedLeaf,
        modeFor(this.lookupLeaf(leafKey), current),
      );
      updatedParam = paramFromLeaf(path[0], path[1], id, leaf);
      updatedScanInfoHistory = this.update(path, leafKey, leaf).serialize();
    }
    return { updatedParam, updatedScanInfoHistory };
  }
}
