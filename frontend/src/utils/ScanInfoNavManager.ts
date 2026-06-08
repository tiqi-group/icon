import {
  HierarchicalNavManager,
  SerializedHierarchicalNav,
  emptyNavHistory,
} from "./HierarchicalNavManager";
import { makeScannedParamKey, extractScannedParamId } from "./scanUtils";
import { ScanParameterValueGenerator } from "../types/ScanParameterValueGenerator";
import { ScanParameterInfo } from "../types/ScanParameterInfo";

export type ScanParamLeaf = ScanParameterValueGenerator;
export type ScanInfoNavHistory = SerializedHierarchicalNav<ScanParamLeaf>;

export const emptyScanInfoNavHistory = emptyNavHistory<ScanParamLeaf>();

const leafFromParam = (p: ScanParameterInfo): ScanParamLeaf => p.generation;

const paramFromLeaf = (
  namespace: string,
  deviceNameOrDisplayGroup: string,
  id: string,
  leaf: ScanParamLeaf,
): ScanParameterInfo => ({
  namespace,
  deviceNameOrDisplayGroup,
  id,
  generation: {
    start: leaf.start,
    stop: leaf.stop,
    points: leaf.points,
    pattern: leaf.pattern,
  },
});

export class ScanInfoNavManager extends HierarchicalNavManager<ScanParamLeaf> {
  constructor(
    defaultLeaf: () => ScanParameterValueGenerator,
    history: ScanInfoNavHistory = emptyScanInfoNavHistory,
  ) {
    super(2, defaultLeaf, history.navTree, history.leaves);
  }

  handleParamUpdate(
    current: ScanParameterInfo,
    update: Partial<ScanParameterInfo>,
  ): { updatedParam: ScanParameterInfo; updatedScanInfoHistory: ScanInfoNavHistory } {
    let updatedParam: ScanParameterInfo;
    let updatedScanInfoHistory: ScanInfoNavHistory;

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
      // Parameter id provided. Lookup leaf node by its globally-unique scanned key.
      const namespace = update.namespace ?? current.namespace;
      const deviceNameOrDisplayGroup =
        update.deviceNameOrDisplayGroup ?? current.deviceNameOrDisplayGroup;
      const leafKey = makeScannedParamKey(
        update.id,
        namespace,
        deviceNameOrDisplayGroup,
      );
      const leaf = this.lookupLeaf(leafKey) ?? this.defaultLeaf();
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
      const { path, leafKey, leaf } = this.resolve(partialPath);
      const id = extractScannedParamId(leafKey, path[0], path[1]);
      updatedParam = paramFromLeaf(path[0], path[1], id, leaf);
      updatedScanInfoHistory = this.update(path, leafKey, leaf).serialize();
    }
    return { updatedParam, updatedScanInfoHistory };
  }
}
