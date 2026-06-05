interface NavNode {
  lastKey: string;
  children?: Record<string, NavNode>;
}

export interface SerializedHierarchicalNav<LeafValue> {
  navTree: NavNode;
  leaves: Record<string, LeafValue>;
}

export const emptyNavHistory = <L>(): SerializedHierarchicalNav<L> => ({
  navTree: { lastKey: "" },
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

export class HierarchicalNavManager<LeafValue> {
  constructor(
    readonly depth: number,
    readonly defaultLeaf: () => LeafValue,
    private readonly navTree: NavNode = { lastKey: "" },
    private readonly leaves: Record<string, LeafValue> = {},
  ) {}

  resolve(partialPath: (string | undefined)[]): {
    path: string[];
    leafKey: string;
    leaf: LeafValue;
  } {
    const path: string[] = [];
    let node: NavNode = this.navTree;

    for (let i = 0; i < this.depth; i++) {
      const key = partialPath[i] ?? node.lastKey;
      path.push(key);
      node = node.children?.[key] ?? { lastKey: "" };
    }

    const leafKey = node.lastKey;
    const leaf = this.leaves[leafKey] ?? this.defaultLeaf();
    return { path, leafKey, leaf };
  }

  lookupLeaf(leafKey: string): LeafValue | undefined {
    return this.leaves[leafKey];
  }

  update(
    path: string[],
    leafKey: string,
    leaf: LeafValue,
  ): HierarchicalNavManager<LeafValue> {
    const newRoot = rebuildNode(this.navTree, [...path, leafKey], 0);
    const newLeaves = { ...this.leaves, [leafKey]: leaf };
    return new HierarchicalNavManager(this.depth, this.defaultLeaf, newRoot, newLeaves);
  }

  serialize(): SerializedHierarchicalNav<LeafValue> {
    return { navTree: this.navTree, leaves: this.leaves };
  }

  static deserialize<L>(
    depth: number,
    defaultLeaf: () => L,
    data: SerializedHierarchicalNav<L>,
  ): HierarchicalNavManager<L> {
    return new HierarchicalNavManager(depth, defaultLeaf, data.navTree, data.leaves);
  }
}
