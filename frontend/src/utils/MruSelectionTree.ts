interface NavNode {
  lastKey: string;
  children?: Record<string, NavNode>;
}

export interface SerializedMruSelectionTree<LeafValue> {
  selectionTree: NavNode;
  leaves: Record<string, LeafValue>;
}

export const emptySelectionHistory = <
  LeafValue,
>(): SerializedMruSelectionTree<LeafValue> => ({
  selectionTree: { lastKey: "" },
  leaves: {},
});

function rebuildNode(node: NavNode, path: string[], depth: number): NavNode {
  const key = path[depth];
  if (depth === path.length - 1) {
    return { lastKey: key };
  }
  const child = node.children?.[key] ?? { lastKey: "" };
  return {
    lastKey: key,
    children: { ...node.children, [key]: rebuildNode(child, path, depth + 1) },
  };
}

/**
 * Tracks the most recently used path through a fixed-depth selection hierarchy and
 * associates a typed leaf value with each fully-qualified path.
 *
 * The path has `depth` levels of string keys.
 * Each node remembers the last key chosen among its children. When a partial
 * path is resolved, missing lower levels are filled in from that memory, cascading
 * all the way down to the leaf.
 *
 * The class is immutable: `update` returns a new instance. Use `serialize` to
 * obtain a plain-object snapshot and pass it to the constructor to restore state
 * across sessions.
 */
export class MruSelectionTree<LeafValue> {
  constructor(
    readonly depth: number,
    readonly defaultLeaf: () => LeafValue,
    private readonly history: SerializedMruSelectionTree<LeafValue>,
  ) {}

  /**
   * Resolves a path prefix to a fully-qualified selection.
   *
   * Each entry in `partialPath` either provides a key for that level or is
   * `undefined`, in which case the last-selected key at that level is used.
   * Unresolveable path segments are populated with "".
   * Unresolveable leaf values are populated with defaultLeaf().
   *
   * @param partialPath - Array of length `depth`; `undefined` entries fall back to MRU.
   * @returns The resolved `path` (length `depth`), the leaf `leafKey`, and the `leaf` value.
   */
  resolve(partialPath: (string | undefined)[]): {
    path: string[];
    leafKey: string;
    leaf: LeafValue;
  } {
    const path: string[] = [];
    let node: NavNode = this.history.selectionTree;

    for (let i = 0; i < this.depth; i++) {
      const key = partialPath[i] ?? node.lastKey;
      path.push(key);
      node = node.children?.[key] ?? { lastKey: "" };
    }

    const leafKey = node.lastKey;
    const leaf = this.history.leaves[leafKey] ?? this.defaultLeaf();
    return { path, leafKey, leaf };
  }

  /**
   * Returns the stored leaf for `leafKey`, or `undefined` if it has never been recorded.
   *
   * `leafKey` is a user-specified key which is unique across all nodes of the tree.
   * Typically, this is some composition of path keys.
   */
  lookupLeaf(leafKey: string): LeafValue | undefined {
    return this.history.leaves[leafKey];
  }

  /**
   * Records a fully-qualified selection and returns a new `MruSelectionTree` with
   * the updated history. The original instance is not modified.
   *
   * Every node along `path` has its last-selected key updated, and `leaf` is
   * stored under `leafKey` in the flat leaf map.
   *
   * @param path - Full path of length `depth` identifying the selection (e.g. `[namespace, displayGroup]`).
   * @param leafKey - Unique key identifying the leaf (must be globally unique across all paths).
   * @param leaf - Value to associate with `leafKey`.
   */
  update(
    path: string[],
    leafKey: string,
    leaf: LeafValue,
  ): MruSelectionTree<LeafValue> {
    const newHist = {
      selectionTree: rebuildNode(this.history.selectionTree, [...path, leafKey], 0),
      leaves: { ...this.history.leaves, [leafKey]: leaf },
    };
    return new MruSelectionTree(this.depth, this.defaultLeaf, newHist);
  }

  /**
   * Returns the plain-object representation of the current history, suitable
   * for JSON serialization.
   */
  serialize(): SerializedMruSelectionTree<LeafValue> {
    return this.history;
  }
}
