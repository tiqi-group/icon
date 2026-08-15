import {
  MruSelectionTree,
  SerializedMruSelectionTree,
  emptySelectionHistory,
} from "./MruSelectionTree";
import { makeScannedParamKey, extractScannedParamId } from "./scanUtils";
import { ScanParameterGenerationSpec } from "../types/ScanParameterGenerationSpec";
import { ScanParameterInfo } from "../types/ScanParameterInfo";

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
  },
});

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
      let leaf = this.lookupLeaf(leafKey) ?? this.defaultLeaf();
      if (recenterOn !== undefined) {
        // Recentre on the new parameter's live value while keeping its own
        // remembered span (and, since only start/stop change, its own points
        // and pattern too).
        const span = leaf.stop - leaf.start;
        leaf = { ...leaf, start: recenterOn - span / 2, stop: recenterOn + span / 2 };
      }
      // Input mode (start/stop vs. center/span) is a card-level view setting, not
      // something tied to the target parameter's own memory — keep whatever mode
      // was active before the switch.
      leaf = { ...leaf, inputMode: current.generation.inputMode };
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
      // Preserve the current view mode across namespace/display-group changes,
      // rather than adopting whatever mode the resolved parameter last used.
      const leaf = { ...resolvedLeaf, inputMode: current.generation.inputMode };
      updatedParam = paramFromLeaf(path[0], path[1], id, leaf);
      updatedScanInfoHistory = this.update(path, leafKey, leaf).serialize();
    }
    return { updatedParam, updatedScanInfoHistory };
  }
}
