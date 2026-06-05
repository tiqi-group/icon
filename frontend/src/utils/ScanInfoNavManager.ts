import {
  HierarchicalNavManager,
  SerializedHierarchicalNav,
  emptyNavHistory,
} from "./HierarchicalNavManager";
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
      // Generation parameter provided. Update the leaf node
      updatedParam = { ...current, ...update };
      updatedScanInfoHistory = this.update(
        [updatedParam.namespace, updatedParam.deviceNameOrDisplayGroup],
        updatedParam.id,
        leafFromParam(updatedParam),
      ).serialize();
    } else if (update.id) {
      // Parameter id provided. Lookup leaf node
      const leaf = this.lookupLeaf(update.id) ?? this.defaultLeaf();
      updatedParam = paramFromLeaf(
        update.namespace ?? current.namespace,
        update.deviceNameOrDisplayGroup ?? current.deviceNameOrDisplayGroup,
        update.id,
        leaf,
      );
      updatedScanInfoHistory = this.update(
        [updatedParam.namespace, updatedParam.deviceNameOrDisplayGroup],
        update.id,
        leaf,
      ).serialize();
    } else {
      // No id or generation parameter. Resolve leaf from partial path
      const partialPath: (string | undefined)[] = [
        update.namespace ?? current.namespace,
        "deviceNameOrDisplayGroup" in update
          ? update.deviceNameOrDisplayGroup
          : undefined,
      ];
      const { path, leafKey, leaf } = this.resolve(partialPath);
      updatedParam = paramFromLeaf(path[0], path[1], leafKey, leaf);
      updatedScanInfoHistory = this.update(path, leafKey, leaf).serialize();
    }
    return { updatedParam, updatedScanInfoHistory };
  }
}
